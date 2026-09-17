"""Pruebas unitarias para las interacciones ambientales enriquecidas y NPCs delimitados:

1. VisualAgent: postura de sentado (sit) y sprite sitting con dimensiones correctas.
2. VisualAgent: postura de beber (drink) y sprite drinking con jarra y espuma.
3. VisualAgent: despliegue de bocadillos cómic con diálogo (say) y temporizador.
4. BartenderNPC: delimitación espacial estricta detrás de la barra (X=80, Y in [160, 420]).
5. BartenderNPC: secuencia de preparación de cóctel, desplazamiento y entrega en el mostrador.
6. BartenderNPC: colocación de copa en la barra (counter_drinks) y consumo progresivo.
7. CleanerNPC: delimitación espacial en zona de mesas (X in [260, 600], Y in [360, 560]).
8. CleanerNPC: desplazamiento entre waypoints de limpieza con cubo y pausas de descanso.
9. CoughingManNPC: delimitación espacial en rincón sur-este (X in [760, 840], Y in [510, 560]).
10. CoughingManNPC: ciclo de tos, estiramiento de piernas y respuesta interactiva al hablarle.
11. Generación de sprites interactivos: copa en barra y bocadillo cómic sin errores.
12. Ejecución headless completa con interacciones de barra y NPCs activos durante 60 frames.
"""

import math
import os
import pygame
import pytest

from src.simulation.agent import BartenderNPC, CleanerNPC, CoughingManNPC, VisualAgent
from src.simulation.app import create_atmosphere_npcs, create_initial_agents, run_simulation
from src.simulation.bdi import BDIController, Desire, DesireType, Intention, IntentionState, create_josep_personality
from src.simulation.sprites import (
    get_agent_sprite,
    get_bartender_sprite,
    get_cleaner_sprite,
    get_counter_drink_sprite,
    get_old_man_sprite,
    render_dialogue_bubble,
)
from src.simulation.world import BarWorld


# =============================================================================
# 1, 2 Y 3. POSTURAS Y DIÁLOGOS DE VISUALAGENT
# =============================================================================

def test_visual_agent_sitting_posture():
    """Valida la activación de la postura sentada y la generación de su sprite."""
    agent = VisualAgent("josep", "barcelona", "Josep", 200.0, 200.0)
    assert agent.is_sitting is False

    agent.sit(True)
    assert agent.is_sitting is True

    sprite_sitting = get_agent_sprite("barcelona", "down", is_sitting=True)
    assert sprite_sitting.get_width() == 32 and sprite_sitting.get_height() == 52

    agent.sit(False)
    assert agent.is_sitting is False


def test_visual_agent_drinking_animation():
    """Valida la activación de la animación de beber y la generación de su sprite."""
    agent = VisualAgent("josep", "barcelona", "Josep", 200.0, 200.0)
    assert agent.is_drinking is False

    agent.drink(True)
    assert agent.is_drinking is True

    agent.update(0.5)
    assert agent.drink_timer > 0.0

    sprite_drinking = get_agent_sprite("barcelona", "left", is_drinking=True, drink_frame=1)
    assert sprite_drinking.get_width() == 32 and sprite_drinking.get_height() == 52

    agent.drink(False)
    assert agent.is_drinking is False
    assert agent.drink_timer == 0.0


def test_visual_agent_dialogue_bubble():
    """Valida el despliegue de bocadillos cómic y su desvanecimiento tras la duración."""
    agent = VisualAgent("paco", "real_madrid", "Paco", 200.0, 200.0)
    assert agent.active_bubble_text is None

    agent.say("¡Hala Madrid!", duration=2.0)
    assert agent.active_bubble_text == "¡Hala Madrid!"
    assert agent.bubble_timer == 2.0

    agent.update(1.0)
    assert agent.active_bubble_text == "¡Hala Madrid!"
    assert agent.bubble_timer == 1.0

    agent.update(1.2)
    assert agent.active_bubble_text is None
    assert agent.bubble_timer <= 0.0


# =============================================================================
# 4, 5 Y 6. BARTENDER MANOLO: ESPACIO DELIMITADO Y SERVICIO DE TRAGOS
# =============================================================================

def test_bartender_delimited_workspace():
    """Verifica que Manolo permanezca estrictamente dentro de su pasillo detrás de la barra."""
    bartender = BartenderNPC(x=80.0, y=240.0)
    assert bartender.x == 80.0

    # Simular 30 segundos de patrulla
    for _ in range(60):
        bartender.update(0.5)
        assert bartender.x == 80.0
        assert bartender.min_y <= bartender.y <= bartender.max_y


def test_bartender_drink_preparation_and_delivery():
    """Verifica la rutina interactiva: detección de cliente, preparación y entrega."""
    bartender = BartenderNPC(x=80.0, y=240.0)
    # Cliente en el taburete 1 (x=176, y=176)
    customer = VisualAgent("josep", "barcelona", "Josep", 176.0, 176.0, initial_facing="left")

    bartender.order_drink(customer)
    assert bartender.state == "PREPARING"
    assert bartender.action == "shake"

    # Avanzar tiempo durante la preparación
    bartender.update(2.0)
    assert bartender.state in ("DELIVERING", "SERVING")

    # Avanzar tiempo para servir
    bartender.update(2.5)
    assert bartender.action in ("serve", "wipe")
    assert len(bartender.counter_drinks) >= 1
    assert bartender.counter_drinks[0]["x"] == 128.0


def test_bartender_counter_drinks_consumption():
    """Valida la colocación de la copa en la barra y su consumo."""
    bartender = BartenderNPC(x=80.0, y=240.0)
    customer = VisualAgent("paco", "real_madrid", "Paco", 176.0, 240.0, initial_facing="left")

    bartender.counter_drinks.append({
        "x": 128.0,
        "y": 240.0,
        "level": 1.0,
        "customer": customer,
        "drinking": True,
    })

    bartender.update(1.0)
    assert bartender.counter_drinks[0]["level"] < 1.0


# =============================================================================
# 7 Y 8. DOÑA CARMEN (LIMPIEZA): ESPACIO DELIMITADO Y RUTINAS
# =============================================================================

def test_cleaner_delimited_workspace_and_waypoints():
    """Verifica que Doña Carmen permanezca en su zona delimitada y recorra sus waypoints."""
    cleaner = CleanerNPC(x=416.0, y=512.0)
    assert 260.0 <= cleaner.x <= 600.0
    assert 360.0 <= cleaner.y <= 560.0

    # Simular 40 segundos de limpieza y desplazamiento
    for _ in range(80):
        cleaner.update(0.5)
        assert 260.0 <= cleaner.x <= 600.0
        assert 360.0 <= cleaner.y <= 560.0


def test_cleaner_cleaning_and_resting_cycle():
    """Valida la transición entre fregar el suelo, descansar con diálogo y caminar."""
    cleaner = CleanerNPC(x=416.0, y=512.0)
    cleaner.state = "CLEANING"
    cleaner.update(5.5)
    assert cleaner.state == "RESTING"

    cleaner.update(2.5)
    assert cleaner.state == "WALKING"
    assert cleaner.is_walking is True


# =============================================================================
# 9 Y 10. DON ANTONIO: ESPACIO DELIMITADO, TOS E INTERACCIÓN
# =============================================================================

def test_old_man_delimited_workspace_and_stretch():
    """Verifica que Don Antonio permanezca en su rincón y se levante a estirar las piernas."""
    old_man = CoughingManNPC(x=800.0, y=544.0)
    assert 760.0 <= old_man.x <= 840.0
    assert 510.0 <= old_man.y <= 560.0

    # Forzar ciclo de estiramiento
    old_man.stretch_timer = 15.0
    old_man.update(0.5)
    assert old_man.state == "STRETCHING"
    assert old_man.is_standing is True


def test_old_man_responds_to_agent_concern():
    """Don Antonio responde agradecido si un agente se acerca y le pregunta si está bien."""
    old_man = CoughingManNPC(x=800.0, y=544.0)
    agent = VisualAgent("josep", "barcelona", "Josep", 810.0, 540.0)
    agent.say("—¿Se encuentra bien, Don Antonio?")

    old_man.update(0.1, nearby_agents=[agent])
    assert old_man.state == "TALKING"
    assert old_man.active_bubble_text is not None
    assert "gracias" in old_man.active_bubble_text.lower()


# =============================================================================
# 11 Y 12. SPRITES INTERACTIVOS Y EJECUCIÓN HEADLESS
# =============================================================================

def test_counter_drink_sprite_and_dialogue_bubble_render():
    """Valida la generación de sprites de vaso y renderizado del bocadillo cómic."""
    drink_surf = get_counter_drink_sprite(level=0.8)
    assert drink_surf.get_width() == 24 and drink_surf.get_height() == 32

    pygame.font.init()
    font = pygame.font.SysFont("Arial", 11)
    test_surface = pygame.Surface((300, 200))
    # Renderizar bocadillo cómic sin errores
    render_dialogue_bubble(
        test_surface,
        150.0,
        100.0,
        "Josep",
        "¡Excelente servicio en el bar!",
        font,
        (0, 77, 152),
    )


def test_headless_simulation_with_all_interactions():
    """Ejecución headless completa durante 60 ticks con BDI y NPCs interactivos."""
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    run_simulation(max_frames=60, debug=True, bdi=True)


def test_auto_sitting_on_stools_chairs_sofa():
    """Valida la detección automática de asientos (taburetes, sillas de mesa y sofá de TV)."""
    world = BarWorld()
    agent = VisualAgent("josep", "barcelona", "Josep", 208.0, 240.0)

    # 1. En el taburete de la barra (bar_stool_1: 176, 176)
    stool = world.get_poi("bar_stool_1")
    agent.x, agent.y = stool.x, stool.y
    agent.update(0.1, world=world)
    assert agent.is_sitting is True
    assert agent.facing == "left"

    # 2. En el sofá frente a la TV (tv_lounge_seat_24: 784, 208)
    sofa_seat = world.get_poi("tv_lounge_seat_24")
    agent.x, agent.y = sofa_seat.x, sofa_seat.y
    agent.update(0.1, world=world)
    assert agent.is_sitting is True
    assert agent.facing == "up"

    # 3. En la silla oeste de la mesa central 1 (mira a la derecha hacia la mesa)
    table_seat = world.get_poi("table_central_1_seat_west")
    agent.x, agent.y = table_seat.x, table_seat.y
    agent.update(0.1, world=world)
    assert agent.is_sitting is True
    assert agent.facing == "right"

    # 4. Al iniciar navegación hacia el pasillo abierto, se levanta inmediatamente
    agent.navigate_to(world, 240.0, 320.0)
    assert agent.is_sitting is False
    assert agent.is_drinking is False


def test_cleaner_waypoints_no_table_collisions():
    """Certifica que los waypoints de Doña Carmen no solapen con mesas ni obstáculos físicos."""
    world = BarWorld()
    cleaner = CleanerNPC()

    for wp in cleaner.waypoints:
        # No colisionar con obstáculos físicos del mundo
        assert world.collides(wp[0] - 10, wp[1] - 10, 20, 20) is False
        # No estar dentro de la caja de table_central_2 ([320, 416] x [384, 448])
        in_table_2 = (320.0 <= wp[0] <= 416.0) and (384.0 <= wp[1] <= 448.0)
        assert in_table_2 is False, f"Waypoint {wp} solapa con la mesa central 2"


def test_bartender_serves_unconditionally_and_customer_drinks():
    """Valida que el camarero atienda al cliente en la barra incluso en modo manual/sin BDI."""
    bartender = BartenderNPC(x=80.0, y=240.0)
    customer = VisualAgent("paco", "real_madrid", "Paco", 176.0, 240.0)

    # 1. Detectar cliente en taburete
    bartender.update(0.1, customers=[customer])
    assert customer.is_sitting is True
    assert customer.facing == "left"
    assert bartender.state == "PREPARING"

    # 2. Completar preparación y servicio
    bartender.update(2.0)
    bartender.update(2.5)
    assert len(bartender.counter_drinks) == 1
    assert customer.is_drinking is True
    assert customer.active_bubble_text is not None


def test_agent_greets_don_antonio_when_nearby():
    """Valida que un agente que se acerque al rincón pregunte por la salud de Don Antonio."""
    world = BarWorld()
    old_man = CoughingManNPC(x=800.0, y=544.0)
    agent = VisualAgent("paco", "real_madrid", "Paco", 780.0, 540.0)

    agent.update(0.1, world=world)
    assert agent.active_bubble_text is not None
    assert "antonio" in agent.active_bubble_text.lower()

    old_man.update(0.1, nearby_agents=[agent])
    assert old_man.state == "TALKING"
    assert old_man.active_bubble_text is not None
    assert "gracias" in old_man.active_bubble_text.lower()


def test_paco_drinks_at_bar_when_thirsty_and_has_bar_preferences():
    """Valida que Paco tenga afinidad por la barra y acuda a un taburete a beber cuando tenga sed."""
    world = BarWorld()
    bdi = BDIController("paco", "real_madrid", "Paco")

    # 1. Verificar que Paco incluya taburetes en sus POIs preferidos
    bar_pois = [poi for poi in bdi.personality.preferred_pois if "bar_stool" in poi]
    assert len(bar_pois) >= 1
    assert bdi.personality.bar_affinity >= 0.60

    # 2. Con sed alta, Paco prioriza Drink y selecciona taburete
    bdi.beliefs.thirst = 0.85
    bdi.beliefs.energy = 0.85
    bdi.evaluate_desires(dt=0.01)
    bdi.select_intention(world, other_agent=None)

    assert bdi.current_intention is not None
    assert bdi.current_intention.desire_type == DesireType.DRINK
    assert "bar_stool" in (bdi.current_intention.target_poi_name or "")


