"""Contratos y estructuras de datos base para la simulación 2D.

Define los tipos fundamentales necesarios para la Fase 0 y Fase 1 (mundo, obstáculos y POIs).
Los contratos de diálogo y BDI (DialogueEvent, DialogueRequest, Beliefs, etc.)
se reservan deliberadamente para las fases correspondientes según el plan aprobado.
"""

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class PointOfInterest:
    """Representa un punto de interés clave en el bar preparado para futuras interacciones.

    Fase 1: Identificación y consulta estática.
    Fases posteriores: Asignación de objetivos y navegación para agentes.
    """

    name: str
    category: str  # 'bar', 'table_seat', 'tv_seat', 'entrance', 'spawn'
    x: float
    y: float
    tile_x: int
    tile_y: int
    description: str
    occupied: bool = False
    occupied_by: Optional[str] = None
    recommended_facing: str = "left"
    interaction_radius: float = 32.0
    is_walkable: bool = True
    exclusive_to: Optional[str] = None


@dataclass(frozen=True)
class Obstacle:
    """Representa un obstáculo físico no transitable en el mapa del bar."""

    name: str
    category: str  # 'wall', 'bar_counter', 'table', 'sofa', 'shelf'
    x: int
    y: int
    width: int
    height: int

    @property
    def bounds(self) -> Tuple[int, int, int, int]:
        """Retorna tupla (x, y, width, height)."""
        return self.x, self.y, self.width, self.height

    def collides_with_rect(self, rx: float, ry: float, rw: float, rh: float) -> bool:
        """Determina si un rectángulo colisiona con este obstáculo (AABB collision)."""
        return not (rx + rw <= self.x or rx >= self.x + self.width or ry + rh <= self.y or ry >= self.y + self.height)


@dataclass(frozen=True)
class WorldBounds:
    """Límites espaciales lógicos del mundo."""

    min_x: float = 0.0
    min_y: float = 0.0
    max_x: float = 960.0
    max_y: float = 640.0

    def contains_point(self, px: float, py: float) -> bool:
        """Verifica si un punto (px, py) se encuentra dentro de los límites del mundo."""
        return self.min_x <= px <= self.max_x and self.min_y <= py <= self.max_y


# -----------------------------------------------------------------------------
# NOTA DE DISEÑO - Contratos reservados para fases posteriores:
#
# Fase 2: AgentVisualState (renderizado de avatares pixel art e idle/walk frames)
# Fase 4: Beliefs, Desire, Intention (motor cognitivo BDI de los agentes)
# Fase 5: DialogueRequest, DialogueEvent (puente concurrente de debate LangGraph)
# -----------------------------------------------------------------------------
