"""Pruebas unitarias para la Fase 2 (Visual): Cámara 2.5D, Sprites Pixel Art y Agentes Estáticos.

Valida:
1. Conservación de dimensiones y colisiones del BarWorld.
2. Transformación determinista y reversible de coordenadas (world_to_screen y screen_to_world).
3. Ordenamiento de profundidad 2.5D para el algoritmo del pintor.
4. Instanciación correcta de Josep (Barça) y Paco (Real Madrid) en sus spawns.
5. Validación de que los agentes no colisionan con obstáculos al aparecer.
6. Verificación de que update(dt) no produce movimiento físico.
7. Generación y cacheo de sprites pixel art sin excepciones.
8. Ejecución headless completa del renderizador y bucle principal de Pygame.
"""

import os
import pytest

from src.simulation.agent import (
    BartenderNPC,
    CleanerNPC,
    CoughingManNPC,
    VisualAgent,
)
from src.simulation.app import (
    create_atmosphere_npcs,
    create_initial_agents,
    run_simulation,
)
from src.simulation.camera import (
    Camera25D,
    get_render_depth,
    screen_to_world,
    world_to_screen,
)
from src.simulation.config import (
    STATE_IDLE,
    STATE_LOOKING_LEFT,
    STATE_LOOKING_RIGHT,
)
from src.simulation.sprites import (
    SCALED_SPRITE_HEIGHT,
    SCALED_SPRITE_WIDTH,
    get_agent_sprite,
    get_bartender_sprite,
    get_cleaner_bucket_sprite,
    get_cleaner_sprite,
    get_old_man_sprite,
)
from src.simulation.world import BarWorld


def test_camera_coordinate_transformations():
    """Valida la precisión y reversibilidad de las transformaciones de coordenadas de la cámara."""
    cam = Camera25D(offset_x=10.0, offset_y=-5.0, zoom=1.0)

    # 1. Transformación mundo -> pantalla
    wx, wy, wz = 100.0, 200.0, 15.0
    sx, sy = cam.world_to_screen(wx, wy, wz)
    assert sx == (100.0 + 10.0)
    assert sy == (200.0 - 15.0 - 5.0)

    # 2. Transformación inversa pantalla -> mundo
    recovered_wx, recovered_wy = cam.screen_to_world(sx, sy, wz)
    assert pytest.approx(recovered_wx) == wx
    assert pytest.approx(recovered_wy) == wy

    # 3. Funciones de conveniencia globales
    g_sx, g_sy = world_to_screen(250.0, 350.0, 20.0)
    g_wx, g_wy = screen_to_world(g_sx, g_sy, 20.0)
    assert pytest.approx(g_wx) == 250.0
    assert pytest.approx(g_wy) == 350.0


def test_camera_depth_sorting():
    """Valida que la profundidad aumente conforme la coordenada Y es mayor (más cerca del espectador)."""
    cam = Camera25D()

    # Objeto A en Y=200, Objeto B en Y=300
    depth_a = cam.get_render_depth(200.0)
    depth_b = cam.get_render_depth(300.0)
    assert depth_b > depth_a

    # Función de utilidad global
    assert get_render_depth(400.0) > get_render_depth(300.0)


def test_camera_window_to_logical_scaling():
    """Valida la conversión de coordenadas físicas de ventana a resolución lógica 960x640."""
    cam = Camera25D()
    # Ventana escalada al doble (1920x1280)
    lx, ly = cam.window_to_logical(960.0, 640.0, (1920, 1280))
    assert pytest.approx(lx) == 480.0
    assert pytest.approx(ly) == 320.0


def test_agent_creation_and_identities():
    """Verifica la inicialización de Josep y Paco con sus atributos visuales correctos."""
    world = BarWorld()
    agents = create_initial_agents(world)
    assert len(agents) == 2

    josep = next(a for a in agents if a.name == "Josep")
    paco = next(a for a in agents if a.name == "Paco")

    # Identidad de Josep
    assert josep.team == "barcelona"
    assert josep.facing == "right"
    assert josep.state == STATE_LOOKING_RIGHT

    # Identidad de Paco
    assert paco.team == "real_madrid"
    assert paco.facing == "left"
    assert paco.state == STATE_LOOKING_LEFT

    # Verificar que están en sus puntos oficiales de spawn
    spawns = world.get_spawn_points()
    assert (josep.x, josep.y) == spawns["barcelona_spawn"]
    assert (paco.x, paco.y) == spawns["real_madrid_spawn"]


def test_agents_within_world_and_not_in_obstacles():
    """Certifica que los agentes estén dentro del mapa y no colisionen con el mobiliario."""
    world = BarWorld()
    agents = create_initial_agents(world)

    for agent in agents:
        # Dentro del mundo
        assert world.is_inside(agent.x, agent.y)
        # Fuera de colisiones (caja de 20x20 alrededor del centro)
        assert not world.collides(agent.x - 10, agent.y - 10, 20, 20)


def test_agent_update_does_not_move_in_phase2():
    """Verifica estrictamente que update(dt) no produzca desplazamiento en esta fase estática."""
    agent = VisualAgent("test_id", "barcelona", "Josep", 150.0, 250.0)
    initial_x, initial_y = agent.x, agent.y

    # Simular 10 frames de actualización
    for _ in range(10):
        agent.update(0.016)

    assert agent.x == initial_x
    assert agent.y == initial_y


def test_agent_facing_and_state_transitions():
    """Valida la conmutación de orientación y estados visuales del agente."""
    agent = VisualAgent("test", "real_madrid", "Paco", 100.0, 100.0)

    agent.set_facing("left")
    assert agent.facing == "left"
    assert agent.state == STATE_LOOKING_LEFT

    agent.set_facing("right")
    assert agent.facing == "right"
    assert agent.state == STATE_LOOKING_RIGHT

    agent.set_facing("down")
    assert agent.facing == "down"
    assert agent.state == STATE_IDLE


def test_pixel_art_sprites_generation():
    """Valida que los sprites procedurales se generen con las dimensiones 32x52 esperadas."""
    for team in ("barcelona", "real_madrid"):
        for facing in ("down", "left", "right"):
            for frame in (0, 1):
                sprite = get_agent_sprite(team, facing, frame)
                assert sprite.get_width() == SCALED_SPRITE_WIDTH == 32
                assert sprite.get_height() == SCALED_SPRITE_HEIGHT == 52


def test_agent_arms_visible_in_profile_sprites():
    """Verifica que los personajes tengan ambos brazos visibles y renderizados en perfil."""
    for team in ("barcelona", "real_madrid"):
        for facing in ("left", "right"):
            sprite = get_agent_sprite(team, facing, 0)
            # El sprite no debe estar vacío ni transparente en la zona de brazos
            opaque_pixels = 0
            for y in range(16, 36):
                for x in range(sprite.get_width()):
                    if sprite.get_at((x, y))[3] > 0:
                        opaque_pixels += 1
            assert opaque_pixels > 80, f"Faltan píxeles en torso/brazos para {team} {facing}"


def test_atmosphere_npcs_creation_and_placement():
    """Verifica que los 3 NPCs de ambientación se creen correctamente y no colisionen."""
    world = BarWorld()
    npcs = create_atmosphere_npcs(world)
    assert len(npcs) == 3

    ids = {npc.agent_id for npc in npcs}
    assert "bartender_manolo" in ids
    assert "cleaner_carmen" in ids
    assert "oldman_antonio" in ids

    for npc in npcs:
        assert world.is_inside(npc.x, npc.y), f"{npc.name} fuera del bar"
        assert not world.collides(npc.x - 10, npc.y - 10, 20, 20), f"{npc.name} colisiona con obstáculo"
        assert npc.depth == npc.y


def test_atmosphere_npcs_update_cycles():
    """Valida los ciclos de animación pasiva de los NPCs de ambientación."""
    bartender = BartenderNPC()
    cleaner = CleanerNPC()
    old_man = CoughingManNPC()

    # 1. Barman agitando cóctel cada 0.2s
    initial_shake = bartender.shake_frame
    bartender.update(0.25)
    assert bartender.shake_frame != initial_shake

    # 2. Limpiadora moviendo fregona cada 0.45s
    initial_mop = cleaner.mop_frame
    cleaner.update(0.5)
    assert cleaner.mop_frame != initial_mop

    # 3. Señor mayor tosiendo periódicamente (> 3.2s en ciclo de 5s)
    old_man.update(1.0)
    assert not old_man.is_coughing
    old_man.update(2.5)  # Tiempo acumulado 3.5s
    assert old_man.is_coughing


def test_atmosphere_sprites_generation():
    """Valida que los sprites procedurales de los NPCs tengan dimensiones correctas."""
    bartender_s = get_bartender_sprite(0)
    assert bartender_s.get_width() == 32 and bartender_s.get_height() == 52

    cleaner_s = get_cleaner_sprite(0)
    assert cleaner_s.get_width() == 32 and cleaner_s.get_height() == 52

    bucket_s = get_cleaner_bucket_sprite()
    assert bucket_s.get_width() == 24 and bucket_s.get_height() == 24

    old_man_s1 = get_old_man_sprite(is_coughing=False)
    old_man_s2 = get_old_man_sprite(is_coughing=True)
    assert old_man_s1.get_width() == 32 and old_man_s1.get_height() == 52
    assert old_man_s2.get_width() == 32 and old_man_s2.get_height() == 52


def test_headless_simulation_app_execution_with_agents_and_npcs():
    """Certifica que el bucle de Pygame renderice la escena 2.5D con agentes y NPCs sin errores."""
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    run_simulation(debug=True, max_frames=5)
