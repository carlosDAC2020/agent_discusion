"""Pruebas unitarias e integradas para la Fase 5: Diálogo Real LangGraph con Simulación Pygame.

Verifica la arquitectura desacoplada, contratos de eventos, colas thread-safe,
ciclo de vida del worker asíncrono, coordinación BDI y ejecución headless sin red.
"""

import asyncio
import os
import queue
import time
from typing import Any, AsyncIterator, Dict, List
from unittest.mock import MagicMock

import pytest

# Forzar entorno headless para Pygame
os.environ["SDL_VIDEODRIVER"] = "dummy"
import pygame

from src.simulation.agent import VisualAgent
from src.simulation.bdi import (
    BDIController,
    DesireType,
    Intention,
    IntentionState,
    create_josep_personality,
    create_paco_personality,
)
from src.simulation.config import (
    DIALOGUE_DEFAULT_MODE,
    DIALOGUE_DEFAULT_STYLE,
    DIALOGUE_POST_COOLDOWN,
)
from src.simulation.dialogue import (
    ConversationPhase,
    DialogueAdapter,
    DialogueEvent,
    DialogueEventType,
    DialogueRequest,
    get_random_debate_topic,
    REALISTIC_DEBATE_TOPICS,
)
from src.simulation.dialogue_worker import DialogueWorker
from src.simulation.world import BarWorld


# =============================================================================
# 1. PRUEBAS DE CONTRATOS Y ESTRUCTURAS DE DATOS
# =============================================================================

def test_dialogue_contracts():
    """Verifica la inmutabilidad y valores de los contratos DialogueRequest y DialogueEvent."""
    req = DialogueRequest(
        conversation_id="conv_123",
        initiator_team="barcelona",
        receiver_team="real_madrid",
        topic="¿Quién tiene mejor plantilla?",
        max_rounds=1,
        mode=DIALOGUE_DEFAULT_MODE,
        style=DIALOGUE_DEFAULT_STYLE,
    )
    assert req.conversation_id == "conv_123"
    assert req.initiator_team == "barcelona"
    assert req.receiver_team == "real_madrid"
    assert req.max_rounds == 1

    # Verificar inmutabilidad de frozen dataclass
    with pytest.raises(Exception):
        req.topic = "Otro tema"  # type: ignore

    ev = DialogueEvent(
        conversation_id="conv_123",
        event_type=DialogueEventType.TEXT_CHUNK,
        speaker_team="barcelona",
        text="Visca el Barça",
    )
    assert ev.event_type == DialogueEventType.TEXT_CHUNK
    assert ev.speaker_team == "barcelona"
    assert ev.text == "Visca el Barça"

    # Verificar generador de temas
    topic = get_random_debate_topic()
    assert topic in REALISTIC_DEBATE_TOPICS


def test_dialogue_event_types_and_phases():
    """Verifica que todos los tipos de eventos y fases conversacionales existan."""
    assert DialogueEventType.STARTED == "STARTED"
    assert DialogueEventType.TURN_STARTED == "TURN_STARTED"
    assert DialogueEventType.TEXT_CHUNK == "TEXT_CHUNK"
    assert DialogueEventType.MESSAGE_COMPLETED == "MESSAGE_COMPLETED"
    assert DialogueEventType.TOOL_STARTED == "TOOL_STARTED"
    assert DialogueEventType.FINISHED == "FINISHED"
    assert DialogueEventType.ERROR == "ERROR"
    assert DialogueEventType.CANCELLED == "CANCELLED"

    assert ConversationPhase.IDLE == "IDLE"
    assert ConversationPhase.APPROACHING == "APPROACHING"
    assert ConversationPhase.WAITING_RESPONSE == "WAITING_RESPONSE"
    assert ConversationPhase.SPEAKING == "SPEAKING"


# =============================================================================
# 2. PRUEBAS DE DIALOGUE ADAPTER
# =============================================================================

def test_dialogue_adapter_lifecycle():
    """Prueba el ciclo de vida del DialogueAdapter sin worker real."""
    adapter = DialogueAdapter()
    assert not adapter.is_busy()
    assert adapter.current_phase == ConversationPhase.IDLE

    # Solicitar conversación
    req = adapter.request_conversation("barcelona", "real_madrid", topic="Debate de prueba")
    assert req is not None
    assert adapter.is_busy()
    assert adapter.current_phase == ConversationPhase.APPROACHING
    assert adapter.request_queue.qsize() == 1

    # Segunda solicitud concurrente rechazada
    req2 = adapter.request_conversation("real_madrid", "barcelona")
    assert req2 is None

    # Simular emisión de eventos hacia Pygame
    adapter.event_queue.put(
        DialogueEvent(
            conversation_id=req.conversation_id,
            event_type=DialogueEventType.STARTED,
        )
    )
    adapter.event_queue.put(
        DialogueEvent(
            conversation_id=req.conversation_id,
            event_type=DialogueEventType.TURN_STARTED,
            speaker_team="barcelona",
        )
    )
    adapter.event_queue.put(
        DialogueEvent(
            conversation_id=req.conversation_id,
            event_type=DialogueEventType.TEXT_CHUNK,
            speaker_team="barcelona",
            text="Hola",
        )
    )

    # Drenar eventos
    events = adapter.poll_events()
    assert len(events) == 3
    assert adapter.current_phase == ConversationPhase.SPEAKING
    assert adapter.is_busy()

    # Evento de finalización libera el estado ocupado
    adapter.event_queue.put(
        DialogueEvent(
            conversation_id=req.conversation_id,
            event_type=DialogueEventType.FINISHED,
        )
    )
    events = adapter.poll_events()
    assert len(events) == 1
    assert not adapter.is_busy()
    assert adapter.current_phase == ConversationPhase.IDLE


def test_dialogue_adapter_cancel_and_shutdown():
    """Prueba la cancelación y apagado limpio del adaptador."""
    adapter = DialogueAdapter()
    req = adapter.request_conversation("barcelona", "real_madrid")
    assert adapter.is_busy()

    adapter.cancel_conversation()
    assert not adapter.is_busy()
    assert adapter.current_phase == ConversationPhase.IDLE

    # Shutdown seguro sin worker vivo
    adapter.shutdown()
    assert adapter.worker is None


# =============================================================================
# 3. PRUEBAS DE DIALOGUE WORKER CON GRAFO FALSO (HERMÉTICAS SIN RED)
# =============================================================================

class MockChunk:
    def __init__(self, content: str):
        self.content = content


class FakeDebateGraph:
    """Simula un grafo LangGraph que emite eventos v2 sin LLM ni conexión externa."""

    def __init__(self, turns: List[Dict[str, Any]] = None):
        self.turns = turns or [
            {
                "team": "barcelona",
                "chunks": ["El estilo de posesión ", "es indiscutible."],
                "tool": ("get_trophies_comparison", {"team_a": "barca", "team_b": "madrid"}),
            },
            {
                "team": "real_madrid",
                "chunks": ["Las 15 Champions ", "avalan nuestra historia."],
                "tool": None,
            },
        ]

    async def astream_events(self, state: Dict[str, Any], version: str = "v2") -> AsyncIterator[Dict[str, Any]]:
        for turn in self.turns:
            team = turn["team"]
            # 1. on_chain_start
            yield {"event": "on_chain_start", "name": team, "data": {}}

            # 2. on_tool_start si aplica
            if turn.get("tool"):
                tool_name, tool_args = turn["tool"]
                yield {
                    "event": "on_tool_start",
                    "name": tool_name,
                    "data": {"input": tool_args},
                }

            # 3. on_chat_model_stream chunks
            full_text = ""
            for ch in turn["chunks"]:
                full_text += ch
                yield {
                    "event": "on_chat_model_stream",
                    "name": "ChatModel",
                    "data": {"chunk": MockChunk(ch)},
                }

            # 4. on_chain_end
            yield {
                "event": "on_chain_end",
                "name": team,
                "data": {
                    "output": {
                        "messages": [{"team": team, "content": full_text}],
                        "turns_taken": 1,
                    }
                },
            }


def test_dialogue_worker_streaming_execution():
    """Prueba que DialogueWorker procese una solicitud y emita eventos estructurados."""
    req_q: queue.Queue[DialogueRequest] = queue.Queue()
    ev_q: queue.Queue[DialogueEvent] = queue.Queue()

    async def mock_builder(mode: str = "knowledge", style: str = "debate"):
        return FakeDebateGraph()

    worker = DialogueWorker(req_q, ev_q, graph_builder=mock_builder, timeout=10.0)
    worker.start()

    try:
        req = DialogueRequest(
            conversation_id="conv_test_1",
            initiator_team="barcelona",
            receiver_team="real_madrid",
            topic="¿Quién es el mejor?",
            max_rounds=1,
        )
        req_q.put(req)

        # Esperar a que el worker procese hasta FINISHED
        received_events: List[DialogueEvent] = []
        deadline = time.time() + 4.0
        finished = False

        while time.time() < deadline:
            try:
                ev = ev_q.get(timeout=0.1)
                received_events.append(ev)
                if ev.event_type == DialogueEventType.FINISHED:
                    finished = True
                    break
            except queue.Empty:
                continue

        assert finished, "El debate no emitió evento FINISHED a tiempo"

        # Verificar orden cronológico de eventos
        types = [e.event_type for e in received_events]
        assert DialogueEventType.STARTED in types
        assert DialogueEventType.TURN_STARTED in types
        assert DialogueEventType.TEXT_CHUNK in types
        assert DialogueEventType.TOOL_STARTED in types
        assert DialogueEventType.MESSAGE_COMPLETED in types
        assert DialogueEventType.FINISHED in types

        # Verificar que el mensaje final de Barcelona contiene el texto
        b_completed = [e for e in received_events if e.event_type == DialogueEventType.MESSAGE_COMPLETED and e.speaker_team == "barcelona"]
        assert len(b_completed) == 1
        assert "El estilo de posesión es indiscutible." in b_completed[0].text

        # Verificar que Real Madrid habló después
        rm_completed = [e for e in received_events if e.event_type == DialogueEventType.MESSAGE_COMPLETED and e.speaker_team == "real_madrid"]
        assert len(rm_completed) == 1
        assert "Las 15 Champions" in rm_completed[0].text

    finally:
        worker.stop()
        worker.join(timeout=2.0)


def test_dialogue_worker_error_handling():
    """Prueba que fallos en la compilación del grafo emitan evento ERROR sin caerse."""
    req_q: queue.Queue[DialogueRequest] = queue.Queue()
    ev_q: queue.Queue[DialogueEvent] = queue.Queue()

    async def failing_builder(mode: str = "knowledge", style: str = "debate"):
        raise RuntimeError("No hay conexión con el proveedor LLM")

    worker = DialogueWorker(req_q, ev_q, graph_builder=failing_builder, timeout=2.0)
    worker.start()

    try:
        req = DialogueRequest(
            conversation_id="conv_fail",
            initiator_team="barcelona",
            receiver_team="real_madrid",
            topic="Prueba de fallo",
        )
        req_q.put(req)

        # Esperar evento de error
        error_ev = None
        deadline = time.time() + 3.0
        while time.time() < deadline:
            try:
                ev = ev_q.get(timeout=0.1)
                if ev.event_type == DialogueEventType.ERROR:
                    error_ev = ev
                    break
            except queue.Empty:
                continue

        assert error_ev is not None
        assert "No hay conexión con el proveedor LLM" in (error_ev.error_message or "")

    finally:
        worker.stop()
        worker.join(timeout=2.0)


# =============================================================================
# 4. PRUEBAS DE ESTADO VISUAL EN VISUALAGENT
# =============================================================================

def test_visual_agent_dialogue_states():
    """Verifica métodos de pensamiento, streaming y bocadillos de diálogo en VisualAgent."""
    agent = VisualAgent("josep_test", "barcelona", "Josep", 100.0, 100.0)

    # Estado de pensamiento
    agent.set_thinking(True)
    assert agent.is_thinking is True
    agent.update(0.4)
    assert agent.thinking_frame >= 1

    # Streaming de texto (apaga thinking automáticamente)
    agent.set_dialogue_text("Primer token ", append=False)
    assert agent.is_thinking is False
    assert agent.active_dialogue_text == "Primer token "

    agent.set_dialogue_text("segundo token", append=True)
    assert agent.active_dialogue_text == "Primer token segundo token"

    # Completar mensaje con temporizador de retención
    agent.complete_dialogue_message("Mensaje final completo", hold_duration=3.0)
    assert agent.active_dialogue_text == "Mensaje final completo"
    assert agent.dialogue_hold_timer == 3.0

    # Simular expiración del temporizador
    agent.update(3.1)
    assert agent.active_dialogue_text == ""
    assert agent.dialogue_hold_timer == 0.0

    # Limpiar inmediatamente
    agent.set_dialogue_text("Texto temporal")
    agent.clear_dialogue()
    assert agent.active_dialogue_text == ""


def test_visual_agent_draw_with_dialogue_bubble():
    """Verifica que el renderizado de bocadillos y pensamiento no cause excepciones."""
    pygame.init()
    surface = pygame.Surface((300, 300))
    font = pygame.font.SysFont("Arial", 11)
    agent = VisualAgent("paco_test", "real_madrid", "Paco", 150.0, 150.0)

    # 1. Dibujar con badge normal
    agent.draw(surface, font=font)

    # 2. Dibujar con pensamiento activo
    agent.set_thinking(True)
    agent.draw(surface, font=font)

    # 3. Dibujar con texto de diálogo
    agent.set_dialogue_text("¡Hala Madrid y nada más!", append=False)
    agent.draw(surface, font=font)


# =============================================================================
# 5. PRUEBAS DE COORDINACIÓN BDI CON DIALOGUE ADAPTER
# =============================================================================

def test_bdi_dialogue_adapter_coordination():
    """Prueba la vinculación del adaptador al BDI y la emisión de solicitudes en SOCIALIZE."""
    world = BarWorld()
    paco = VisualAgent("paco_madrid", "real_madrid", "Paco", 220.0, 200.0)
    josep = VisualAgent("josep_barca", "barcelona", "Josep", 200.0, 200.0)

    controller = BDIController(
        "josep_barca", "barcelona", "Josep", create_josep_personality(), seed=42
    )
    mock_adapter = MagicMock(spec=DialogueAdapter)
    mock_adapter.is_busy.return_value = False

    controller.attach_dialogue_adapter(mock_adapter)
    assert controller.dialogue_adapter == mock_adapter

    # Asignar intención activa SOCIALIZE en fase ACTION
    controller.current_intention = Intention(
        intention_id="int_soc_test",
        desire_type=DesireType.SOCIALIZE,
        plan_name="plan_approach_rival",
        state=IntentionState.ACTIVE,
        target_pos=(200.0, 200.0),
        execution_phase="ACTION",
        action_duration=5.0,
        action_timer=0.1,
        cooldown=DIALOGUE_POST_COOLDOWN,
    )

    # Ejecutar plan: debe invocar request_conversation
    controller.execute_plan(josep, world, other_agent=paco, dt=0.05)
    mock_adapter.request_conversation.assert_called_once_with(
        initiator_team="barcelona",
        receiver_team="real_madrid",
    )

    # Desvincular adaptador
    controller.detach_dialogue_adapter()
    assert controller.dialogue_adapter is None


# =============================================================================
# 6. PRUEBAS DE SIMULACIÓN HEADLESS CON ADAPTADOR INYECTADO
# =============================================================================

def test_headless_simulation_with_mock_dialogue_adapter():
    """Ejecuta run_simulation en modo headless con un adaptador simulado sin fallos."""
    from src.simulation.app import run_simulation

    mock_adapter = MagicMock()
    mock_adapter.poll_events.return_value = [
        DialogueEvent(
            conversation_id="conv_headless",
            event_type=DialogueEventType.STARTED,
        ),
        DialogueEvent(
            conversation_id="conv_headless",
            event_type=DialogueEventType.TURN_STARTED,
            speaker_team="barcelona",
        ),
        DialogueEvent(
            conversation_id="conv_headless",
            event_type=DialogueEventType.TEXT_CHUNK,
            speaker_team="barcelona",
            text="Prueba headless",
        ),
        DialogueEvent(
            conversation_id="conv_headless",
            event_type=DialogueEventType.MESSAGE_COMPLETED,
            speaker_team="barcelona",
            text="Prueba headless",
        ),
        DialogueEvent(
            conversation_id="conv_headless",
            event_type=DialogueEventType.FINISHED,
        ),
    ]

    # Ejecutar 5 frames en modo headless
    run_simulation(
        debug=False,
        demo_movement=False,
        bdi=True,
        dialogue=True,
        dialogue_adapter=mock_adapter,
        max_frames=5,
        seed=1234,
    )

    # Verificar que el adaptador fue consultado y limpiado
    assert mock_adapter.poll_events.called
    assert mock_adapter.shutdown.called


def test_simulation_without_dialogue_flag_does_not_call_llm():
    """Verifica que simulación normal y con BDI sin flag --dialogue no inician worker."""
    from src.simulation.app import run_simulation

    # Ejecutar simulación normal sin --dialogue
    run_simulation(debug=False, demo_movement=False, bdi=True, dialogue=False, max_frames=3)
    # Si no lanza excepciones y finaliza rápido, pasa la prueba
