"""Publica el debate en un chat/canal de Telegram, turno por turno.

Cada turno se manda como un mensaje separado, encadenado con
`reply_to_message_id` al turno anterior (asi el hilo de Telegram refleja
la secuencia de rebates del debate). Requiere que el bot ya este agregado
como administrador del chat/canal destino.
"""

from typing import Optional

import requests

from src.config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from src.social.base import DebatePublisher, PublishError, PublishResult
from src.social.models import Debate

_API_BASE = "https://api.telegram.org"
_MAX_MESSAGE_LEN = 4000  # limite real de Telegram: 4096 caracteres UTF-16
_TRUNCATED_SUFFIX = "… (truncado)"


def _clip(text: str) -> str:
    if len(text) <= _MAX_MESSAGE_LEN:
        return text
    return text[: _MAX_MESSAGE_LEN - len(_TRUNCATED_SUFFIX)] + _TRUNCATED_SUFFIX


class TelegramPublisher(DebatePublisher):
    name = "telegram"

    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        self.bot_token = bot_token or TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or TELEGRAM_CHAT_ID

    def _send_message(self, text: str, reply_to_message_id: Optional[int] = None) -> int:
        if not self.bot_token or not self.chat_id:
            raise PublishError(
                "Faltan credenciales de Telegram: definir TELEGRAM_BOT_TOKEN y "
                "TELEGRAM_CHAT_ID en tu .env."
            )

        payload = {"chat_id": self.chat_id, "text": _clip(text)}
        if reply_to_message_id is not None:
            payload["reply_to_message_id"] = reply_to_message_id

        try:
            response = requests.post(
                f"{_API_BASE}/bot{self.bot_token}/sendMessage", json=payload, timeout=15
            )
        except requests.RequestException as exc:
            raise PublishError(f"No se pudo conectar con la API de Telegram: {exc}") from exc

        data = response.json()
        if not response.ok or not data.get("ok"):
            detail = data.get("description", response.text)
            raise PublishError(f"Telegram respondio con un error: {detail}")

        return data["result"]["message_id"]

    def _header_text(self, debate: Debate) -> str:
        return (
            f"\U0001f5e3 Debate: {debate.question}\n"
            f"(modo={debate.mode}, estilo={debate.style})"
        )

    def _turn_text(self, turn) -> str:
        emoji = "\U0001f535" if turn.team == "barcelona" else "⚪"
        return f"{emoji} {turn.team_label}: {turn.content}"

    def publish(self, debate: Debate) -> PublishResult:
        last_message_id = self._send_message(self._header_text(debate))
        references = [str(last_message_id)]

        for turn in debate.turns:
            last_message_id = self._send_message(
                self._turn_text(turn), reply_to_message_id=last_message_id
            )
            references.append(str(last_message_id))

        return PublishResult(platform=self.name, posted=len(references), references=references)
