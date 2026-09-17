"""Motor de renderizado 2.5D para la escena del Bar y agentes en Pygame.

Implementa:
1. Composición oblicua/2.5D con volumen, caras frontales y superiores visibles.
2. Suelo procedural con textura de tablones y variaciones de madera deterministas.
3. Mobiliario con profundidad aparente (barra de caoba, taburetes, mesas, TV, sofá).
4. Algoritmo del pintor (Painter's Algorithm) con ordenamiento por profundidad Y.
5. Cacheo de fondos estáticos para mantener 60 FPS estables sin regenerar texturas por frame.
"""

from typing import Any, List, Optional, Tuple

import pygame

from src.simulation.camera import Camera25D, default_camera
from src.simulation.config import (
    COLOR_BANNER_FCB_BLUE,
    COLOR_BANNER_FCB_RED,
    COLOR_BANNER_RMA_GOLD,
    COLOR_BANNER_RMA_WHITE,
    COLOR_BAR_BRASS_RAIL,
    COLOR_BAR_FRONT_PANEL,
    COLOR_BAR_TOP,
    COLOR_BAR_TRIM,
    COLOR_BAR_WOOD,
    COLOR_BEER_FOAM,
    COLOR_CHAIR,
    COLOR_CHAIR_BACK,
    COLOR_CHAIR_SEAT,
    COLOR_DEBUG_BLOCKED_TILE,
    COLOR_DEBUG_GOAL,
    COLOR_DEBUG_OBSTACLE,
    COLOR_DEBUG_PATH,
    COLOR_DEBUG_POI,
    COLOR_DEBUG_TEXT,
    COLOR_DEBUG_WAYPOINT,
    COLOR_FLOOR,
    COLOR_FLOOR_ALT_1,
    COLOR_FLOOR_ALT_2,
    COLOR_FLOOR_KNOT,
    COLOR_FLOOR_PLANK,
    COLOR_GLASS_BEER,
    COLOR_HUD_BG,
    COLOR_LAMP_CONE,
    COLOR_MAT_BORDER,
    COLOR_MAT_FILL,
    COLOR_PLANT_HIGHLIGHT,
    COLOR_PLANT_LEAVES,
    COLOR_PLANT_POT,
    COLOR_SHELF_BG,
    COLOR_SHELF_WOOD,
    COLOR_SOFA_BASE,
    COLOR_SOFA_CUSHION,
    COLOR_SOFA_TUFT,
    COLOR_STOOL_CUSHION,
    COLOR_STOOL_HIGHLIGHT,
    COLOR_STOOL_LEG,
    COLOR_STOOL_OUTER,
    COLOR_TABLE_LEG,
    COLOR_TABLE_RIM,
    COLOR_TABLE_SHADOW,
    COLOR_TABLE_TOP,
    COLOR_TABLE_WOOD,
    COLOR_TV_BEZEL,
    COLOR_TV_FRAME,
    COLOR_TV_SCREEN,
    COLOR_WALL_BG,
    COLOR_WALL_BORDER,
    COLOR_WALL_CROWN,
    COLOR_WALL_PAPER,
    COLOR_WALL_TOP,
    COLOR_WALL_WAINSCOT,
    COLOR_WALL_WAINSCOT_DARK,
    GRID_COLS,
    GRID_ROWS,
    LOGICAL_HEIGHT,
    LOGICAL_WIDTH,
    TILE_SIZE,
)
from src.simulation.world import BarWorld

# Cache del fondo estático (suelo, paredes y arquitectura fija)
_STATIC_BACKGROUND_SURFACE: Optional[pygame.Surface] = None


def render_scene(
    surface: pygame.Surface,
    world: BarWorld,
    font: pygame.font.Font,
    agents: Optional[List[Any]] = None,
    camera: Optional[Camera25D] = None,
) -> None:
    """Renderiza la escena completa 2.5D con ordenamiento de profundidad y agentes estáticos."""
    cam = camera or default_camera

    # 1. Fondo estático cacheado (suelo, paredes, TV en pared y arquitectura)
    bg = _get_or_create_static_background(world, font, cam)
    surface.blit(bg, (0, 0))

    # 2. Recolección de entidades renderizables ordenadas por profundidad (Y)
    render_queue: List[Tuple[float, Any, str]] = []

    # A. Taburetes de la barra
    for r in (5, 7, 9, 11, 13):
        sx = 5 * TILE_SIZE + TILE_SIZE // 2
        sy = r * TILE_SIZE + TILE_SIZE // 2
        render_queue.append((sy, (sx, sy), "stool"))

    # B. Mesas y sillas
    for t in world.tables_data:
        tc = t["col"] * TILE_SIZE
        tr = t["row"] * TILE_SIZE
        tw = t["width"]
        th = t["height"]
        # La mesa se ordena según su base inferior en el suelo
        render_queue.append((tr + th, (tc, tr, tw, th, t["name"]), "table"))

    # C. Agentes visuales (Josep y Paco)
    if agents:
        for agent in agents:
            render_queue.append((agent.depth, agent, "agent"))

    # D. Detalles de barra (barril o decoración de primer plano)
    render_queue.append((14 * TILE_SIZE, (1 * TILE_SIZE + 8, 14 * TILE_SIZE - 6), "barrel"))

    # Ordenamiento estricto por coordenada Y (Algoritmo del Pintor)
    render_queue.sort(key=lambda item: item[0])

    # 3. Dibujar elementos ordenados por profundidad
    for depth, data, kind in render_queue:
        if kind == "stool":
            _render_stool_25d(surface, data[0], data[1], cam)
        elif kind == "table":
            _render_table_and_chairs_25d(surface, data[0], data[1], data[2], data[3], cam)
        elif kind == "agent":
            data.draw(surface, cam, font)
        elif kind == "barrel":
            _render_wooden_barrel(surface, data[0], data[1], cam)

    # 4. Iluminación atmosférica cálida (conos de luz de lámparas colgantes)
    _render_warm_lighting_overlay(surface, cam)


def _get_or_create_static_background(
    world: BarWorld, font: pygame.font.Font, camera: Camera25D
) -> pygame.Surface:
    """Retorna o genera de forma determinista la superficie estática de fondo."""
    global _STATIC_BACKGROUND_SURFACE
    if _STATIC_BACKGROUND_SURFACE is None:
        surf = pygame.Surface((LOGICAL_WIDTH, LOGICAL_HEIGHT))
        _render_procedural_floor(surf, camera)
        _render_walls_25d(surf, camera)
        _render_entrance_25d(surf, camera)
        _render_sports_lounge_25d(surf, camera)
        _render_bar_counter_and_backstage(surf, camera)
        _render_decorations_and_signs(surf, font, camera)
        _STATIC_BACKGROUND_SURFACE = surf
    return _STATIC_BACKGROUND_SURFACE


def _render_procedural_floor(surface: pygame.Surface, camera: Camera25D) -> None:
    """Genera un suelo de madera retro en espiga/tablones con textura determinista."""
    surface.fill(COLOR_FLOOR)
    # Patrón determinista de tablones intercalados con sutiles variaciones tonales
    for r in range(GRID_ROWS):
        y = r * TILE_SIZE
        # Línea de unión entre filas de madera
        pygame.draw.line(surface, COLOR_FLOOR_PLANK, (0, y), (LOGICAL_WIDTH, y), 1)

        # Tablones de 64 px de largo con desfase intercalado de 32 px
        offset = 16 if (r % 2 == 0) else 0
        for x in range(offset - 32, LOGICAL_WIDTH + 32, 64):
            # Selección pseudo-aleatoria pero estable usando coordenadas
            tone_idx = (x * 7 + r * 13) % 4
            if tone_idx == 0:
                plank_col = COLOR_FLOOR_ALT_1
            elif tone_idx == 1:
                plank_col = COLOR_FLOOR_ALT_2
            else:
                plank_col = COLOR_FLOOR

            # Relleno del tablón
            if x >= 0 and x + 64 <= LOGICAL_WIDTH and y >= 2 * TILE_SIZE:
                pygame.draw.rect(surface, plank_col, (x + 1, y + 1, 62, TILE_SIZE - 2))
                # Junta vertical entre tablones
                pygame.draw.line(surface, COLOR_FLOOR_PLANK, (x, y), (x, y + TILE_SIZE), 1)
                # Pequeños detalles de veta o nudos de madera
                if (x + r) % 5 == 0:
                    pygame.draw.circle(surface, COLOR_FLOOR_KNOT, (x + 24, y + 12), 2)
                    pygame.draw.circle(surface, COLOR_FLOOR_KNOT, (x + 26, y + 13), 1)


def _render_walls_25d(surface: pygame.Surface, camera: Camera25D) -> None:
    """Dibuja las paredes perimetrales con grosor, molduras, friso de madera y papel tapiz."""
    wall_h = 2 * TILE_SIZE  # 64 px de altura visual
    wainscot_h = 24  # Friso de madera inferior

    # 1. Pared Superior Principal
    # Papel tapiz superior cálido
    pygame.draw.rect(surface, COLOR_WALL_PAPER, (0, 0, LOGICAL_WIDTH, wall_h - wainscot_h))
    # Cornisa superior
    pygame.draw.rect(surface, COLOR_WALL_TOP, (0, 0, LOGICAL_WIDTH, 14))
    pygame.draw.rect(surface, COLOR_WALL_CROWN, (0, 12, LOGICAL_WIDTH, 4))

    # Friso de madera (wainscoting) en la base de la pared
    wainscot_y = wall_h - wainscot_h
    pygame.draw.rect(surface, COLOR_WALL_WAINSCOT, (0, wainscot_y, LOGICAL_WIDTH, wainscot_h))
    pygame.draw.line(surface, COLOR_WALL_BORDER, (0, wainscot_y), (LOGICAL_WIDTH, wainscot_y), 2)
    # Paneles verticales del friso
    for px in range(TILE_SIZE, LOGICAL_WIDTH - TILE_SIZE, 32):
        pygame.draw.line(
            surface, COLOR_WALL_WAINSCOT_DARK, (px, wainscot_y), (px, wall_h), 1
        )
    # Rodapié inferior
    pygame.draw.rect(surface, COLOR_WALL_BG, (0, wall_h - 4, LOGICAL_WIDTH, 4))
    pygame.draw.line(surface, (14, 8, 6), (0, wall_h - 1), (LOGICAL_WIDTH, wall_h - 1), 2)

    # 2. Paredes Laterales con profundidad oblicua
    # Pared lateral izquierda
    pygame.draw.rect(surface, COLOR_WALL_BG, (0, 0, TILE_SIZE, LOGICAL_HEIGHT))
    pygame.draw.rect(surface, COLOR_WALL_WAINSCOT, (TILE_SIZE - 6, wall_h, 6, LOGICAL_HEIGHT - wall_h))
    pygame.draw.line(surface, COLOR_WALL_BORDER, (TILE_SIZE - 1, 0), (TILE_SIZE - 1, LOGICAL_HEIGHT), 2)

    # Pared lateral derecha
    pygame.draw.rect(surface, COLOR_WALL_BG, (LOGICAL_WIDTH - TILE_SIZE, 0, TILE_SIZE, LOGICAL_HEIGHT))
    pygame.draw.rect(surface, COLOR_WALL_WAINSCOT, (LOGICAL_WIDTH - TILE_SIZE, wall_h, 6, LOGICAL_HEIGHT - wall_h))
    pygame.draw.line(
        surface, COLOR_WALL_BORDER, (LOGICAL_WIDTH - TILE_SIZE, 0), (LOGICAL_WIDTH - TILE_SIZE, LOGICAL_HEIGHT), 2
    )

    # 3. Pared Inferior con vano de entrada
    door_x1 = 14 * TILE_SIZE
    door_x2 = 17 * TILE_SIZE
    bottom_y = LOGICAL_HEIGHT - TILE_SIZE

    pygame.draw.rect(surface, COLOR_WALL_BG, (0, bottom_y, door_x1, TILE_SIZE))
    pygame.draw.rect(surface, COLOR_WALL_BG, (door_x2, bottom_y, LOGICAL_WIDTH - door_x2, TILE_SIZE))
    pygame.draw.rect(surface, COLOR_WALL_CROWN, (0, bottom_y, door_x1, 4))
    pygame.draw.rect(surface, COLOR_WALL_CROWN, (door_x2, bottom_y, LOGICAL_WIDTH - door_x2, 4))


def _render_entrance_25d(surface: pygame.Surface, camera: Camera25D) -> None:
    """Dibuja el vano de la puerta de entrada con profundidad, marco y felpudo con textura de fibra."""
    door_x1 = 14 * TILE_SIZE
    door_x2 = 17 * TILE_SIZE
    mat_w = 3 * TILE_SIZE - 8
    mat_rect = pygame.Rect(door_x1 + 4, LOGICAL_HEIGHT - TILE_SIZE + 2, mat_w, 28)

    # Sombra del umbral de entrada
    pygame.draw.rect(surface, (16, 10, 8), (door_x1, LOGICAL_HEIGHT - TILE_SIZE, 3 * TILE_SIZE, 3))
    # Felpudo de fibra de coco
    pygame.draw.rect(surface, COLOR_MAT_FILL, mat_rect, border_radius=3)
    pygame.draw.rect(surface, COLOR_MAT_BORDER, mat_rect, width=2, border_radius=3)
    # Textura estriada del felpudo
    for fx in range(mat_rect.left + 4, mat_rect.right - 4, 4):
        pygame.draw.line(surface, COLOR_MAT_BORDER, (fx, mat_rect.top + 3), (fx, mat_rect.bottom - 3), 1)

    # Marcos laterales de la puerta
    pygame.draw.rect(surface, COLOR_WALL_CROWN, (door_x1 - 4, LOGICAL_HEIGHT - TILE_SIZE, 4, TILE_SIZE))
    pygame.draw.rect(surface, COLOR_WALL_CROWN, (door_x2, LOGICAL_HEIGHT - TILE_SIZE, 4, TILE_SIZE))


def _render_bar_counter_and_backstage(surface: pygame.Surface, camera: Camera25D) -> None:
    """Dibuja el mostrador de caoba con cara frontal 2.5D, tirador de cerveza, estantería y botellas."""
    bar_x = 3 * TILE_SIZE
    bar_y = 4 * TILE_SIZE
    bar_w = 2 * TILE_SIZE
    bar_h = 10 * TILE_SIZE

    # Sombra arrojada por la barra hacia la derecha
    bar_shadow = pygame.Rect(bar_x + bar_w, bar_y + 8, 12, bar_h)
    shadow_surf = pygame.Surface((12, bar_h), pygame.SRCALPHA)
    shadow_surf.fill((COLOR_TABLE_SHADOW[0], COLOR_TABLE_SHADOW[1], COLOR_TABLE_SHADOW[2], 90))
    surface.blit(shadow_surf, bar_shadow.topleft)

    # 1. Estantería posterior de licores (Columna 1, filas 4 a 13)
    shelf_rect = pygame.Rect(1 * TILE_SIZE + 4, bar_y, TILE_SIZE - 4, bar_h)
    pygame.draw.rect(surface, COLOR_SHELF_BG, shelf_rect, border_radius=3)
    # Baldas de madera horizontales
    for sy in range(bar_y + 16, bar_y + bar_h, 32):
        pygame.draw.rect(surface, COLOR_SHELF_WOOD, (shelf_rect.x, sy, shelf_rect.width, 4))
        # Botellas de varias formas, alturas y colores en la balda
        bottle_colors = [
            (200, 50, 40), (45, 160, 65), (230, 190, 50),
            (140, 65, 175), (210, 110, 30), (70, 180, 220)
        ]
        for bx_offset in (2, 8, 14, 20):
            c = bottle_colors[(sy + bx_offset) % len(bottle_colors)]
            bh = 10 + ((sy + bx_offset) % 5)
            pygame.draw.rect(surface, c, (shelf_rect.x + bx_offset, sy - bh, 4, bh), border_radius=1)
            # Cuello de botella
            pygame.draw.rect(surface, (230, 230, 240), (shelf_rect.x + bx_offset + 1, sy - bh - 3, 2, 3))

    # 2. Mostrador de la barra (Perspectiva 2.5D: cara frontal con molduras y encimera superior biselada)
    counter_rect = pygame.Rect(bar_x, bar_y, bar_w, bar_h)
    # Cuerpo frontal
    pygame.draw.rect(surface, COLOR_BAR_WOOD, counter_rect, border_radius=4)
    # Paneles decorativos de madera en la cara visible
    for py in range(bar_y + 12, bar_y + bar_h - 20, 48):
        panel = pygame.Rect(bar_x + 6, py, bar_w - 12, 36)
        pygame.draw.rect(surface, COLOR_BAR_FRONT_PANEL, panel, border_radius=2)
        pygame.draw.rect(surface, COLOR_BAR_WOOD, panel, width=1, border_radius=2)

    # Reposapiés de latón en la base
    pygame.draw.line(surface, COLOR_BAR_BRASS_RAIL, (bar_x + bar_w - 4, bar_y + 8), (bar_x + bar_w - 4, bar_y + bar_h - 8), 3)

    # Encimera superior de caoba pulida (brillante)
    top_rim = pygame.Rect(bar_x + 2, bar_y + 2, bar_w - 4, bar_h - 4)
    pygame.draw.rect(surface, COLOR_BAR_TOP, top_rim, border_radius=3)
    # Borde de bisel con resalte de luz
    pygame.draw.rect(surface, COLOR_BAR_TRIM, counter_rect, width=2, border_radius=4)
    pygame.draw.line(surface, (175, 110, 65), (bar_x + 3, bar_y + 3), (bar_x + bar_w - 3, bar_y + 3), 2)

    # 3. Equipamiento sobre la barra: Torre de cerveza de barril y cafetera
    # Grifo de cerveza (fila 7)
    tap_y = bar_y + 70
    pygame.draw.rect(surface, (180, 180, 190), (bar_x + 14, tap_y, 8, 14), border_radius=2)
    pygame.draw.rect(surface, (215, 175, 55), (bar_x + 12, tap_y + 3, 12, 4))  # Caño de latón
    pygame.draw.circle(surface, (40, 40, 40), (bar_x + 18, tap_y - 2), 3)  # Maneta negra

    # Cafetera espresso retro (fila 11)
    exp_y = bar_y + 190
    pygame.draw.rect(surface, (190, 40, 40), (bar_x + 10, exp_y, 16, 18), border_radius=3)
    pygame.draw.rect(surface, (220, 220, 230), (bar_x + 12, exp_y + 2, 12, 6))  # Frontal de acero


def _render_stool_25d(surface: pygame.Surface, cx: float, cy: float, camera: Camera25D) -> None:
    """Dibuja un taburete con volumen: sombra en suelo, patas torneadas y asiento acolchado con realce."""
    # Sombra en suelo
    pygame.draw.ellipse(surface, (16, 10, 8, 120), (cx - 10, cy + 3, 20, 8))

    # Patas de madera torneada
    pygame.draw.line(surface, COLOR_STOOL_LEG, (cx - 6, cy + 4), (cx - 5, cy - 8), 2)
    pygame.draw.line(surface, COLOR_STOOL_LEG, (cx + 6, cy + 4), (cx + 5, cy - 8), 2)
    pygame.draw.line(surface, COLOR_STOOL_LEG, (cx, cy + 5), (cx, cy - 8), 2)
    # Aro reposapiés
    pygame.draw.ellipse(surface, (80, 50, 30), (cx - 7, cy - 2, 14, 4), 1)

    # Asiento acolchado circular (con cara frontal y cara superior biselada)
    # Borde lateral del cojín
    pygame.draw.ellipse(surface, COLOR_STOOL_OUTER, (cx - 11, cy - 14, 22, 12))
    # Superficie superior acolchada
    pygame.draw.ellipse(surface, COLOR_STOOL_CUSHION, (cx - 10, cy - 16, 20, 10))
    # Brillo de luz de cuero
    pygame.draw.ellipse(surface, COLOR_STOOL_HIGHLIGHT, (cx - 6, cy - 17, 8, 3))


def _render_table_and_chairs_25d(
    surface: pygame.Surface,
    tx: int,
    ty: int,
    tw: int,
    th: int,
    camera: Camera25D,
) -> None:
    """Dibuja una mesa con faldón, tapa biselada, accesorios decorativos y sus sillas con respaldo 2.5D."""
    table_rect = pygame.Rect(tx, ty, tw, th)

    # 1. Sombra elíptica arrojada por la mesa
    shadow_rect = table_rect.inflate(14, 10).move(4, 4)
    pygame.draw.ellipse(surface, COLOR_TABLE_SHADOW, shadow_rect)

    # 2. Sillas norte (detrás de la mesa)
    _render_chair_25d(surface, tx + tw // 2, ty - 14, facing="south")

    # 3. Soporte central / pata torneada de la mesa
    pygame.draw.rect(surface, COLOR_TABLE_LEG, (tx + tw // 2 - 4, ty + 10, 8, th - 10), border_radius=2)
    # Pie en cruz de la mesa
    pygame.draw.ellipse(surface, (50, 26, 14), (tx + tw // 2 - 14, ty + th - 6, 28, 8))

    # 4. Faldón / cara frontal de la mesa
    pygame.draw.rect(surface, COLOR_TABLE_WOOD, table_rect, border_radius=6)

    # 5. Tapa superior de la mesa (elevada con bisel y veta)
    top_rect = table_rect.inflate(-6, -6).move(0, -3)
    pygame.draw.rect(surface, COLOR_TABLE_TOP, top_rect, border_radius=5)
    pygame.draw.rect(surface, COLOR_TABLE_RIM, table_rect, width=2, border_radius=6)
    # Detalle de veta de madera
    pygame.draw.line(surface, COLOR_TABLE_RIM, (top_rect.left + 8, top_rect.centery), (top_rect.right - 8, top_rect.centery), 1)

    # 6. Pequeño accesorio sobre la mesa (Jarra de cerveza con espuma o servilletero)
    mug_x = top_rect.centerx - 6
    mug_y = top_rect.centery - 6
    pygame.draw.rect(surface, COLOR_GLASS_BEER, (mug_x, mug_y, 6, 8), border_radius=1)
    pygame.draw.rect(surface, COLOR_BEER_FOAM, (mug_x - 1, mug_y - 2, 8, 3), border_radius=1)

    # 7. Sillas laterales y sur (delante de la mesa)
    _render_chair_25d(surface, tx - 16, ty + th // 2, facing="east")
    _render_chair_25d(surface, tx + tw + 16, ty + th // 2, facing="west")
    _render_chair_25d(surface, tx + tw // 2, ty + th + 14, facing="north")


def _render_chair_25d(
    surface: pygame.Surface, cx: float, cy: float, facing: str
) -> None:
    """Dibuja una silla con patas, asiento tapizado y respaldo 2.5D según orientación."""
    # Sombra en suelo
    pygame.draw.ellipse(surface, (18, 10, 8, 100), (cx - 8, cy + 2, 16, 6))

    # Asiento
    pygame.draw.ellipse(surface, COLOR_CHAIR, (cx - 9, cy - 7, 18, 10))
    pygame.draw.ellipse(surface, COLOR_CHAIR_SEAT, (cx - 7, cy - 8, 14, 8))

    # Respaldo según la orientación
    if facing == "south":
        # Vista posterior del respaldo (hacia el espectador)
        pygame.draw.rect(surface, COLOR_CHAIR_BACK, (cx - 8, cy - 18, 16, 10), border_radius=2)
        pygame.draw.line(surface, (50, 28, 16), (cx - 4, cy - 18), (cx - 4, cy - 8), 1)
        pygame.draw.line(surface, (50, 28, 16), (cx + 4, cy - 18), (cx + 4, cy - 8), 1)
    elif facing in ("east", "west"):
        offset = -4 if facing == "east" else 4
        pygame.draw.rect(surface, COLOR_CHAIR_BACK, (cx + offset - 2, cy - 18, 5, 12), border_radius=2)
    else:
        # Orientación norte: respaldo al frente
        pygame.draw.rect(surface, COLOR_CHAIR_BACK, (cx - 8, cy - 4, 16, 6), border_radius=2)


def _render_sports_lounge_25d(surface: pygame.Surface, camera: Camera25D) -> None:
    """Dibuja el televisor gigante con marco 2.5D, pantalla táctica y sofá capitoné."""
    # 1. Televisor en pared superior (cols 21 a 27)
    tv_rect = pygame.Rect(21 * TILE_SIZE, 1 * TILE_SIZE + 2, 7 * TILE_SIZE, 2 * TILE_SIZE)
    # Sombra bajo el marco del televisor
    pygame.draw.rect(surface, (14, 8, 6), tv_rect.inflate(8, 8).move(0, 4), border_radius=6)
    # Marco exterior y bisel
    pygame.draw.rect(surface, COLOR_TV_FRAME, tv_rect.inflate(8, 8), border_radius=6)
    pygame.draw.rect(surface, COLOR_TV_BEZEL, tv_rect.inflate(4, 4), border_radius=5)
    pygame.draw.rect(surface, COLOR_TV_SCREEN, tv_rect, border_radius=3)

    # Gráficos tácticos de fútbol en la pantalla
    center_x = tv_rect.centerx
    pygame.draw.line(surface, (255, 255, 255), (center_x, tv_rect.top + 3), (center_x, tv_rect.bottom - 3), 2)
    pygame.draw.circle(surface, (255, 255, 255), tv_rect.center, 15, 2)
    # Áreas de portería
    pygame.draw.rect(surface, (255, 255, 255), (tv_rect.left + 3, tv_rect.centery - 14, 14, 28), 2)
    pygame.draw.rect(surface, (255, 255, 255), (tv_rect.right - 17, tv_rect.centery - 14, 14, 28), 2)
    # Jugadores simulados como puntos en el campo
    pygame.draw.circle(surface, (0, 77, 152), (center_x - 30, tv_rect.centery), 3)
    pygame.draw.circle(surface, (240, 240, 240), (center_x + 30, tv_rect.centery), 3)
    pygame.draw.circle(surface, (255, 220, 0), (center_x + 4, tv_rect.centery + 6), 2)  # Balón

    # LED de encendido
    pygame.draw.circle(surface, (60, 255, 80), (tv_rect.right + 1, tv_rect.bottom + 2), 2)

    # 2. Sofá de aficionados frente a la TV (cols 22 a 26, fila 5)
    sofa_rect = pygame.Rect(22 * TILE_SIZE, 5 * TILE_SIZE, 5 * TILE_SIZE, TILE_SIZE)
    # Sombra arrojada en el suelo
    pygame.draw.rect(surface, COLOR_TABLE_SHADOW, sofa_rect.inflate(6, 4).move(2, 4), border_radius=5)
    # Base del sofá
    pygame.draw.rect(surface, COLOR_SOFA_BASE, sofa_rect, border_radius=6)
    # Cojín superior capitoné
    cushion = sofa_rect.inflate(-4, -4).move(0, -2)
    pygame.draw.rect(surface, COLOR_SOFA_CUSHION, cushion, border_radius=4)
    # Botones de tapizado (capitoné)
    for bx in range(cushion.left + 14, cushion.right - 8, 24):
        pygame.draw.circle(surface, COLOR_SOFA_TUFT, (bx, cushion.centery), 2)
    # Reposabrazos
    pygame.draw.rect(surface, COLOR_SOFA_BASE, (sofa_rect.left - 4, sofa_rect.top, 6, sofa_rect.height), border_radius=3)
    pygame.draw.rect(surface, COLOR_SOFA_BASE, (sofa_rect.right - 2, sofa_rect.top, 6, sofa_rect.height), border_radius=3)


def _render_wooden_barrel(surface: pygame.Surface, bx: int, by: int, camera: Camera25D) -> None:
    """Dibuja un barril de cerveza decorativo con aros metálicos."""
    pygame.draw.ellipse(surface, COLOR_TABLE_SHADOW, (bx - 2, by + 12, 24, 8))
    # Cuerpo del barril
    barrel_rect = pygame.Rect(bx, by - 12, 20, 26)
    pygame.draw.rect(surface, (88, 48, 24), barrel_rect, border_radius=6)
    # Aros metálicos de hierro
    pygame.draw.line(surface, (40, 40, 44), (bx, by - 6), (bx + 19, by - 6), 2)
    pygame.draw.line(surface, (40, 40, 44), (bx, by + 6), (bx + 19, by + 6), 2)
    # Tapa superior
    pygame.draw.ellipse(surface, (112, 64, 34), (bx + 1, by - 14, 18, 6))


def _render_decorations_and_signs(surface: pygame.Surface, font: pygame.font.Font, camera: Camera25D) -> None:
    """Dibuja los banderines azulgrana y merengue con bordes, el cartel de madera y plantas."""
    # 1. Banderín FC Barcelona (azulgrana a rayas con flecos)
    fcb_rect = pygame.Rect(9 * TILE_SIZE + 4, 8, 76, 34)
    pygame.draw.rect(surface, COLOR_BANNER_FCB_BLUE, fcb_rect, border_radius=3)
    pygame.draw.rect(surface, COLOR_BANNER_FCB_RED, (fcb_rect.x + 24, fcb_rect.y, 28, 34))
    pygame.draw.rect(surface, (230, 190, 40), fcb_rect, width=1, border_radius=3)
    fcb_lbl = font.render("FCB", True, (255, 220, 40))
    surface.blit(fcb_lbl, (fcb_rect.centerx - fcb_lbl.get_width() // 2, fcb_rect.centery - fcb_lbl.get_height() // 2))

    # 2. Banderín Real Madrid (blanco con banda dorada y flecos, flanqueando el rótulo)
    rma_rect = pygame.Rect(18 * TILE_SIZE + 4, 8, 76, 34)
    pygame.draw.rect(surface, COLOR_BANNER_RMA_WHITE, rma_rect, border_radius=3)
    pygame.draw.rect(surface, COLOR_BANNER_RMA_GOLD, (rma_rect.x + 26, rma_rect.y, 24, 34))
    pygame.draw.rect(surface, (200, 160, 40), rma_rect, width=1, border_radius=3)
    rma_lbl = font.render("RMA", True, (0, 0, 75))
    surface.blit(rma_lbl, (rma_rect.centerx - rma_lbl.get_width() // 2, rma_rect.centery - rma_lbl.get_height() // 2))

    # 3. Rótulo central superior "BAR EL CLÁSICO" tallado en madera con borde dorado
    sign_rect = pygame.Rect(LOGICAL_WIDTH // 2 - 80, 5, 160, 24)
    pygame.draw.rect(surface, (54, 30, 16), sign_rect, border_radius=4)
    pygame.draw.rect(surface, (215, 175, 60), sign_rect, width=2, border_radius=4)
    title_font = pygame.font.SysFont("Arial", 14, bold=True)
    title_surf = title_font.render("BAR EL CLÁSICO", True, (250, 220, 120))
    surface.blit(title_surf, (sign_rect.centerx - title_surf.get_width() // 2, sign_rect.centery - title_surf.get_height() // 2))

    # 4. Plantas decorativas en macetas de terracota en las esquinas
    for px, py in (
        (TILE_SIZE + 8, LOGICAL_HEIGHT - TILE_SIZE - 28),
        (LOGICAL_WIDTH - TILE_SIZE - 26, LOGICAL_HEIGHT - TILE_SIZE - 28),
    ):
        pygame.draw.ellipse(surface, COLOR_TABLE_SHADOW, (px - 2, py + 18, 22, 6))
        pygame.draw.rect(surface, COLOR_PLANT_POT, (px, py + 10, 18, 14), border_radius=2)
        pygame.draw.circle(surface, COLOR_PLANT_LEAVES, (px + 9, py + 7), 11)
        pygame.draw.circle(surface, COLOR_PLANT_HIGHLIGHT, (px + 7, py + 5), 7)


def _render_warm_lighting_overlay(surface: pygame.Surface, camera: Camera25D) -> None:
    """Añade una capa sutil de iluminación cálida focalizada sobre la barra y mesas."""
    light_surf = pygame.Surface((LOGICAL_WIDTH, LOGICAL_HEIGHT), pygame.SRCALPHA)

    # Focos cálidos sobre la barra (lámparas colgantes vintage)
    for ly in (6 * TILE_SIZE, 9 * TILE_SIZE, 12 * TILE_SIZE):
        lx = 4 * TILE_SIZE
        # Cono sutil de luz ámbar
        pygame.draw.ellipse(
            light_surf,
            (COLOR_LAMP_CONE[0], COLOR_LAMP_CONE[1], COLOR_LAMP_CONE[2], 22),
            (lx - 28, ly - 18, 56, 36),
        )

    surface.blit(light_surf, (0, 0))


def render_debug_overlay(
    surface: pygame.Surface,
    world: BarWorld,
    font: pygame.font.Font,
    agents: Optional[List[Any]] = None,
    selected_agent_idx: int = 0,
    camera: Optional[Camera25D] = None,
) -> None:
    """Capa técnica de depuración: dibuja cuadrícula, celdas bloqueadas/transitables, cajas de colisión y telemetría."""
    cam = camera or default_camera
    debug_surf = pygame.Surface((LOGICAL_WIDTH, LOGICAL_HEIGHT), pygame.SRCALPHA)

    # 1. Celdas bloqueadas de la grilla (sombreado rojo translúcido)
    for r in range(GRID_ROWS):
        for c in range(GRID_COLS):
            if not world.walkable[r][c]:
                tile_rect = pygame.Rect(c * TILE_SIZE, r * TILE_SIZE, TILE_SIZE, TILE_SIZE)
                pygame.draw.rect(
                    debug_surf,
                    (COLOR_DEBUG_BLOCKED_TILE[0], COLOR_DEBUG_BLOCKED_TILE[1], COLOR_DEBUG_BLOCKED_TILE[2], 55),
                    tile_rect,
                )

    # 2. Cuadrícula
    for c in range(GRID_COLS):
        pygame.draw.line(debug_surf, (255, 255, 255, 25), (c * TILE_SIZE, 0), (c * TILE_SIZE, LOGICAL_HEIGHT))
    for r in range(GRID_ROWS):
        pygame.draw.line(debug_surf, (255, 255, 255, 25), (0, r * TILE_SIZE), (LOGICAL_WIDTH, r * TILE_SIZE))

    # 3. Cajas de obstáculos físicas
    for obs in world.obstacles:
        pygame.draw.rect(debug_surf, COLOR_DEBUG_OBSTACLE, obs.bounds, width=1)

    # 4. Puntos de interés (POIs)
    for poi in world.pois.values():
        pygame.draw.circle(debug_surf, COLOR_DEBUG_POI, (int(poi.x), int(poi.y)), 4)
        lbl = font.render(poi.name, True, COLOR_DEBUG_TEXT)
        debug_surf.blit(lbl, (int(poi.x) + 6, int(poi.y) - 6))

    # 5. Visualización de rutas y destinos para agentes navegables
    if agents:
        for idx, agent in enumerate(agents):
            is_selected = idx == selected_agent_idx
            if hasattr(agent, "is_navigating") and agent.is_navigating and agent.active_waypoints:
                # Líneas de la ruta calculada
                pts = [cam.world_to_screen(agent.x, agent.y)]
                w_idx = agent.follower.current_waypoint_idx
                for wx, wy in agent.active_waypoints[w_idx:]:
                    pts.append(cam.world_to_screen(wx, wy))
                if len(pts) >= 2:
                    pygame.draw.lines(debug_surf, COLOR_DEBUG_PATH, False, pts, 2)
                for px, py in pts[1:]:
                    pygame.draw.circle(debug_surf, COLOR_DEBUG_WAYPOINT, (int(px), int(py)), 3)

            # Destino marcado
            if hasattr(agent, "target_pos") and agent.target_pos is not None:
                tx, ty = agent.target_pos
                stx, sty = cam.world_to_screen(tx, ty)
                pygame.draw.circle(debug_surf, COLOR_DEBUG_GOAL, (int(stx), int(sty)), 5, width=2)

            # Collider físico centrado en pies (20x20)
            if hasattr(agent, "collider_rect"):
                sx, sy = cam.world_to_screen(agent.x, agent.y)
                box = pygame.Rect(int(sx - 10), int(sy - 10), 20, 20)
                col = (60, 255, 60) if is_selected else (0, 220, 220)
                pygame.draw.rect(debug_surf, col, box, width=1)

    surface.blit(debug_surf, (0, 0))

    # 6. Banner superior de estado y controles
    hud_surf = pygame.Surface((LOGICAL_WIDTH, 22), pygame.SRCALPHA)
    hud_surf.fill(COLOR_HUD_BG)
    surface.blit(hud_surf, (0, 0))
    info_text = font.render(
        "[DEBUG] D: Alternar | B: Modo BDI | M: Modo Demo | Clic Izq: Asignar Destino | TAB/1/2: Elegir Agente | C: Cancelar",
        True,
        COLOR_DEBUG_TEXT,
    )
    surface.blit(info_text, (10, 4))

    # 7. Banner inferior con telemetría del agente seleccionado
    if agents and 0 <= selected_agent_idx < len(agents):
        sel_agent = agents[selected_agent_idx]
        if hasattr(sel_agent, "is_navigating"):
            has_bdi = getattr(sel_agent, "bdi_controller", None) is not None
            bot_h = 36 if has_bdi else 20
            bot_hud = pygame.Surface((LOGICAL_WIDTH, bot_h), pygame.SRCALPHA)
            bot_hud.fill(COLOR_HUD_BG)
            surface.blit(bot_hud, (0, LOGICAL_HEIGHT - bot_h))

            if has_bdi:
                bdi = sel_agent.bdi_controller
                b = bdi.beliefs
                cur_int = bdi.current_intention
                int_desc = f"{cur_int.desire_type.value} ({cur_int.state.value} - {cur_int.execution_phase})" if cur_int else "NINGUNA (IDLE)"
                line1 = f"[BDI ACTIVO] {sel_agent.name} | Intención: {int_desc} | Celda: {sel_agent.current_cell} -> Destino: {sel_agent.target_cell or 'None'}"
                line2 = f"Sed: {b.thirst:.2f} | Energía: {b.energy:.2f} | Sociab: {b.sociability:.2f} | Dist Rival: {b.other_agent_distance:.1f}px | Replanif: {bdi.replan_count}"
                surface.blit(font.render(line1, True, (255, 230, 100)), (10, LOGICAL_HEIGHT - bot_h + 2))
                surface.blit(font.render(line2, True, (180, 230, 255)), (10, LOGICAL_HEIGHT - bot_h + 18))
            else:
                nav_info = f"Seleccionado: {sel_agent.name} | Estado: {sel_agent.state} | Pos: ({sel_agent.x:.1f}, {sel_agent.y:.1f}) | Celda: {sel_agent.current_cell} | Vel: {sel_agent.speed:.0f}px/s"
                if sel_agent.target_cell:
                    nav_info += f" | Destino: {sel_agent.target_cell}"
                if sel_agent.last_path_error:
                    nav_info += f" | Error: {sel_agent.last_path_error}"
                bot_lbl = font.render(nav_info, True, (255, 230, 100))
                surface.blit(bot_lbl, (10, LOGICAL_HEIGHT - 17))
