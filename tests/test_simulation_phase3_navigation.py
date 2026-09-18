"""Pruebas unitarias para la Fase 3: Movimiento y Navegación 2D con Pathfinding A*.

Valida exhaustivamente los 20 requisitos de navegación:
1. Conversión matemática entre posición continua y celda de grilla.
2. Conversión entre celda y posición central lógica.
3. Cálculo de ruta válida entre dos puntos transitables.
4. Rechazo controlado de rutas hacia celdas bloqueadas (obstáculos/paredes).
5. Rechazo controlado cuando el origen o destino está fuera de los límites.
6. Prohibición estricta de atajos diagonales para evitar cortes de esquina.
7. Continuidad y corrección topológica en la reconstrucción de la ruta.
8. Determinismo absoluto del algoritmo A*.
9. Movimiento progresivo dependiente estrictamente de dt (tiempo delta).
10. Independencia de la velocidad respecto al framerate.
11. Detección exacta de llegada al destino final.
12. Capacidad de cancelar la navegación en cualquier momento.
13. Actualización automática de la orientación visual según el vector de avance.
14. Transición correcta de estados: IDLE -> WALKING -> IDLE.
15. Respeto estricto de obstáculos durante el desplazamiento.
16. Mantenimiento dentro de los límites del mundo.
17. Inmovilidad por defecto si no se ordena navegación ni se activa el modo demo.
18. Compatibilidad con la proyección y ordenamiento de profundidad de la cámara 2.5D.
19. Ejecución completa y robusta en modo headless.
20. Integración y compatibilidad con las fases previas.
"""

import os
import pytest

from src.simulation.agent import VisualAgent
from src.simulation.app import create_initial_agents, run_simulation
from src.simulation.camera import default_camera
from src.simulation.config import (
    STATE_IDLE,
    STATE_LOOKING_RIGHT,
    STATE_WALKING,
    TILE_SIZE,
)
from src.simulation.navigation import (
    PathFollower,
    cell_to_pos,
    find_nearest_walkable_cell,
    find_path_astar,
    manhattan_distance,
    pos_to_cell,
)
from src.simulation.world import BarWorld


# =============================================================================
# 1 Y 2. CONVERSIÓN DE COORDENADAS Y CELDAS
# =============================================================================


def test_pos_to_cell_conversion():
    """Valida la conversión de coordenadas lógicas a índices de celda (col, row)."""
    assert pos_to_cell(0.0, 0.0) == (0, 0)
    assert pos_to_cell(31.9, 31.9) == (0, 0)
    assert pos_to_cell(32.0, 32.0) == (1, 1)
    assert pos_to_cell(48.0, 80.0) == (1, 2)
    assert pos_to_cell(960.0 - 1.0, 640.0 - 1.0) == (29, 19)


def test_cell_to_pos_conversion():
    """Valida que una celda (col, row) se traduzca al centro geométrico en coordenadas continuas."""
    cx, cy = cell_to_pos(0, 0)
    assert cx == 16.0
    assert cy == 16.0

    cx, cy = cell_to_pos(5, 7)
    assert cx == (5 * TILE_SIZE + 16.0)
    assert cy == (7 * TILE_SIZE + 16.0)

    # Reversibilidad exacta
    col, row = 12, 8
    pos_x, pos_y = cell_to_pos(col, row)
    recovered_col, recovered_row = pos_to_cell(pos_x, pos_y)
    assert (recovered_col, recovered_row) == (col, row)


# =============================================================================
# 3, 4, 5, 6, 7 Y 8. ALGORITMO A* Y REGLAS DE RUTA
# =============================================================================


def test_astar_valid_path_between_walkable_cells():
    """Valida que A* encuentre una ruta válida entre dos zonas abiertas del bar."""
    world = BarWorld()
    # Origen: spawn de Barcelona (6, 7) -> x=208, y=240
    # Destino: taburete bar 1 (5, 5) -> x=176, y=176
    res = find_path_astar(world, 208.0, 240.0, 176.0, 176.0)
    assert res.success is True
    assert len(res.path) > 1
    assert len(res.waypoints) == len(res.path)
    assert res.cost > 0.0
    assert res.error_reason is None

    # El primer nodo debe corresponder a la celda de origen y el último a la de destino
    assert res.path[0] == pos_to_cell(208.0, 240.0)
    assert res.path[-1] == pos_to_cell(176.0, 176.0)


def test_astar_blocked_goal_rejected():
    """Certifica que una solicitud hacia un obstáculo sólido sea rechazada con error controlado."""
    world = BarWorld()
    # Mesa central 1 está en col 10-12, row 6-7 -> Celda (10, 6) bloqueada
    table_cx, table_cy = cell_to_pos(10, 6)
    assert not world.is_tile_walkable(10, 6)

    res = find_path_astar(world, 208.0, 240.0, table_cx, table_cy)
    assert res.success is False
    assert res.error_reason == "goal_blocked"
    assert len(res.path) == 0


def test_astar_blocked_start_rejected():
    """Certifica que si el origen está dentro de una pared u obstáculo se rechace con error."""
    world = BarWorld()
    # Fila 0 es la pared superior (bloqueada)
    wall_x, wall_y = cell_to_pos(5, 0)
    res = find_path_astar(world, wall_x, wall_y, 200.0, 200.0)
    assert res.success is False
    assert res.error_reason == "start_blocked"


def test_astar_out_of_bounds_rejected():
    """Certifica que destinos u orígenes fuera del mapa sean rechazados sin excepción."""
    world = BarWorld()
    res = find_path_astar(world, 200.0, 200.0, -50.0, 300.0)
    assert res.success is False
    assert res.error_reason == "goal_out_of_bounds"

    res_start = find_path_astar(world, 1200.0, 200.0, 200.0, 200.0)
    assert res_start.success is False
    assert res_start.error_reason == "start_out_of_bounds"


def test_astar_strictly_orthogonal_no_diagonal_cutting():
    """Verifica que cada paso de la ruta sea estrictamente ortogonal (distancia Manhattan = 1)."""
    world = BarWorld()
    # Ruta alrededor de obstáculos (ej. desde spawn barca hasta la entrada principal)
    spawns = world.get_spawn_points()
    bx, by = spawns["barcelona_spawn"]
    entrance = world.get_poi("entrance")
    assert entrance is not None

    res = find_path_astar(world, bx, by, entrance.x, entrance.y)
    assert res.success is True

    for i in range(len(res.path) - 1):
        c1, r1 = res.path[i]
        c2, r2 = res.path[i + 1]
        step_dist = abs(c1 - c2) + abs(r1 - r2)
        # Paso exactamente ortogonal: dx=1 o dy=1, nunca diagonal (dx=1 y dy=1 -> dist=2)
        assert step_dist == 1, f"Paso no ortogonal detectado entre {c1, r1} y {c2, r2}"
        # Todas las celdas de la ruta deben ser transitables
        assert world.is_tile_walkable(c2, r2)


def test_astar_path_reconstruction_continuity():
    """Certifica la continuidad ininterrumpida de los waypoints."""
    world = BarWorld()
    res = find_path_astar(world, 208.0, 240.0, 480.0, 400.0)
    assert res.success is True

    # Verificar que los waypoints coinciden exactamente con los centros de celda
    for idx, (col, row) in enumerate(res.path):
        expected_wp = cell_to_pos(col, row)
        assert res.waypoints[idx] == expected_wp


def test_astar_determinism():
    """Comprueba que dos llamadas con idénticos parámetros devuelvan exactamente la misma ruta y coste."""
    world = BarWorld()
    res1 = find_path_astar(world, 208.0, 240.0, 720.0, 300.0)
    res2 = find_path_astar(world, 208.0, 240.0, 720.0, 300.0)

    assert res1.success is True and res2.success is True
    assert res1.path == res2.path
    assert res1.waypoints == res2.waypoints
    assert res1.cost == res2.cost


# =============================================================================
# 9, 10, 11 Y 12. MOVIMIENTO CON DT, VELOCIDAD, LLEGADA Y CANCELACIÓN
# =============================================================================


def test_movement_proportional_to_dt():
    """Valida que el avance físico dependa linealmente de dt."""
    follower = PathFollower(speed=100.0)
    # Ruta de (0, 0) a (100, 0)
    follower.set_path([(0.0, 0.0), (100.0, 0.0)])

    # Con dt = 0.5s y speed = 100 px/s, debe avanzar 50 píxeles
    new_x, new_y, facing, state, arrived = follower.update(0.0, 0.0, dt=0.5)
    assert pytest.approx(new_x) == 50.0
    assert pytest.approx(new_y) == 0.0
    assert facing == "right"
    assert state == STATE_WALKING
    assert not arrived


def test_speed_independent_of_framerate():
    """Certifica que una simulación a 10 FPS recorra lo mismo que una a 100 FPS en 1 segundo."""
    # Simulación A: 10 pasos de dt = 0.1s (total 1.0s)
    f_a = PathFollower(speed=80.0)
    f_a.set_path([(0.0, 0.0), (200.0, 0.0)])
    cur_x_a, cur_y_a = 0.0, 0.0
    for _ in range(10):
        cur_x_a, cur_y_a, _, _, _ = f_a.update(cur_x_a, cur_y_a, dt=0.1)

    # Simulación B: 100 pasos de dt = 0.01s (total 1.0s)
    f_b = PathFollower(speed=80.0)
    f_b.set_path([(0.0, 0.0), (200.0, 0.0)])
    cur_x_b, cur_y_b = 0.0, 0.0
    for _ in range(100):
        cur_x_b, cur_y_b, _, _, _ = f_b.update(cur_x_b, cur_y_b, dt=0.01)

    assert pytest.approx(cur_x_a, abs=0.5) == 80.0
    assert pytest.approx(cur_x_b, abs=0.5) == 80.0
    assert pytest.approx(cur_x_a, abs=0.5) == cur_x_b


def test_arrival_detection_and_completion():
    """Valida la detección exacta de llegada al destino final y cambio de estado."""
    follower = PathFollower(speed=100.0, arrival_threshold=2.0)
    follower.set_path([(10.0, 10.0), (20.0, 10.0)])

    # Avanzar con dt suficiente para alcanzar el destino
    new_x, new_y, facing, state, arrived = follower.update(10.0, 10.0, dt=0.2)
    assert arrived is True
    assert state == STATE_IDLE
    assert not follower.is_active
    assert pytest.approx(new_x) == 20.0


def test_navigation_cancellation():
    """Valida que cancel_navigation detenga inmediatamente el avance y limpie la ruta."""
    world = BarWorld()
    agent = VisualAgent("test", "barcelona", "Josep", 208.0, 240.0)
    res = agent.navigate_to(world, 272.0, 240.0)
    assert res.success is True
    assert agent.is_navigating is True
    assert agent.state == STATE_WALKING

    agent.cancel_navigation()
    assert agent.is_navigating is False
    assert agent.state == STATE_IDLE
    assert len(agent.active_waypoints) == 0
    assert agent.target_pos is None


# =============================================================================
# 13 Y 14. ORIENTACIÓN Y TRANSICIONES DE ESTADO
# =============================================================================


def test_facing_direction_changes_with_movement():
    """Verifica que el agente cambie de orientación visual según el vector de desplazamiento."""
    world = BarWorld()
    agent = VisualAgent("test", "real_madrid", "Paco", 480.0, 320.0)

    # 1. Hacia la derecha
    agent.navigate_to(world, 544.0, 320.0)
    agent.update(0.05, world=world)
    assert agent.facing == "right"

    # 2. Hacia la izquierda
    agent.navigate_to(world, 416.0, 320.0)
    agent.update(0.05, world=world)
    assert agent.facing == "left"

    # 3. Hacia abajo
    agent.navigate_to(world, agent.x, agent.y + 64.0)
    agent.update(0.05, world=world)
    assert agent.facing == "down"

    # 4. Hacia arriba
    agent.navigate_to(world, agent.x, agent.y - 64.0)
    agent.update(0.05, world=world)
    assert agent.facing == "up"


def test_state_transition_idle_walking_idle():
    """Valida la secuencia completa: reposo (IDLE) -> marcha (WALKING) -> reposo (IDLE)."""
    world = BarWorld()
    agent = VisualAgent("test", "barcelona", "Josep", 208.0, 240.0)
    assert agent.state == STATE_IDLE

    # Iniciar marcha hacia una celda vecina (208 + 32, 240)
    target_x, target_y = 240.0, 240.0
    res = agent.navigate_to(world, target_x, target_y)
    assert res.success is True
    assert agent.state == STATE_WALKING

    # Actualizar hasta llegar (con velocidad 80 px/s, 32 px tardan ~0.4s)
    for _ in range(30):
        agent.update(0.02, world=world)
        if not agent.is_navigating:
            break

    assert agent.is_navigating is False
    assert agent.state in (STATE_IDLE, STATE_LOOKING_RIGHT)
    assert pytest.approx(agent.x, abs=1.0) == target_x


# =============================================================================
# 15, 16 Y 17. COLISIONES, LÍMITES E INMOVILIDAD POR DEFECTO
# =============================================================================


def test_agent_never_crosses_obstacles():
    """Certifica que durante todo el recorrido el agente mantenga su collider libre de obstáculos."""
    world = BarWorld()
    spawns = world.get_spawn_points()
    bx, by = spawns["barcelona_spawn"]
    agent = VisualAgent("josep", "barcelona", "Josep", bx, by)

    # Navegar desde el spawn del Barça hasta el sofá del TV Lounge
    entrance = world.get_poi("entrance")
    assert entrance is not None
    res = agent.navigate_to(world, entrance.x, entrance.y)
    assert res.success is True

    # Simular paso a paso y verificar que en ningún frame colisione
    while agent.is_navigating:
        agent.update(0.016, world=world)
        # Collider de 20x20 alrededor de (agent.x, agent.y)
        assert not world.collides(agent.x - 10, agent.y - 10, 20, 20), f"Colisión detectada en ({agent.x}, {agent.y})"


def test_agent_stays_within_world_bounds():
    """Certifica que el agente permanezca estrictamente dentro de los límites del BarWorld."""
    world = BarWorld()
    agent = VisualAgent("paco", "real_madrid", "Paco", 784.0, 544.0)
    # Intentar enviar cerca de las esquinas transitables
    res = agent.navigate_to(world, 500.0, 544.0)
    assert res.success is True

    while agent.is_navigating:
        agent.update(0.02, world=world)
        assert world.is_inside(agent.x, agent.y)


def test_agents_remain_static_without_demo_or_orders():
    """Certifica que sin órdenes explícitas ni modo demo, los agentes no se muevan de sus posiciones."""
    world = BarWorld()
    agents = create_initial_agents(world)
    pos_before = [(a.x, a.y) for a in agents]

    # Simular 30 frames de actualización ordinaria
    for _ in range(30):
        for a in agents:
            a.update(0.016, world=world)

    pos_after = [(a.x, a.y) for a in agents]
    assert pos_before == pos_after
    for a in agents:
        assert not a.is_navigating
        assert a.state != STATE_WALKING


# =============================================================================
# 18, 19 Y 20. CÁMARA 2.5D, EJECUCIÓN HEADLESS Y SUITE COMPLETA
# =============================================================================


def test_camera_25d_depth_updates_smoothly_during_movement():
    """Verifica que la profundidad de renderizado (depth = agent.y) se actualice continuamente."""
    world = BarWorld()
    agent = VisualAgent("josep", "barcelona", "Josep", 200.0, 200.0)
    agent.navigate_to(world, 200.0, 300.0)

    initial_depth = agent.depth
    agent.update(0.5, world=world)
    # Al moverse hacia abajo (Y creciente), la profundidad debe aumentar
    assert agent.depth > initial_depth
    screen_x, screen_y = default_camera.world_to_screen(agent.x, agent.y)
    assert screen_x == agent.x
    assert screen_y == agent.y


def test_headless_execution_with_demo_movement_flag():
    """Valida la ejecución en modo headless de run_simulation con --demo-movement activado."""
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    # Corre 10 frames con demo activo y debug activado sin errores
    run_simulation(debug=True, demo_movement=True, max_frames=10)


def test_nearest_walkable_cell_utility():
    """Valida la función de conveniencia find_nearest_walkable_cell para destinos en bordes de obstáculos."""
    world = BarWorld()
    # Celda (10, 6) es la esquina superior izquierda de mesa 1 (bloqueada)
    assert not world.is_tile_walkable(10, 6)
    nearest = find_nearest_walkable_cell(world, 10, 6, max_radius=3)
    assert nearest is not None
    assert world.is_tile_walkable(nearest[0], nearest[1])
    # Distancia Manhattan razonable
    assert manhattan_distance(10, 6, nearest[0], nearest[1]) <= 2
