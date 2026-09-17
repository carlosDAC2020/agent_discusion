"""Configuración centralizada para la simulación 2D del Bar.

Define constantes de pantalla, cuadrícula, paleta de colores retro/pixel art,
tiempos, dimensiones y paletas temáticas de agentes e iluminación 2.5D.
"""

from typing import Tuple

# -----------------------------------------------------------------------------
# Dimensiones lógicas y de ventana
# -----------------------------------------------------------------------------
LOGICAL_WIDTH: int = 960
LOGICAL_HEIGHT: int = 640
BAR_WIDTH: int = LOGICAL_WIDTH
CHAT_PANEL_WIDTH: int = 380
WINDOW_WIDTH: int = BAR_WIDTH + CHAT_PANEL_WIDTH  # 1340 px
WINDOW_HEIGHT: int = 640
WINDOW_TITLE: str = "Bar El Clásico - Simulación 2.5D & Tertulia"

TARGET_FPS: int = 60

# -----------------------------------------------------------------------------
# Cuadrícula y sistema de coordenadas
# -----------------------------------------------------------------------------
TILE_SIZE: int = 32
GRID_COLS: int = LOGICAL_WIDTH // TILE_SIZE  # 30 columnas
GRID_ROWS: int = LOGICAL_HEIGHT // TILE_SIZE  # 20 filas

# -----------------------------------------------------------------------------
# Paleta de colores temáticos del bar deportivo retro (RGB)
# -----------------------------------------------------------------------------
# Suelo de madera en espiga / tablones con variedad tonal
COLOR_FLOOR: Tuple[int, int, int] = (48, 32, 22)
COLOR_FLOOR_PLANK: Tuple[int, int, int] = (38, 24, 16)
COLOR_FLOOR_ALT_1: Tuple[int, int, int] = (54, 36, 24)
COLOR_FLOOR_ALT_2: Tuple[int, int, int] = (44, 28, 18)
COLOR_FLOOR_KNOT: Tuple[int, int, int] = (32, 20, 14)

# Paredes y carpintería con volumen
COLOR_WALL_BG: Tuple[int, int, int] = (32, 22, 16)
COLOR_WALL_TOP: Tuple[int, int, int] = (18, 12, 8)
COLOR_WALL_BORDER: Tuple[int, int, int] = (62, 42, 30)
COLOR_WALL_WAINSCOT: Tuple[int, int, int] = (58, 34, 20)  # Friso de madera inferior
COLOR_WALL_WAINSCOT_DARK: Tuple[int, int, int] = (42, 24, 14)
COLOR_WALL_PAPER: Tuple[int, int, int] = (74, 52, 38)  # Papel tapiz superior cálido
COLOR_WALL_CROWN: Tuple[int, int, int] = (85, 55, 32)  # Cornisa superior

# Barra con volumen y encimera pulida
COLOR_BAR_WOOD: Tuple[int, int, int] = (78, 42, 24)
COLOR_BAR_TOP: Tuple[int, int, int] = (118, 66, 36)
COLOR_BAR_TRIM: Tuple[int, int, int] = (145, 84, 46)
COLOR_BAR_FRONT_PANEL: Tuple[int, int, int] = (64, 34, 18)
COLOR_BAR_BRASS_RAIL: Tuple[int, int, int] = (200, 160, 50)  # Reposapiés de latón
COLOR_SHELF_BG: Tuple[int, int, int] = (36, 22, 14)
COLOR_SHELF_WOOD: Tuple[int, int, int] = (56, 32, 18)

# Taburetes con volumen (asiento acolchado + aro de patas)
COLOR_STOOL_OUTER: Tuple[int, int, int] = (140, 35, 35)
COLOR_STOOL_CUSHION: Tuple[int, int, int] = (185, 45, 45)
COLOR_STOOL_HIGHLIGHT: Tuple[int, int, int] = (220, 70, 70)
COLOR_STOOL_LEG: Tuple[int, int, int] = (50, 30, 18)

# Sillas con respaldo y patas 2.5D
COLOR_CHAIR: Tuple[int, int, int] = (70, 40, 22)
COLOR_CHAIR_SEAT: Tuple[int, int, int] = (92, 52, 28)
COLOR_CHAIR_BACK: Tuple[int, int, int] = (80, 46, 25)

# Mesas con volumen y moldura de borde
COLOR_TABLE_WOOD: Tuple[int, int, int] = (96, 52, 28)
COLOR_TABLE_TOP: Tuple[int, int, int] = (124, 72, 42)
COLOR_TABLE_RIM: Tuple[int, int, int] = (142, 86, 50)
COLOR_TABLE_LEG: Tuple[int, int, int] = (68, 36, 18)
COLOR_TABLE_SHADOW: Tuple[int, int, int] = (20, 12, 8)

# Televisor / Zona deportiva
COLOR_TV_FRAME: Tuple[int, int, int] = (18, 18, 20)
COLOR_TV_BEZEL: Tuple[int, int, int] = (42, 42, 46)
COLOR_TV_SCREEN: Tuple[int, int, int] = (28, 112, 48)
COLOR_SOFA_BASE: Tuple[int, int, int] = (62, 24, 24)
COLOR_SOFA_CUSHION: Tuple[int, int, int] = (88, 34, 34)
COLOR_SOFA_TUFT: Tuple[int, int, int] = (50, 18, 18)

# Banderines de clubes
COLOR_BANNER_FCB_BLUE: Tuple[int, int, int] = (0, 77, 152)
COLOR_BANNER_FCB_RED: Tuple[int, int, int] = (165, 0, 68)
COLOR_BANNER_RMA_WHITE: Tuple[int, int, int] = (245, 245, 245)
COLOR_BANNER_RMA_GOLD: Tuple[int, int, int] = (235, 195, 60)

# Entrada y decoración
COLOR_MAT_BORDER: Tuple[int, int, int] = (75, 55, 30)
COLOR_MAT_FILL: Tuple[int, int, int] = (115, 85, 45)
COLOR_PLANT_POT: Tuple[int, int, int] = (130, 65, 35)
COLOR_PLANT_LEAVES: Tuple[int, int, int] = (40, 120, 50)
COLOR_PLANT_HIGHLIGHT: Tuple[int, int, int] = (60, 160, 70)

# Sombras y atmósfera de iluminación cálida
COLOR_SHADOW_SOFT: Tuple[int, int, int] = (14, 8, 6)
COLOR_LAMP_CONE: Tuple[int, int, int] = (255, 220, 130)
COLOR_GLASS_BEER: Tuple[int, int, int] = (230, 180, 50)
COLOR_BEER_FOAM: Tuple[int, int, int] = (255, 250, 230)

# Personajes de ambientación (NPCs)
# Bartender (Manolo)
COLOR_BARTENDER_SHIRT: Tuple[int, int, int] = (245, 245, 250)
COLOR_BARTENDER_VEST: Tuple[int, int, int] = (22, 22, 26)
COLOR_BARTENDER_BOWTIE: Tuple[int, int, int] = (180, 30, 30)
COLOR_BARTENDER_SHAKER: Tuple[int, int, int] = (210, 215, 225)
COLOR_BARTENDER_SHAKER_HIGHLIGHT: Tuple[int, int, int] = (255, 255, 255)

# Señora de la limpieza (Doña Carmen)
COLOR_CLEANER_DRESS: Tuple[int, int, int] = (65, 105, 160)
COLOR_CLEANER_APRON: Tuple[int, int, int] = (245, 245, 240)
COLOR_CLEANER_BANDANA: Tuple[int, int, int] = (220, 90, 120)
COLOR_CLEANER_MOP_WOOD: Tuple[int, int, int] = (180, 130, 70)
COLOR_CLEANER_MOP_HEAD: Tuple[int, int, int] = (230, 230, 220)
COLOR_CLEANER_BUCKET: Tuple[int, int, int] = (220, 180, 40)
COLOR_CLEANER_WATER: Tuple[int, int, int] = (70, 140, 210)

# Señor en la esquina tosiendo (Don Antonio)
COLOR_OLDMAN_COAT: Tuple[int, int, int] = (82, 60, 42)
COLOR_OLDMAN_PANTS: Tuple[int, int, int] = (50, 48, 46)
COLOR_OLDMAN_CAP: Tuple[int, int, int] = (60, 52, 46)
COLOR_OLDMAN_HAIR: Tuple[int, int, int] = (190, 190, 195)
COLOR_OLDMAN_SCARF: Tuple[int, int, int] = (150, 40, 40)
COLOR_COUGH_PUFF: Tuple[int, int, int] = (240, 240, 245)
COLOR_COUGH_TEXT: Tuple[int, int, int] = (220, 40, 40)

# UI y depuración
COLOR_DEBUG_OBSTACLE: Tuple[int, int, int] = (255, 60, 60)
COLOR_DEBUG_POI: Tuple[int, int, int] = (60, 255, 60)
COLOR_DEBUG_TEXT: Tuple[int, int, int] = (255, 255, 0)
COLOR_HUD_BG: Tuple[int, int, int] = (12, 10, 8)

# -----------------------------------------------------------------------------
# Paleta y especificaciones visuales de los Agentes Pixel Art
# -----------------------------------------------------------------------------
# Josep (FC Barcelona)
COLOR_JOSEP_JERSEY_BLUE: Tuple[int, int, int] = (0, 65, 140)
COLOR_JOSEP_JERSEY_RED: Tuple[int, int, int] = (160, 15, 60)
COLOR_JOSEP_PANTS: Tuple[int, int, int] = (20, 24, 52)
COLOR_JOSEP_HAIR: Tuple[int, int, int] = (38, 26, 18)
COLOR_JOSEP_SKIN: Tuple[int, int, int] = (238, 192, 154)
COLOR_JOSEP_SKIN_SHADOW: Tuple[int, int, int] = (206, 156, 122)
COLOR_JOSEP_BOOTS: Tuple[int, int, int] = (26, 26, 28)
COLOR_JOSEP_TAG: Tuple[int, int, int] = (255, 215, 60)

# Paco (Real Madrid CF)
COLOR_PACO_JERSEY_WHITE: Tuple[int, int, int] = (246, 246, 248)
COLOR_PACO_JERSEY_SHADOW: Tuple[int, int, int] = (208, 210, 216)
COLOR_PACO_JERSEY_GOLD: Tuple[int, int, int] = (225, 185, 48)
COLOR_PACO_JERSEY_PURPLE: Tuple[int, int, int] = (85, 45, 120)
COLOR_PACO_PANTS: Tuple[int, int, int] = (48, 46, 44)
COLOR_PACO_HAIR: Tuple[int, int, int] = (72, 48, 32)
COLOR_PACO_SKIN: Tuple[int, int, int] = (244, 202, 168)
COLOR_PACO_SKIN_SHADOW: Tuple[int, int, int] = (212, 168, 134)
COLOR_PACO_BOOTS: Tuple[int, int, int] = (42, 28, 20)
COLOR_PACO_TAG: Tuple[int, int, int] = (240, 240, 250)

# Estados visuales de los agentes
STATE_IDLE: str = "IDLE"
STATE_LOOKING_LEFT: str = "LOOKING_LEFT"
STATE_LOOKING_RIGHT: str = "LOOKING_RIGHT"
STATE_WALKING: str = "WALKING"
STATE_DEBUG: str = "DEBUG"

# Velocidad de desplazamiento por defecto (píxeles lógicos por segundo, rango sugerido 75-90)
DEFAULT_AGENT_SPEED: float = 80.0

# Colores adicionales para depuración de navegación y rutas
COLOR_DEBUG_PATH: Tuple[int, int, int] = (60, 220, 255)
COLOR_DEBUG_WAYPOINT: Tuple[int, int, int] = (255, 230, 80)
COLOR_DEBUG_BLOCKED_TILE: Tuple[int, int, int] = (220, 40, 40)
COLOR_DEBUG_GOAL: Tuple[int, int, int] = (50, 255, 120)

# -----------------------------------------------------------------------------
# Parámetros centralizados de la Arquitectura BDI (Fase 4)
# -----------------------------------------------------------------------------
# Frecuencia de decisión del ciclo deliberativo (en Hz y su intervalo en segundos)
BDI_DECISION_FREQUENCY: float = 4.0  # 4 decisiones por segundo
BDI_DECISION_INTERVAL: float = 1.0 / BDI_DECISION_FREQUENCY  # 0.25 segundos

# Valores iniciales y tasas de evolución de necesidades internas (0.0 a 1.0)
BDI_INITIAL_ENERGY: float = 0.90
BDI_INITIAL_THIRST: float = 0.15
BDI_INITIAL_SOCIABILITY: float = 0.40

# Tasas de cambio por segundo
BDI_ENERGY_DECAY_RATE: float = 0.015  # ~65s para agotamiento completo
BDI_THIRST_GROWTH_RATE: float = 0.020  # ~50s para sed máxima
BDI_SOCIABILITY_GROWTH_RATE: float = 0.018

# Tiempos de permanencia y acción en el punto objetivo
BDI_DRINK_DURATION: float = 3.0
BDI_REST_DURATION: float = 4.0
BDI_EXPLORE_DURATION: float = 2.0
BDI_SOCIALIZE_DURATION: float = 3.5

# Efectos de satisfacción de necesidades
BDI_THIRST_QUENCH_AMOUNT: float = 0.85
BDI_ENERGY_RECOVERY_AMOUNT: float = 0.60
BDI_SOCIABILITY_SATISFY_AMOUNT: float = 0.50

# Distancias espaciales sociales entre agentes (en píxeles lógicos)
BDI_MIN_SOCIAL_DISTANCE: float = 40.0  # Espacio personal mínimo (~1.25 celdas)
BDI_MAX_SOCIAL_DISTANCE: float = 96.0  # Rango de proximidad social (~3 celdas)

# Prevención de oscilaciones y persistencia de intenciones
BDI_MIN_INTENTION_DURATION: float = 2.5  # Segundos mínimos antes de permitir preempción
BDI_UTILITY_PREEMPT_THRESHOLD: float = 0.30  # Diferencia de utilidad necesaria para interrumpir
BDI_DESIRE_COOLDOWN: float = 12.0  # Cooldown para re-seleccionar el mismo deseo
BDI_DEFAULT_SEED: int = 42

# -----------------------------------------------------------------------------
# Parámetros centralizados de Diálogo en Simulación (Fase 5)
# -----------------------------------------------------------------------------
DIALOGUE_DEFAULT_MODE: str = "knowledge"
DIALOGUE_DEFAULT_STYLE: str = "debate"
DIALOGUE_MAX_ROUNDS: int = 4  # 4 rondas (iteraciones) = 8 turnos (4 de Josep y 4 de Paco) con réplicas y cierre
DIALOGUE_TIMEOUT_SECONDS: float = 240.0  # Tiempo suficiente para procesar 8 turnos de debate completo
DIALOGUE_POST_COOLDOWN: float = 25.0
DIALOGUE_SOCIAL_TRIGGER_DISTANCE: float = 85.0
DIALOGUE_BUBBLE_MAX_WIDTH: int = 220
DIALOGUE_BUBBLE_HOLD_SECONDS: float = 6.0
DEBATE_FINISHED_HOLD_SECONDS: float = 4.0
MANOLO_QUESTION_HOLD_SECONDS: float = 3.5

# -----------------------------------------------------------------------------
# Parámetros centralizados de Audio y Gemini TTS (Fase 6)
# -----------------------------------------------------------------------------
