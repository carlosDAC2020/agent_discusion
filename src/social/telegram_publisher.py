"""Publica el debate en un chat/canal de Telegram, turno por turno.

Cada turno se manda como un mensaje separado, encadenado con
`reply_to_message_id` al turno anterior (asi el hilo de Telegram refleja
la secuencia de rebates del debate). Requiere que el bot ya este agregado
como administrador del chat/canal destino.
"""

import html
import time
from typing import Optional

import requests

from src.config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from src.social.base import DebatePublisher, PublishError, PublishResult
from src.social.models import Debate, DebateTurn

_API_BASE = "https://api.telegram.org"
_MAX_MESSAGE_LEN = 4000  # limite real de Telegram: 4096 caracteres UTF-16
_MAX_CONTENT_LEN = 3500  # deja margen para el header/traza de tools alrededor
_TRUNCATED_SUFFIX = "… (truncado)"

# Telegram permite ~1 mensaje/segundo a un mismo chat; nos quedamos un poco
# por debajo para no rozar el limite ante debates con muchas rondas.
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

    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        # `is None` (no truthiness) a proposito: permite instanciar con
        # bot_token="" / chat_id="" explicito (p.ej. en tests) sin que
        # caiga silenciosamente al valor de settings.
        self.bot_token = TELEGRAM_BOT_TOKEN if bot_token is None else bot_token
        self.chat_id = TELEGRAM_CHAT_ID if chat_id is None else chat_id
        self._last_sent_at: Optional[float] = None

    def _check_credentials(self) -> None:
        if not self.bot_token or not self.chat_id:
            raise PublishError(
                "Faltan credenciales de Telegram: definir TELEGRAM_BOT_TOKEN y "
                "TELEGRAM_CHAT_ID en tu .env."
            )

    def ensure_ready(self) -> None:
        """Valida credenciales antes de correr el debate (ver DebatePublisher.ensure_ready)."""
        self._check_credentials()

    def _throttle(self) -> None:
        if self._last_sent_at is None:
            return
        wait = _MIN_INTERVAL_SECONDS - (time.monotonic() - self._last_sent_at)
        if wait > 0:
            time.sleep(wait)

    def _post(self, payload: dict) -> requests.Response:
        try:
            return requests.post(
                f"{_API_BASE}/bot{self.bot_token}/sendMessage", json=payload, timeout=15
            )
        except requests.RequestException as exc:
            raise PublishError(f"No se pudo conectar con la API de Telegram: {exc}") from exc
        finally:
            self._last_sent_at = time.monotonic()

    def _send_message(self, text: str, reply_to_message_id: Optional[int] = None) -> int:
        self._check_credentials()

        payload = {"chat_id": self.chat_id, "text": _clip(text), "parse_mode": "HTML"}
        if reply_to_message_id is not None:
            payload["reply_to_message_id"] = reply_to_message_id

        for attempt in range(1, _MAX_RATE_LIMIT_RETRIES + 1):
            self._throttle()
            response = self._post(payload)
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
        emoji = "\U0001f535" if turn.team == "barcelona" else "⚪"
        lines = [f"{emoji} <b>{_escape_html(turn.team_label)}</b>"]
        lines.extend(_escape_html(line) for line in _tool_trace_lines(turn.tool_calls))
        lines.append(_escape_html(_clip(turn.content, _MAX_CONTENT_LEN)))
        return _clip("\n".join(lines))

    def publish(self, debate: Debate) -> PublishResult:
        last_message_id = self._send_message(self._header_text(debate))
        references = [str(last_message_id)]

        for turn in debate.turns:
            last_message_id = self._send_message(
                self._turn_text(turn), reply_to_message_id=last_message_id
            )
            references.append(str(last_message_id))

        return PublishResult(platform=self.name, posted=len(references), references=references)
