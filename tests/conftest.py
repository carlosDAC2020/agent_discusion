"""Configuración global de pytest para la suite de pruebas.

Garantiza controladores dummy de Pygame en entornos CI (GitHub Actions / Linux headless)
para evitar fallos por falta de servidor X11 o hardware de audio (ALSA/PulseAudio).
"""

import os

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
