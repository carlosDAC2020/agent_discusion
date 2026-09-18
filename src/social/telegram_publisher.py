"""Publica el debate en un grupo de Telegram con 3 bots independientes.

Un bot "narrador" publica la pregunta inicial, y Josep/Paco publican sus
propios turnos como cuentas de Telegram distintas -no un unico bot
narrando ambos lados-, asi que la identidad del hablante la da el bot
(nombre, foto de perfil) en vez de una etiqueta de texto.

IMPORTANTE: Telegram no permite que un bot construya un `reply_to_message_id`
sobre un mensaje enviado por OTRO bot (falla con "message to be replied not
found", confirmado en pruebas manuales, independiente del Privacy Mode). Por
eso los turnos NO se encadenan por reply entre si: el orden cronologico de
llegada al grupo ya cuenta la secuencia del debate.

Los 3 bots deben estar agregados a un GRUPO (no canal: en un canal todos los
posts se muestran bajo la identidad del canal, no la del bot que publico).
"""

import html
import time
from typing import Optional

import requests

from src.agents.barcelona_agent import TEAM_NAME as BARCELONA
from src.agents.real_madrid_agent import TEAM_NAME as REAL_MADRID
from src.config.settings import (
    TELEGRAM_BOT_TOKEN,
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
# un poco por debajo. Es POR BOT (dict), no global: cada bot es una cuenta
# distinta con su propio cupo.
_MIN_INTERVAL_SECONDS = 1.1
_MAX_RATE_LIMIT_RETRIES = 3


def _clip(text: str, max_len: int = _MAX_MESSAGE_LEN) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - len(_TRUNCATED_SUFFIX)] + _TRUNCATED_SUFFIX


def _escape_html(text: str) -> str:
    """Escapa para el `parse_mode=HTML` de Telegram (no toca comillas)."""
    return html.escape(text, quote=False)


class TelegramPublisher(DebatePublisher):
    name = "telegram"

    def __init__(
        self,
        narrator_token: Optional[str] = None,
        bot_tokens: Optional[dict] = None,
        chat_id: Optional[str] = None,
    ):
        # `is None` (no truthiness) a proposito: permite instanciar con
        # valores vacios explicitos en tests sin caer al valor de settings.
        self.narrator_token = TELEGRAM_BOT_TOKEN if narrator_token is None else narrator_token
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
        if not self.narrator_token:
            missing.append("TELEGRAM_BOT_TOKEN")
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

    def _send_message(self, bot_token: str, text: str) -> int:
        # Sin reply_to_message_id: Telegram no deja que un bot responda a un
        # mensaje de otro bot (ver docstring del modulo). El orden de envio
        # ya transmite la secuencia del debate.
        payload = {"chat_id": self.chat_id, "text": _clip(text), "parse_mode": "HTML"}

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
        # Sin "(modo=..., estilo=...)": es detalle tecnico de configuracion,
        # no algo que le interese a quien lee el grupo. Esa trazabilidad ya
        # se ve en la consola de la CLI.
        question = _escape_html(_clip(debate.question, _MAX_CONTENT_LEN))
        return f"\U0001f5e3 <b>Debate</b>: {question}"

    def _turn_text(self, turn: DebateTurn) -> str:
        # Sin nombre de equipo en negrita (la identidad la da el bot que
        # publica) ni traza de tools (🔧 ...): eso queda para la consola de
        # la CLI, en Telegram solo va el texto del turno.
        return _escape_html(_clip(turn.content, _MAX_CONTENT_LEN))

    def publish(self, debate: Debate) -> PublishResult:
        self.ensure_ready()

        header_id = self._send_message(self.narrator_token, self._header_text(debate))
        references = [str(header_id)]

        for turn in debate.turns:
            message_id = self._send_message(self.bot_tokens[turn.team], self._turn_text(turn))
            references.append(str(message_id))

        return PublishResult(platform=self.name, posted=len(references), references=references)
