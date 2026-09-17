"""Generación y cacheo de sprites en Pixel Art procedural.

Crea los avatares retro con cuadrícula de píxeles nativa escalada con vecino más cercano:
- Josep (FC Barcelona) y Paco (Real Madrid) con ambos brazos bien definidos en todas las direcciones.
- Bartender (Manolo) agitando su coctelera en la barra.
- Señora de la limpieza (Doña Carmen) barriendo con su fregona y cubo de agua.
- Señor mayor (Don Antonio) sentado en una esquina tosiendo con bocadillo animado.
"""

from typing import Dict, Optional, Tuple

import pygame

from src.simulation.config import (
    COLOR_BARTENDER_BOWTIE,
    COLOR_BARTENDER_SHAKER,
    COLOR_BARTENDER_SHAKER_HIGHLIGHT,
    COLOR_BARTENDER_SHIRT,
    COLOR_BARTENDER_VEST,
    COLOR_CLEANER_APRON,
    COLOR_CLEANER_BANDANA,
    COLOR_CLEANER_BUCKET,
    COLOR_CLEANER_DRESS,
    COLOR_CLEANER_MOP_HEAD,
    COLOR_CLEANER_MOP_WOOD,
    COLOR_CLEANER_WATER,
    COLOR_COUGH_PUFF,
    COLOR_COUGH_TEXT,
    COLOR_JOSEP_BOOTS,
    COLOR_JOSEP_HAIR,
    COLOR_JOSEP_JERSEY_BLUE,
    COLOR_JOSEP_JERSEY_RED,
    COLOR_JOSEP_PANTS,
    COLOR_JOSEP_SKIN,
    COLOR_JOSEP_SKIN_SHADOW,
    COLOR_JOSEP_TAG,
    COLOR_OLDMAN_CAP,
    COLOR_OLDMAN_COAT,
    COLOR_OLDMAN_HAIR,
    COLOR_OLDMAN_PANTS,
    COLOR_OLDMAN_SCARF,
    COLOR_PACO_BOOTS,
    COLOR_PACO_HAIR,
    COLOR_PACO_JERSEY_GOLD,
    COLOR_PACO_JERSEY_PURPLE,
    COLOR_PACO_JERSEY_SHADOW,
    COLOR_PACO_JERSEY_WHITE,
    COLOR_PACO_PANTS,
    COLOR_PACO_SKIN,
    COLOR_PACO_SKIN_SHADOW,
    COLOR_PACO_TAG,
    COLOR_SHADOW_SOFT,
)

# Dimensiones base del sprite nativo pixel art (16x26) y escalado x2 (32x52)
NATIVE_SPRITE_WIDTH: int = 16
NATIVE_SPRITE_HEIGHT: int = 26
PIXEL_SCALE: int = 2
SCALED_SPRITE_WIDTH: int = NATIVE_SPRITE_WIDTH * PIXEL_SCALE  # 32
SCALED_SPRITE_HEIGHT: int = NATIVE_SPRITE_HEIGHT * PIXEL_SCALE  # 52

# Cache en memoria de superficies de sprites para no recrearlas en cada frame
_SPRITE_CACHE: Dict[Tuple[str, str, int], pygame.Surface] = {}
_NPC_CACHE: Dict[str, pygame.Surface] = {}


# =============================================================================
# 1. SPRITES DE AGENTES PRINCIPALES (Josep y Paco)
# =============================================================================

def get_agent_sprite(
    team: str,
    facing: str,
    frame: int = 0,
    is_walking: bool = False,
    is_sitting: bool = False,
    is_drinking: bool = False,
    drink_frame: int = 0,
) -> pygame.Surface:
    """Retorna la superficie pixel art cacheada para el agente, dirección, frame y estados."""
    key = (team, facing, frame, is_walking, is_sitting, is_drinking, drink_frame)
    if key not in _SPRITE_CACHE:
        _SPRITE_CACHE[key] = _generate_procedural_agent_sprite(
            team,
            facing,
            frame,
            is_walking=is_walking,
            is_sitting=is_sitting,
            is_drinking=is_drinking,
            drink_frame=drink_frame,
        )
    return _SPRITE_CACHE[key]


def _generate_procedural_agent_sprite(
    team: str,
    facing: str,
    frame: int,
    is_walking: bool = False,
    is_sitting: bool = False,
    is_drinking: bool = False,
    drink_frame: int = 0,
) -> pygame.Surface:
    """Construye un sprite con anatomía completa y soporte de ciclo de marcha, sentado y bebiendo."""
    raw = pygame.Surface((NATIVE_SPRITE_WIDTH, NATIVE_SPRITE_HEIGHT), pygame.SRCALPHA)
    is_barca = team == "barcelona"

    skin = COLOR_JOSEP_SKIN if is_barca else COLOR_PACO_SKIN
    skin_shadow = COLOR_JOSEP_SKIN_SHADOW if is_barca else COLOR_PACO_SKIN_SHADOW
    hair = COLOR_JOSEP_HAIR if is_barca else COLOR_PACO_HAIR
    pants = COLOR_JOSEP_PANTS if is_barca else COLOR_PACO_PANTS
    boots = COLOR_JOSEP_BOOTS if is_barca else COLOR_PACO_BOOTS

    step_f = frame % 2

    if is_sitting:
        # En postura sentada: el torso y cabeza bajan 3 px hacia el asiento
        by = 3
        leg_offset_1 = 0
        leg_offset_2 = 0
    elif is_walking:
        # En marcha: bobbing de 1 px al pisar el suelo
        by = 1 if step_f == 1 else 0
        leg_offset_1 = -1 if step_f == 0 else 1
        leg_offset_2 = 1 if step_f == 0 else -1
    else:
        # En reposo (IDLE): respiración sutil
        by = 1 if step_f == 1 else 0
        leg_offset_1 = 0
        leg_offset_2 = 0

    # Inclinación de cabeza hacia atrás si está tomando un trago
    head_tilt = -1 if (is_drinking and drink_frame % 2 == 1) else 0

    # 1. PIES Y ZAPATOS
    if is_sitting:
        if facing == "left":
            # Botas reposando al frente izquierdo
            raw.fill(boots, (0, 21 + by, 4, 2))
            raw.fill((180, 180, 190), (1, 21 + by, 2, 1))
        elif facing == "right":
            # Botas reposando al frente derecho
            raw.fill(boots, (12, 21 + by, 4, 2))
            raw.fill((180, 180, 190), (13, 21 + by, 2, 1))
        else:
            # De frente o espalda: ambos pies apoyados
            raw.fill(boots, (2, 21 + by, 4, 2))
            raw.fill(boots, (10, 21 + by, 4, 2))
            raw.fill((180, 180, 190), (3, 21 + by, 2, 1))
            raw.fill((180, 180, 190), (11, 21 + by, 2, 1))
    elif is_walking and facing in ("left", "right"):
        raw.fill(boots, (4 + leg_offset_1, 23, 3, 3))
        raw.fill(boots, (9 + leg_offset_2, 23, 3, 3))
        raw.fill((180, 180, 190), (5 + leg_offset_1, 23, 1, 1))
        raw.fill((180, 180, 190), (10 + leg_offset_2, 23, 1, 1))
    elif is_walking:
        lift_1 = 1 if step_f == 0 else 0
        lift_2 = 1 if step_f == 1 else 0
        raw.fill(boots, (4, 23 - lift_1, 3, 3))
        raw.fill(boots, (9, 23 - lift_2, 3, 3))
        raw.fill((180, 180, 190), (5, 23 - lift_1, 1, 1))
        raw.fill((180, 180, 190), (10, 23 - lift_2, 1, 1))
    else:
        raw.fill(boots, (4, 23, 3, 3))
        raw.fill(boots, (9, 23, 3, 3))
        raw.fill((180, 180, 190), (5, 23, 1, 1))
        raw.fill((180, 180, 190), (10, 23, 1, 1))

    # 2. PIERNAS Y PANTALONES
    if is_sitting:
        if facing == "left":
            # Muslos horizontales proyectados hacia la barra / mesa (izquierda)
            raw.fill(pants, (1, 15 + by, 9, 3))
            # Pantorrillas bajando verticalmente
            raw.fill(pants, (1, 18 + by, 3, 3))
            raw.fill((18, 16, 22), (8, 15 + by, 2, 3))
        elif facing == "right":
            # Muslos horizontales proyectados hacia la derecha
            raw.fill(pants, (6, 15 + by, 9, 3))
            # Pantorrillas bajando verticalmente
            raw.fill(pants, (12, 18 + by, 3, 3))
            raw.fill((18, 16, 22), (6, 15 + by, 2, 3))
        else:
            # Sentado de frente o espalda: muslos extendidos y rodillas dobladas
            raw.fill(pants, (2, 15 + by, 12, 3))
            raw.fill(pants, (3, 18 + by, 3, 3))
            raw.fill(pants, (10, 18 + by, 3, 3))
            raw.fill((18, 16, 22), (7, 16 + by, 2, 2))
    elif is_walking and facing in ("left", "right"):
        raw.fill(pants, (4 + leg_offset_1, 17 + by, 3, 6 - by))
        raw.fill(pants, (9 + leg_offset_2, 17 + by, 3, 6 - by))
        raw.fill((18, 16, 22), (7, 18 + by, 2, 2))
    elif is_walking:
        raw.fill(pants, (4, 17 + by - lift_1, 3, 6 - by))
        raw.fill(pants, (9, 17 + by - lift_2, 3, 6 - by))
        raw.fill((18, 16, 22), (7, 18 + by, 2, 2))
    else:
        raw.fill(pants, (4, 17 + by, 3, 6 - by))
        raw.fill(pants, (9, 17 + by, 3, 6 - by))
        raw.fill((18, 16, 22), (7, 18 + by, 2, 2))


    # 3. TORSO / EQUIPACIÓN DEPORTIVA (Y: 9 a 16)
    if is_barca:
        raw.fill(COLOR_JOSEP_JERSEY_BLUE, (4, 9 + by, 8, 8))
        raw.fill(COLOR_JOSEP_JERSEY_RED, (5, 9 + by, 2, 8))
        raw.fill(COLOR_JOSEP_JERSEY_RED, (9, 9 + by, 2, 8))
        raw.fill((235, 205, 50), (5, 11 + by, 1, 1))  # Escudo
    else:
        raw.fill(COLOR_PACO_JERSEY_WHITE, (4, 9 + by, 8, 8))
        raw.fill(COLOR_PACO_JERSEY_SHADOW, (4, 15 + by, 8, 2))
        raw.fill(COLOR_PACO_JERSEY_GOLD, (4, 12 + by, 8, 1))
        raw.fill(COLOR_PACO_JERSEY_PURPLE, (7, 9 + by, 2, 1))
        raw.fill(COLOR_PACO_JERSEY_GOLD, (5, 11 + by, 1, 2))

    raw.fill((30, 26, 22), (4, 16 + by, 8, 1))

    # 4. AMBOS BRAZOS Y MANOS (Con soporte de tomar bebida)
    arm_col = COLOR_JOSEP_JERSEY_BLUE if is_barca else COLOR_PACO_JERSEY_WHITE
    arm_shadow = (0, 48, 105) if is_barca else (195, 198, 205)
    arm_swing = (1 if step_f == 0 else -1) if is_walking else 0

    if is_drinking:
        # Colores de la jarra de bebida
        glass_col = (200, 220, 245)
        beer_col = (235, 165, 30)
        foam_col = (255, 255, 250)

        mug_y = 10 + by + head_tilt
        if facing == "left":
            # Brazo izquierdo levantado con la jarra
            raw.fill(arm_col, (2, 10 + by, 3, 4))
            raw.fill(skin, (2, 9 + by + head_tilt, 2, 2))
            # Jarra con cerveza y espuma
            raw.fill(glass_col, (0, mug_y, 4, 5))
            raw.fill(beer_col, (1, mug_y + 1, 2, 3))
            raw.fill(foam_col, (0, mug_y, 4, 1))
            # Brazo derecho descansando
            raw.fill(arm_shadow, (11, 11 + by, 2, 5))
            raw.fill(skin_shadow, (11, 16 + by, 2, 2))
        elif facing == "right":
            # Brazo izquierdo posterior
            raw.fill(arm_shadow, (3, 11 + by, 2, 5))
            raw.fill(skin_shadow, (3, 16 + by, 2, 2))
            # Brazo derecho levantado con la jarra
            raw.fill(arm_col, (11, 10 + by, 3, 4))
            raw.fill(skin, (12, 9 + by + head_tilt, 2, 2))
            # Jarra con cerveza y espuma
            raw.fill(glass_col, (12, mug_y, 4, 5))
            raw.fill(beer_col, (13, mug_y + 1, 2, 3))
            raw.fill(foam_col, (12, mug_y, 4, 1))
        else:
            # De frente: sostiene la jarra al pecho / boca
            raw.fill(arm_col, (2, 10 + by, 3, 4))
            raw.fill(skin, (4, mug_y + 2, 2, 2))
            raw.fill(arm_col, (11, 10 + by, 3, 4))
            raw.fill(skin, (10, mug_y + 2, 2, 2))
            raw.fill(glass_col, (6, mug_y, 4, 5))
            raw.fill(beer_col, (7, mug_y + 1, 2, 3))
            raw.fill(foam_col, (6, mug_y, 4, 1))
    else:
        if facing == "left":
            raw.fill(arm_col, (2 + arm_swing, 10 + by, 3, 5))
            raw.fill(skin, (2 + arm_swing, 15 + by, 2, 2))
            raw.fill(arm_shadow, (11 - arm_swing, 9 + by, 2, 5))
            raw.fill(skin_shadow, (11 - arm_swing, 14 + by, 2, 2))
        elif facing == "right":
            raw.fill(arm_shadow, (3 - arm_swing, 9 + by, 2, 5))
            raw.fill(skin_shadow, (3 - arm_swing, 14 + by, 2, 2))
            raw.fill(arm_col, (11 + arm_swing, 10 + by, 3, 5))
            raw.fill(skin, (12 + arm_swing, 15 + by, 2, 2))
        else:
            raw.fill(arm_col, (2, 10 + by + arm_swing, 2, 5))
            raw.fill(skin, (2, 15 + by + arm_swing, 2, 2))
            raw.fill(arm_col, (12, 10 + by - arm_swing, 2, 5))
            raw.fill(skin, (12, 15 + by - arm_swing, 2, 2))

    # 5. CUELLO Y CABEZA (Y: 2 a 8)
    head_y = 2 + by + head_tilt
    raw.fill(skin_shadow, (7, 8 + by + head_tilt, 2, 1))
    raw.fill(skin, (4, head_y, 8, 6))

    # Pelo con volumen
    raw.fill(hair, (4, head_y - 1, 8, 3))
    if facing == "left":
        raw.fill(hair, (9, head_y, 3, 5))
        raw.fill(hair, (3, head_y, 2, 2))
    elif facing == "right":
        raw.fill(hair, (4, head_y, 3, 5))
        raw.fill(hair, (11, head_y, 2, 2))
    else:
        raw.fill(hair, (3, head_y, 2, 3))
        raw.fill(hair, (11, head_y, 2, 3))

    # Rasgos faciales
    eye_col = (24, 20, 22)
    if is_drinking and head_tilt != 0:
        # Ojos cerrados disfrutando del trago
        if facing == "left":
            raw.fill(eye_col, (5, head_y + 3, 2, 1))
        elif facing == "right":
            raw.fill(eye_col, (9, head_y + 3, 2, 1))
        else:
            raw.fill(eye_col, (5, head_y + 3, 2, 1))
            raw.fill(eye_col, (9, head_y + 3, 2, 1))
    else:
        if facing == "left":
            raw.fill(eye_col, (5, head_y + 3, 1, 1))
            raw.fill(skin_shadow, (4, head_y + 4, 1, 1))
        elif facing == "right":
            raw.fill(eye_col, (10, head_y + 3, 1, 1))
            raw.fill(skin_shadow, (11, head_y + 4, 1, 1))
        else:
            raw.fill(eye_col, (6, head_y + 3, 1, 1))
            raw.fill(eye_col, (9, head_y + 3, 1, 1))
            raw.fill(hair, (5, head_y + 2, 2, 1))
            raw.fill(hair, (9, head_y + 2, 2, 1))
            raw.fill((150, 80, 80), (7, head_y + 5, 2, 1))

    return pygame.transform.scale(raw, (SCALED_SPRITE_WIDTH, SCALED_SPRITE_HEIGHT))


# =============================================================================
# 2. BARTENDER (Manolo) PREPARANDO CÓCTELES EN LA BARRA
# =============================================================================

def get_bartender_sprite(shake_frame: int = 0, action: str = "shake") -> pygame.Surface:
    """Genera al camarero en sus distintas acciones (agitar cóctel, limpiar barra, servir trago)."""
    key = f"bartender_{shake_frame}_{action}"
    if key in _NPC_CACHE:
        return _NPC_CACHE[key]

    raw = pygame.Surface((NATIVE_SPRITE_WIDTH, NATIVE_SPRITE_HEIGHT), pygame.SRCALPHA)
    skin = (242, 196, 160)
    hair = (40, 32, 24)

    step_f = shake_frame % 2

    # 1. Zapatos y pantalones
    raw.fill((20, 20, 24), (4, 23, 3, 3))
    raw.fill((20, 20, 24), (9, 23, 3, 3))
    raw.fill((30, 30, 38), (4, 17, 3, 6))
    raw.fill((30, 30, 38), (9, 17, 3, 6))

    # 2. Camisa blanca con chaleco negro y pajarita roja
    raw.fill(COLOR_BARTENDER_SHIRT, (4, 9, 8, 8))
    raw.fill(COLOR_BARTENDER_VEST, (4, 10, 2, 7))
    raw.fill(COLOR_BARTENDER_VEST, (10, 10, 2, 7))
    raw.fill(COLOR_BARTENDER_BOWTIE, (7, 9, 2, 1))

    # 3. Cabeza con bigote de barman clásico
    raw.fill(skin, (4, 2, 8, 6))
    raw.fill(hair, (3, 1, 10, 3))
    raw.fill((20, 20, 20), (6, 5, 1, 1))
    raw.fill((20, 20, 20), (9, 5, 1, 1))
    raw.fill(hair, (6, 7, 4, 1))  # Bigote elegante

    if action == "wipe":
        # Limpiando la barra con un paño blanco
        wipe_x = 9 + (2 if step_f == 1 else -2)
        raw.fill(COLOR_BARTENDER_SHIRT, (2, 10, 3, 4))
        raw.fill(skin, (2, 14, 2, 2))
        raw.fill(COLOR_BARTENDER_SHIRT, (11, 10, 3, 4))
        raw.fill(skin, (wipe_x, 14, 2, 2))
        # Paño blanco de barra
        raw.fill((240, 240, 245), (wipe_x - 1, 15, 4, 3))
        raw.fill((200, 200, 210), (wipe_x, 16, 2, 2))
    elif action == "serve":
        # Brazo derecho extendido hacia el mostrador sirviendo una copa
        raw.fill(COLOR_BARTENDER_SHIRT, (2, 10, 3, 4))
        raw.fill(skin, (2, 14, 2, 2))
        raw.fill(COLOR_BARTENDER_SHIRT, (11, 10, 4, 3))
        raw.fill(skin, (13, 12, 3, 2))
        # Jarra de cristal sostenida
        raw.fill((210, 230, 250), (13, 13, 3, 5))
        raw.fill((240, 175, 40), (13, 14, 2, 3))
        raw.fill((255, 255, 250), (13, 13, 3, 1))
    else:
        # Acción "shake": agitando la coctelera de metal
        shaker_offset = -2 if step_f == 0 else 2
        raw.fill(COLOR_BARTENDER_SHIRT, (2, 10, 3, 3))
        raw.fill(skin, (4, 11 + shaker_offset, 2, 2))
        raw.fill(COLOR_BARTENDER_SHIRT, (11, 10, 3, 3))
        raw.fill(skin, (10, 11 + shaker_offset, 2, 2))

        # Coctelera plateada metálica
        shaker_y = 10 + shaker_offset
        raw.fill(COLOR_BARTENDER_SHAKER, (6, shaker_y, 4, 6))
        raw.fill((180, 185, 195), (7, shaker_y - 2, 2, 2))
        raw.fill(COLOR_BARTENDER_SHAKER_HIGHLIGHT, (6, shaker_y + 1, 1, 4))

    scaled = pygame.transform.scale(raw, (SCALED_SPRITE_WIDTH, SCALED_SPRITE_HEIGHT))
    _NPC_CACHE[key] = scaled
    return scaled


def get_counter_drink_sprite(level: float = 1.0) -> pygame.Surface:
    """Genera una copa o jarra de cerveza espumosa para colocar sobre el mostrador de la barra."""
    level_key = max(0, min(10, int(level * 10)))
    key = f"counter_drink_{level_key}"
    if key in _NPC_CACHE:
        return _NPC_CACHE[key]

    raw = pygame.Surface((12, 16), pygame.SRCALPHA)
    # Jarra de cristal
    raw.fill((210, 230, 250, 170), (2, 4, 8, 11))
    raw.fill((255, 255, 255, 220), (2, 4, 1, 10))  # Brillo

    # Cerveza ámbar según nivel
    liquid_h = int(8 * max(0.1, min(1.0, level)))
    liquid_y = 14 - liquid_h
    raw.fill((225, 165, 35), (3, liquid_y, 6, liquid_h))
    raw.fill((245, 195, 65), (4, liquid_y + 1, 2, max(1, liquid_h - 2)))

    # Corona de espuma blanca
    if level > 0.2:
        raw.fill((255, 255, 245), (2, liquid_y - 2, 8, 3))
        raw.fill((255, 255, 255), (3, liquid_y - 3, 6, 2))

    # Asa de cristal
    raw.fill((190, 215, 240, 180), (0, 6, 2, 6))
    raw.fill((0, 0, 0, 0), (1, 8, 1, 2))
    # Base pesada
    raw.fill((180, 205, 235, 220), (2, 14, 8, 2))

    scaled = pygame.transform.scale(raw, (24, 32))
    _NPC_CACHE[key] = scaled
    return scaled


# =============================================================================
# 3. SEÑORA DE LA LIMPIEZA (Doña Carmen) CON FREGONA Y CUBO
# =============================================================================

def get_cleaner_sprite(mop_frame: int = 0, is_walking: bool = False) -> pygame.Surface:
    """Genera a la señora de la limpieza con delantal, moño y fregona (en marcha o barriendo)."""
    key = f"cleaner_{mop_frame}_{is_walking}"
    if key in _NPC_CACHE:
        return _NPC_CACHE[key]

    raw = pygame.Surface((NATIVE_SPRITE_WIDTH, NATIVE_SPRITE_HEIGHT), pygame.SRCALPHA)
    skin = (244, 200, 168)
    hair = (90, 85, 80)

    step_f = mop_frame % 2

    # 1. Zapatillas cómodas y falda/vestido con delantal blanco
    if is_walking:
        leg_offset_1 = -1 if step_f == 0 else 1
        leg_offset_2 = 1 if step_f == 0 else -1
        raw.fill((50, 45, 40), (4 + leg_offset_1, 23, 3, 3))
        raw.fill((50, 45, 40), (9 + leg_offset_2, 23, 3, 3))
    else:
        raw.fill((50, 45, 40), (4, 23, 3, 3))
        raw.fill((50, 45, 40), (9, 23, 3, 3))

    raw.fill(COLOR_CLEANER_DRESS, (3, 15, 10, 8))
    # Delantal blanco
    raw.fill(COLOR_CLEANER_APRON, (5, 11, 6, 11))
    raw.fill(COLOR_CLEANER_DRESS, (4, 9, 8, 3))

    # 2. Cabeza con pañuelo rosa y moño alto
    raw.fill(skin, (4, 2, 8, 6))
    raw.fill(hair, (4, 1, 8, 2))
    raw.fill(hair, (6, 0, 4, 2))  # Moño alto
    raw.fill(COLOR_CLEANER_BANDANA, (4, 2, 8, 2))
    raw.fill((20, 20, 20), (6, 5, 1, 1))
    raw.fill((20, 20, 20), (9, 5, 1, 1))

    # 3. Brazos sujetando el palo de la fregona
    mop_x_offset = -2 if step_f == 0 else 2
    raw.fill(COLOR_CLEANER_DRESS, (2, 10, 2, 3))
    raw.fill(skin, (3, 13, 2, 2))
    raw.fill(COLOR_CLEANER_DRESS, (12, 10, 2, 3))
    raw.fill(skin, (11, 13, 2, 2))

    # Palo de madera de la fregona
    palo_x = 7 + mop_x_offset
    pygame.draw.line(raw, COLOR_CLEANER_MOP_WOOD, (palo_x - 1, 11), (palo_x - 3, 24), 1)
    raw.fill(COLOR_CLEANER_MOP_HEAD, (palo_x - 5, 23, 5, 3))
    raw.fill((190, 190, 180), (palo_x - 4, 22, 3, 1))

    scaled = pygame.transform.scale(raw, (SCALED_SPRITE_WIDTH, SCALED_SPRITE_HEIGHT))
    _NPC_CACHE[key] = scaled
    return scaled


def get_cleaner_bucket_sprite() -> pygame.Surface:
    """Genera el cubo de fregar amarillo con agua azul para situar junto a la señora."""
    if "bucket" in _NPC_CACHE:
        return _NPC_CACHE["bucket"]

    raw = pygame.Surface((12, 12), pygame.SRCALPHA)
    raw.fill(COLOR_CLEANER_BUCKET, (2, 4, 8, 8))
    raw.fill((180, 140, 30), (1, 3, 10, 2))
    raw.fill(COLOR_CLEANER_WATER, (3, 4, 6, 2))
    raw.fill((120, 120, 130), (5, 1, 2, 3))
    scaled = pygame.transform.scale(raw, (24, 24))
    _NPC_CACHE["bucket"] = scaled
    return scaled


# =============================================================================
# 4. SEÑOR EN LA ESQUINA TOSIENDO (Don Antonio)
# =============================================================================

def get_old_man_sprite(is_coughing: bool = False, is_standing: bool = False) -> pygame.Surface:
    """Genera al señor mayor sentado o de pie paseando en su rincón, con boina y abrigo."""
    key = f"oldman_{is_coughing}_{is_standing}"
    if key in _NPC_CACHE:
        return _NPC_CACHE[key]

    raw = pygame.Surface((NATIVE_SPRITE_WIDTH, NATIVE_SPRITE_HEIGHT), pygame.SRCALPHA)
    skin = (235, 190, 155)

    # 1. Zapatos marrones y pantalones de pana
    raw.fill((45, 30, 20), (4, 23, 3, 3))
    raw.fill((45, 30, 20), (9, 23, 3, 3))
    raw.fill(COLOR_OLDMAN_PANTS, (4, 17, 3, 6))
    raw.fill(COLOR_OLDMAN_PANTS, (9, 17, 3, 6))

    lean_y = 2 if is_coughing else 0

    # 2. Abrigo de lana marrón con bufanda roja
    raw.fill(COLOR_OLDMAN_COAT, (3, 9 + lean_y, 10, 9 - lean_y))
    raw.fill(COLOR_OLDMAN_SCARF, (6, 8 + lean_y, 4, 3))

    # 3. Cabeza, pelo blanco y boina tradicional
    raw.fill(skin, (4, 2 + lean_y, 8, 6))
    raw.fill(COLOR_OLDMAN_HAIR, (3, 4 + lean_y, 2, 4))
    raw.fill(COLOR_OLDMAN_HAIR, (11, 4 + lean_y, 2, 4))
    raw.fill(COLOR_OLDMAN_CAP, (3, 1 + lean_y, 10, 3))
    raw.fill((40, 36, 32), (2, 3 + lean_y, 4, 1))

    if is_coughing:
        # Ojos cerrados apretados por toser y mano en la boca
        raw.fill((30, 20, 20), (6, 5 + lean_y, 2, 1))
        raw.fill((30, 20, 20), (9, 5 + lean_y, 2, 1))
        raw.fill(COLOR_OLDMAN_COAT, (11, 10 + lean_y, 3, 3))
        raw.fill(skin, (7, 6 + lean_y, 4, 3))
    elif is_standing:
        # De pie estirando las piernas: bastón de paseo en la mano derecha
        raw.fill((30, 20, 20), (6, 5, 1, 1))
        raw.fill((30, 20, 20), (9, 5, 1, 1))
        raw.fill(COLOR_OLDMAN_COAT, (2, 10, 2, 5))
        raw.fill(skin, (2, 15, 2, 2))
        raw.fill(COLOR_OLDMAN_COAT, (12, 10, 2, 4))
        raw.fill(skin, (12, 14, 2, 2))
        # Bastón de madera
        raw.fill((110, 65, 30), (13, 14, 1, 10))
        raw.fill((110, 65, 30), (12, 13, 2, 1))
    else:
        # Sentado descansando
        raw.fill((30, 20, 20), (6, 5, 1, 1))
        raw.fill((30, 20, 20), (9, 5, 1, 1))
        raw.fill(COLOR_OLDMAN_COAT, (2, 10, 2, 5))
        raw.fill(skin, (2, 15, 2, 2))
        raw.fill(COLOR_OLDMAN_COAT, (12, 10, 2, 5))
        raw.fill(skin, (12, 15, 2, 2))

    scaled = pygame.transform.scale(raw, (SCALED_SPRITE_WIDTH, SCALED_SPRITE_HEIGHT))
    _NPC_CACHE[key] = scaled
    return scaled


# =============================================================================
# 5. DETALLES Y ELEMENTOS DE SOPORTE
# =============================================================================

def render_contact_shadow(surface: pygame.Surface, screen_x: float, screen_y: float) -> None:
    """Dibuja una sombra elíptica suave bajo los pies del personaje sobre el plano del suelo."""
    shadow_w = 26
    shadow_h = 10
    shadow_surf = pygame.Surface((shadow_w, shadow_h), pygame.SRCALPHA)
    pygame.draw.ellipse(
        shadow_surf,
        (COLOR_SHADOW_SOFT[0], COLOR_SHADOW_SOFT[1], COLOR_SHADOW_SOFT[2], 110),
        (0, 0, shadow_w, shadow_h),
    )
    surface.blit(shadow_surf, (screen_x - shadow_w // 2, screen_y - shadow_h // 2))


def render_agent_name_tag(
    surface: pygame.Surface,
    screen_x: float,
    screen_y: float,
    name: str,
    team: str,
    font: pygame.font.Font,
) -> None:
    """Dibuja un badge retro con el nombre del personaje sobre su cabeza."""
    is_barca = team == "barcelona"
    is_madrid = team == "real_madrid"

    if is_barca:
        tag_color = COLOR_JOSEP_TAG
        tag_text = f"{name} [Culé]"
        border_col = (0, 77, 152)
    elif is_madrid:
        tag_color = COLOR_PACO_TAG
        tag_text = f"{name} [Madridista]"
        border_col = (190, 160, 45)
    else:
        tag_color = (230, 230, 230)
        tag_text = name
        border_col = (120, 100, 80)

    text_surf = font.render(tag_text, True, tag_color)
    box_rect = text_surf.get_rect(center=(int(screen_x), int(screen_y)))

    bg_surf = pygame.Surface((box_rect.width + 6, box_rect.height + 2), pygame.SRCALPHA)
    bg_surf.fill((16, 12, 10, 210))
    pygame.draw.rect(bg_surf, border_col, bg_surf.get_rect(), width=1, border_radius=2)

    surface.blit(bg_surf, (box_rect.x - 3, box_rect.y - 1))
    surface.blit(text_surf, box_rect)


def clamp_bubble_rect(
    bubble_w: int,
    bubble_h: int,
    anchor_x: float,
    anchor_y: float,
    viewport_bounds: pygame.Rect,
    min_top_margin: int = 36,
) -> Tuple[pygame.Rect, str]:
    """Calcula la posición de un bocadillo asegurando su confinamiento estricto en el viewport.

    Si el bocadillo supera el margen superior (bubble_y < viewport_bounds.top + min_top_margin),
    invierte su posición vertical dibujándolo debajo del personaje con
    el rabillo apuntando hacia arriba.

    Retorna:
        (rect_ajustado, orientacion_rabillo: 'bottom' | 'top')
    """
    bx = int(anchor_x - bubble_w // 2)
    by = int(anchor_y - bubble_h - 18)
    tail_dir = "bottom"

    # Si se desborda por arriba, voltear hacia abajo de los pies
    if by < viewport_bounds.top + min_top_margin:
        by = int(anchor_y + 24)
        tail_dir = "top"

    # Sujeción horizontal dentro del viewport del bar
    if bx < viewport_bounds.left + 10:
        bx = viewport_bounds.left + 10
    elif bx + bubble_w > viewport_bounds.right - 10:
        bx = viewport_bounds.right - 10 - bubble_w

    # Sujeción vertical inferior y superior de seguridad
    if by + bubble_h > viewport_bounds.bottom - 10:
        by = viewport_bounds.bottom - 10 - bubble_h
    if by < viewport_bounds.top + 10:
        by = viewport_bounds.top + 10

    return pygame.Rect(bx, by, bubble_w, bubble_h), tail_dir


def render_dialogue_bubble(
    surface: pygame.Surface,
    screen_x: float,
    screen_y: float,
    speaker_name: str,
    text: str,
    font: pygame.font.Font,
    accent_color: Tuple[int, int, int] = (40, 80, 140),
    max_width: int = 180,
    viewport_bounds: Optional[pygame.Rect] = None,
    max_lines: int = 3,
) -> None:
    """Renderiza un bocadillo de diálogo retro estilo viñeta de cómic con rabillo apuntador y confinamiento."""
    # Dividir texto por palabras para ajuste de ancho
    words = text.split(" ")
    all_lines = []
    curr_line = ""
    for w in words:
        test_line = (curr_line + " " + w).strip()
        if font.size(test_line)[0] <= max_width:
            curr_line = test_line
        else:
            if curr_line:
                all_lines.append(curr_line)
            curr_line = w
    if curr_line:
        all_lines.append(curr_line)

    is_truncated = len(all_lines) > max_lines
    if is_truncated:
        lines = all_lines[-max_lines:]
        if lines and not lines[-1].endswith("..."):
            lines[-1] = lines[-1] + "..."
    else:
        lines = all_lines

    line_height = font.get_linesize()
    text_width = max(font.size(l)[0] for l in lines) if lines else 40
    bubble_w = max(text_width + 16, font.size(speaker_name)[0] + 20)
    bubble_h = len(lines) * line_height + 18

    bounds = viewport_bounds or pygame.Rect(0, 0, 960, 640)
    bubble_rect, tail_dir = clamp_bubble_rect(
        bubble_w, bubble_h, screen_x, screen_y, bounds, min_top_margin=36
    )

    # Sombra del bocadillo
    shadow_surf = pygame.Surface((bubble_rect.width + 4, bubble_rect.height + 4), pygame.SRCALPHA)
    pygame.draw.rect(
        shadow_surf, (0, 0, 0, 70), (0, 0, bubble_rect.width + 4, bubble_rect.height + 4), border_radius=6
    )
    surface.blit(shadow_surf, (bubble_rect.x + 2, bubble_rect.y + 2))

    # Cuerpo del bocadillo (blanco cálido cómic)
    pygame.draw.rect(surface, (255, 252, 242), bubble_rect, border_radius=6)
    pygame.draw.rect(surface, (45, 38, 30), bubble_rect, width=2, border_radius=6)

    # Rabillo del bocadillo según dirección (apuntando al personaje)
    tail_x = int(screen_x)
    tail_x = max(bubble_rect.left + 12, min(tail_x, bubble_rect.right - 12))

    if tail_dir == "bottom":
        tail_y = bubble_rect.bottom
        tail_pts = [(tail_x - 6, tail_y - 1), (tail_x + 6, tail_y - 1), (tail_x, tail_y + 8)]
        pygame.draw.polygon(surface, (255, 252, 242), tail_pts)
        pygame.draw.line(surface, (45, 38, 30), (tail_x - 6, tail_y - 1), (tail_x, tail_y + 8), 2)
        pygame.draw.line(surface, (45, 38, 30), (tail_x + 6, tail_y - 1), (tail_x, tail_y + 8), 2)
    else:
        tail_y = bubble_rect.top
        tail_pts = [(tail_x - 6, tail_y + 1), (tail_x + 6, tail_y + 1), (tail_x, tail_y - 8)]
        pygame.draw.polygon(surface, (255, 252, 242), tail_pts)
        pygame.draw.line(surface, (45, 38, 30), (tail_x - 6, tail_y + 1), (tail_x, tail_y - 8), 2)
        pygame.draw.line(surface, (45, 38, 30), (tail_x + 6, tail_y + 1), (tail_x, tail_y - 8), 2)

    # Badge pequeño con el nombre del personaje
    badge_surf = font.render(speaker_name, True, accent_color)
    surface.blit(badge_surf, (bubble_rect.x + 8, bubble_rect.y + 3))

    # Texto en el cuerpo
    for idx, line in enumerate(lines):
        txt_surf = font.render(line, True, (24, 20, 18))
        surface.blit(txt_surf, (bubble_rect.x + 8, bubble_rect.y + 16 + idx * line_height))


def render_cough_comic_puff(
    surface: pygame.Surface, screen_x: float, screen_y: float, font: pygame.font.Font
) -> None:
    """Renderiza el bocadillo animado de tos '*cof! cof!*' con nubecilla cómic."""
    puff_text = "*cof! cof!*"
    text_surf = font.render(puff_text, True, COLOR_COUGH_TEXT)
    px = int(screen_x + 12)
    py = int(screen_y - 36)

    # Nubecilla de tos
    pygame.draw.circle(surface, COLOR_COUGH_PUFF, (px + 14, py + 8), 12)
    pygame.draw.circle(surface, COLOR_COUGH_PUFF, (px + 28, py + 8), 14)
    pygame.draw.circle(surface, COLOR_COUGH_PUFF, (px + 42, py + 8), 12)
    pygame.draw.circle(surface, (180, 180, 190), (px + 6, py + 14), 4, 1)

    surface.blit(text_surf, (px + 6, py + 2))

