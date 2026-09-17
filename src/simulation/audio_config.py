"""Configuración centralizada para el subsistema de audio y síntesis de voz (TTS).

Gestiona parámetros de hardware, perfiles de voz de los personajes y opciones
de Gemini TTS de forma desacoplada y configurable mediante variables de entorno.
"""

import os
from dataclasses import dataclass
from typing import Dict

from dotenv import load_dotenv

load_dotenv()

# -----------------------------------------------------------------------------
# 1. Banderas generales de activación
# -----------------------------------------------------------------------------
AUDIO_ENABLED: bool = os.getenv("AUDIO_ENABLED", "true").lower() in ("true", "1", "yes")
GEMINI_TTS_ENABLED: bool = os.getenv("GEMINI_TTS_ENABLED", "true").lower() in ("true", "1", "yes")

# -----------------------------------------------------------------------------
# 2. Configuración de Gemini TTS
# -----------------------------------------------------------------------------
# Modelo TTS dedicado de Google Gemini para generación de audio nativa
GEMINI_TTS_MODEL: str = os.getenv("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")

# Voces preconstruidas oficiales validadas en Google Gemini
MANOLO_TTS_VOICE: str = os.getenv("MANOLO_TTS_VOICE", "Charon")
JOSEP_TTS_VOICE: str = os.getenv("JOSEP_TTS_VOICE", "Orus")
PACO_TTS_VOICE: str = os.getenv("PACO_TTS_VOICE", "Fenrir")
GEMINI_TTS_FALLBACK_VOICE: str = os.getenv("GEMINI_TTS_FALLBACK_VOICE", "Puck")

# Credencial existente del proyecto
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")

# Tiempos límite y límites de segmentación
TTS_TIMEOUT_SECONDS: float = float(os.getenv("TTS_TIMEOUT_SECONDS", "8.0"))
TTS_MAX_SEGMENT_CHARACTERS: int = int(os.getenv("TTS_MAX_SEGMENT_CHARACTERS", "140"))
TTS_MIN_SEGMENT_CHARACTERS: int = int(os.getenv("TTS_MIN_SEGMENT_CHARACTERS", "10"))

# -----------------------------------------------------------------------------
# 3. Parámetros de Audio PCM y Pygame Mixer
# -----------------------------------------------------------------------------
AUDIO_SAMPLE_RATE: int = int(os.getenv("AUDIO_SAMPLE_RATE", "24000"))
AUDIO_CHANNELS: int = int(os.getenv("AUDIO_CHANNELS", "1"))  # Mono
AUDIO_SAMPLE_WIDTH: int = 2  # 16-bit PCM (2 bytes/muestra)
AUDIO_BUFFER_SIZE: int = int(os.getenv("AUDIO_BUFFER_SIZE", "1024"))

# Volúmenes por defecto (0.0 a 1.0)
VOICE_VOLUME: float = float(os.getenv("VOICE_VOLUME", "0.95"))
MUSIC_VOLUME: float = float(os.getenv("MUSIC_VOLUME", "0.30"))
EFFECTS_VOLUME: float = float(os.getenv("EFFECTS_VOLUME", "0.60"))
MASTER_VOLUME: float = float(os.getenv("MASTER_VOLUME", "1.00"))


# -----------------------------------------------------------------------------
# 4. Perfiles de Voz de los Personajes
# -----------------------------------------------------------------------------
@dataclass(frozen=True)
class VoiceProfile:
    """Especificación fonética y de configuración para un personaje."""

    speaker_id: str
    voice_name: str
    fallback_voice: str = GEMINI_TTS_FALLBACK_VOICE
    language: str = "es"
    volume: float = 1.0


VOICE_PROFILES: Dict[str, VoiceProfile] = {
    "manolo": VoiceProfile(
        speaker_id="manolo",
        voice_name=MANOLO_TTS_VOICE,
        fallback_voice=GEMINI_TTS_FALLBACK_VOICE,
        volume=1.0,
    ),
    "josep": VoiceProfile(
        speaker_id="josep",
        voice_name=JOSEP_TTS_VOICE,
        fallback_voice=GEMINI_TTS_FALLBACK_VOICE,
        volume=1.0,
    ),
    "paco": VoiceProfile(
        speaker_id="paco",
        voice_name=PACO_TTS_VOICE,
        fallback_voice=GEMINI_TTS_FALLBACK_VOICE,
        volume=1.0,
    ),
}


CHARACTER_VOICES: Dict[str, VoiceProfile] = VOICE_PROFILES

FALLBACK_PROFILE: VoiceProfile = VoiceProfile(
    speaker_id="fallback",
    voice_name=GEMINI_TTS_FALLBACK_VOICE,
    fallback_voice=GEMINI_TTS_FALLBACK_VOICE,
    volume=1.0,
)


def get_voice_profile(speaker: str) -> VoiceProfile:
    """Obtiene el perfil de voz configurado para un personaje o el perfil fallback."""
    key = (speaker or "").lower().strip()
    if "manolo" in key:
        return VOICE_PROFILES["manolo"]
    elif "josep" in key or "barca" in key or "barcelona" in key:
        return VOICE_PROFILES["josep"]
    elif "paco" in key or "madrid" in key or "real_madrid" in key:
        return VOICE_PROFILES["paco"]
    return VOICE_PROFILES.get(key, FALLBACK_PROFILE)
