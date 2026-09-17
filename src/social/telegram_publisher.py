"""Publica el debate en Telegram con un bot INDEPENDIENTE por equipo.

Josep (Barcelona) y Paco (Real Madrid) publican sus propios turnos como
cuentas de Telegram distintas -no un unico bot narrando ambos lados-, asi
que la identidad del hablante la da el bot (nombre, foto de perfil) en vez
de una etiqueta de texto. Ambos bots deben estar agregados como
administradores del mismo chat/canal. Cada turno se encadena con
`reply_to_message_id` al anterior (el id de mensaje es valido entre bots
distintos, ambos escriben en el mismo chat).
"""

import html
import time
from typing import Optional

import requests

from src.agents.barcelona_agent import TEAM_NAME as BARCELONA
from src.agents.real_madrid_agent import TEAM_NAME as REAL_MADRID
from src.config.settings import (
    TELEGRAM_BOT_TOKEN_BARCELONA,
    TELEGRAM_BOT_TOKEN_REAL_MADRID,
    TELEGRAM_CHAT_ID,
)
from src.social.base import DebatePublisher, PublishError, PublishResult
from src.social.models import Debate, DebateTurn

_API_BASE = "https://api.telegram.org"
_MAX_MESSAGE_LEN = 4000  # limite real de Telegram: 4096 caracteres UTF-16
_MAX_CONTENT_LEN = 3500  # deja margen para la traza de tools alrededor
_TRUNCATED_SUFFIX = "… (truncado)"

# Telegram permite ~1 mensaje/segundo por bot a un mismo chat; nos quedamos
# un poco por debajo. Es POR BOT (dict), no global: como Josep y Paco son
# bots distintos, cada uno tiene su propio cupo y no hace falta esperar el
# turno del otro.
_MIN_INTERVAL_SECONDS = 1.1
_MAX_RATE_LIMIT_RETRIES = 3


def _clip(text: str, max_len: int = _MAX_MESSAGE_LEN) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - len(_TRUNCATED_SUFFIX)] + _TRUNCATED_SUFFIX


def _escape_html(text: str) -> str:
    """Escapa para el `parse_mode=HTML` de Telegram (no toca comillas)."""
    return html.escape(text, quote=False)


def _tool_trace_lines(tool_calls: list[dict]) -> list[str]:
    lines = []
    for call in tool_calls:
        args_str = ", ".join(f"{k}={v!r}" for k, v in call.get("args", {}).items())
        lines.append(f"\U0001f527 {call.get('tool', '?')}({args_str})")
    return lines


class TelegramPublisher(DebatePublisher):
    name = "telegram"

    def __init__(self, bot_tokens: Optional[dict] = None, chat_id: Optional[str] = None):
        # `is None` (no truthiness) a proposito: permite instanciar con
        # valores vacios explicitos en tests sin caer al valor de settings.
        self.bot_tokens = (
            {BARCELONA: TELEGRAM_BOT_TOKEN_BARCELONA, REAL_MADRID: TELEGRAM_BOT_TOKEN_REAL_MADRID}
            if bot_tokens is None
            else bot_tokens
        )
        self.chat_id = TELEGRAM_CHAT_ID if chat_id is None else chat_id
        self._last_sent_at: dict[str, float] = {}

    def _missing_credentials(self) -> list[str]:
        missing = []
        if not self.chat_id:
            missing.append("TELEGRAM_CHAT_ID")
        if not self.bot_tokens.get(BARCELONA):
            missing.append("TELEGRAM_BOT_TOKEN_BARCELONA")
        if not self.bot_tokens.get(REAL_MADRID):
            missing.append("TELEGRAM_BOT_TOKEN_REAL_MADRID")
        return missing

    def _check_credentials(self) -> None:
        missing = self._missing_credentials()
        if missing:
            raise PublishError(f"Faltan credenciales de Telegram: definir {', '.join(missing)} en tu .env.")

    def ensure_ready(self) -> None:
        """Valida credenciales antes de correr el debate (ver DebatePublisher.ensure_ready)."""
        self._check_credentials()

    def _throttle(self, bot_token: str) -> None:
        last_sent_at = self._last_sent_at.get(bot_token)
        if last_sent_at is None:
            return
        wait = _MIN_INTERVAL_SECONDS - (time.monotonic() - last_sent_at)
        if wait > 0:
            time.sleep(wait)

    def _post(self, bot_token: str, payload: dict) -> requests.Response:
        try:
            return requests.post(f"{_API_BASE}/bot{bot_token}/sendMessage", json=payload, timeout=15)
        except requests.RequestException as exc:
            raise PublishError(f"No se pudo conectar con la API de Telegram: {exc}") from exc
        finally:
            self._last_sent_at[bot_token] = time.monotonic()

    def _send_message(self, bot_token: str, text: str, reply_to_message_id: Optional[int] = None) -> int:
        payload = {"chat_id": self.chat_id, "text": _clip(text), "parse_mode": "HTML"}
        if reply_to_message_id is not None:
            payload["reply_to_message_id"] = reply_to_message_id

        for attempt in range(1, _MAX_RATE_LIMIT_RETRIES + 1):
            self._throttle(bot_token)
            response = self._post(bot_token, payload)
            data = response.json()

            retry_after = (data.get("parameters") or {}).get("retry_after")
            if response.status_code == 429 or (not data.get("ok") and retry_after is not None):
                if attempt == _MAX_RATE_LIMIT_RETRIES:
                    raise PublishError(
                        f"Telegram devolvio rate-limit (429) {attempt} veces seguidas; "
                        "se dejo de reintentar."
                    )
                time.sleep(retry_after or 1)
                continue

            if not response.ok or not data.get("ok"):
                detail = data.get("description", response.text)
                raise PublishError(f"Telegram respondio con un error: {detail}")

            return data["result"]["message_id"]

        raise PublishError("No se pudo publicar el mensaje en Telegram (reintentos agotados).")

    def _header_text(self, debate: Debate) -> str:
        question = _escape_html(_clip(debate.question, _MAX_CONTENT_LEN))
        mode = _escape_html(debate.mode)
        style = _escape_html(debate.style)
        return f"\U0001f5e3 <b>Debate</b>: {question}\n(modo={mode}, estilo={style})"

    def _turn_text(self, turn: DebateTurn) -> str:
        # Sin nombre de equipo en negrita: la identidad la da el bot que
        # publica (nombre + foto de perfil en Telegram), no una etiqueta.
        lines = [_escape_html(line) for line in _tool_trace_lines(turn.tool_calls)]
        lines.append(_escape_html(_clip(turn.content, _MAX_CONTENT_LEN)))
        return _clip("\n".join(lines))

    def publish(self, debate: Debate) -> PublishResult:
        self.ensure_ready()

        header_team = debate.turns[0].team if debate.turns else BARCELONA
        header_bot = self.bot_tokens[header_team]
        last_message_id = self._send_message(header_bot, self._header_text(debate))
        references = [str(last_message_id)]

        for turn in debate.turns:
            last_message_id = self._send_message(
                self.bot_tokens[turn.team], self._turn_text(turn), reply_to_message_id=last_message_id
            )
            references.append(str(last_message_id))

        return PublishResult(platform=self.name, posted=len(references), references=references)
