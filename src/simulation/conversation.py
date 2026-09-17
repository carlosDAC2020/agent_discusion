"""Coordinador central de conversación, tertulia y moderación para la simulación 2D.

Desacopla la gestión del estado conversacional fuera de app.py y orquesta:
1. Recepción y encolado de preguntas del usuario (UserQuestion).
2. Máquina de estados de la conversación (ConversationCoordinatorState).
3. Solicitud de desplazamiento y posicionamiento en POIs semánticos de debate.
4. Moderación visual de Manolo (BartenderNPC).
5. Bloqueo y permanencia de Josep y Paco durante el debate y el tiempo de retención.
6. Procesamiento de eventos en tiempo real de LangGraph y actualización del historial.
"""

from dataclasses import dataclass, field
from enum import Enum
import math
import time
from typing import Any, Dict, List, Optional, Tuple

from src.simulation.config import (
    DEBATE_FINISHED_HOLD_SECONDS,
    DIALOGUE_MAX_ROUNDS,
    MANOLO_QUESTION_HOLD_SECONDS,
)
from src.simulation.dialogue import DialogueEvent, DialogueEventType


# =============================================================================
# CONTRATOS DE DATOS DE CONVERSACIÓN
# =============================================================================

@dataclass(frozen=True)
class UserQuestion:
    """Pregunta formulada por el usuario desde la interfaz lateral."""
    question_id: str
    text: str
    created_at: float = field(default_factory=time.time)


@dataclass
class ChatMessage:
    """Mensaje persistente en el historial de la tertulia."""
    message_id: str
    author: str           # "Tú", "Manolo [Barman]", "Josep (Barça)", "Paco (Madrid)", "Sistema"
    role: str             # "user", "manolo", "josep", "paco", "system"
    text: str
    timestamp: float = field(default_factory=time.time)
    conversation_id: Optional[str] = None
    complete: bool = False


class ConversationCoordinatorState(str, Enum):
    """Estados del ciclo de vida de la sesión de tertulia y debate."""
    IDLE = "IDLE"
    AGENTS_GOING_TO_BAR = "AGENTS_GOING_TO_BAR"
    MANOLO_ASKING = "MANOLO_ASKING"
    READY_TO_DEBATE = "READY_TO_DEBATE"
    DEBATE_ACTIVE = "DEBATE_ACTIVE"
    DEBATE_FINISHED_HOLD = "DEBATE_FINISHED_HOLD"
    ERROR = "ERROR"


# =============================================================================
# COORDINADOR DE CONVERSACIÓN
# =============================================================================

class ConversationCoordinator:
    """Orquestador de alto nivel del debate en la barra entre usuario, Manolo y tertulianos."""

    def __init__(self) -> None:
        self.state: ConversationCoordinatorState = ConversationCoordinatorState.IDLE
        self.current_question: Optional[UserQuestion] = None
        self.pending_question: Optional[UserQuestion] = None
        self.active_conversation_id: Optional[str] = None

        # Temporizadores de fase
        self.manolo_timer: float = 0.0
        self.hold_timer: float = 0.0
        self.error_timer: float = 0.0
        self.nav_timeout_timer: float = 0.0

        # Historial persistente de mensajes
        self.messages: List[ChatMessage] = []
        self.status_message: str = "Escribe tu pregunta para iniciar el debate..."

        # Referencia al mensaje en streaming activo
        self._current_streaming_message: Optional[ChatMessage] = None

    @property
    def is_busy(self) -> bool:
        """Indica si hay una conversación activa o en transición."""
        return self.state != ConversationCoordinatorState.IDLE

    @property
    def has_pending_question(self) -> bool:
        """Indica si ya existe una pregunta en cola."""
        return self.pending_question is not None

    def submit_question(
        self, text: str, world: Optional[Any] = None, agents: Optional[List[Any]] = None
    ) -> Tuple[bool, str]:
        """Recibe una pregunta del usuario y la procesa o encola según el estado actual."""
        clean_text = text.strip()
        if not clean_text:
            return False, "La pregunta no puede estar vacía."

        q_id = f"q_{int(time.time() * 1000)}"
        user_q = UserQuestion(question_id=q_id, text=clean_text)

        if self.state == ConversationCoordinatorState.IDLE:
            self.current_question = user_q
            # Agregar pregunta del usuario al historial
            self.messages.append(
                ChatMessage(
                    message_id=f"msg_{q_id}",
                    author="Tú",
                    role="user",
                    text=clean_text,
                    complete=True,
                )
            )
            self.messages.append(
                ChatMessage(
                    message_id=f"sys_{q_id}",
                    author="Sistema",
                    role="system",
                    text="Josep y Paco se dirigen a la barra para escuchar la pregunta.",
                    complete=True,
                )
            )

            # Iniciar desplazamiento hacia la barra
            if world is not None and agents is not None and len(agents) >= 2:
                self._dispatch_agents_to_bar(world, agents)

            self.state = ConversationCoordinatorState.AGENTS_GOING_TO_BAR
            self.nav_timeout_timer = 30.0
            self.status_message = "Josep y Paco acudiendo a la barra..."
            return True, "Pregunta enviada a la barra."

        else:
            # Ya hay una conversación activa: verificar cola
            if self.pending_question is None:
                self.pending_question = user_q
                self.messages.append(
                    ChatMessage(
                        message_id=f"msg_{q_id}",
                        author="Tú",
                        role="user",
                        text=clean_text,
                        complete=True,
                    )
                )
                self.messages.append(
                    ChatMessage(
                        message_id=f"sys_queue_{q_id}",
                        author="Sistema",
                        role="system",
                        text=f"Pregunta en espera: \"{clean_text}\". Se formulará al concluir el debate actual.",
                        complete=True,
                    )
                )
                return True, "Debate en curso. Pregunta puesta en espera."
            else:
                return False, "Ya hay una pregunta en espera en la barra. Por favor espera a que comience."

    def _dispatch_agents_to_bar(self, world: Any, agents: List[Any]) -> None:
        """Asigna destinos semánticos de debate y aplica bloqueo BDI a los agentes."""
        josep = agents[0]
        paco = agents[1]

        # Asegurar que se levanten o terminen de beber de inmediato
        if hasattr(josep, "sit") and josep.is_sitting:
            josep.sit(False)
        if hasattr(josep, "drink") and josep.is_drinking:
            josep.drink(False)
        if hasattr(paco, "sit") and paco.is_sitting:
            paco.sit(False)
        if hasattr(paco, "drink") and paco.is_drinking:
            paco.drink(False)

        # Aplicar cerrojo explícito a ambos
        josep.is_conversation_locked = True
        paco.is_conversation_locked = True

        if hasattr(josep, "bdi_controller") and josep.bdi_controller:
            josep.bdi_controller.command_debate_at_bar(josep, world, "barcelona_debate_spot")
        else:
            poi = world.pois.get("barcelona_debate_spot")
            if poi:
                josep.navigate_to(world, poi.x, poi.y)

        if hasattr(paco, "bdi_controller") and paco.bdi_controller:
            paco.bdi_controller.command_debate_at_bar(paco, world, "real_madrid_debate_spot")
        else:
            poi = world.pois.get("real_madrid_debate_spot")
            if poi:
                paco.navigate_to(world, poi.x, poi.y)

    def update(
        self,
        dt: float,
        world: Any,
        agents: List[Any],
        manolo: Any,
        dialogue_adapter: Optional[Any],
    ) -> None:
        """Avanza la máquina de estados de la conversación frame a frame."""
        if len(agents) < 2 or self.state == ConversationCoordinatorState.IDLE:
            return

        josep, paco = agents[0], agents[1]

        # ---------------------------------------------------------------------
        # ESTADO: AGENTS_GOING_TO_BAR
        # ---------------------------------------------------------------------
        if self.state == ConversationCoordinatorState.AGENTS_GOING_TO_BAR:
            self.nav_timeout_timer -= dt

            # Comprobar llegada de ambos a sus POIs semánticos
            b_spot = world.pois.get("barcelona_debate_spot")
            m_spot = world.pois.get("real_madrid_debate_spot")

            j_dist = math.hypot(josep.x - b_spot.x, josep.y - b_spot.y) if b_spot else 0.0
            p_dist = math.hypot(paco.x - m_spot.x, paco.y - m_spot.y) if m_spot else 0.0

            j_arrived = (j_dist <= 12.0 or (j_dist <= 28.0 and not josep.is_navigating))
            p_arrived = (p_dist <= 12.0 or (p_dist <= 28.0 and not paco.is_navigating))
            both_arrived = j_arrived and p_arrived

            # Si ambos llegaron o se acaba el tiempo límite de navegación
            if both_arrived or self.nav_timeout_timer <= 0.0:
                josep.cancel_navigation()
                paco.cancel_navigation()
                if self.nav_timeout_timer <= 0.0 and b_spot and m_spot:
                    josep.x, josep.y = float(b_spot.x), float(b_spot.y)
                    paco.x, paco.y = float(m_spot.x), float(m_spot.y)

                # Orientar a ambos hacia Manolo (izquierda)
                josep.set_facing("left")
                paco.set_facing("left")

                # Iniciar moderación de Manolo
                if self.current_question and hasattr(manolo, "moderate_question"):
                    manolo.moderate_question(
                        self.current_question.text, duration=MANOLO_QUESTION_HOLD_SECONDS
                    )
                    self.messages.append(
                        ChatMessage(
                            message_id=f"manolo_{self.current_question.question_id}",
                            author="Manolo [Barman]",
                            role="manolo",
                            text=self.current_question.text,
                            complete=True,
                        )
                    )

                self.manolo_timer = MANOLO_QUESTION_HOLD_SECONDS
                self.state = ConversationCoordinatorState.MANOLO_ASKING
                self.status_message = "Manolo presentando la pregunta en la barra..."

        # ---------------------------------------------------------------------
        # ESTADO: MANOLO_ASKING
        # ---------------------------------------------------------------------
        elif self.state == ConversationCoordinatorState.MANOLO_ASKING:
            self.manolo_timer -= dt
            # Mantener a Josep y Paco orientados hacia Manolo
            josep.set_facing("left")
            paco.set_facing("left")

            if self.manolo_timer <= 0.0:
                # Transicionar a debate: encarar entre sí
                josep.set_facing("left")
                paco.set_facing("left")
                self.state = ConversationCoordinatorState.READY_TO_DEBATE
                self.status_message = "Iniciando debate entre Josep y Paco..."

        # ---------------------------------------------------------------------
        # ESTADO: READY_TO_DEBATE
        # ---------------------------------------------------------------------
        elif self.state == ConversationCoordinatorState.READY_TO_DEBATE:
            # Si el adaptador no existe, intentar instanciarlo perezosamente
            if dialogue_adapter is None:
                try:
                    from src.simulation.dialogue import DialogueAdapter
                    dialogue_adapter = DialogueAdapter()
                    dialogue_adapter.start()
                except Exception:
                    dialogue_adapter = None

            if dialogue_adapter is not None and self.current_question:
                # Si el adaptador estaba ocupado con otra conversación, cancelarla
                if (
                    dialogue_adapter.is_busy()
                    and dialogue_adapter.active_conversation_id != self.active_conversation_id
                ):
                    dialogue_adapter.cancel_conversation()

                # Lanzar solicitud de debate con la pregunta como tema real
                req = dialogue_adapter.request_conversation(
                    initiator_team="barcelona",
                    receiver_team="real_madrid",
                    topic=self.current_question.text,
                    max_rounds=DIALOGUE_MAX_ROUNDS,
                )
                if req is not None:
                    self.active_conversation_id = req.conversation_id
                    self.state = ConversationCoordinatorState.DEBATE_ACTIVE
                    self.status_message = "Debate en curso: FC Barcelona vs Real Madrid"
                else:
                    self.state = ConversationCoordinatorState.ERROR
                    self.error_timer = 3.0
                    self.status_message = "Adaptador ocupado o no disponible."
            else:
                # Fallback sin adaptador de diálogo: debate local simulado
                self.messages.append(
                    ChatMessage(
                        message_id=f"err_no_adapter_{int(time.time()*1000)}",
                        author="Sistema",
                        role="system",
                        text="[Aviso]: Adaptador de diálogo no disponible para conectar con LangGraph.",
                        complete=True,
                    )
                )
                self.state = ConversationCoordinatorState.DEBATE_FINISHED_HOLD
                self.hold_timer = 3.0

        # ---------------------------------------------------------------------
        # ESTADO: DEBATE_ACTIVE
        # ---------------------------------------------------------------------
        elif self.state == ConversationCoordinatorState.DEBATE_ACTIVE:
            # Los agentes deben permanecer bloqueados y sin moverse
            josep.is_conversation_locked = True
            paco.is_conversation_locked = True

        # ---------------------------------------------------------------------
        # ESTADO: DEBATE_FINISHED_HOLD
        # ---------------------------------------------------------------------
        elif self.state == ConversationCoordinatorState.DEBATE_FINISHED_HOLD:
            # Mantener en la barra durante el tiempo de retención
            josep.is_conversation_locked = True
            paco.is_conversation_locked = True
            self.hold_timer -= dt

            if self.hold_timer <= 0.0:
                # Si hay una pregunta en espera, encadenar directamente
                if self.pending_question is not None:
                    self.current_question = self.pending_question
                    self.pending_question = None

                    # Orientar a Manolo de nuevo
                    josep.set_facing("left")
                    paco.set_facing("left")

                    if hasattr(manolo, "moderate_question"):
                        manolo.moderate_question(
                            self.current_question.text, duration=MANOLO_QUESTION_HOLD_SECONDS
                        )
                        self.messages.append(
                            ChatMessage(
                                message_id=f"manolo_{self.current_question.question_id}",
                                author="Manolo [Barman]",
                                role="manolo",
                                text=self.current_question.text,
                                complete=True,
                            )
                        )

                    self.manolo_timer = MANOLO_QUESTION_HOLD_SECONDS
                    self.state = ConversationCoordinatorState.MANOLO_ASKING
                    self.status_message = "Manolo presentando la siguiente pregunta..."

                else:
                    # Sin preguntas pendientes: liberar el cerrojo de conversación
                    self.release_conversation_lock(agents)
                    self.current_question = None
                    self.active_conversation_id = None
                    self.state = ConversationCoordinatorState.IDLE
                    self.status_message = "Escribe tu pregunta para iniciar el debate..."

        # ---------------------------------------------------------------------
        # ESTADO: ERROR
        # ---------------------------------------------------------------------
        elif self.state == ConversationCoordinatorState.ERROR:
            self.error_timer -= dt
            if self.error_timer <= 0.0:
                self.release_conversation_lock(agents)
                self.current_question = None
                self.state = ConversationCoordinatorState.IDLE
                self.status_message = "Escribe tu pregunta para iniciar el debate..."

    def process_dialogue_event(self, ev: DialogueEvent, agents: List[Any]) -> None:
        """Procesa eventos streaming de LangGraph actualizando el historial y tarjetas."""
        speaker_name = "Josep (Barça)" if ev.speaker_team == "barcelona" else "Paco (Madrid)"
        role = "josep" if ev.speaker_team == "barcelona" else "paco"

        if ev.event_type == DialogueEventType.TURN_STARTED:
            # Crear nueva tarjeta para el orador en el chat
            msg = ChatMessage(
                message_id=f"msg_turn_{int(time.time()*1000)}_{role}",
                author=speaker_name,
                role=role,
                text="",
                conversation_id=ev.conversation_id,
                complete=False,
            )
            self.messages.append(msg)
            self._current_streaming_message = msg
            self.status_message = f"{speaker_name} respondiendo..."

        elif ev.event_type == DialogueEventType.TEXT_CHUNK:
            if self._current_streaming_message and self._current_streaming_message.role == role:
                self._current_streaming_message.text += ev.text
            elif self.messages and self.messages[-1].role == role:
                self.messages[-1].text += ev.text

        elif ev.event_type == DialogueEventType.MESSAGE_COMPLETED:
            if self._current_streaming_message and self._current_streaming_message.role == role:
                self._current_streaming_message.text = ev.text
                self._current_streaming_message.complete = True
                self._current_streaming_message = None
            elif self.messages and self.messages[-1].role == role:
                self.messages[-1].text = ev.text
                self.messages[-1].complete = True

        elif ev.event_type == DialogueEventType.FINISHED:
            if self._current_streaming_message:
                self._current_streaming_message.complete = True
                self._current_streaming_message = None
            self.state = ConversationCoordinatorState.DEBATE_FINISHED_HOLD
            self.hold_timer = DEBATE_FINISHED_HOLD_SECONDS
            self.status_message = "Debate finalizado. Turno de conclusiones en la barra..."

        elif ev.event_type == DialogueEventType.ERROR:
            err_text = ev.error_message or "Error en la conexión con el modelo."
            self.messages.append(
                ChatMessage(
                    message_id=f"err_{int(time.time()*1000)}",
                    author="Sistema",
                    role="system",
                    text=f"[Error]: {err_text}",
                    complete=True,
                )
            )
            self.state = ConversationCoordinatorState.ERROR
            self.error_timer = 3.0
            self.status_message = "Error en el debate."

    def release_conversation_lock(self, agents: List[Any]) -> None:
        """Libera de forma controlada el bloqueo en los agentes y sus controladores BDI."""
        for agent in agents:
            agent.is_conversation_locked = False
            if hasattr(agent, "bdi_controller") and agent.bdi_controller:
                agent.bdi_controller.release_conversation_lock()
