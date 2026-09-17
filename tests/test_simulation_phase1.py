"""Pruebas unitarias para la Fase 0 y Fase 1: Simulación 2D del Bar.

Valida:
1. Dimensiones y límites espaciales del mundo.
2. Definición y consulta de obstáculos físicos.
3. Existencia y registro de puntos de interés (POIs).
4. Detección de colisiones (dentro, fuera, y contra obstáculos).
5. Ausencia de efectos secundarios o inicialización de display al importar.
6. Integración del comando CLI `sim`.
7. Ejecución limpia del bucle de simulación en entorno headless (dummy video driver).
"""

import os
from typer.testing import CliRunner

from src.cli.main import app
from src.simulation.config import (
    GRID_COLS,
    GRID_ROWS,
    LOGICAL_HEIGHT,
    LOGICAL_WIDTH,
    TILE_SIZE,
)
from src.simulation.world import BarWorld


def test_no_side_effects_on_import():
    """Verifica que importar los módulos de simulación no inicialice el display de Pygame."""
    import pygame

    # El display no debe estar inicializado simplemente por haber importado los módulos
    assert not pygame.display.get_init()


def test_world_dimensions_and_bounds():
    """Valida dimensiones lógicas, celdas y límites del BarWorld."""
    world = BarWorld()
    assert world.width == LOGICAL_WIDTH == 960
    assert world.height == LOGICAL_HEIGHT == 640
    assert world.cols == GRID_COLS == 30
    assert world.rows == GRID_ROWS == 20
    assert world.tile_size == TILE_SIZE == 32

    # Límites espaciales
    assert world.is_inside(0, 0)
    assert world.is_inside(960, 640)
    assert world.is_inside(480, 320)
    assert not world.is_inside(-1, 100)
    assert not world.is_inside(100, -1)
    assert not world.is_inside(961, 300)
    assert not world.is_inside(500, 641)


def test_obstacles_definition_and_categories():
    """Comprueba que se registren los obstáculos perimetrales y de mobiliario."""
    world = BarWorld()
    assert len(world.obstacles) > 0

    categories = {obs.category for obs in world.obstacles}
    assert "wall" in categories
    assert "bar_counter" in categories
    assert "table" in categories
    assert "shelf" in categories
    assert "sofa" in categories

    # Verificar que los obstáculos tienen coordenadas válidas
    for obs in world.obstacles:
        assert obs.width > 0
        assert obs.height > 0
        assert world.is_inside(obs.x, obs.y)


def test_collision_detection():
    """Valida la detección de colisiones contra obstáculos y fuera del mapa."""
    world = BarWorld()

    # 1. Zona de pared superior debe colisionar
    assert world.collides(0, 0, 32, 32)

    # 2. Mostrador de la barra (columna 3, fila 5 = x: 96, y: 160) debe colisionar
    assert world.collides(96, 160, 32, 32)

    # 3. Mesa central 1 (columna 10, fila 6 = x: 320, y: 192) debe colisionar
    assert world.collides(320, 192, 32, 32)

    # 4. Pasillo libre (columna 7, fila 8 = x: 224, y: 256) NO debe colisionar
    assert not world.collides(224, 256, 24, 24)

    # 5. Rectángulo fuera de los bordes debe colisionar
    assert world.collides(-10, 100, 20, 20)
    assert world.collides(950, 630, 30, 30)


def test_points_of_interest_and_spawns():
    """Verifica el registro de puntos de interés y spawns para futuros agentes."""
    world = BarWorld()

    # POI Entrada
    entrance = world.get_poi("entrance")
    assert entrance is not None
    assert entrance.category == "entrance"

    # Taburetes de la barra
    assert any(name.startswith("bar_stool_") for name in world.pois)
    # Sillas de mesas
    assert any("seat" in name for name in world.pois)
    # Asientos de TV
    assert any(name.startswith("tv_lounge_seat_") for name in world.pois)

    # Spawns reservados para Josep y Paco (Fase 2)
    spawns = world.get_spawn_points()
    assert "barcelona_spawn" in spawns
    assert "real_madrid_spawn" in spawns
    bx, by = spawns["barcelona_spawn"]
    rx, ry = spawns["real_madrid_spawn"]
    assert world.is_inside(bx, by)
    assert world.is_inside(rx, ry)
    # Los puntos de spawn no deben estar dentro de un obstáculo
    assert not world.collides(bx - 10, by - 10, 20, 20)
    assert not world.collides(rx - 10, ry - 10, 20, 20)


def test_walkability_matrix():
    """Verifica que la matriz booleana coincida con los obstáculos."""
    world = BarWorld()

    # Pared superior no transitable
    assert not world.is_tile_walkable(0, 0)
    assert not world.is_tile_walkable(15, 1)

    # Puerta de entrada sí transitable
    assert world.is_tile_walkable(15, world.rows - 1)

    # Pasillo central transitable
    assert world.is_tile_walkable(7, 8)

    # Coordenadas inválidas
    assert not world.is_tile_walkable(-1, 5)
    assert not world.is_tile_walkable(50, 5)


def test_cli_sim_command_resolution():
    """Verifica que la CLI resuelva el comando 'sim' y su ayuda sin ejecutar la ventana."""
    runner = CliRunner()
    result = runner.invoke(app, ["sim", "--help"])
    assert result.exit_code == 0
    assert "Lanza la simulacion 2D en Pygame" in result.output
    assert "--debug" in result.output


def test_cli_existing_commands_remain_functional():
    """Verifica que los comandos preexistentes 'ask' y 'chat' sigan disponibles."""
    runner = CliRunner()

    ask_help = runner.invoke(app, ["ask", "--help"])
    assert ask_help.exit_code == 0
    assert "Hace una sola pregunta y termina" in ask_help.output

    chat_help = runner.invoke(app, ["chat", "--help"])
    assert chat_help.exit_code == 0
    assert "Chat interactivo" in chat_help.output


def test_headless_simulation_app_execution():
    """Ejecuta la ventana en modo dummy (headless) por 3 frames para certificar inicio y cierre limpio."""
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    from src.simulation.app import run_simulation

    # Debe correr 3 frames y finalizar limpiamente sin excepciones
    run_simulation(debug=True, max_frames=3)
