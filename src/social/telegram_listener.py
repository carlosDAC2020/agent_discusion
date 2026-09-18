"""Escucha el chat de Telegram para disparar debates con "/debate <pregunta>".

Long-polling sobre `getUpdates` con el bot narrador -sin webhook, para no
necesitar un endpoint HTTPS publico-. Cuando detecta un mensaje que empieza
con `TRIGGER_PREFIX` en el chat configurado, devuelve la pregunta para que
el caller (`src/cli/main.py`) corra el debate y lo publique.
"""

from typing import Optional

import requests

from src.config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from src.social.base import PublishError

_API_BASE = "https://api.telegram.org"
TRIGGER_PREFIX = "/debate"
_POLL_TIMEOUT_SECONDS = 30


class TelegramListener:
    """Detecta comandos `/debate <pregunta>` en el chat configurado."""

    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        # `is None` (no truthiness) a proposito, mismo motivo que en
        # TelegramPublisher: permite valores vacios explicitos en tests.
        self.bot_token = TELEGRAM_BOT_TOKEN if bot_token is None else bot_token
        self.chat_id = str(TELEGRAM_CHAT_ID if chat_id is None else chat_id)
        self._offset: Optional[int] = None

    def ensure_ready(self) -> None:
        if not self.bot_token or not self.chat_id:
            raise PublishError(
                "Faltan credenciales de Telegram: definir TELEGRAM_BOT_TOKEN y "
                "TELEGRAM_CHAT_ID en tu .env."
            )

    def _get_updates(self) -> list[dict]:
        params = {"timeout": _POLL_TIMEOUT_SECONDS}
        if self._offset is not None:
            params["offset"] = self._offset

        try:
            response = requests.get(
                f"{_API_BASE}/bot{self.bot_token}/getUpdates",
                params=params,
                timeout=_POLL_TIMEOUT_SECONDS + 10,
            )
        except requests.RequestException as exc:
            raise PublishError(f"No se pudo conectar con la API de Telegram: {exc}") from exc

        data = response.json()
        if not response.ok or not data.get("ok"):
            detail = data.get("description", response.text)
            raise PublishError(f"Telegram respondio con un error al escuchar: {detail}")
        return data["result"]

    def _extract_question(self, update: dict) -> Optional[str]:
        message = update.get("message") or {}
        chat_id = str(message.get("chat", {}).get("id", ""))
        if chat_id != self.chat_id:
            return None

        text = (message.get("text") or "").strip()
        if not text.lower().startswith(TRIGGER_PREFIX):
            return None

        question = text[len(TRIGGER_PREFIX) :].strip()
        return question or None

    def poll_once(self) -> list[str]:
        """Trae las updates pendientes (bloquea hasta `_POLL_TIMEOUT_SECONDS`
        si no hay ninguna nueva) y devuelve las preguntas detectadas, en
        el orden en que llegaron. Avanza el offset para no reprocesarlas."""
        updates = self._get_updates()
        questions = []
        for update in updates:
            self._offset = update["update_id"] + 1
            question = self._extract_question(update)
            if question:
                questions.append(question)
        return questions
