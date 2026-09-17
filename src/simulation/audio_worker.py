"""Worker multihilo desacoplado para la síntesis de voz con Google Gemini TTS.

Se ejecuta completamente fuera del hilo principal de Pygame:
- Recibe peticiones VoiceSegmentRequest por cola FIFO.
- Invoca la API de Gemini TTS o el MockTTSProvider.
- Convierte el PCM lineal devuelto en un buffer WAV RIFF de 24 kHz mono.
- Emite eventos VOICE_READY hacia Pygame.
- NUNCA importa ni modifica objetos visuales de Pygame ni crea instancias de pygame.mixer.Sound.
"""

import io
import queue
import threading
import time
import wave
from typing import Any, Optional

from src.simulation.audio_config import (
    AUDIO_CHANNELS,
    AUDIO_SAMPLE_RATE,
    AUDIO_SAMPLE_WIDTH,
    GEMINI_API_KEY,
    GEMINI_TTS_FALLBACK_VOICE,
    GEMINI_TTS_MODEL,
    TTS_TIMEOUT_SECONDS,
    VoiceProfile,
)
from src.simulation.audio_events import AudioEvent, AudioEventType, VoiceSegmentRequest
from src.simulation.debug_logger import debug_log


# =============================================================================
# 1. FUNCIÓN PURA: CONVERSIÓN PCM A WAV
# =============================================================================

def pcm_to_wav_bytes(
    pcm_data: bytes,
    sample_rate: int = AUDIO_SAMPLE_RATE,
    channels: int = AUDIO_CHANNELS,
    sample_width: int = AUDIO_SAMPLE_WIDTH,
) -> bytes:
    """Convierte bytes crudos de PCM lineal a un archivo WAV canónico con cabecera RIFF.

    Valida:
    - Que los datos PCM no estén vacíos.
    - Que el número de bytes sea múltiplo del tamaño de muestra (sample_width * channels).
    - Que la cabecera generada sea un formato WAV RIFF válido.
    """
    if not pcm_data or not isinstance(pcm_data, (bytes, bytearray)):
        raise ValueError("Datos PCM vacíos o inválidos: se requiere un buffer de bytes con audio.")

    bytes_per_sample = sample_width * channels
    if len(pcm_data) % bytes_per_sample != 0:
        raise ValueError(
            f"Longitud de PCM ({len(pcm_data)} bytes) no es múltiplo del bloque de muestra ({bytes_per_sample} bytes)."
        )

    wav_io = io.BytesIO()
    with wave.open(wav_io, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_data)

    wav_bytes = wav_io.getvalue()
    if len(wav_bytes) < 44 or wav_bytes[:4] != b"RIFF" or wav_bytes[8:12] != b"WAVE":
        raise ValueError("Error de serialización: no se generó una cabecera WAV RIFF válida.")

    return wav_bytes


# =============================================================================
# 2. PROVEEDORES DE SÍNTESIS TTS
# =============================================================================

class BaseTTSProvider:
    """Interfaz base para proveedores de síntesis de voz."""

    def synthesize(self, text: str, voice_profile: VoiceProfile) -> bytes:
        raise NotImplementedError

    def close(self) -> None:
        pass


class MockTTSProvider(BaseTTSProvider):
    """Proveedor TTS de prueba para tests herméticos sin consumo de API ni conexión de red.

    Genera buffers WAV sintéticos válidos con cabecera RIFF y tonos suaves procedurales.
    """

    def __init__(self, sample_rate: int = AUDIO_SAMPLE_RATE, simulated_latency: float = 0.01):
        self.sample_rate = sample_rate
        self.simulated_latency = simulated_latency
        self.should_fail = False

    def synthesize(self, text: str, voice_profile: VoiceProfile) -> bytes:
        if self.should_fail:
            raise RuntimeError("Fallo simulado en MockTTSProvider.")

        if self.simulated_latency > 0:
            time.sleep(self.simulated_latency)

        # Generar ~0.2 segundos de audio PCM con tono característico según el personaje
        freq = 220.0
        if "manolo" in voice_profile.speaker_id:
            freq = 140.0
        elif "paco" in voice_profile.speaker_id:
            freq = 180.0
        elif "josep" in voice_profile.speaker_id:
            freq = 240.0

        duration_sec = max(0.15, min(1.5, len(text) * 0.03))
        total_samples = int(self.sample_rate * duration_sec)
        import math

        pcm_chunks = bytearray()
        for i in range(total_samples):
            # Onda sinusoidal de 16 bits
            sample_val = int(32767.0 * 0.3 * math.sin(2.0 * math.pi * freq * (i / self.sample_rate)))
            pcm_chunks.extend(sample_val.to_bytes(2, byteorder="little", signed=True))

        return pcm_to_wav_bytes(bytes(pcm_chunks), sample_rate=self.sample_rate, channels=1, sample_width=2)


class GeminiTTSProvider(BaseTTSProvider):
    """Proveedor de producción que utiliza la API de Google Gemini (google-genai) para síntesis TTS."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = GEMINI_TTS_MODEL,
        timeout: float = TTS_TIMEOUT_SECONDS,
    ):
        if api_key is not None:
            self.api_key = api_key
        else:
            self.api_key = GEMINI_API_KEY
        self.model_name = model_name
        self.timeout = timeout
        self._client: Optional[Any] = None

    def _get_client(self) -> Any:
        if self._client is None:
            if not self.api_key:
                raise RuntimeError("GEMINI_API_KEY no configurada para GeminiTTSProvider.")
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def synthesize(self, text: str, voice_profile: VoiceProfile) -> bytes:
        """Invoca Gemini TTS y retorna bytes WAV listos para reproducir."""
        from google.genai import types

        client = self._get_client()
        voice_to_use = voice_profile.voice_name or "Charon"

        def _call_api(target_voice: str) -> bytes:
            config = types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=target_voice)
                    )
                ),
            )
            response = client.models.generate_content(
                model=self.model_name,
                contents=text,
                config=config,
            )
            if not response.candidates:
                raise RuntimeError("Gemini TTS devolvió una lista de candidatos vacía.")

            candidate = response.candidates[0]
            if not candidate.content or not candidate.content.parts:
                raise RuntimeError("Gemini TTS no devolvió partes de contenido en el candidato.")

            for part in candidate.content.parts:
                if getattr(part, "inline_data", None) and part.inline_data.data:
                    raw_pcm = part.inline_data.data
                    return pcm_to_wav_bytes(
                        raw_pcm, sample_rate=AUDIO_SAMPLE_RATE, channels=AUDIO_CHANNELS, sample_width=2
                    )

            raise RuntimeError("Gemini TTS no incluyó datos binarios de audio en la respuesta.")

        try:
            return _call_api(voice_to_use)
        except Exception as primary_exc:
            # Reintento transparente con voz fallback si la principal falla
            fallback = voice_profile.fallback_voice or GEMINI_TTS_FALLBACK_VOICE
            if fallback and fallback != voice_to_use:
                debug_log(
                    "GEMINI_TTS",
                    "FALLBACK_VOICE_ATTEMPT",
                    f"primary_voice={voice_to_use} failed ({primary_exc}), trying fallback={fallback}",
                )
                try:
                    return _call_api(fallback)
                except Exception as fallback_exc:
                    raise RuntimeError(
                        f"Error Gemini TTS en voz principal ({primary_exc}) y en fallback ({fallback_exc})"
                    ) from fallback_exc
            raise primary_exc


# =============================================================================
# 3. WORKER DE AUDIO ASÍNCRONO
# =============================================================================

class AudioWorker(threading.Thread):
    """Hilo trabajador desacoplado que sintetiza oraciones de voz y emite eventos VOICE_READY."""

    def __init__(
        self,
        request_queue: queue.Queue[VoiceSegmentRequest],
        event_queue: queue.Queue[AudioEvent],
        provider: Optional[BaseTTSProvider] = None,
        timeout: float = TTS_TIMEOUT_SECONDS,
    ):
        super().__init__(name="AudioWorkerThread", daemon=True)
        self.request_queue = request_queue
        self.event_queue = event_queue
        self.provider = provider or GeminiTTSProvider(timeout=timeout)
        self.timeout = timeout

        self.stop_event = threading.Event()
        self.cancel_event = threading.Event()

    def run(self) -> None:
        debug_log("AUDIO_WORKER", "STARTED", "hilo de audio worker iniciado")
        while not self.stop_event.is_set():
            try:
                req = self.request_queue.get(timeout=0.05)
            except queue.Empty:
                continue

            if self.stop_event.is_set():
                break

            # Si hay una cancelación activa, descartar solicitudes pendientes
            if self.cancel_event.is_set():
                self.event_queue.put(
                    AudioEvent(
                        event_type=AudioEventType.VOICE_CANCELLED,
                        audio_id=req.request_id,
                        conversation_id=req.conversation_id,
                        turn_id=req.turn_id,
                        speaker=req.speaker,
                        segment_index=req.segment_index,
                        total_segments=req.total_segments,
                        text_segment=req.text_segment,
                    )
                )
                self.request_queue.task_done()
                continue

            self._process_request(req)
            self.request_queue.task_done()

        debug_log("AUDIO_WORKER", "STOPPED", "hilo de audio worker finalizado limpiamente")

    def _process_request(self, req: VoiceSegmentRequest) -> None:
        """Procesa una solicitud de síntesis convirtiendo el texto a WAV y emitiendo VOICE_READY."""
        audio_id = req.request_id
        start_t = time.time()
        debug_log(
            "AUDIO_WORKER",
            "SYNTHESIZE_START",
            f"audio_id={audio_id}, speaker={req.speaker}, text_len={len(req.text_segment)}",
            conversation_id=req.conversation_id,
        )

        try:
            wav_bytes = self.provider.synthesize(req.text_segment, req.voice_profile)
            duration_s = max(0.2, (len(wav_bytes) - 44) / (AUDIO_SAMPLE_RATE * AUDIO_CHANNELS * AUDIO_SAMPLE_WIDTH))

            if self.cancel_event.is_set():
                self.event_queue.put(
                    AudioEvent(
                        event_type=AudioEventType.VOICE_CANCELLED,
                        audio_id=audio_id,
                        conversation_id=req.conversation_id,
                        turn_id=req.turn_id,
                        speaker=req.speaker,
                        segment_index=req.segment_index,
                        total_segments=req.total_segments,
                        text_segment=req.text_segment,
                    )
                )
                return

            # Emitir evento VOICE_READY hacia el hilo de Pygame con los bytes WAV
            self.event_queue.put(
                AudioEvent(
                    event_type=AudioEventType.VOICE_READY,
                    audio_id=audio_id,
                    conversation_id=req.conversation_id,
                    turn_id=req.turn_id,
                    speaker=req.speaker,
                    segment_index=req.segment_index,
                    total_segments=req.total_segments,
                    text_segment=req.text_segment,
                    wav_bytes=wav_bytes,
                    duration_seconds=duration_s,
                )
            )
            debug_log(
                "AUDIO_WORKER",
                "VOICE_READY_EMITTED",
                f"audio_id={audio_id}, wav_size={len(wav_bytes)}, duration={duration_s:.2f}s, elapsed={time.time()-start_t:.2f}s",
                conversation_id=req.conversation_id,
            )

        except Exception as exc:
            debug_log(
                "AUDIO_WORKER",
                "VOICE_ERROR",
                f"audio_id={audio_id}, error={exc}",
                conversation_id=req.conversation_id,
            )
            self.event_queue.put(
                AudioEvent(
                    event_type=AudioEventType.VOICE_ERROR,
                    audio_id=audio_id,
                    conversation_id=req.conversation_id,
                    turn_id=req.turn_id,
                    speaker=req.speaker,
                    segment_index=req.segment_index,
                    total_segments=req.total_segments,
                    text_segment=req.text_segment,
                    error_message=str(exc),
                )
            )

    def cancel_active(self) -> None:
        """Activa la señal de cancelación para descartar solicitudes en cola."""
        self.cancel_event.set()

    def clear_cancellation(self) -> None:
        """Restablece la señal de cancelación para aceptar nuevas solicitudes."""
        self.cancel_event.clear()

    def submit(self, request: VoiceSegmentRequest) -> None:
        """Encola una solicitud de síntesis de segmento."""
        self.request_queue.put(request)

    def cancel(self) -> None:
        """Activa la señal de cancelación y purga las solicitudes en la cola."""
        self.cancel_active()
        while not self.request_queue.empty():
            try:
                self.request_queue.get_nowait()
                self.request_queue.task_done()
            except Exception:
                break

    def shutdown(self) -> None:
        """Alias para stop()."""
        self.stop()

    def stop(self) -> None:
        """Envía señal de terminación al worker."""
        self.stop_event.set()
        if hasattr(self.provider, "close"):
            self.provider.close()
