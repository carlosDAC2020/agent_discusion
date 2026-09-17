"""Pruebas unitarias y de integración herméticas para el Panel de Tertulia, ChatUI,
Coordinador de Conversación y corrección de globos de diálogo (Fase 5 - Extensión).
"""

import os
import pygame
import pytest

from src.simulation.agent import BartenderNPC, VisualAgent
from src.simulation.camera import Camera25D, default_camera
from src.simulation.chat_ui import ChatUI
from src.simulation.config import (
    CHAT_PANEL_WIDTH,
    DEBATE_FINISHED_HOLD_SECONDS,
    LOGICAL_HEIGHT,
    LOGICAL_WIDTH,
    MANOLO_QUESTION_HOLD_SECONDS,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)
from src.simulation.conversation import (
    ChatMessage,
    ConversationCoordinator,
    ConversationCoordinatorState,
    UserQuestion,
)
from src.simulation.dialogue import DialogueEvent, DialogueEventType
from src.simulation.navigation import find_path_astar
from src.simulation.sprites import clamp_bubble_rect
from src.simulation.world import BarWorld


# Fixture para inicializar Pygame en modo headless para pruebas
@pytest.fixture(scope="module", autouse=True)
def init_headless_pygame():
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    pygame.init()
    pygame.font.init()
    yield
    pygame.quit()


# -----------------------------------------------------------------------------
# 1. Contratos y Creación de Mensajes
# -----------------------------------------------------------------------------

def test_chat_message_creation():
    """Verifica la creación correcta de mensajes con los roles autorizados."""
    roles = ["user", "manolo", "josep", "paco", "system"]
    for role in roles:
        msg = ChatMessage(
            message_id=f"id_{role}",
            author=role.capitalize(),
            role=role,
            text=f"Mensaje de {role}",
            complete=True,
        )
        assert msg.role == role
        assert msg.complete is True
        assert msg.timestamp > 0


def test_token_streaming_updates_existing_message():
    """Verifica que TEXT_CHUNK actualice el mensaje en curso sin crear tarjetas duplicadas."""
    coord = ConversationCoordinator()
    coord.state = ConversationCoordinatorState.DEBATE_ACTIVE
    agents = [VisualAgent("josep", "barcelona", "Josep", 200, 200)]

    # Iniciar turno
    coord.process_dialogue_event(
        DialogueEvent(conversation_id="c1", event_type=DialogueEventType.TURN_STARTED, speaker_team="barcelona"),
        agents,
    )
    assert len(coord.messages) == 1
    assert coord.messages[0].role == "josep"
    assert coord.messages[0].complete is False

    # Streaming token a token
    coord.process_dialogue_event(
        DialogueEvent(conversation_id="c1", event_type=DialogueEventType.TEXT_CHUNK, speaker_team="barcelona", text="Hola "),
        agents,
    )
    coord.process_dialogue_event(
        DialogueEvent(conversation_id="c1", event_type=DialogueEventType.TEXT_CHUNK, speaker_team="barcelona", text="Paco."),
        agents,
    )

    assert len(coord.messages) == 1
    assert coord.messages[0].text == "Hola Paco."
    assert coord.messages[0].complete is False


def test_message_completed_marks_complete():
    """Verifica que MESSAGE_COMPLETED consolide el mensaje final y fije complete=True."""
    coord = ConversationCoordinator()
    coord.state = ConversationCoordinatorState.DEBATE_ACTIVE
    agents = [VisualAgent("josep", "barcelona", "Josep", 200, 200)]

    coord.process_dialogue_event(
        DialogueEvent(conversation_id="c1", event_type=DialogueEventType.TURN_STARTED, speaker_team="barcelona"),
        agents,
    )
    coord.process_dialogue_event(
        DialogueEvent(conversation_id="c1", event_type=DialogueEventType.TEXT_CHUNK, speaker_team="barcelona", text="Texto inicial"),
        agents,
    )
    coord.process_dialogue_event(
        DialogueEvent(conversation_id="c1", event_type=DialogueEventType.MESSAGE_COMPLETED, speaker_team="barcelona", text="Texto final consolidado."),
        agents,
    )

    assert len(coord.messages) == 1
    assert coord.messages[0].text == "Texto final consolidado."
    assert coord.messages[0].complete is True


def test_history_persistence_multiple_rounds():
    """Verifica que los mensajes anteriores persistan intactos tras turnos sucesivos."""
    coord = ConversationCoordinator()
    coord.state = ConversationCoordinatorState.DEBATE_ACTIVE
    agents = [
        VisualAgent("josep", "barcelona", "Josep", 200, 200),
        VisualAgent("paco", "real_madrid", "Paco", 200, 260),
    ]

    # Turno 1: Josep
    coord.process_dialogue_event(DialogueEvent("c1", DialogueEventType.TURN_STARTED, "barcelona"), agents)
    coord.process_dialogue_event(DialogueEvent("c1", DialogueEventType.TEXT_CHUNK, "barcelona", text="Mensaje 1"), agents)
    coord.process_dialogue_event(DialogueEvent("c1", DialogueEventType.MESSAGE_COMPLETED, "barcelona", text="Mensaje 1"), agents)

    # Turno 2: Paco
    coord.process_dialogue_event(DialogueEvent("c1", DialogueEventType.TURN_STARTED, "real_madrid"), agents)
    coord.process_dialogue_event(DialogueEvent("c1", DialogueEventType.TEXT_CHUNK, "real_madrid", text="Mensaje 2"), agents)
    coord.process_dialogue_event(DialogueEvent("c1", DialogueEventType.MESSAGE_COMPLETED, "real_madrid", text="Mensaje 2"), agents)

    assert len(coord.messages) == 2
    assert coord.messages[0].author == "Josep (Barça)"
    assert coord.messages[0].text == "Mensaje 1"
    assert coord.messages[1].author == "Paco (Madrid)"
    assert coord.messages[1].text == "Mensaje 2"


# -----------------------------------------------------------------------------
# 2. Entrada de Usuario y Política de Preguntas Concurrentes
# -----------------------------------------------------------------------------

def test_user_question_submission():
    """Verifica que una pregunta enviada pase al coordinador y genere registros."""
    world = BarWorld()
    agents = [
        VisualAgent("josep", "barcelona", "Josep", 208, 240),
        VisualAgent("paco", "real_madrid", "Paco", 720, 272),
    ]
    coord = ConversationCoordinator()

    success, msg = coord.submit_question("¿Quién tiene mejor plantilla?", world=world, agents=agents)
    assert success is True
    assert coord.state == ConversationCoordinatorState.AGENTS_GOING_TO_BAR
    assert coord.current_question is not None
    assert coord.current_question.text == "¿Quién tiene mejor plantilla?"
    assert agents[0].is_conversation_locked is True
    assert agents[1].is_conversation_locked is True


def test_concurrent_question_queued():
    """Verifica que una segunda pregunta durante un debate activo quede en cola (pending_question)."""
    coord = ConversationCoordinator()
    coord.state = ConversationCoordinatorState.DEBATE_ACTIVE
    coord.current_question = UserQuestion("q1", "¿Pregunta 1?")

    success, msg = coord.submit_question("¿Pregunta 2 en espera?")
    assert success is True
    assert coord.pending_question is not None
    assert coord.pending_question.text == "¿Pregunta 2 en espera?"
    assert coord.has_pending_question is True


def test_concurrent_question_rejection_when_queue_full():
    """Verifica que una tercera pregunta sea rechazada temporalmente si la cola ya tiene 1 elemento."""
    coord = ConversationCoordinator()
    coord.state = ConversationCoordinatorState.DEBATE_ACTIVE
    coord.current_question = UserQuestion("q1", "¿Pregunta 1?")
    coord.pending_question = UserQuestion("q2", "¿Pregunta 2?")

    success, msg = coord.submit_question("¿Pregunta 3 excedente?")
    assert success is False
    assert "Ya hay una pregunta en espera" in msg


def test_empty_question_rejected():
    """Verifica que preguntas en blanco sean rechazadas."""
    coord = ConversationCoordinator()
    success, msg = coord.submit_question("   ")
    assert success is False
    assert "vacía" in msg


# -----------------------------------------------------------------------------
# 3. Máquina de Estados y Bloqueo BDI
# -----------------------------------------------------------------------------

def test_state_machine_agents_going_to_bar_and_manolo_asking():
    """Verifica la transición de AGENTS_GOING_TO_BAR a MANOLO_ASKING al llegar a la barra."""
    world = BarWorld()
    manolo = BartenderNPC(80, 240, "Manolo [Barman]")
    # Situar agentes exactamente en sus spots
    b_spot = world.pois["barcelona_debate_spot"]
    m_spot = world.pois["real_madrid_debate_spot"]

    josep = VisualAgent("josep", "barcelona", "Josep", b_spot.x, b_spot.y)
    paco = VisualAgent("paco", "real_madrid", "Paco", m_spot.x, m_spot.y)
    agents = [josep, paco]

    coord = ConversationCoordinator()
    coord.submit_question("¿Quién ganará El Clásico?", world=world, agents=agents)
    assert coord.state == ConversationCoordinatorState.AGENTS_GOING_TO_BAR

    # Un tick de actualización detecta la llegada
    coord.update(0.1, world=world, agents=agents, manolo=manolo, dialogue_adapter=None)

    assert coord.state == ConversationCoordinatorState.MANOLO_ASKING
    assert manolo.active_bubble_text is not None
    assert "¿Quién ganará El Clásico?" in manolo.active_bubble_text
    assert josep.facing == "left"
    assert paco.facing == "left"


def test_manolo_asking_to_ready_to_debate():
    """Verifica que al expirar el tiempo de Manolo se transicione a READY_TO_DEBATE."""
    world = BarWorld()
    manolo = BartenderNPC(80, 240)
    agents = [
        VisualAgent("josep", "barcelona", "Josep", 208, 240),
        VisualAgent("paco", "real_madrid", "Paco", 208, 304),
    ]
    coord = ConversationCoordinator()
    coord.state = ConversationCoordinatorState.MANOLO_ASKING
    coord.manolo_timer = 0.05
    coord.current_question = UserQuestion("q1", "Tema de debate")

    coord.update(0.1, world=world, agents=agents, manolo=manolo, dialogue_adapter=None)
    assert coord.state == ConversationCoordinatorState.READY_TO_DEBATE


def test_agents_remain_locked_during_hold():
    """Verifica que los agentes permanezcan bloqueados durante DEBATE_FINISHED_HOLD."""
    agents = [
        VisualAgent("josep", "barcelona", "Josep", 208, 240),
        VisualAgent("paco", "real_madrid", "Paco", 208, 304),
    ]
    agents[0].is_conversation_locked = True
    agents[1].is_conversation_locked = True

    coord = ConversationCoordinator()
    coord.state = ConversationCoordinatorState.DEBATE_FINISHED_HOLD
    coord.hold_timer = 3.0

    coord.update(0.5, world=BarWorld(), agents=agents, manolo=None, dialogue_adapter=None)
    assert coord.state == ConversationCoordinatorState.DEBATE_FINISHED_HOLD
    assert agents[0].is_conversation_locked is True
    assert agents[1].is_conversation_locked is True


def test_next_pending_question_triggers_automatically_after_hold():
    """Verifica que una pregunta pendiente se active automáticamente tras el hold sin liberar agentes."""
    world = BarWorld()
    manolo = BartenderNPC(80, 240)
    agents = [
        VisualAgent("josep", "barcelona", "Josep", 208, 240),
        VisualAgent("paco", "real_madrid", "Paco", 208, 304),
    ]
    agents[0].is_conversation_locked = True
    agents[1].is_conversation_locked = True

    coord = ConversationCoordinator()
    coord.state = ConversationCoordinatorState.DEBATE_FINISHED_HOLD
    coord.hold_timer = 0.05
    coord.pending_question = UserQuestion("q2", "¿Siguiente tema?")

    coord.update(0.1, world=world, agents=agents, manolo=manolo, dialogue_adapter=None)

    assert coord.state == ConversationCoordinatorState.MANOLO_ASKING
    assert coord.current_question.text == "¿Siguiente tema?"
    assert coord.pending_question is None
    assert agents[0].is_conversation_locked is True
    assert agents[1].is_conversation_locked is True


def test_release_lock_when_no_pending_questions():
    """Verifica que al expirar el hold sin preguntas pendientes se libere a los agentes a IDLE."""
    world = BarWorld()
    agents = [
        VisualAgent("josep", "barcelona", "Josep", 208, 240),
        VisualAgent("paco", "real_madrid", "Paco", 208, 304),
    ]
    agents[0].is_conversation_locked = True
    agents[1].is_conversation_locked = True

    coord = ConversationCoordinator()
    coord.state = ConversationCoordinatorState.DEBATE_FINISHED_HOLD
    coord.hold_timer = 0.05
    coord.pending_question = None

    coord.update(0.1, world=world, agents=agents, manolo=None, dialogue_adapter=None)

    assert coord.state == ConversationCoordinatorState.IDLE
    assert agents[0].is_conversation_locked is False
    assert agents[1].is_conversation_locked is False


# -----------------------------------------------------------------------------
# 4. Geometría y Sujeción de Globos (clamp_bubble_rect)
# -----------------------------------------------------------------------------

def test_clamp_bubble_rect_top_overflow_flips_down():
    """Si el personaje está cerca del borde superior, el bocadillo se voltea abajo con tail_dir='top'."""
    viewport = pygame.Rect(0, 0, 960, 640)
    # Personaje en y = 30 (muy cerca del borde superior)
    rect, tail_dir = clamp_bubble_rect(
        bubble_w=180,
        bubble_h=60,
        anchor_x=400,
        anchor_y=30,
        viewport_bounds=viewport,
        min_top_margin=36,
    )
    assert tail_dir == "top"
    assert rect.top >= 30  # Se ubica debajo del personaje
    assert rect.bottom <= viewport.bottom


def test_clamp_bubble_rect_all_borders():
    """Verifica que el bocadillo quede contenido dentro de los 4 márgenes del viewport."""
    viewport = pygame.Rect(0, 0, 960, 640)

    # 1. Borde izquierdo extremo
    rect_left, _ = clamp_bubble_rect(200, 50, anchor_x=10, anchor_y=300, viewport_bounds=viewport)
    assert rect_left.left >= viewport.left + 10

    # 2. Borde derecho extremo
    rect_right, _ = clamp_bubble_rect(200, 50, anchor_x=955, anchor_y=300, viewport_bounds=viewport)
    assert rect_right.right <= viewport.right - 10

    # 3. Borde inferior extremo
    rect_bot, _ = clamp_bubble_rect(200, 50, anchor_x=400, anchor_y=630, viewport_bounds=viewport)
    assert rect_bot.bottom <= viewport.bottom - 10


# -----------------------------------------------------------------------------
# 5. POIs Semánticos y Navegación A*
# -----------------------------------------------------------------------------

def test_all_semantic_pois_valid_and_walkable():
    """Verifica que los POIs de debate existan y cumplan las reglas de transitabilidad y distancia."""
    world = BarWorld()

    assert "barcelona_debate_spot" in world.pois
    assert "real_madrid_debate_spot" in world.pois
    assert "bartender_position" in world.pois
    assert "bartender_interaction_zone" in world.pois

    b_poi = world.pois["barcelona_debate_spot"]
    m_poi = world.pois["real_madrid_debate_spot"]
    barman_poi = world.pois["bartender_position"]

    # Los spots de escucha de los agentes deben ser transitables
    assert b_poi.is_walkable is True
    assert world.is_tile_walkable(b_poi.tile_x, b_poi.tile_y) is True

    assert m_poi.is_walkable is True
    assert world.is_tile_walkable(m_poi.tile_x, m_poi.tile_y) is True

    # La posición del barman detrás de la barra NO debe ser transitable por clientes
    assert barman_poi.is_walkable is False
    assert barman_poi.exclusive_to == "bartender"

    # Distancia entre Josep y Paco: deben tener separación física sin superponerse
    dist = ((b_poi.x - m_poi.x) ** 2 + (b_poi.y - m_poi.y) ** 2) ** 0.5
    assert 60.0 <= dist <= 70.0  # Exactamente ~64 px (2 celdas de separación)


def test_astar_route_from_spawns_to_debate_spots():
    """Verifica que exista ruta ortogonal A* válida y sin colisiones desde los spawns a los spots de debate."""
    world = BarWorld()
    b_spawn = world.pois["barcelona_spawn"]
    m_spawn = world.pois["real_madrid_spawn"]

    b_spot = world.pois["barcelona_debate_spot"]
    m_spot = world.pois["real_madrid_debate_spot"]

    res_b = find_path_astar(world, b_spawn.x, b_spawn.y, b_spot.x, b_spot.y)
    assert res_b.success is True

    res_m = find_path_astar(world, m_spawn.x, m_spawn.y, m_spot.x, m_spot.y)
    assert res_m.success is True


# -----------------------------------------------------------------------------
# 6. Interfaz Lateral ChatUI y Enrutamiento de Eventos
# -----------------------------------------------------------------------------

def test_chat_ui_event_routing():
    """Verifica que ChatUI capture clics en su campo de texto y botón."""
    chat_ui = ChatUI(width=380, height=640)
    # Clic dentro de la caja de entrada (offset_x = 960)
    click_event = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN,
        pos=(960 + chat_ui.input_rect.x + 10, chat_ui.input_rect.y + 10),
        button=1,
    )
    chat_ui.handle_event(click_event, offset_x=960)
    assert chat_ui.input_active is True

    # Escribir texto
    key_event = pygame.event.Event(pygame.KEYDOWN, unicode="Hola", key=pygame.K_h)
    chat_ui.handle_event(key_event, offset_x=960)
    assert "Hola" in chat_ui.input_text

    # Clic en botón Enviar
    click_send = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN,
        pos=(960 + chat_ui.send_btn_rect.x + 10, chat_ui.send_btn_rect.y + 10),
        button=1,
    )
    submitted = chat_ui.handle_event(click_send, offset_x=960)
    assert submitted == "Hola"
    assert chat_ui.input_text == ""  # Se limpia tras enviar


def test_chat_ui_scroll():
    """Verifica que el scroll vertical de la UI ajuste scroll_y dentro de límites válidos."""
    chat_ui = ChatUI(width=380, height=640)
    chat_ui.max_scroll = 150.0

    chat_ui.scroll(30)
    assert chat_ui.scroll_y == 30.0

    chat_ui.scroll(-10)
    assert chat_ui.scroll_y == 20.0

    chat_ui.scroll(-50)
    assert chat_ui.scroll_y == 0.0  # Límite superior protegido

    chat_ui.scroll(300)
    assert chat_ui.scroll_y == 150.0  # Límite inferior max_scroll


def test_full_question_preserved_in_history():
    """Verifica que la pregunta completa se conserve íntegramente en ChatMessage sin truncarse."""
    coord = ConversationCoordinator()
    long_question = "¿Quién tiene mejor plantilla esta temporada teniendo en cuenta los fichajes de verano y la cantera?"
    coord.submit_question(long_question)

    user_msg = next((m for m in coord.messages if m.role == "user"), None)
    assert user_msg is not None
    assert user_msg.text == long_question


def test_mousewheel_scroll_only_in_panel():
    """Verifica que el evento pygame.MOUSEWHEEL ajuste el scroll."""
    chat_ui = ChatUI(width=380, height=640)
    chat_ui.max_scroll = 100.0

    wheel_event = pygame.event.Event(pygame.MOUSEWHEEL, y=-2, x=0)
    chat_ui.handle_event(wheel_event, offset_x=960)
    assert chat_ui.scroll_y == 72.0


def test_api_error_handling_and_recovery():
    """Verifica que un error de API notifique en el chat y recupere a IDLE tras el temporizador."""
    world = BarWorld()
    agents = [
        VisualAgent("josep", "barcelona", "Josep", 208, 240),
        VisualAgent("paco", "real_madrid", "Paco", 208, 304),
    ]
    agents[0].is_conversation_locked = True
    agents[1].is_conversation_locked = True

    coord = ConversationCoordinator()
    coord.state = ConversationCoordinatorState.DEBATE_ACTIVE
    coord.process_dialogue_event(
        DialogueEvent("c1", DialogueEventType.ERROR, error_message="Fallo de cuota en API"),
        agents,
    )

    assert coord.state == ConversationCoordinatorState.ERROR
    assert any("Fallo de cuota en API" in m.text for m in coord.messages)

    # Avanzar tiempo para recuperación
    coord.update(3.1, world=world, agents=agents, manolo=None, dialogue_adapter=None)
    assert coord.state == ConversationCoordinatorState.IDLE
    assert agents[0].is_conversation_locked is False
    assert agents[1].is_conversation_locked is False


def test_render_chat_ui_runs_cleanly():
    """Verifica que render() dibuje correctamente las tarjetas y retorne superficie válida."""
    chat_ui = ChatUI(width=380, height=640)
    coord = ConversationCoordinator()
    coord.submit_question("¿Quién ganará?")
    coord.messages.append(ChatMessage("m1", "Josep", "josep", "El Barça tiene mejor proyecto.", complete=True))
    coord.messages.append(ChatMessage("m2", "Paco", "paco", "El Madrid tiene 15 Champions.", complete=False))

    font_sm = pygame.font.SysFont("Arial", 11)
    font_b = pygame.font.SysFont("Arial", 11, bold=True)
    font_t = pygame.font.SysFont("Arial", 9)

    surface = chat_ui.render(coord, font_sm, font_b, font_t)
    assert isinstance(surface, pygame.Surface)
    assert surface.get_size() == (380, 640)


def test_bdi_controller_respects_lock():
    """Verifica que un BDIController bloqueado no sobreescriba la intención con otros deseos."""
    from src.simulation.bdi import BDIController, DesireType, IntentionState
    bdi = BDIController("josep", "barcelona", "Josep")
    world = BarWorld()
    agent = VisualAgent("josep", "barcelona", "Josep", 208, 240)

    bdi.command_debate_at_bar(agent, world, "barcelona_debate_spot")
    assert bdi.is_locked is True
    assert bdi.current_intention.plan_name == "DEBATE_AT_BAR"

    # Simular que tiene mucha sed
    bdi.beliefs.thirst = 1.0
    bdi.update(agent, world, None, dt=0.5)

    # Debe mantenerse en DEBATE_AT_BAR y no cambiar a DRINK
    assert bdi.current_intention.plan_name == "DEBATE_AT_BAR"
    assert bdi.is_locked is True

    # Liberación controlada
    bdi.release_conversation_lock()
    assert bdi.is_locked is False


def test_bartender_moderate_question():
    """Verifica que moderate_question ajuste la máquina de estados de Manolo y active su globo."""
    manolo = BartenderNPC(80, 240, "Manolo [Barman]")
    manolo.moderate_question("¿Quién ganará el Clásico?", duration=3.5)

    assert manolo.state == "MODERATING"
    assert manolo.action == "idle"
    assert manolo.active_bubble_text is not None
    assert "¿Quién ganará el Clásico?" in manolo.active_bubble_text
    assert manolo.current_question_text == "¿Quién ganará el Clásico?"


def test_chat_ui_input_focus_release_mechanisms():
    """Verifica que el campo de texto libere el foco al enviar, pulsar ESC o hacer clic en el bar."""
    chat_ui = ChatUI(width=380, height=640)
    offset_x = 960

    # 1. Enfocar campo de texto con un clic dentro
    click_in = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN,
        pos=(offset_x + chat_ui.input_rect.x + 5, chat_ui.input_rect.y + 5),
        button=1,
    )
    chat_ui.handle_event(click_in, offset_x=offset_x)
    assert chat_ui.input_active is True

    # 2. Pulsar Enter para enviar texto debe liberar el foco
    chat_ui.input_text = "¿Quién es mejor?"
    enter_ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
    submitted = chat_ui.handle_event(enter_ev, offset_x=offset_x)
    assert submitted == "¿Quién es mejor?"
    assert chat_ui.input_active is False, "Enter debe liberar el foco del campo de texto"

    # 3. Enfocar de nuevo y pulsar ESC debe liberar el foco
    chat_ui.input_active = True
    esc_ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)
    chat_ui.handle_event(esc_ev, offset_x=offset_x)
    assert chat_ui.input_active is False, "ESCAPE debe desenfocar el campo de texto"

    # 4. Enfocar de nuevo y hacer clic en el bar (mouse_x < offset_x) debe liberar el foco
    chat_ui.input_active = True
    click_bar = pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(500, 300), button=1)
    chat_ui.handle_event(click_bar, offset_x=offset_x)
    assert chat_ui.input_active is False, "Hacer clic en el bar debe liberar el foco del panel"


def test_dispatch_agents_to_bar_resets_sitting_and_drinking():
    """Verifica que al acudir a la barra se cancelen las posturas de sentado y bebida."""
    coord = ConversationCoordinator()
    world = BarWorld()
    josep = VisualAgent("josep", "barcelona", "Josep", 200, 200)
    paco = VisualAgent("paco", "real_madrid", "Paco", 400, 400)

    josep.sit(True)
    josep.drink(True)
    paco.sit(True)
    paco.drink(True)

    assert josep.is_sitting is True
    assert josep.is_drinking is True
    assert paco.is_sitting is True
    assert paco.is_drinking is True

    coord.submit_question("¿Quién gana LaLiga?", world=world, agents=[josep, paco])

    assert josep.is_sitting is False
    assert josep.is_drinking is False
    assert paco.is_sitting is False
    assert paco.is_drinking is False
    assert josep.is_conversation_locked is True
    assert paco.is_conversation_locked is True


def test_coordinator_nav_timeout_and_lazy_adapter():
    """Verifica que el timeout prolongado sitúe a los agentes en sus spots y se maneje el adaptador."""
    coord = ConversationCoordinator()
    world = BarWorld()
    josep = VisualAgent("josep", "barcelona", "Josep", 700, 500)
    paco = VisualAgent("paco", "real_madrid", "Paco", 600, 400)
    manolo = BartenderNPC(80, 240, "Manolo [Barman]")

    coord.submit_question("¿Quién tiene mejor cantera?", world=world, agents=[josep, paco])
    assert coord.state == ConversationCoordinatorState.AGENTS_GOING_TO_BAR
    assert coord.nav_timeout_timer == 30.0

    # Simular expiración de timeout de navegación
    coord.update(31.0, world=world, agents=[josep, paco], manolo=manolo, dialogue_adapter=None)

    # Los agentes deben haber sido situados en sus spots de debate
    b_spot = world.pois["barcelona_debate_spot"]
    m_spot = world.pois["real_madrid_debate_spot"]
    assert (josep.x, josep.y) == (float(b_spot.x), float(b_spot.y))
    assert (paco.x, paco.y) == (float(m_spot.x), float(m_spot.y))
    assert coord.state == ConversationCoordinatorState.MANOLO_ASKING
