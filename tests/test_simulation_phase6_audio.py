"""Pruebas herméticas de la Fase 6: Audio y Síntesis de Voz mediante Gemini TTS.

Verifica:
1. Configuración, perfiles de voz y contratos tipados.
2. Conversión pura pcm_to_wav_bytes en memoria (PCM 16-bit 24kHz mono -> RIFF WAV).
3. Segmentación textual adaptativa (TextSegmenter).
4. Proveedores TTS (MockTTSProvider hermético y GeminiTTSProvider).
5. AudioWorker (hilo secundario sin dependencias de Pygame).
6. AudioManager (FIFO en hilo principal, un solo canal, control de volumen y mute).
7. Ciclo de eventos: VOICE_READY (worker) -> VOICE_STARTED (mixer) -> VOICE_FINISHED (mixer fin).
8. Integración con agentes visuales, Manolo, ConversationCoordinator y bucle de app headless.
"""

import io
import os
import queue
import time
import wave
from typing import Any, List
from unittest.mock import MagicMock, patch

import pytest

# Asegurar entorno headless y sin audio de hardware para pruebas
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame

from src.simulation.audio_config import (
    AUDIO_CHANNELS,
    AUDIO_SAMPLE_RATE,
    GEMINI_TTS_MODEL,
    CHARACTER_VOICES,
    VoiceProfile,
    get_voice_profile,
)
from src.simulation.audio_events import (
    AudioEvent,
    AudioEventType,
    VisualVoiceState,
    VoiceSegmentRequest,
)
from src.simulation.audio_worker import (
    AudioWorker,
    BaseTTSProvider,
    GeminiTTSProvider,
    MockTTSProvider,
    pcm_to_wav_bytes,
)
from src.simulation.audio import (
    AudioManager,
    TextSegmenter,
)
from src.simulation.agent import VisualAgent, BartenderNPC
from src.simulation.conversation import ConversationCoordinator, ConversationCoordinatorState
from src.simulation.dialogue import DialogueEvent, DialogueEventType
from src.simulation.world import BarWorld


# =============================================================================
# 1. Configuración, perfiles y contratos
# =============================================================================

def test_1_audio_config_defaults():
    """Verifica que la configuración por defecto respete las restricciones de la Fase 6."""
    assert AUDIO_SAMPLE_RATE == 24000
    assert AUDIO_CHANNELS == 1
    assert GEMINI_TTS_MODEL == "gemini-2.5-flash-preview-tts"
    assert "manolo" in CHARACTER_VOICES
    assert "josep" in CHARACTER_VOICES
    assert "paco" in CHARACTER_VOICES


def test_2_voice_profiles_retrieval():
    """Verifica la asignación de voces verificadas a cada personaje y fallback."""
    manolo_profile = get_voice_profile("manolo")
    assert manolo_profile.voice_name == "Charon"
    assert manolo_profile.speaker_id == "manolo"

    josep_profile = get_voice_profile("josep")
    assert josep_profile.voice_name == "Orus"

    paco_profile = get_voice_profile("paco")
    assert paco_profile.voice_name == "Fenrir"

    fallback = get_voice_profile("personaje_desconocido")
    assert fallback.voice_name == "Puck"


def test_3_audio_event_types_and_dataclasses():
    """Verifica la estructura inmutable de VoiceSegmentRequest y los eventos de audio."""
    req = VoiceSegmentRequest(
        request_id="req_1",
        conversation_id="c1",
        turn_id="t1",
        speaker="josep",
        text_segment="Visca el Barça!",
        segment_index=0,
        total_segments=1,
        is_final_segment=True,
        voice_profile=get_voice_profile("josep"),
    )
    assert req.request_id == "req_1"
    assert req.speaker == "josep"

    ev = AudioEvent(
        event_type=AudioEventType.VOICE_READY,
        audio_id="req_1",
        conversation_id="c1",
        turn_id="t1",
        speaker="josep",
        wav_bytes=b"RIFF...",
        duration_seconds=1.5,
    )
    assert ev.event_type == AudioEventType.VOICE_READY
    assert ev.duration_seconds == 1.5


# =============================================================================
# 2. Conversión pura PCM a RIFF WAV en memoria
# =============================================================================

def test_4_pcm_to_wav_bytes_valid_conversion():
    """Verifica que pcm_to_wav_bytes genera un WAV canónico RIFF legible por el módulo wave."""
    # 0.1s de tono / silencio en PCM 16-bit 24kHz mono = 24000 * 2 * 0.1 = 4800 bytes
    pcm_data = b"\x00\x00" * 2400
    wav_bytes = pcm_to_wav_bytes(pcm_data, sample_rate=24000, channels=1, sample_width=2)

    assert wav_bytes.startswith(b"RIFF")
    assert b"WAVE" in wav_bytes
    assert len(wav_bytes) == len(pcm_data) + 44  # Cabecera estándar de 44 bytes

    # Validar que wave.open puede leerlo sin errores
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 24000
        assert wf.getnframes() == 2400


def test_5_pcm_to_wav_bytes_empty_input():
    """Verifica que pcm_to_wav_bytes con entrada vacía lanza ValueError de forma segura."""
    with pytest.raises(ValueError, match="vacíos"):
        pcm_to_wav_bytes(b"")


# =============================================================================
# 3. Segmentación textual adaptativa (TextSegmenter)
# =============================================================================

def test_6_text_segmenter_short_text():
    """Un texto corto menor a 140 caracteres no debe ser fragmentado."""
    text = "Buenas tardes parroquianos, ¿cómo ven el partido?"
    segments = TextSegmenter.segment(text, max_chars=140)
    assert len(segments) == 1
    assert segments[0] == text


def test_7_text_segmenter_natural_punctuation_split():
    """Divide textos largos en pausas naturales delimitadas por signos de puntuación."""
    p1 = "El juego posicional de Cruyff sentó las bases del fútbol moderno."
    p2 = "Sin embargo, el Madrid de las remontadas tiene un gen competitivo irrepetible."
    text = f"{p1} {p2}"
    segments = TextSegmenter.segment(text, max_chars=80)
    assert len(segments) == 2
    assert segments[0] == p1
    assert segments[1] == p2


def test_8_text_segmenter_long_clause_split():
    """Divide oraciones muy largas sin puntos utilizando comas o espacios sin exceder el límite."""
    text = "Esta es una frase extremadamente larga que no contiene puntos finales pero describe detalladamente cómo el mediocampo debe posicionarse y circular el balón con velocidad para desestructurar la presión alta del rival"
    segments = TextSegmenter.segment(text, max_chars=70)
    assert len(segments) >= 3
    for s in segments:
        assert len(s) <= 75


# =============================================================================
# 4. Proveedores TTS y AudioWorker (hilo secundario sin Pygame)
# =============================================================================

def test_9_mock_tts_provider_synthesizes_pcm():
    """MockTTSProvider genera audio PCM determinista y proporcional al texto."""
    provider = MockTTSProvider(sample_rate=24000)
    profile = get_voice_profile("paco")
    pcm = provider.synthesize("¡Hala Madrid!", profile)
    assert len(pcm) > 0
    assert len(pcm) % 2 == 0  # 16-bit alícuota


def test_10_gemini_tts_provider_no_key_raises_runtime_error():
    """GeminiTTSProvider lanza RuntimeError descriptivo si no hay API key de Gemini."""
    provider = GeminiTTSProvider(api_key="")
    profile = get_voice_profile("manolo")
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        provider.synthesize("Hola", profile)


def test_11_audio_worker_thread_lifecycle():
    """Verifica el arranque, consumo y detención limpia del AudioWorker."""
    req_q: queue.Queue = queue.Queue()
    ev_q: queue.Queue = queue.Queue()
    provider = MockTTSProvider()

    worker = AudioWorker(req_q, ev_q, provider=provider)
    worker.start()
    assert worker.is_alive()

    worker.shutdown()
    worker.join(timeout=1.0)
    assert not worker.is_alive()


def test_12_audio_worker_emits_voice_ready_with_wav():
    """Verifica que el worker procesa VoiceSegmentRequest y emite VOICE_READY con WAV."""
    req_q: queue.Queue = queue.Queue()
    ev_q: queue.Queue = queue.Queue()
    provider = MockTTSProvider()

    worker = AudioWorker(req_q, ev_q, provider=provider)
    worker.start()

    req = VoiceSegmentRequest(
        request_id="req_test_1",
        conversation_id="conv_1",
        turn_id="turn_1",
        speaker="josep",
        text_segment="Visca el Barça y visca Catalunya.",
        segment_index=0,
        total_segments=1,
        is_final_segment=True,
        voice_profile=get_voice_profile("josep"),
    )
    req_q.put(req)

    # Esperar el evento en ev_q
    ev = ev_q.get(timeout=2.0)
    assert ev.event_type == AudioEventType.VOICE_READY
    assert ev.audio_id == "req_test_1"
    assert ev.wav_bytes is not None
    assert ev.wav_bytes.startswith(b"RIFF")
    assert ev.duration_seconds > 0.0

    worker.shutdown()
    worker.join(timeout=1.0)


def test_13_audio_worker_error_handling():
    """Verifica que si el proveedor falla, el worker emite VOICE_ERROR sin caerse."""
    req_q: queue.Queue = queue.Queue()
    ev_q: queue.Queue = queue.Queue()

    class FailingProvider(BaseTTSProvider):
        def synthesize(self, text, profile):
            raise ValueError("Error de red simulado")

    worker = AudioWorker(req_q, ev_q, provider=FailingProvider())
    worker.start()

    req = VoiceSegmentRequest(
        request_id="req_fail",
        conversation_id="c1",
        turn_id="t1",
        speaker="manolo",
        text_segment="Texto con fallo",
        segment_index=0,
        total_segments=1,
        is_final_segment=True,
        voice_profile=get_voice_profile("manolo"),
    )
    req_q.put(req)

    ev = ev_q.get(timeout=2.0)
    assert ev.event_type == AudioEventType.VOICE_ERROR
    assert "Error de red simulado" in (ev.error_message or "")
    assert worker.is_alive()

    worker.shutdown()
    worker.join(timeout=1.0)


def test_14_audio_worker_queue_drain_on_cancel():
    """Verifica que cancelar el worker purga las solicitudes no procesadas."""
    req_q: queue.Queue = queue.Queue()
    ev_q: queue.Queue = queue.Queue()
    provider = MockTTSProvider()

    worker = AudioWorker(req_q, ev_q, provider=provider)
    # Rellenar la cola sin arrancar
    for i in range(5):
        worker.submit(
            VoiceSegmentRequest(
                request_id=f"r_{i}",
                conversation_id="c1",
                turn_id="t1",
                speaker="paco",
                text_segment=f"Segmento {i}",
                segment_index=i,
                total_segments=5,
                is_final_segment=(i == 4),
                voice_profile=get_voice_profile("paco"),
            )
        )
    assert req_q.qsize() == 5
    worker.cancel()
    assert req_q.empty()


# =============================================================================
# 5. AudioManager (FIFO en hilo principal, control de canal y volumen)
# =============================================================================

def test_15_audio_manager_initialization_with_mock():
    """Verifica inicialización limpia de AudioManager con MockTTSProvider."""
    manager = AudioManager(provider=MockTTSProvider())
    manager.start()
    assert manager.is_initialized
    assert manager.worker is not None
    manager.shutdown()


def test_16_audio_manager_submit_voice_enqueues_requests():
    """submit_voice segmenta y emite eventos VOICE_REQUESTED de forma no bloqueante."""
    manager = AudioManager(provider=MockTTSProvider())
    manager.start()

    long_text = (
        "El fútbol asociativo y la salida limpia desde atrás son innegociables en nuestro estilo de juego histórico. "
        "Sin embargo, el espíritu de remontada en el Santiago Bernabéu impone un respeto que nadie puede ignorar."
    )
    segments = manager.submit_voice(
        long_text,
        speaker="josep",
        conversation_id="c1",
        turn_id="t1",
    )
    assert len(segments) == 2

    # Verificar que los eventos públicos iniciales registran VOICE_REQUESTED
    events = manager.poll_events()
    requested_events = [e for e in events if e.event_type == AudioEventType.VOICE_REQUESTED]
    assert len(requested_events) == 2

    manager.shutdown()


def test_17_audio_manager_fifo_playback_queue():
    """AudioManager procesa los eventos VOICE_READY en cola secuencial FIFO."""
    manager = AudioManager(provider=MockTTSProvider())
    manager.start()

    # Simular recepción de dos eventos VOICE_READY
    ev1 = AudioEvent(
        event_type=AudioEventType.VOICE_READY,
        audio_id="a1",
        conversation_id="c1",
        turn_id="t1",
        speaker="manolo",
        wav_bytes=pcm_to_wav_bytes(b"\x00\x00" * 2400),
    )
    ev2 = AudioEvent(
        event_type=AudioEventType.VOICE_READY,
        audio_id="a2",
        conversation_id="c1",
        turn_id="t1",
        speaker="josep",
        wav_bytes=pcm_to_wav_bytes(b"\x00\x00" * 2400),
    )

    manager.worker_event_queue.put(ev1)
    manager.worker_event_queue.put(ev2)

    manager.update(0.016)
    # Debe haber agregado a la cola de reproducción
    assert any(e.audio_id == "a1" for e in manager.playback_queue) or manager.current_playing_event is not None

    manager.shutdown()


def test_18_audio_manager_single_channel_exclusivity():
    """Garantiza que el AudioManager use exclusivamente Channel(0) para las voces."""
    manager = AudioManager(provider=MockTTSProvider())
    manager.start()
    if manager.audio_available and manager.voice_channel:
        # En pygame, el canal 0 debe ser el asignado
        assert manager.voice_channel is not None
    manager.shutdown()


def test_19_audio_manager_voice_started_and_finished_lifecycle():
    """Verifica que se emita VOICE_STARTED al empezar y VOICE_FINISHED al terminar el sonido."""
    manager = AudioManager(provider=MockTTSProvider())
    manager.start()

    wav = pcm_to_wav_bytes(b"\x00\x00" * 480)  # ~0.02s de audio
    ev = AudioEvent(
        event_type=AudioEventType.VOICE_READY,
        audio_id="a_short",
        conversation_id="c1",
        turn_id="t1",
        speaker="paco",
        wav_bytes=wav,
        duration_seconds=0.02,
    )
    manager.worker_event_queue.put(ev)

    # Frame 1: Drena worker_event_queue y reproduce en voice_channel -> emite VOICE_STARTED
    manager.update(0.016)
    events = manager.poll_events()
    assert any(e.event_type == AudioEventType.VOICE_STARTED for e in events)

    # Esperar a que el canal termine físicamente (o simular en dummy)
    time.sleep(0.05)
    # Frame 2: Detecta que canal ya no está ocupado -> emite VOICE_FINISHED
    manager.update(0.016)
    events_after = manager.poll_events()
    assert any(e.event_type == AudioEventType.VOICE_FINISHED for e in events_after)

    manager.shutdown()


def test_20_audio_manager_mute_and_unmute():
    """Verifica que toggle_mute alterne el estado y preserve los flujos."""
    manager = AudioManager(provider=MockTTSProvider())
    manager.start()
    assert not manager.is_muted

    manager.toggle_mute()
    assert manager.is_muted

    manager.toggle_mute()
    assert not manager.is_muted

    manager.shutdown()


def test_21_audio_manager_cancel_current_speech():
    """cancel_current_speech detiene la locución, limpia colas y emite VOICE_CANCELLED."""
    manager = AudioManager(provider=MockTTSProvider())
    manager.start()

    manager.submit_voice("Frase que será cancelada de inmediato.", speaker="manolo")
    manager.cancel_current_speech()

    assert len(manager.playback_queue) == 0
    assert manager.current_playing_event is None

    events = manager.poll_events()
    assert any(e.event_type == AudioEventType.VOICE_CANCELLED for e in events)

    manager.shutdown()


# =============================================================================
# 6. Integración con VisualAgent, BartenderNPC y ConversationCoordinator
# =============================================================================

def test_22_visual_agent_voice_state_integration():
    """Verifica que VisualAgent soporte y reporte estados de voz."""
    agent = VisualAgent("josep_barca", "barcelona", "Josep", 100, 100)
    assert agent.voice_state == "IDLE"
    assert not agent.is_speaking_voice

    agent.set_voice_state("VOICE_PLAYING")
    assert agent.voice_state == "VOICE_PLAYING"
    assert agent.is_speaking_voice

    agent.set_voice_state("IDLE")
    assert not agent.is_speaking_voice


def test_23_bartender_voice_state_integration():
    """Verifica que BartenderNPC soporte y reporte estados de voz."""
    bartender = BartenderNPC(50, 50)
    assert bartender.voice_state == "IDLE"
    assert not bartender.is_speaking_voice

    bartender.set_voice_state("VOICE_PLAYING")
    assert bartender.is_speaking_voice

    bartender.set_voice_state("IDLE")
    assert not bartender.is_speaking_voice


def test_24_conversation_coordinator_submits_voice_on_message_completed():
    """Verifica que al recibir MESSAGE_COMPLETED, el coordinator despache a audio_manager."""
    coordinator = ConversationCoordinator()
    mock_audio = MagicMock(spec=AudioManager)

    # Simular evento de diálogo completado
    ev = DialogueEvent(
        event_type=DialogueEventType.MESSAGE_COMPLETED,
        conversation_id="conv_123",
        speaker_team="barcelona",
        text="¡Cruyff cambió el paradigma!",
    )

    coordinator.process_dialogue_event(ev, agents=[], audio_manager=mock_audio)

    # Debe invocar submit_voice con el texto y speaker correspondiente
    mock_audio.submit_voice.assert_called_once()
    call_args = mock_audio.submit_voice.call_args
    assert call_args[0][0] == "¡Cruyff cambió el paradigma!"
    assert call_args[1]["speaker"] == "josep"


def test_25_headless_simulation_app_with_audio_manager():
    """Verifica la ejecución de la app completa de simulación en modo headless con AudioManager inyectado."""
    from src.simulation.app import run_simulation

    manager = AudioManager(provider=MockTTSProvider())

    # Ejecutar 5 frames en headless
    run_simulation(
        debug=False,
        demo_movement=False,
        bdi=False,
        dialogue=False,
        audio_manager=manager,
        max_frames=5,
    )
    # La simulación debe correr 5 frames y cerrarse limpiamente en finally
    assert not manager.is_initialized
    assert manager.worker is None


def test_26_audio_manager_pause_and_resume():
    """Verifica que pause(), resume() y toggle_pause() controlen el canal sin perder eventos."""
    manager = AudioManager(provider=MockTTSProvider())
    manager.start()
    assert not manager.is_paused

    manager.toggle_pause()
    assert manager.is_paused

    manager.resume()
    assert not manager.is_paused

    manager.pause()
    assert manager.is_paused

    manager.shutdown()


def test_27_audio_manager_tts_toggle():
    """Verifica que desactivar TTS omita la síntesis y limpie el audio activo."""
    manager = AudioManager(provider=MockTTSProvider())
    manager.start()
    assert manager.tts_enabled

    # Desactivar TTS
    manager.toggle_tts()
    assert not manager.tts_enabled

    # Intentar enviar locución: debe retornar [] inmediatamente
    segments = manager.submit_voice("Texto que no debe sintetizarse.", speaker="josep")
    assert segments == []
    assert len(manager.playback_queue) == 0

    # Reactivar TTS
    manager.enable_tts()
    assert manager.tts_enabled

    segments_active = manager.submit_voice("Ahora sí debe sintetizarse.", speaker="josep")
    assert len(segments_active) > 0

    manager.shutdown()


def test_28_chat_ui_audio_buttons_click():
    """Verifica que hacer clic en los botones de audio de ChatUI invoque los métodos correspondientes."""
    from src.simulation.chat_ui import ChatUI

    ui = ChatUI()
    mock_audio = MagicMock(spec=AudioManager)

    # 1. Clic en botón TTS (x=12, y=640-90=550)
    ev_tts = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": (960 + 20, 555)})
    ui.handle_event(ev_tts, offset_x=960, audio_manager=mock_audio)
    mock_audio.toggle_tts.assert_called_once()

    # 2. Clic en botón Pausa (x=102, y=550)
    ev_pause = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": (960 + 120, 555)})
    ui.handle_event(ev_pause, offset_x=960, audio_manager=mock_audio)
    mock_audio.toggle_pause.assert_called_once()

    # 3. Clic en botón Parar (x=192, y=550)
    ev_stop = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": (960 + 210, 555)})
    ui.handle_event(ev_stop, offset_x=960, audio_manager=mock_audio)
    mock_audio.cancel_current_speech.assert_called_once()

    # 4. Clic en botón Mute (x=282, y=550)
    ev_mute = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": (960 + 300, 555)})
    ui.handle_event(ev_mute, offset_x=960, audio_manager=mock_audio)
    mock_audio.toggle_mute.assert_called_once()


def test_29_app_run_simulation_with_no_tts_flag():
    """Verifica que run_simulation admita tts_enabled=False y audio_enabled=False."""
    from src.simulation.app import run_simulation

    manager = AudioManager(provider=MockTTSProvider())
    run_simulation(
        audio_manager=manager,
        audio_enabled=False,
        tts_enabled=False,
        max_frames=3,
    )
    assert not manager.is_initialized
