"""Paquete de simulación 2D / 2.5D para agent_discusion.

Fase 1 y Fase 2 (estática): Escena 2.5D del bar, cámara oblicua y agentes pixel art Josep y Paco.
No inicializa Pygame en import time para garantizar compatibilidad con entornos sin pantalla.
"""

from src.simulation.agent import BartenderNPC, CleanerNPC, CoughingManNPC, VisualAgent
from src.simulation.app import (
    create_atmosphere_npcs,
    create_initial_agents,
    run_simulation,
)
from src.simulation.bdi import (
    AgentBeliefs,
    AgentPersonality,
    BDIController,
    Desire,
    DesireType,
    Intention,
    IntentionState,
    create_josep_personality,
    create_paco_personality,
)
from src.simulation.camera import Camera25D, get_render_depth, screen_to_world, world_to_screen
from src.simulation.events import Obstacle, PointOfInterest, WorldBounds
from src.simulation.navigation import (
    PathFollower,
    PathResult,
    cell_to_pos,
    find_nearest_walkable_cell,
    find_path_astar,
    pos_to_cell,
)
from src.simulation.sprites import (
    get_agent_sprite,
    get_bartender_sprite,
    get_cleaner_bucket_sprite,
    get_cleaner_sprite,
    get_old_man_sprite,
)
from src.simulation.world import BarWorld

__all__ = [
    "AgentBeliefs",
    "AgentPersonality",
    "BDIController",
    "BarWorld",
    "BartenderNPC",
    "Camera25D",
    "CleanerNPC",
    "CoughingManNPC",
    "Desire",
    "DesireType",
    "Intention",
    "IntentionState",
    "Obstacle",
    "PathFollower",
    "PathResult",
    "PointOfInterest",
    "VisualAgent",
    "WorldBounds",
    "cell_to_pos",
    "create_atmosphere_npcs",
    "create_initial_agents",
    "create_josep_personality",
    "create_paco_personality",
    "find_nearest_walkable_cell",
    "find_path_astar",
    "get_agent_sprite",
    "get_bartender_sprite",
    "get_cleaner_bucket_sprite",
    "get_cleaner_sprite",
    "get_old_man_sprite",
    "get_render_depth",
    "pos_to_cell",
    "run_simulation",
    "screen_to_world",
    "world_to_screen",
]
