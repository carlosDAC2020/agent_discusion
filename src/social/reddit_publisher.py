"""Publica el debate en Reddit: post inicial + un comentario por turno.

Cada turno se manda como un comentario, encadenado como reply al turno
anterior (o al post inicial, para el primer turno) - asi el hilo de
Reddit refleja la secuencia de rebates del debate. Requiere una app tipo
"script" en Reddit (client_id/secret) y una cuenta con permiso de post en
el subreddit destino (uno propio es lo mas simple).

A diferencia de Telegram, no throttleamos a mano: `praw` ya respeta los
headers de rate-limit de Reddit y duerme automaticamente si hace falta.
"""

from typing import Optional

import praw
import prawcore

from src.config.settings import (
    REDDIT_CLIENT_ID,
    REDDIT_CLIENT_SECRET,
    REDDIT_PASSWORD,
    REDDIT_SUBREDDIT,
    REDDIT_USER_AGENT,
    REDDIT_USERNAME,
)
from src.social.base import DebatePublisher, PublishError, PublishResult
from src.social.models import Debate, DebateTurn

_MAX_TITLE_LEN = 280  # Reddit permite 300; dejamos margen
_MAX_BODY_LEN = 9000  # Reddit permite ~40000; nos quedamos conservadores
_TRUNCATED_SUFFIX = "… (truncado)"


def _clip(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - len(_TRUNCATED_SUFFIX)] + _TRUNCATED_SUFFIX


def _tool_trace_lines(tool_calls: list[dict]) -> list[str]:
    lines = []
    for call in tool_calls:
        args_str = ", ".join(f"{k}={v!r}" for k, v in call.get("args", {}).items())
        lines.append(f"> \U0001f527 `{call.get('tool', '?')}({args_str})`")
    return lines


class RedditPublisher(DebatePublisher):
    name = "reddit"

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        user_agent: Optional[str] = None,
        subreddit: Optional[str] = None,
    ):
        # `is None` (no truthiness), mismo motivo que TelegramPublisher: poder
        # instanciar con valores vacios explicitos en tests sin caer al
        # valor de settings.
        self.client_id = REDDIT_CLIENT_ID if client_id is None else client_id
        self.client_secret = REDDIT_CLIENT_SECRET if client_secret is None else client_secret
        self.username = REDDIT_USERNAME if username is None else username
        self.password = REDDIT_PASSWORD if password is None else password
        self.user_agent = REDDIT_USER_AGENT if user_agent is None else user_agent
        self.subreddit = REDDIT_SUBREDDIT if subreddit is None else subreddit

    def _missing_credentials(self) -> list[str]:
        required = {
            "REDDIT_CLIENT_ID": self.client_id,
            "REDDIT_CLIENT_SECRET": self.client_secret,
            "REDDIT_USERNAME": self.username,
            "REDDIT_PASSWORD": self.password,
            "REDDIT_SUBREDDIT": self.subreddit,
        }
        return [name for name, value in required.items() if not value]

    def ensure_ready(self) -> None:
        """Valida credenciales antes de correr el debate (ver DebatePublisher.ensure_ready)."""
        missing = self._missing_credentials()
        if missing:
            raise PublishError(
                f"Faltan credenciales de Reddit: definir {', '.join(missing)} en tu .env."
            )

    def _client(self) -> praw.Reddit:
        return praw.Reddit(
            client_id=self.client_id,
            client_secret=self.client_secret,
            username=self.username,
            password=self.password,
            user_agent=self.user_agent,
        )

    def _title(self, debate: Debate) -> str:
        return _clip(f"[Debate IA] {debate.question}", _MAX_TITLE_LEN)

    def _header_body(self, debate: Debate) -> str:
        return (
            "Debate generado automaticamente entre dos agentes IA "
            f"(modo={debate.mode}, estilo={debate.style}).\n\n"
            "Cada respuesta llega como comentario, en orden."
        )

    def _turn_body(self, turn: DebateTurn) -> str:
        lines = [f"**{turn.team_label}**", ""]
        lines.extend(_tool_trace_lines(turn.tool_calls))
        lines.append(_clip(turn.content, _MAX_BODY_LEN))
        return "\n".join(lines)

    def publish(self, debate: Debate) -> PublishResult:
        self.ensure_ready()

        try:
            reddit = self._client()
            subreddit = reddit.subreddit(self.subreddit)
            submission = subreddit.submit(
                title=self._title(debate), selftext=self._header_body(debate)
            )

            references = [submission.id]
            last = submission
            for turn in debate.turns:
                last = last.reply(self._turn_body(turn))
                references.append(last.id)
        except prawcore.exceptions.PrawcoreException as exc:
            raise PublishError(
                f"Reddit respondio con un error de autenticacion/red: {exc}"
            ) from exc
        except praw.exceptions.PRAWException as exc:
            raise PublishError(f"Reddit respondio con un error: {exc}") from exc

        return PublishResult(platform=self.name, posted=len(references), references=references)
