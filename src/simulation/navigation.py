"""Módulo de navegación 2D y Pathfinding A* para la simulación del Bar.

Responsabilidades:
1. Conversión matemática entre coordenadas lógicas del mundo y celdas de la grilla.
2. Algoritmo A* determinista con heurística Manhattan para movimiento ortogonal de 4 direcciones.
3. Validación estricta de transitabilidad y límites físicos del mapa.
4. Generación de rutas seguras que evitan cortes de esquinas y colisiones.
5. Seguimiento continuo de waypoints en función del tiempo delta (dt) a velocidad configurable.
"""

from dataclasses import dataclass, field
import heapq
import math
from typing import List, Optional, Tuple

from src.simulation.config import (
    DEFAULT_AGENT_SPEED,
    GRID_COLS,
    GRID_ROWS,
    STATE_IDLE,
    STATE_LOOKING_LEFT,
    STATE_LOOKING_RIGHT,
    STATE_WALKING,
    TILE_SIZE,
)
from src.simulation.world import BarWorld


# =============================================================================
# 1. CONVERSIÓN DE COORDENADAS Y UTILIDADES DE GRILLA
# =============================================================================

def pos_to_cell(x: float, y: float, tile_size: int = TILE_SIZE) -> Tuple[int, int]:
    """Convierte una coordenada lógica continua (x, y) a índices de celda (col, row)."""
    col = int(math.floor(x / tile_size))
    row = int(math.floor(y / tile_size))
    return col, row


def cell_to_pos(col: int, row: int, tile_size: int = TILE_SIZE) -> Tuple[float, float]:
    """Retorna las coordenadas lógicas continuas (x, y) del centro de la celda especificada."""
    cx = float(col * tile_size + tile_size / 2.0)
    cy = float(row * tile_size + tile_size / 2.0)
    return cx, cy


def is_cell_in_bounds(col: int, row: int, cols: int = GRID_COLS, rows: int = GRID_ROWS) -> bool:
    """Verifica si una celda (col, row) se encuentra dentro de los límites de la cuadrícula."""
    return 0 <= col < cols and 0 <= row < rows


def manhattan_distance(c1: int, r1: int, c2: int, r2: int) -> float:
    """Calcula la distancia Manhattan entre dos celdas (heurística admisible y consistente en 4-dir)."""
    return float(abs(c1 - c2) + abs(r1 - r2))


# =============================================================================
# 2. ESTRUCTURA DE RESULTADO DE RUTA
# =============================================================================

@dataclass
class PathResult:
    """Resultado estructurado del cálculo de una ruta A*."""
    success: bool
    path: List[Tuple[int, int]] = field(default_factory=list)  # Celdas (col, row)
    waypoints: List[Tuple[float, float]] = field(default_factory=list)  # Puntos lógicos (x, y)
    cost: float = 0.0
    error_reason: Optional[str] = None


# =============================================================================
# 3. ALGORITMO A* DETERMINISTA EN 4 DIRECCIONES
# =============================================================================

# Direcciones de movimiento ortogonal estricto: Arriba, Abajo, Izquierda, Derecha
ORTHOGONAL_NEIGHBORS: Tuple[Tuple[int, int], ...] = (
    (0, -1),  # Arriba
    (0, 1),   # Abajo
    (-1, 0),  # Izquierda
    (1, 0),   # Derecha
)


def find_path_astar(
    world: BarWorld,
    start_x: float,
    start_y: float,
    goal_x: float,
    goal_y: float,
    max_iterations: int = 2400,
) -> PathResult:
    """Calcula una ruta ortogonal óptima evitando colisiones mediante A*.

    Args:
        world: Instancia del BarWorld con matriz walkable y dimensiones.
        start_x, start_y: Coordenadas lógicas de origen del agente.
        goal_x, goal_y: Coordenadas lógicas del destino deseado.
        max_iterations: Límite de expansiones para prevenir bucles en casos anómalos.

    Returns:
        PathResult con la secuencia de celdas, waypoints lógicos continuos y costo total.
    """
    # 1. Validación de límites en origen y destino
    if not world.is_inside(start_x, start_y):
        return PathResult(success=False, error_reason="start_out_of_bounds")
    if not world.is_inside(goal_x, goal_y):
        return PathResult(success=False, error_reason="goal_out_of_bounds")

    start_cell = pos_to_cell(start_x, start_y, world.tile_size)
    goal_cell = pos_to_cell(goal_x, goal_y, world.tile_size)

    # 2. Validación de transitabilidad
    if not is_cell_in_bounds(start_cell[0], start_cell[1], world.cols, world.rows):
        return PathResult(success=False, error_reason="start_out_of_bounds")
    if not is_cell_in_bounds(goal_cell[0], goal_cell[1], world.cols, world.rows):
        return PathResult(success=False, error_reason="goal_out_of_bounds")

    if not world.is_tile_walkable(start_cell[0], start_cell[1]):
        return PathResult(success=False, error_reason="start_blocked")
    if not world.is_tile_walkable(goal_cell[0], goal_cell[1]):
        return PathResult(success=False, error_reason="goal_blocked")

    # Si origen y destino ya comparten la misma celda
    if start_cell == goal_cell:
        wp = cell_to_pos(start_cell[0], start_cell[1], world.tile_size)
        return PathResult(
            success=True,
            path=[start_cell],
            waypoints=[wp],
            cost=0.0,
        )

    # 3. Inicialización de A*
    # Elementos en heap: (f_score, tie_breaker_counter, cell)
    open_heap: List[Tuple[float, int, Tuple[int, int]]] = []
    counter = 0

    g_score: dict[Tuple[int, int], float] = {start_cell: 0.0}
    f_start = manhattan_distance(start_cell[0], start_cell[1], goal_cell[0], goal_cell[1])
    heapq.heappush(open_heap, (f_start, counter, start_cell))

    came_from: dict[Tuple[int, int], Tuple[int, int]] = {}
    closed_set: set[Tuple[int, int]] = set()

    iterations = 0

    while open_heap and iterations < max_iterations:
        iterations += 1
        current_f, _, current_cell = heapq.heappop(open_heap)

        if current_cell == goal_cell:
            # Reconstrucción de la ruta desde destino hacia origen
            path: List[Tuple[int, int]] = []
            curr = current_cell
            while curr in came_from:
                path.append(curr)
                curr = came_from[curr]
            path.append(start_cell)
            path.reverse()

            waypoints = [
                cell_to_pos(c[0], c[1], world.tile_size) for c in path
            ]

            return PathResult(
                success=True,
                path=path,
                waypoints=waypoints,
                cost=g_score[goal_cell],
            )

        closed_set.add(current_cell)
        cx, cy = current_cell

        for dx, dy in ORTHOGONAL_NEIGHBORS:
            nx, ny = cx + dx, cy + dy
            neighbor = (nx, ny)

            if not is_cell_in_bounds(nx, ny, world.cols, world.rows):
                continue
            if not world.is_tile_walkable(nx, ny):
                continue
            if neighbor in closed_set:
                continue

            tentative_g = g_score[current_cell] + 1.0  # Coste unitario ortogonal

            if tentative_g < g_score.get(neighbor, float("inf")):
                came_from[neighbor] = current_cell
                g_score[neighbor] = tentative_g
                h = manhattan_distance(nx, ny, goal_cell[0], goal_cell[1])
                f = tentative_g + h
                counter += 1
                heapq.heappush(open_heap, (f, counter, neighbor))

    if iterations >= max_iterations:
        return PathResult(success=False, error_reason="max_iterations_exceeded")

    return PathResult(success=False, error_reason="no_path_found")


def find_nearest_walkable_cell(
    world: BarWorld, target_col: int, target_row: int, max_radius: int = 4
) -> Optional[Tuple[int, int]]:
    """Encuentra la celda transitable más cercana en distancia Manhattan a una coordenada dada."""
    if (
        is_cell_in_bounds(target_col, target_row, world.cols, world.rows)
        and world.is_tile_walkable(target_col, target_row)
    ):
        return target_col, target_row

    best_cell = None
    best_dist = float("inf")

    for radius in range(1, max_radius + 1):
        for dc in range(-radius, radius + 1):
            for dr in range(-radius, radius + 1):
                if abs(dc) + abs(dr) != radius:
                    continue
                nc = target_col + dc
                nr = target_row + dr
                if is_cell_in_bounds(nc, nr, world.cols, world.rows) and world.is_tile_walkable(nc, nr):
                    dist = manhattan_distance(target_col, target_row, nc, nr)
                    if dist < best_dist:
                        best_dist = dist
                        best_cell = (nc, nr)
        if best_cell is not None:
            return best_cell

    return None


# =============================================================================
# 4. CONTROLADOR DE MOVIMIENTO CONTINUO (PathFollower)
# =============================================================================

class PathFollower:
    """Gestiona el seguimiento suave de una ruta de waypoints en función del tiempo (dt)."""

    def __init__(self, speed: float = DEFAULT_AGENT_SPEED, arrival_threshold: float = 2.0):
        self.speed: float = speed
        self.arrival_threshold: float = arrival_threshold
        self.waypoints: List[Tuple[float, float]] = []
        self.current_waypoint_idx: int = 0
        self.is_active: bool = False
        self.current_facing: str = "down"

    def set_path(self, waypoints: List[Tuple[float, float]]) -> None:
        """Asigna una nueva ruta y comienza la navegación."""
        self.waypoints = list(waypoints)
        self.current_waypoint_idx = 0
        self.is_active = len(self.waypoints) > 0

    def cancel(self) -> None:
        """Detiene y cancela la navegación actual."""
        self.waypoints.clear()
        self.current_waypoint_idx = 0
        self.is_active = False

    def update(
        self, current_x: float, current_y: float, dt: float
    ) -> Tuple[float, float, str, str, bool]:
        """Avanza la posición hacia el waypoint activo.

        Retorna:
            Tuple con (nuevo_x, nuevo_y, nueva_orientacion, nuevo_estado, ha_llegado_al_destino)
        """
        if not self.is_active or not self.waypoints:
            return current_x, current_y, self.current_facing, STATE_IDLE, False

        # Si ya hemos superado el último waypoint
        if self.current_waypoint_idx >= len(self.waypoints):
            self.is_active = False
            return current_x, current_y, self.current_facing, STATE_IDLE, True

        remaining_step = self.speed * dt
        new_x = current_x
        new_y = current_y

        while remaining_step > 0 and self.current_waypoint_idx < len(self.waypoints):
            target_x, target_y = self.waypoints[self.current_waypoint_idx]
            dx = target_x - new_x
            dy = target_y - new_y
            dist = math.hypot(dx, dy)

            # Si ya estamos en el waypoint actual
            if dist <= self.arrival_threshold:
                new_x = target_x
                new_y = target_y
                self.current_waypoint_idx += 1
                if self.current_waypoint_idx >= len(self.waypoints):
                    self.is_active = False
                    return new_x, new_y, self.current_facing, STATE_IDLE, True
                continue

            # 1. Determinar orientación según el vector de movimiento hacia el objetivo actual
            if abs(dx) >= abs(dy) and abs(dx) > 0.001:
                self.current_facing = "right" if dx > 0 else "left"
            elif abs(dy) > abs(dx) and abs(dy) > 0.001:
                self.current_facing = "down" if dy > 0 else "up"

            # 2. Desplazamiento
            if dist <= remaining_step:
                new_x = target_x
                new_y = target_y
                remaining_step -= dist
                self.current_waypoint_idx += 1
                if self.current_waypoint_idx >= len(self.waypoints):
                    self.is_active = False
                    return new_x, new_y, self.current_facing, STATE_IDLE, True
            else:
                dir_x = dx / dist
                dir_y = dy / dist
                new_x += dir_x * remaining_step
                new_y += dir_y * remaining_step
                remaining_step = 0.0
                return new_x, new_y, self.current_facing, STATE_WALKING, False

        return new_x, new_y, self.current_facing, STATE_WALKING, False
