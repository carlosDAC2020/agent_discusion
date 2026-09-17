"""Modelo de datos del mundo y lógica de colisiones del Bar.

Mantiene la cuadrícula, los obstáculos físicos, las zonas transitables y los puntos de interés.
Este módulo no ejecuta renderizado gráfico (delegado a rendering.py) para mantener
una separación estricta de responsabilidades y permitir pruebas unitarias sin display.
"""

import math
from typing import Dict, List, Optional, Tuple


from src.simulation.config import (
    GRID_COLS,
    GRID_ROWS,
    LOGICAL_HEIGHT,
    LOGICAL_WIDTH,
    TILE_SIZE,
)
from src.simulation.events import Obstacle, PointOfInterest, WorldBounds


class BarWorld:
    """Representa el estado espacial, físico y de colisión del Bar."""

    def __init__(self):
        self.width: int = LOGICAL_WIDTH
        self.height: int = LOGICAL_HEIGHT
        self.cols: int = GRID_COLS
        self.rows: int = GRID_ROWS
        self.tile_size: int = TILE_SIZE
        self.bounds = WorldBounds(0.0, 0.0, float(self.width), float(self.height))

        # Matriz booleana de transitabilidad: True = caminable, False = bloqueado
        self.walkable: List[List[bool]] = [[True for _ in range(self.cols)] for _ in range(self.rows)]

        # Lista de obstáculos rectangulares
        self.obstacles: List[Obstacle] = []

        # Diccionario de puntos de interés (POIs)
        self.pois: Dict[str, PointOfInterest] = {}

        # Configuración de mesas para facilitar renderizado y futuras consultas
        self.tables_data: List[Dict] = []

        # Construcción inicial de la escena estática
        self._build_bar_environment()

    def _build_bar_environment(self) -> None:
        """Construye las paredes perimetrales, barra, mesas y puntos de interés."""
        # 1. Paredes perimetrales
        # Pared superior completa (filas 0 y 1 para dar perspectiva de muro alto)
        self._add_obstacle("wall_top", "wall", 0, 0, self.width, 2 * self.tile_size)
        for r in (0, 1):
            for c in range(self.cols):
                self.walkable[r][c] = False

        # Pared lateral izquierda
        self._add_obstacle("wall_left", "wall", 0, 0, self.tile_size, self.height)
        for r in range(self.rows):
            self.walkable[r][0] = False

        # Pared lateral derecha
        self._add_obstacle("wall_right", "wall", self.width - self.tile_size, 0, self.tile_size, self.height)
        for r in range(self.rows):
            self.walkable[r][self.cols - 1] = False

        # Pared inferior con apertura de entrada (puerta en columnas 14 a 16)
        door_col_start = 14
        door_col_end = 16  # Inclusive
        door_x1 = door_col_start * self.tile_size
        door_x2 = (door_col_end + 1) * self.tile_size

        # Muro inferior izquierdo
        self._add_obstacle("wall_bottom_left", "wall", 0, self.height - self.tile_size, door_x1, self.tile_size)
        for c in range(door_col_start):
            self.walkable[self.rows - 1][c] = False

        # Muro inferior derecho
        self._add_obstacle(
            "wall_bottom_right",
            "wall",
            door_x2,
            self.height - self.tile_size,
            self.width - door_x2,
            self.tile_size,
        )
        for c in range(door_col_end + 1, self.cols):
            self.walkable[self.rows - 1][c] = False

        # Puerta transitable
        for c in range(door_col_start, door_col_end + 1):
            self.walkable[self.rows - 1][c] = True

        # POI Entrada del Bar
        self._add_poi(
            name="entrance",
            category="entrance",
            tile_x=15,
            tile_y=self.rows - 2,
            description="Entrada principal del Bar",
        )

        # 2. La Barra del Bar (Zona Izquierda)
        # Estantería de botellas trasera (columna 1, filas 4 a 13)
        self._add_obstacle(
            "shelf_bottles",
            "shelf",
            1 * self.tile_size,
            4 * self.tile_size,
            self.tile_size,
            10 * self.tile_size,
        )
        for r in range(4, 14):
            self.walkable[r][1] = False
            self.walkable[r][2] = False  # Pasillo interior reservado para el camarero

        # Mostrador de la barra (columnas 3 y 4, filas 4 a 13)
        self._add_obstacle(
            "bar_counter",
            "bar_counter",
            3 * self.tile_size,
            4 * self.tile_size,
            2 * self.tile_size,
            10 * self.tile_size,
        )
        for r in range(4, 14):
            self.walkable[r][3] = False
            self.walkable[r][4] = False

        # Taburetes frente a la barra (columna 5, filas 5, 7, 9, 11, 13)
        for idx, r in enumerate([5, 7, 9, 11, 13], start=1):
            self._add_poi(
                name=f"bar_stool_{idx}",
                category="bar",
                tile_x=5,
                tile_y=r,
                description=f"Taburete de la barra {idx}",
            )

        # 3. Mesas y sillas (Área central y derecha)
        table_definitions = [
            {"name": "table_central_1", "col": 10, "row": 6, "w": 3, "h": 2, "desc": "Mesa Central 1"},
            {"name": "table_central_2", "col": 10, "row": 12, "w": 3, "h": 2, "desc": "Mesa Central 2"},
            {"name": "table_side_1", "col": 19, "row": 9, "w": 3, "h": 2, "desc": "Mesa Lateral"},
            {"name": "table_corner_1", "col": 19, "row": 14, "w": 3, "h": 2, "desc": "Mesa Rincón"},
        ]

        for t in table_definitions:
            tc, tr, tw, th = t["col"], t["row"], t["w"], t["h"]
            # Añadir obstáculo físico de la mesa
            self._add_obstacle(
                t["name"],
                "table",
                tc * self.tile_size,
                tr * self.tile_size,
                tw * self.tile_size,
                th * self.tile_size,
            )
            for dr in range(th):
                for dc in range(tw):
                    self.walkable[tr + dr][tc + dc] = False

            # Asientos (POIs) alrededor de la mesa
            seats_info = [
                (f"{t['name']}_seat_west", tc - 1, tr, "Silla Oeste"),
                (f"{t['name']}_seat_east", tc + tw, tr, "Silla Este"),
                (f"{t['name']}_seat_north", tc + 1, tr - 1, "Silla Norte"),
                (f"{t['name']}_seat_south", tc + 1, tr + th, "Silla Sur"),
            ]
            seat_names = []
            for sname, sc, sr, sdesc in seats_info:
                if 0 <= sc < self.cols and 0 <= sr < self.rows and self.walkable[sr][sc]:
                    self._add_poi(sname, "table_seat", sc, sr, f"{sdesc} de {t['desc']}")
                    seat_names.append(sname)

            self.tables_data.append(
                {
                    "name": t["name"],
                    "col": tc,
                    "row": tr,
                    "width": tw * self.tile_size,
                    "height": th * self.tile_size,
                    "seats": seat_names,
                }
            )

        # 4. Zona de TV / Pantalla Gigante (Esquina Superior Derecha)
        # Sofá frente a la TV (filas 5, columnas 22 a 26)
        self._add_obstacle(
            "sofa_tv",
            "sofa",
            22 * self.tile_size,
            5 * self.tile_size,
            5 * self.tile_size,
            self.tile_size,
        )
        for c in range(22, 27):
            self.walkable[5][c] = False

        # Asientos del sofá como POIs
        for c in range(22, 27):
            self._add_poi(
                name=f"tv_lounge_seat_{c}",
                category="tv_seat",
                tile_x=c,
                tile_y=6,
                description=f"Asiento TV Lounge {c - 21}",
            )

        # 5. Spawns reservados para agentes futuros (Josep y Paco)
        self._add_poi(
            name="barcelona_spawn",
            category="spawn",
            tile_x=6,
            tile_y=7,
            description="Punto de inicio para Josep (FC Barcelona)",
            recommended_facing="right",
            exclusive_to="barcelona",
        )
        self._add_poi(
            name="real_madrid_spawn",
            category="spawn",
            tile_x=22,
            tile_y=8,
            description="Punto de inicio para Paco (Real Madrid)",
            recommended_facing="left",
            exclusive_to="real_madrid",
        )

        # 6. POIs Semánticos para el debate y moderación en la barra
        self._add_poi(
            name="barcelona_debate_spot",
            category="debate",
            tile_x=6,
            tile_y=7,
            description="Posición de debate frente a la barra para Josep (FC Barcelona)",
            recommended_facing="left",
            interaction_radius=32.0,
            exclusive_to="barcelona",
        )
        self._add_poi(
            name="real_madrid_debate_spot",
            category="debate",
            tile_x=6,
            tile_y=9,
            description="Posición de debate frente a la barra para Paco (Real Madrid)",
            recommended_facing="left",
            interaction_radius=32.0,
            exclusive_to="real_madrid",
        )
        self._add_poi(
            name="bartender_position",
            category="bartender",
            tile_x=2,
            tile_y=7,
            description="Posición de trabajo del barman detrás de la barra",
            recommended_facing="right",
            interaction_radius=40.0,
            is_walkable=False,
            exclusive_to="bartender",
        )
        self._add_poi(
            name="bartender_interaction_zone",
            category="bartender",
            tile_x=4,
            tile_y=8,
            description="Zona de atención en el mostrador entre Manolo y tertulianos",
            recommended_facing="center",
            interaction_radius=48.0,
            is_walkable=False,
        )

    def _add_obstacle(self, name: str, category: str, x: int, y: int, w: int, h: int) -> None:
        """Registra un obstáculo en la lista."""
        self.obstacles.append(Obstacle(name=name, category=category, x=x, y=y, width=w, height=h))

    def _add_poi(
        self,
        name: str,
        category: str,
        tile_x: int,
        tile_y: int,
        description: str,
        recommended_facing: str = "left",
        interaction_radius: float = 32.0,
        is_walkable: Optional[bool] = None,
        exclusive_to: Optional[str] = None,
    ) -> None:
        """Registra un punto de interés en el diccionario."""
        px = tile_x * self.tile_size + self.tile_size // 2
        py = tile_y * self.tile_size + self.tile_size // 2
        walkable_val = is_walkable if is_walkable is not None else self.is_tile_walkable(tile_x, tile_y)
        self.pois[name] = PointOfInterest(
            name=name,
            category=category,
            x=float(px),
            y=float(py),
            tile_x=tile_x,
            tile_y=tile_y,
            description=description,
            recommended_facing=recommended_facing,
            interaction_radius=interaction_radius,
            is_walkable=walkable_val,
            exclusive_to=exclusive_to,
        )

    def is_inside(self, x: float, y: float) -> bool:
        """Comprueba si un punto (x, y) se encuentra dentro de los límites del mundo."""
        return self.bounds.contains_point(x, y)

    def is_tile_walkable(self, tile_x: int, tile_y: int) -> bool:
        """Determina si una celda específica es transitable."""
        if 0 <= tile_x < self.cols and 0 <= tile_y < self.rows:
            return self.walkable[tile_y][tile_x]
        return False

    def collides(self, x: float, y: float, width: float, height: float) -> bool:
        """Verifica si un rectángulo (x, y, width, height) colisiona con algún obstáculo del bar."""
        # 1. Colisión fuera del mundo
        if x < 0 or y < 0 or x + width > self.width or y + height > self.height:
            return True

        # 2. Colisión contra obstáculos registrados
        for obs in self.obstacles:
            if obs.collides_with_rect(x, y, width, height):
                return True
        return False

    def get_poi(self, name: str) -> Optional[PointOfInterest]:
        """Obtiene un punto de interés por su clave."""
        return self.pois.get(name)

    def get_poi_at(self, x: float, y: float, max_dist: float = 24.0) -> Optional[PointOfInterest]:
        """Busca el punto de interés más cercano dentro del radio especificado."""
        nearest_poi = None
        nearest_dist = max_dist
        for poi in self.pois.values():
            d = math.hypot(poi.x - x, poi.y - y)
            if d < nearest_dist:
                nearest_dist = d
                nearest_poi = poi
        return nearest_poi

    def get_pois_by_category(self, category: str) -> List[PointOfInterest]:
        """Retorna todos los puntos de interés de una categoría dada."""
        return [poi for poi in self.pois.values() if poi.category == category]

    def get_spawn_points(self) -> Dict[str, Tuple[float, float]]:
        """Retorna las coordenadas (x, y) de los puntos de spawn de agentes."""
        spawns = {}
        for k in ("barcelona_spawn", "real_madrid_spawn"):
            poi = self.pois.get(k)
            if poi:
                spawns[k] = (poi.x, poi.y)
        return spawns
