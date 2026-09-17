"""Worker asíncrono desacoplado para la ejecución de LangGraph fuera del hilo principal.

Este módulo corre en un hilo independiente (DialogueWorker) con su propio
bucle de eventos asyncio, consume solicitudes de debate de forma segura
y emite eventos tipados hacia la cola de Pygame.
"""

import asyncio
import queue
import threading
import time
from typing import Any, Callable, Dict, Optional

from src.orchestrator.graph import _extract_text, build_debate_graph
from src.orchestrator.state import initial_state
from src.simulation.config import DIALOGUE_TIMEOUT_SECONDS
from src.simulation.debug_logger import debug_log
from src.simulation.dialogue import DialogueEvent, DialogueEventType, DialogueRequest


class DialogueWorker(threading.Thread):
    """Hilo trabajador que ejecuta el grafo real de LangGraph en un event loop propio."""

    def __init__(
        self,
        request_queue: queue.Queue[DialogueRequest],
        event_queue: queue.Queue[DialogueEvent],
        graph_builder: Optional[Callable[..., Any]] = None,
        timeout: float = DIALOGUE_TIMEOUT_SECONDS,
    ):
        super().__init__(name="DialogueWorkerThread", daemon=False)
        self.request_queue: queue.Queue[DialogueRequest] = request_queue
        self.event_queue: queue.Queue[DialogueEvent] = event_queue
        self.graph_builder = graph_builder or build_debate_graph
        self.timeout: float = float(timeout)

        self.stop_event: threading.Event = threading.Event()
        self.cancel_event: threading.Event = threading.Event()

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._cached_graph: Optional[Any] = None

    def stop(self) -> None:
        """Señala al worker que debe detenerse de forma limpia."""
        self.stop_event.set()
        self.cancel_event.set()

    def cancel_active(self) -> None:
        """Cancela la conversación activa actualmente en ejecución."""
        self.cancel_event.set()

    def run(self) -> None:
        """Punto de entrada del hilo secundario. Inicializa y gestiona el bucle asyncio."""
        from src.simulation.debug_logger import debug_log

        debug_log(
            "WORKER_THREAD",
            "THREAD_STARTED",
            f"thread_name={self.name}, thread_ident={threading.get_ident()}",
        )
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        debug_log(
            "WORKER_THREAD",
            "ASYNCIO_LOOP_CREATED",
            f"loop_id={id(self._loop)}",
        )

        try:
            self._loop.run_until_complete(self._worker_main_loop())
        finally:
            debug_log("WORKER_THREAD", "SHUTTING_DOWN_LOOP", "closing pending tasks")
            # Cancelar tareas pendientes antes de cerrar el loop
            pending = asyncio.all_tasks(self._loop)
            for t in pending:
                t.cancel()
            if pending:
                self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            self._loop.close()
            self._loop = None
            debug_log("WORKER_THREAD", "THREAD_EXITED", "loop closed")

    async def _worker_main_loop(self) -> None:
        """Bucle principal asíncrono que sondea solicitudes de la cola thread-safe."""
        from src.simulation.debug_logger import debug_log

        debug_log("WORKER_LOOP", "LOOP_STARTED", "polling request queue")
        while not self.stop_event.is_set():
            try:
                # Obtener solicitud sin bloquear indefinidamente
                req = self.request_queue.get_nowait()
            except queue.Empty:
                await asyncio.sleep(0.04)
                continue

            # Procesar la conversación solicitada
            debug_log(
                "WORKER_LOOP",
                "REQUEST_DEQUEUED",
                f"conv_id={req.conversation_id}, initiator={req.initiator_team}, receiver={req.receiver_team}, topic_len={len(req.topic)}",
                conversation_id=req.conversation_id,
            )
            await self._process_request(req)

    async def _process_request(self, req: DialogueRequest) -> None:
        """Ejecuta una solicitud de debate utilizando el grafo real de LangGraph."""
        import traceback
        from src.simulation.debug_logger import debug_log

        self.cancel_event.clear()
        conv_id = req.conversation_id

        # 1. Notificar inicio de la conversación
        self.event_queue.put(
            DialogueEvent(
                conversation_id=conv_id,
                event_type=DialogueEventType.STARTED,
                timestamp=time.time(),
            )
        )
        debug_log(
            "WORKER_PROCESS",
            "EVENT_STARTED_EMITTED",
            "pushed DialogueEventType.STARTED to event_queue",
            conversation_id=conv_id,
        )

        # 2. Inicializar o reutilizar el grafo compilado
        try:
            if self._cached_graph is None:
                debug_log(
                    "WORKER_PROCESS",
                    "BUILDING_DEBATE_GRAPH_START",
                    f"mode={req.mode}, style={req.style}",
                    conversation_id=conv_id,
                )
                self._cached_graph = await self.graph_builder(mode=req.mode, style=req.style)
                debug_log(
                    "WORKER_PROCESS",
                    "BUILDING_DEBATE_GRAPH_FINISHED",
                    f"graph_type={type(self._cached_graph).__name__}",
                    conversation_id=conv_id,
                )
            graph = self._cached_graph
        except Exception as exc:
            tb = traceback.format_exc()
            debug_log(
                "WORKER_PROCESS",
                "GRAPH_BUILD_FAILED",
                f"error={exc}\n{tb}",
                conversation_id=conv_id,
            )
            self.event_queue.put(
                DialogueEvent(
                    conversation_id=conv_id,
                    event_type=DialogueEventType.ERROR,
                    error_message=f"Error compilando el grafo de debate: {exc}",
                    timestamp=time.time(),
                )
            )
            return

        # 3. Preparar estado inicial compatible con DebateState
        state = initial_state(req.topic, max_rounds=req.max_rounds, style=req.style)
        # Respetar el orden asignado: iniciador toma el primer turno
        state["turn_order"] = [req.initiator_team, req.receiver_team]
        debug_log(
            "WORKER_PROCESS",
            "INITIAL_STATE_PREPARED",
            f"turn_order={state['turn_order']}, turns_taken={state['turns_taken']}, max_turns={state['max_turns']}, style={state['style']}",
            conversation_id=conv_id,
        )

        # 4. Consumir eventos del grafo en tiempo real mediante astream_events v2
        try:
            debug_log("WORKER_PROCESS", "STREAMING_EVENTS_START", "entering astream_events", conversation_id=conv_id)
            await asyncio.wait_for(
                self._stream_debate_events(graph, state, conv_id),
                timeout=self.timeout,
            )
            debug_log("WORKER_PROCESS", "STREAMING_EVENTS_FINISHED", "debate stream completed", conversation_id=conv_id)
        except asyncio.TimeoutError:
            debug_log("WORKER_PROCESS", "TIMEOUT_EXCEEDED", f"timeout={self.timeout}s", conversation_id=conv_id)
            self.event_queue.put(
                DialogueEvent(
                    conversation_id=conv_id,
                    event_type=DialogueEventType.ERROR,
                    error_message=f"Timeout superado ({self.timeout}s) esperando respuesta del modelo.",
                    timestamp=time.time(),
                )
            )
        except asyncio.CancelledError:
            debug_log("WORKER_PROCESS", "STREAM_CANCELLED", "cancelled by request", conversation_id=conv_id)
            self.event_queue.put(
                DialogueEvent(
                    conversation_id=conv_id,
                    event_type=DialogueEventType.CANCELLED,
                    timestamp=time.time(),
                )
            )
        except Exception as exc:
            tb = traceback.format_exc()
            debug_log(
                "WORKER_PROCESS",
                "STREAM_EXCEPTION",
                f"error={exc}\n{tb}",
                conversation_id=conv_id,
            )
            self.event_queue.put(
                DialogueEvent(
                    conversation_id=conv_id,
                    event_type=DialogueEventType.ERROR,
                    error_message=f"Error durante el debate: {exc}",
                    timestamp=time.time(),
                )
            )

    async def _stream_debate_events(self, graph: Any, state: Dict[str, Any], conv_id: str) -> None:
        """Itera sobre astream_events y transforma los eventos del grafo para Pygame."""
        current_team: Optional[str] = None
        turn_buffer = ""

        async for event in graph.astream_events(state, version="v2"):
            if self.stop_event.is_set() or self.cancel_event.is_set():
                self.event_queue.put(
                    DialogueEvent(
                        conversation_id=conv_id,
                        event_type=DialogueEventType.CANCELLED,
                        timestamp=time.time(),
                    )
                )
                return

            kind = event.get("event")
            name = event.get("name")

            # A) Inicio de turno de un equipo ("barcelona" o "real_madrid")
            if kind == "on_chain_start" and name in ("barcelona", "real_madrid"):
                current_team = name
                turn_buffer = ""
                debug_log(
                    "WORKER_STREAM",
                    "TURN_STARTED_EVENT",
                    f"team={current_team}",
                    conversation_id=conv_id,
                )
                self.event_queue.put(
                    DialogueEvent(
                        conversation_id=conv_id,
                        event_type=DialogueEventType.TURN_STARTED,
                        speaker_team=current_team,
                        timestamp=time.time(),
                    )
                )

            # B) Streaming de fragmentos de texto (tokens)
            elif kind == "on_chat_model_stream" and current_team is not None:
                chunk = event.get("data", {}).get("chunk")
                content = getattr(chunk, "content", None)
                if content is not None:
                    text_chunk = _extract_text(content)
                    if text_chunk:
                        turn_buffer += text_chunk
                        self.event_queue.put(
                            DialogueEvent(
                                conversation_id=conv_id,
                                event_type=DialogueEventType.TEXT_CHUNK,
                                speaker_team=current_team,
                                text=text_chunk,
                                timestamp=time.time(),
                            )
                        )

            # C) Inicio de llamada a herramienta
            elif kind == "on_tool_start" and current_team is not None:
                tool_input = event.get("data", {}).get("input") or {}
                debug_log(
                    "WORKER_STREAM",
                    "TOOL_STARTED_EVENT",
                    f"team={current_team}, tool={name}",
                    conversation_id=conv_id,
                )
                self.event_queue.put(
                    DialogueEvent(
                        conversation_id=conv_id,
                        event_type=DialogueEventType.TOOL_STARTED,
                        speaker_team=current_team,
                        tool_name=name,
                        tool_args=tool_input if isinstance(tool_input, dict) else {},
                        timestamp=time.time(),
                    )
                )

            # D) Final de turno del equipo
            elif kind == "on_chain_end" and name in ("barcelona", "real_madrid"):
                output = event.get("data", {}).get("output")
                completed_text = ""
                if output and isinstance(output, dict):
                    msgs = output.get("messages") or []
                    if msgs and isinstance(msgs[-1], dict):
                        completed_text = msgs[-1].get("content", "")
                if not completed_text.strip() and turn_buffer:
                    completed_text = turn_buffer

                debug_log(
                    "WORKER_STREAM",
                    "MESSAGE_COMPLETED_EVENT",
                    f"team={name}, text_len={len(completed_text)}",
                    conversation_id=conv_id,
                )
                self.event_queue.put(
                    DialogueEvent(
                        conversation_id=conv_id,
                        event_type=DialogueEventType.MESSAGE_COMPLETED,
                        speaker_team=name,
                        text=completed_text,
                        timestamp=time.time(),
                    )
                )
                current_team = None

        # 5. Notificar finalización exitosa del debate
        debug_log(
            "WORKER_STREAM",
            "DEBATE_FINISHED_EVENT",
            "emitting DialogueEventType.FINISHED",
            conversation_id=conv_id,
        )
        self.event_queue.put(
            DialogueEvent(
                conversation_id=conv_id,
                event_type=DialogueEventType.FINISHED,
                timestamp=time.time(),
            )
        )
