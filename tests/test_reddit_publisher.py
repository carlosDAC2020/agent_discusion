"""Tests de RedditPublisher: `praw.Reddit` mockeado, sin red real."""

from unittest.mock import MagicMock, patch

import praw.exceptions
import prawcore.exceptions
import pytest

from src.agents.barcelona_agent import DISPLAY_NAME as BARCELONA_DISPLAY_NAME
from src.social.base import PublishError
from src.social.models import Debate, DebateTurn
from src.social.reddit_publisher import RedditPublisher

_CREDS = dict(
    client_id="CID",
    client_secret="CSECRET",
    username="bot_user",
    password="pw",
    subreddit="debateagentes",
)


def _publisher() -> RedditPublisher:
    return RedditPublisher(**_CREDS)


def test_ensure_ready_sin_credenciales_lista_lo_que_falta():
    publisher = RedditPublisher(
        client_id="", client_secret="", username="", password="", subreddit=""
    )
    with pytest.raises(PublishError, match="REDDIT_CLIENT_ID"):
        publisher.ensure_ready()


def test_ensure_ready_con_credenciales_no_lanza():
    assert _publisher().ensure_ready() is None


def _fake_reddit_client():
    """Arma un Mock que imita `praw.Reddit(...).subreddit(...).submit(...)`."""
    submission = MagicMock()
    submission.id = "post1"

    comment_1 = MagicMock()
    comment_1.id = "comment1"
    comment_2 = MagicMock()
    comment_2.id = "comment2"
    submission.reply.return_value = comment_1
    comment_1.reply.return_value = comment_2

    subreddit = MagicMock()
    subreddit.submit.return_value = submission

    reddit = MagicMock()
    reddit.subreddit.return_value = subreddit
    return reddit, submission, subreddit


def test_publish_crea_post_y_encadena_un_comentario_por_turno():
    debate = Debate(
        question="Quien tiene mejor cantera?",
        mode="mcp",
        style="debate",
        turns=[
            DebateTurn(team="barcelona", content="Vamos Barca"),
            DebateTurn(team="real_madrid", content="Hala Madrid"),
        ],
    )
    publisher = _publisher()
    reddit, submission, subreddit = _fake_reddit_client()

    with patch("src.social.reddit_publisher.praw.Reddit", return_value=reddit) as reddit_cls:
        result = publisher.publish(debate)

    reddit_cls.assert_called_once_with(
        client_id="CID",
        client_secret="CSECRET",
        username="bot_user",
        password="pw",
        user_agent=publisher.user_agent,
    )
    reddit.subreddit.assert_called_once_with("debateagentes")
    subreddit.submit.assert_called_once()
    assert "Quien tiene mejor cantera?" in subreddit.submit.call_args.kwargs["title"]

    assert result.platform == "reddit"
    assert result.posted == 3
    assert result.references == ["post1", "comment1", "comment2"]

    # Primer turno responde al post; segundo turno responde al primer comentario.
    submission.reply.assert_called_once()
    assert BARCELONA_DISPLAY_NAME in submission.reply.call_args.args[0]
    comment_1 = submission.reply.return_value
    comment_1.reply.assert_called_once()
    assert "Hala Madrid" in comment_1.reply.call_args.args[0]


def test_publish_incluye_traza_de_tools_en_markdown():
    debate = Debate(
        question="q",
        mode="mcp",
        style="debate",
        turns=[
            DebateTurn(
                team="barcelona",
                content="Con datos, Lewandowski manda.",
                tool_calls=[{"tool": "compare_players", "args": {"player_a": "A", "player_b": "B"}}],
            )
        ],
    )
    publisher = _publisher()
    reddit, submission, _subreddit = _fake_reddit_client()

    with patch("src.social.reddit_publisher.praw.Reddit", return_value=reddit):
        publisher.publish(debate)

    turn_body = submission.reply.call_args.args[0]
    assert "compare_players(" in turn_body
    assert f"**{BARCELONA_DISPLAY_NAME}**" in turn_body


def test_publish_envuelve_error_de_autenticacion_prawcore():
    debate = Debate(question="q", mode="mcp", style="debate", turns=[])
    publisher = _publisher()

    with patch(
        "src.social.reddit_publisher.praw.Reddit",
        side_effect=prawcore.exceptions.PrawcoreException("credenciales invalidas"),
    ):
        with pytest.raises(PublishError, match="autenticacion"):
            publisher.publish(debate)


def test_publish_envuelve_error_de_api_praw():
    debate = Debate(question="q", mode="mcp", style="debate", turns=[])
    publisher = _publisher()
    reddit, submission, subreddit = _fake_reddit_client()
    subreddit.submit.side_effect = praw.exceptions.PRAWException("subreddit no existe")

    with patch("src.social.reddit_publisher.praw.Reddit", return_value=reddit):
        with pytest.raises(PublishError, match="subreddit no existe"):
            publisher.publish(debate)
