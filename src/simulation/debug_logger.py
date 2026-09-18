"""Módulo de logging estructurado e instrumentación de depuración para la simulación.

Proporciona registros con timestamp, componente, identidad de agente/conversación
y estado relevante, filtrando redundancias para no emitir eventos en cada frame.
"""

import datetime
from typing import Dict, Optional, Tuple


class SimulationDebugLogger:
    """Logger estructurado para la trazabilidad end-to-end de la simulación."""

    _last_logged_states: Dict[str, Tuple[str, ...]] = {}

    @classmethod
    def log(
        cls,
        component: str,
        action: str,
        details: str,
        agent_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> None:
        """Emite una línea de log estructurada inmediatamente a stdout."""
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        ctx_parts = []
        if agent_id:
            ctx_parts.append(f"agent={agent_id}")
        if conversation_id:
            ctx_parts.append(f"conv={conversation_id}")
        ctx_str = f" [{', '.join(ctx_parts)}]" if ctx_parts else ""
        print(f"[{now_str}] [{component.upper()}]{ctx_str} {action} -> {details}", flush=True)

    @classmethod
    def log_state_change(
        cls,
        key: str,
        state_tuple: Tuple[str, ...],
        component: str,
        action: str,
        details: str,
        agent_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> None:
        """Emite log únicamente si la tupla de estado ha cambiado respecto a la última emisión."""
        if cls._last_logged_states.get(key) != state_tuple:
            cls._last_logged_states[key] = state_tuple
            cls.log(component, action, details, agent_id=agent_id, conversation_id=conversation_id)

    @classmethod
    def reset(cls) -> None:
        """Reinicia el caché de estados registrados."""
        cls._last_logged_states.clear()


debug_log = SimulationDebugLogger.log
debug_log_state = SimulationDebugLogger.log_state_change
