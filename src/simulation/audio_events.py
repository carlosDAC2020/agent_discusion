"""Contratos tipados y tipos de eventos para el subsistema de audio y síntesis de voz.

Diferencia claramente las fases del ciclo de vida del audio:
- Generado / Listo (VOICE_READY, emitido por el AudioWorker).
- Iniciado en reproducción (VOICE_STARTED, emitido por Pygame AudioManager).
- Finalizado de reproducir (VOICE_FINISHED, emitido por Pygame AudioManager al vaciarse el canal).
- Errores y cancelaciones (VOICE_ERROR, VOICE_CANCELLED, AUDIO_DISABLED).
"""

from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Optional

from src.simulation.audio_config import VoiceProfile


class AudioEventType(str, Enum):
    """Tipos de eventos emitidos en el ciclo de audio."""
    VOICE_REQUESTED = "VOICE_REQUESTED"
    VOICE_READY = "VOICE_READY"
    VOICE_STARTED = "VOICE_STARTED"
    VOICE_FINISHED = "VOICE_FINISHED"
    VOICE_ERROR = "VOICE_ERROR"
    VOICE_CANCELLED = "VOICE_CANCELLED"
    AUDIO_DISABLED = "AUDIO_DISABLED"
    MUSIC_STARTED = "MUSIC_STARTED"
    MUSIC_STOPPED = "MUSIC_STOPPED"
    EFFECT_PLAYED = "EFFECT_PLAYED"


class VisualVoiceState(str, Enum):
    """Estados visuales del personaje respecto a la locución."""
    IDLE = "IDLE"
    VOICE_PENDING = "VOICE_PENDING"
    VOICE_PLAYING = "VOICE_PLAYING"
    VOICE_FINISHED = "VOICE_FINISHED"
    VOICE_ERROR = "VOICE_ERROR"


@dataclass(frozen=True)
class VoiceSegmentRequest:
    """Solicitud tipada e inmutable de síntesis de voz enviada al AudioWorker."""
    request_id: str
    conversation_id: str
    turn_id: str
    speaker: str               # "manolo", "josep", "paco"
    text_segment: str
    segment_index: int
    total_segments: int
    is_final_segment: bool
    voice_profile: VoiceProfile
    created_at: float = field(default_factory=time.time)


@dataclass
class AudioEvent:
    """Evento del subsistema de audio transmitido hacia el bucle de Pygame."""
    event_type: AudioEventType
    audio_id: str
    conversation_id: str
    turn_id: str
    speaker: str
    segment_index: int = 0
    total_segments: int = 1
    text_segment: str = ""
    wav_bytes: Optional[bytes] = None
    duration_seconds: float = 0.0
    error_message: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
