"""Módulo principal de gestión y reproducción de audio para Pygame.

Provee la interfaz AudioManager consumida exclusivamente desde el hilo principal de Pygame:
- Inicializa pygame.mixer solo cuando se invoca start() explícitamente.
- Segmenta textos por oraciones naturales sin generar llamadas por token.
- Consume eventos VOICE_READY y carga pygame.mixer.Sound en memoria.
- Reproduce voz de forma no bloqueante a través de un canal exclusivo (Channel 0).
- Emite VOICE_STARTED y VOICE_FINISHED en sincronía con la reproducción física real.
- Gestiona controles de volumen, mute/unmute y modos sin audio/headless (dummy).
"""

import io
import queue
import re
import time
from typing import Any, Callable, List, Optional

from src.simulation.audio_config import (
    AUDIO_BUFFER_SIZE,
    AUDIO_CHANNELS,
    AUDIO_ENABLED,
    AUDIO_SAMPLE_RATE,
    EFFECTS_VOLUME,
    GEMINI_TTS_ENABLED,
    MASTER_VOLUME,
    MUSIC_VOLUME,
    TTS_MAX_SEGMENT_CHARACTERS,
    VOICE_VOLUME,
    get_voice_profile,
)
from src.simulation.audio_events import AudioEvent, AudioEventType, VoiceSegmentRequest
from src.simulation.audio_worker import AudioWorker, BaseTTSProvider
from src.simulation.debug_logger import debug_log


# =============================================================================
# 1. SEGMENTADOR DE TEXTO (TEXT SEGMENTER)
# =============================================================================


class TextSegmenter:
    """Divide mensajes completos en oraciones naturales preservando la coherencia semántica."""

    @staticmethod
    def segment(text: str, max_chars: int = TTS_MAX_SEGMENT_CHARACTERS) -> List[str]:
        """Divide un texto por puntuación natural (. ! ? : ;) respetando el límite máximo."""
        clean_text = (text or "").strip()
        if not clean_text:
            return []

        # Expresión regular que divide por puntos, signos de exclamación/interrogación, dos puntos o saltos
        delimiters = r"([.!?:\n;]+)"
        raw_parts = re.split(delimiters, clean_text)

        tokens: List[str] = []
        for i in range(0, len(raw_parts) - 1, 2):
            sentence = (raw_parts[i] + raw_parts[i + 1]).strip()
            if sentence:
                tokens.append(sentence)
        if len(raw_parts) % 2 == 1 and raw_parts[-1].strip():
            tokens.append(raw_parts[-1].strip())

        if not tokens:
            tokens = [clean_text]

        # Agrupar tokens pequeños o cortar los que excedan max_chars
        segments: List[str] = []
        current_segment = ""

        for tok in tokens:
            if not current_segment:
                if len(tok) <= max_chars:
                    current_segment = tok
                else:
                    # Si una sola oración supera max_chars, cortar por palabras
                    words = tok.split()
                    sub_seg = ""
                    for w in words:
                        if len(sub_seg) + len(w) + 1 <= max_chars:
                            sub_seg = f"{sub_seg} {w}".strip()
                        else:
                            if sub_seg:
                                segments.append(sub_seg)
                            sub_seg = w
                    if sub_seg:
                        current_segment = sub_seg
            else:
                if len(current_segment) + len(tok) + 1 <= max_chars:
                    current_segment = f"{current_segment} {tok}".strip()
                else:
                    segments.append(current_segment)
                    current_segment = tok

        if current_segment:
            segments.append(current_segment)

        return [s for s in segments if len(s.strip()) > 0]


# =============================================================================
# 2. GESTOR DE AUDIO PARA PYGAME (AUDIO MANAGER)
# =============================================================================


class AudioManager:
    """Fachada de audio principal ejecutada en el bucle de Pygame.

    Responsable de la reproducción no bloqueante, volumen, colas y sincronía visual.
    """

    def __init__(
        self,
        worker_factory: Optional[Callable[..., AudioWorker]] = None,
        provider: Optional[BaseTTSProvider] = None,
    ):
        self.request_queue: queue.Queue[VoiceSegmentRequest] = queue.Queue()
        self.worker_event_queue: queue.Queue[AudioEvent] = queue.Queue()
        self.public_events: List[AudioEvent] = []

        self.worker_factory = worker_factory
        self.provider = provider
        self.worker: Optional[AudioWorker] = None

        self.is_initialized: bool = False
        self.audio_available: bool = False
        self.is_muted: bool = False
        self.is_paused: bool = False
        self.tts_enabled: bool = GEMINI_TTS_ENABLED

        # Configuración de volúmenes
        self.master_volume: float = MASTER_VOLUME
        self.voice_volume: float = VOICE_VOLUME
        self.music_volume: float = MUSIC_VOLUME
        self.effects_volume: float = EFFECTS_VOLUME

        # Cola de reproducción secuencial (FIFO) de audios listos para sonar
        self.playback_queue: List[AudioEvent] = []
        self.current_playing_event: Optional[AudioEvent] = None
        self.voice_channel: Optional[Any] = None

        # Seguimiento de hablante activo
        self.current_speaker: Optional[str] = None
        self.request_counter: int = 0

    def start(self) -> None:
        """Inicializa el mixer de Pygame de forma protegida y arranca el AudioWorker."""
        if self.is_initialized:
            return

        import pygame

        self.audio_available = False
        if AUDIO_ENABLED:
            try:
                if not pygame.mixer.get_init():
                    pygame.mixer.init(
                        frequency=AUDIO_SAMPLE_RATE,
                        size=-16,  # 16 bits firmado
                        channels=AUDIO_CHANNELS,
                        buffer=AUDIO_BUFFER_SIZE,
                    )
                # Asignar canal exclusivo para voz
                pygame.mixer.set_num_channels(8)
                self.voice_channel = pygame.mixer.Channel(0)
                self.audio_available = True
                debug_log("AUDIO_MANAGER", "MIXER_INIT_SUCCESS", f"freq={AUDIO_SAMPLE_RATE}, ch={AUDIO_CHANNELS}")
            except Exception as e:
                debug_log("AUDIO_MANAGER", "MIXER_INIT_FAILED", f"error={e}, funcionando en modo sin audio")
                self.audio_available = False
                self.public_events.append(
                    AudioEvent(
                        event_type=AudioEventType.AUDIO_DISABLED,
                        audio_id="init_failed",
                        conversation_id="",
                        turn_id="",
                        speaker="",
                        error_message=str(e),
                    )
                )

        # Iniciar worker si TTS está habilitado
        if GEMINI_TTS_ENABLED and self.worker is None:
            if self.worker_factory is not None:
                self.worker = self.worker_factory(self.request_queue, self.worker_event_queue)
            else:
                self.worker = AudioWorker(
                    self.request_queue,
                    self.worker_event_queue,
                    provider=self.provider,
                )
            self.worker.start()

        self.is_initialized = True
        self._apply_volumes()

    def submit_voice(
        self,
        text: str,
        speaker: str,
        conversation_id: str = "",
        turn_id: str = "",
    ) -> List[str]:
        """Segmenta un mensaje completado y encola sus fragmentos para síntesis en el worker.

        Retorna la lista de segmentos textuales generados, o [] si TTS está desactivado.
        """
        if not self.tts_enabled or not self.audio_available:
            return []

        segments = TextSegmenter.segment(text)
        if not segments:
            return []

        voice_profile = get_voice_profile(speaker)
        total = len(segments)

        for idx, seg in enumerate(segments):
            self.request_counter += 1
            req_id = f"aud_{int(time.time() * 1000)}_{self.request_counter}"
            req = VoiceSegmentRequest(
                request_id=req_id,
                conversation_id=conversation_id,
                turn_id=turn_id,
                speaker=speaker,
                text_segment=seg,
                segment_index=idx,
                total_segments=total,
                is_final_segment=(idx == total - 1),
                voice_profile=voice_profile,
            )
            self.request_queue.put(req)

            # Notificar que se solicitó el audio
            self.public_events.append(
                AudioEvent(
                    event_type=AudioEventType.VOICE_REQUESTED,
                    audio_id=req_id,
                    conversation_id=conversation_id,
                    turn_id=turn_id,
                    speaker=speaker,
                    segment_index=idx,
                    total_segments=total,
                    text_segment=seg,
                )
            )

        debug_log(
            "AUDIO_MANAGER",
            "VOICE_SUBMITTED",
            f"speaker={speaker}, segments={total}, total_chars={len(text)}",
            conversation_id=conversation_id,
        )
        return segments

    def update(self, dt: float) -> None:
        """Actualiza el estado de reproducción en cada frame de Pygame sin bloquear."""
        # 1. Drenar eventos del worker
        while True:
            try:
                ev = self.worker_event_queue.get_nowait()
                if ev.event_type == AudioEventType.VOICE_READY:
                    # Si TTS fue desactivado entre tanto, descartar buffer
                    if not self.tts_enabled:
                        continue
                    # Audio WAV listo: encolar en reproducción FIFO
                    self.playback_queue.append(ev)
                    self.public_events.append(ev)
                else:
                    self.public_events.append(ev)
            except queue.Empty:
                break

        # Si el audio está pausado o TTS está apagado, no avanzar reproducción
        if self.is_paused or not self.tts_enabled:
            return

        # 2. Si no hay audio sonando en el canal exclusivo y hay buffers listos, reproducir siguiente
        if self.audio_available and self.voice_channel is not None:
            is_busy = self.voice_channel.get_busy()

            if is_busy and self.current_playing_event:
                # El audio sigue reproduciéndose en hardware
                pass

            elif not is_busy and self.current_playing_event:
                # La reproducción del segmento actual finalizó físicamente
                finished_ev = self.current_playing_event
                self.current_playing_event = None
                self.current_speaker = None

                self.public_events.append(
                    AudioEvent(
                        event_type=AudioEventType.VOICE_FINISHED,
                        audio_id=finished_ev.audio_id,
                        conversation_id=finished_ev.conversation_id,
                        turn_id=finished_ev.turn_id,
                        speaker=finished_ev.speaker,
                        segment_index=finished_ev.segment_index,
                        total_segments=finished_ev.total_segments,
                        text_segment=finished_ev.text_segment,
                        duration_seconds=finished_ev.duration_seconds,
                    )
                )
                debug_log(
                    "AUDIO_MANAGER",
                    "VOICE_FINISHED_EMITTED",
                    f"audio_id={finished_ev.audio_id}, speaker={finished_ev.speaker}",
                    conversation_id=finished_ev.conversation_id,
                )

            # Iniciar el siguiente en cola si el canal está libre
            if not self.voice_channel.get_busy() and self.playback_queue:
                next_ev = self.playback_queue.pop(0)
                if next_ev.wav_bytes:
                    try:
                        import pygame

                        sound = pygame.mixer.Sound(io.BytesIO(next_ev.wav_bytes))
                        effective_vol = 0.0 if self.is_muted else (self.master_volume * self.voice_volume)
                        sound.set_volume(effective_vol)
                        self.voice_channel.play(sound)
                        self.current_playing_event = next_ev
                        self.current_speaker = next_ev.speaker

                        self.public_events.append(
                            AudioEvent(
                                event_type=AudioEventType.VOICE_STARTED,
                                audio_id=next_ev.audio_id,
                                conversation_id=next_ev.conversation_id,
                                turn_id=next_ev.turn_id,
                                speaker=next_ev.speaker,
                                segment_index=next_ev.segment_index,
                                total_segments=next_ev.total_segments,
                                text_segment=next_ev.text_segment,
                                duration_seconds=next_ev.duration_seconds,
                            )
                        )
                        debug_log(
                            "AUDIO_MANAGER",
                            "VOICE_STARTED_EMITTED",
                            f"audio_id={next_ev.audio_id}, speaker={next_ev.speaker}, text={next_ev.text_segment[:40]}",
                            conversation_id=next_ev.conversation_id,
                        )
                    except Exception as play_err:
                        debug_log("AUDIO_MANAGER", "PLAY_SOUND_ERROR", f"error={play_err}")
                        self.public_events.append(
                            AudioEvent(
                                event_type=AudioEventType.VOICE_ERROR,
                                audio_id=next_ev.audio_id,
                                conversation_id=next_ev.conversation_id,
                                turn_id=next_ev.turn_id,
                                speaker=next_ev.speaker,
                                error_message=str(play_err),
                            )
                        )

    def poll_events(self) -> List[AudioEvent]:
        """Drena y retorna todos los eventos de audio acumulados."""
        evs = list(self.public_events)
        self.public_events.clear()
        return evs

    def stop(self) -> None:
        """Detiene de inmediato la locución activa y vacía la cola de reproducción."""
        if self.voice_channel and self.audio_available:
            try:
                self.voice_channel.stop()
            except Exception:
                pass
        self.is_paused = False
        self.playback_queue.clear()
        self.current_playing_event = None
        self.current_speaker = None
        if self.worker:
            self.worker.cancel_active()

    def cancel_conversation(self, conversation_id: Optional[str] = None) -> None:
        """Cancela audios pendientes asociados a una conversación específica o actual."""
        self.stop()
        if self.worker:
            self.worker.clear_cancellation()

    def cancel_current_speech(self) -> None:
        """Detiene de inmediato la locución activa, vacía la cola y emite VOICE_CANCELLED."""
        prev = self.current_playing_event
        self.stop()
        self.public_events.append(
            AudioEvent(
                event_type=AudioEventType.VOICE_CANCELLED,
                audio_id=prev.audio_id if prev else "cancelled",
                conversation_id=prev.conversation_id if prev else "",
                turn_id=prev.turn_id if prev else "",
                speaker=prev.speaker if prev else "",
            )
        )

    def pause(self) -> bool:
        """Pausa la reproducción del canal de voz si está reproduciendo."""
        if self.audio_available and self.voice_channel:
            try:
                self.voice_channel.pause()
                self.is_paused = True
                debug_log("AUDIO_MANAGER", "VOICE_PAUSED", f"speaker={self.current_speaker}")
                return True
            except Exception:
                pass
        return False

    def resume(self) -> bool:
        """Reanuda la reproducción del canal de voz si estaba pausado."""
        if self.audio_available and self.voice_channel and self.is_paused:
            try:
                self.voice_channel.unpause()
                self.is_paused = False
                debug_log("AUDIO_MANAGER", "VOICE_RESUMED", f"speaker={self.current_speaker}")
                return True
            except Exception:
                pass
        return False

    def toggle_pause(self) -> bool:
        """Alterna entre pausa y reproducción del canal de voz."""
        if self.is_paused:
            self.resume()
        else:
            self.pause()
        return self.is_paused

    def toggle_tts(self) -> bool:
        """Activa o desactiva la generación y emisión de voz TTS."""
        self.tts_enabled = not self.tts_enabled
        debug_log("AUDIO_MANAGER", "TTS_TOGGLED", f"tts_enabled={self.tts_enabled}")
        if not self.tts_enabled:
            self.cancel_current_speech()
        return self.tts_enabled

    def enable_tts(self) -> None:
        self.tts_enabled = True

    def disable_tts(self) -> None:
        self.tts_enabled = False
        self.cancel_current_speech()

    def set_voice_volume(self, value: float) -> None:
        self.voice_volume = max(0.0, min(1.0, float(value)))
        self._apply_volumes()

    def set_music_volume(self, value: float) -> None:
        self.music_volume = max(0.0, min(1.0, float(value)))
        self._apply_volumes()

    def set_effects_volume(self, value: float) -> None:
        self.effects_volume = max(0.0, min(1.0, float(value)))
        self._apply_volumes()

    def set_master_volume(self, value: float) -> None:
        self.master_volume = max(0.0, min(1.0, float(value)))
        self._apply_volumes()

    def mute(self) -> None:
        self.is_muted = True
        self._apply_volumes()

    def unmute(self) -> None:
        self.is_muted = False
        self._apply_volumes()

    def toggle_mute(self) -> bool:
        """Alterna el silencio de audio y retorna el nuevo estado de mute."""
        if self.is_muted:
            self.unmute()
        else:
            self.mute()
        return self.is_muted

    def play_effect(self, name: str) -> None:
        """Efectos de sonido de apoyo (no bloqueantes)."""
        pass

    def play_music(self, name: str) -> None:
        """Música ambiental de apoyo (no bloqueante)."""
        pass

    def is_speaking(self, speaker: Optional[str] = None) -> bool:
        """Indica si hay audio reproduciéndose activamente en hardware (o pausado)."""
        if not self.audio_available or not self.voice_channel:
            return False
        if self.is_paused and self.current_playing_event is not None:
            if speaker is not None:
                return self.current_speaker == speaker
            return True
        busy = self.voice_channel.get_busy()
        if not busy:
            return False
        if speaker is not None:
            return self.current_speaker == speaker
        return True

    def _apply_volumes(self) -> None:
        if not self.audio_available or not self.voice_channel:
            return
        effective_vol = 0.0 if self.is_muted else (self.master_volume * self.voice_volume)
        try:
            self.voice_channel.set_volume(effective_vol)
        except Exception:
            pass

    def shutdown(self) -> None:
        """Detiene limpiamente el worker, el canal de voz y libera pygame.mixer."""
        self.stop()
        if self.worker:
            self.worker.stop()
            self.worker.join(timeout=1.5)
            self.worker = None

        if self.audio_available:
            try:
                import pygame

                if pygame.mixer.get_init():
                    pygame.mixer.quit()
            except Exception:
                pass
            self.audio_available = False
        self.is_initialized = False
