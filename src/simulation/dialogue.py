"""Contratos de datos y adaptador de diálogo para la integración de LangGraph en Pygame.

Provee una interfaz síncrona y thread-safe para que el bucle principal de Pygame
se comunique con el hilo asíncrono del worker de LangGraph sin bloquear el renderizado.
"""

from dataclasses import dataclass, field
from enum import Enum
import queue
import random
import time
from typing import Any, Dict, List, Optional

from src.simulation.config import (
    DIALOGUE_DEFAULT_MODE,
    DIALOGUE_DEFAULT_STYLE,
    DIALOGUE_MAX_ROUNDS,
)


# =============================================================================
# 1. CONTRATOS DE DATOS Y ENUMS
# =============================================================================


class DialogueEventType(str, Enum):
    """Tipos de eventos emitidos por el worker de LangGraph hacia Pygame."""

    STARTED = "STARTED"
    TURN_STARTED = "TURN_STARTED"
    TEXT_CHUNK = "TEXT_CHUNK"
    MESSAGE_COMPLETED = "MESSAGE_COMPLETED"
    TOOL_STARTED = "TOOL_STARTED"
    TOOL_COMPLETED = "TOOL_COMPLETED"
    FINISHED = "FINISHED"
    ERROR = "ERROR"
    CANCELLED = "CANCELLED"


class ConversationPhase(str, Enum):
    """Fases del ciclo de vida visual de una conversación en Pygame."""

    IDLE = "IDLE"
    APPROACHING = "APPROACHING"
    READY = "READY"
    WAITING_RESPONSE = "WAITING_RESPONSE"
    SPEAKING = "SPEAKING"
    FINISHED = "FINISHED"
    ERROR = "ERROR"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class DialogueRequest:
    """Solicitud tipada e inmutable de debate enviada al worker de LangGraph."""

    conversation_id: str
    initiator_team: str
    receiver_team: str
    topic: str
    max_rounds: int = DIALOGUE_MAX_ROUNDS
    mode: str = DIALOGUE_DEFAULT_MODE
    style: str = DIALOGUE_DEFAULT_STYLE
    timestamp: float = field(default_factory=time.time)


@dataclass(frozen=True)
class DialogueEvent:
    """Evento serializable y desacoplado emitido desde el worker hacia Pygame."""

    conversation_id: str
    event_type: DialogueEventType
    speaker_team: Optional[str] = None
    text: str = ""
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


# =============================================================================
# 2. GENERADOR DE TEMAS DE DEBATE FUTBOLÍSTICO
# =============================================================================

REALISTIC_DEBATE_TOPICS: List[str] = [
    "¿Quién tiene mejor plantilla esta temporada: el FC Barcelona o el Real Madrid?",
    "¿Qué estilo es más efectivo en Europa: el fútbol de posesión o las transiciones verticales?",
    "¿Quién tiene mayor mérito: el Sextete del Barça de Guardiola o las tres Champions seguidas de Zidane?",
    "¿Qué cantera produce mejores talentos en la actualidad: La Masia o La Fábrica?",
    "¿Quién fue más decisivo en los Clásicos históricos: Leo Messi o Cristiano Ronaldo?",
    "¿Qué equipo llega en mejor momento táctico para ganar el próximo Clásico?",
    "¿Es más importante ganar la Champions League o la regularidad de LaLiga?",
]


def get_random_debate_topic(rng: Optional[random.Random] = None) -> str:
    """Retorna un tema de debate futbolístico contextualizado y realista."""
    if rng is not None:
        return rng.choice(REALISTIC_DEBATE_TOPICS)
    return random.choice(REALISTIC_DEBATE_TOPICS)


# =============================================================================
# 3. ADAPTADOR DE DIÁLOGO PARA PYGAME
# =============================================================================


class DialogueAdapter:
    """Adaptador de alto nivel para gestionar la comunicación entre Pygame y LangGraph.

    Asegura que Pygame nunca realice llamadas de red, mantenga 60 FPS y
    consuma eventos a través de colas seguras sin esperas bloqueantes.
    """

    def __init__(self, worker_factory: Optional[Any] = None):
        self.request_queue: queue.Queue[DialogueRequest] = queue.Queue()
        self.event_queue: queue.Queue[DialogueEvent] = queue.Queue()

        self.worker_factory = worker_factory
        self.worker: Optional[Any] = None
        self.active_conversation_id: Optional[str] = None
        self.current_phase: ConversationPhase = ConversationPhase.IDLE

    def start(self) -> None:
        """Inicia el worker en segundo plano si aún no está corriendo."""
        if self.worker is not None and self.worker.is_alive():
            return

        if self.worker_factory is not None:
            self.worker = self.worker_factory(self.request_queue, self.event_queue)
        else:
            from src.simulation.dialogue_worker import DialogueWorker

            self.worker = DialogueWorker(self.request_queue, self.event_queue)

        self.worker.start()

    def request_conversation(
        self,
        initiator_team: str,
        receiver_team: str,
        topic: Optional[str] = None,
        max_rounds: int = DIALOGUE_MAX_ROUNDS,
        mode: str = DIALOGUE_DEFAULT_MODE,
        style: str = DIALOGUE_DEFAULT_STYLE,
    ) -> Optional[DialogueRequest]:
        """Envía una nueva solicitud de conversación si no hay otra en curso.

        Retorna la solicitud generada o None si ya hay una conversación activa.
        """
        from src.simulation.debug_logger import debug_log

        if self.is_busy():
            debug_log(
                "DIALOGUE_ADAPTER",
                "REQUEST_REJECTED_BUSY",
                f"active_conversation_id={self.active_conversation_id}, phase={self.current_phase.value}",
            )
            return None

        chosen_topic = topic or get_random_debate_topic()
        conv_id = f"conv_{int(time.time() * 1000)}"

        req = DialogueRequest(
            conversation_id=conv_id,
            initiator_team=initiator_team,
            receiver_team=receiver_team,
            topic=chosen_topic,
            max_rounds=max_rounds,
            mode=mode,
            style=style,
        )

        self.active_conversation_id = conv_id
        self.current_phase = ConversationPhase.APPROACHING
        self.request_queue.put(req)
        debug_log(
            "DIALOGUE_ADAPTER",
            "REQUEST_ENQUEUED",
            f"conv_id={conv_id}, initiator={initiator_team}, receiver={receiver_team}, rounds={max_rounds}, mode={mode}, style={style}, queue_size={self.request_queue.qsize()}",
            conversation_id=conv_id,
        )
        return req

    def poll_events(self) -> List[DialogueEvent]:
        """Drena y retorna todos los eventos recibidos sin bloquear el hilo principal."""
        events: List[DialogueEvent] = []
        while True:
            try:
                ev = self.event_queue.get_nowait()
                events.append(ev)

                # Actualizar fase interna según el evento
                if ev.event_type == DialogueEventType.STARTED:
                    self.current_phase = ConversationPhase.WAITING_RESPONSE
                elif ev.event_type == DialogueEventType.TURN_STARTED:
                    self.current_phase = ConversationPhase.WAITING_RESPONSE
                elif ev.event_type == DialogueEventType.TEXT_CHUNK:
                    self.current_phase = ConversationPhase.SPEAKING
                elif ev.event_type == DialogueEventType.MESSAGE_COMPLETED:
                    self.current_phase = ConversationPhase.WAITING_RESPONSE
                elif ev.event_type in (
                    DialogueEventType.FINISHED,
                    DialogueEventType.ERROR,
                    DialogueEventType.CANCELLED,
                ):
                    self.active_conversation_id = None
                    self.current_phase = ConversationPhase.IDLE

            except queue.Empty:
                break
        return events

    def is_busy(self) -> bool:
        """Indica si existe una conversación activa en proceso."""
        return self.active_conversation_id is not None

    def cancel_conversation(self, conversation_id: Optional[str] = None) -> None:
        """Solicita la cancelación de la conversación activa."""
        if self.worker is not None and hasattr(self.worker, "cancel_active"):
            self.worker.cancel_active()
        self.active_conversation_id = None
        self.current_phase = ConversationPhase.IDLE

    def shutdown(self, timeout: float = 2.0) -> None:
        """Detiene limpiamente el worker y libera los recursos asociados."""
        if self.worker is not None:
            if hasattr(self.worker, "stop"):
                self.worker.stop()
            self.worker.join(timeout=timeout)
            self.worker = None
        self.active_conversation_id = None
        self.current_phase = ConversationPhase.IDLE
