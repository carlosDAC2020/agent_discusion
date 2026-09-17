"""Tests de src/social: adaptador de datos, registry y TelegramPublisher.

TelegramPublisher se prueba con `requests.post` mockeado, sin red real.
RedditPublisher tiene su propio archivo: tests/test_reddit_publisher.py.
"""

from unittest.mock import Mock, patch

import pytest

from src.agents.barcelona_agent import DISPLAY_NAME as BARCELONA_DISPLAY_NAME
from src.agents.real_madrid_agent import DISPLAY_NAME as REAL_MADRID_DISPLAY_NAME
from src.social.base import PublishError
from src.social.models import Debate, DebateTurn, debate_from_result
from src.social.registry import (
    IMPLEMENTED_PLATFORMS,
    PLANNED_PLATFORMS,
    available_platforms,
    get_publisher,
)
from src.social.telegram_publisher import TelegramPublisher


def test_debate_from_result_adapta_mensajes_del_orquestador():
    result = {
        "messages": [
            {"team": "barcelona", "content": "Vamos Barca", "tool_calls": []},
            {"team": "real_madrid", "content": "Hala Madrid", "tool_calls": []},
        ]
    }
    debate = debate_from_result("pregunta", "mcp", "debate", result)

    assert debate.question == "pregunta"
    assert debate.mode == "mcp"
    assert debate.style == "debate"
    assert debate.turns == [
        DebateTurn(team="barcelona", content="Vamos Barca"),
        DebateTurn(team="real_madrid", content="Hala Madrid"),
    ]


def test_debate_turn_team_label_conoce_ambos_equipos():
    # Se compara contra DISPLAY_NAME (no un string hardcodeado): si Dev 2
    # vuelve a cambiar el nombre de presentacion, este test lo sigue.
    assert DebateTurn(team="barcelona", content="x").team_label == BARCELONA_DISPLAY_NAME
    assert DebateTurn(team="real_madrid", content="x").team_label == REAL_MADRID_DISPLAY_NAME
    assert DebateTurn(team="otro", content="x").team_label == "otro"


def test_registry_conoce_las_4_plataformas():
    assert available_platforms() == ["bluesky", "discord", "reddit", "telegram"]
    assert IMPLEMENTED_PLATFORMS == {"telegram", "reddit"}
    assert PLANNED_PLATFORMS == {"bluesky", "discord"}


def test_get_publisher_plataforma_desconocida_da_value_error():
    with pytest.raises(ValueError, match="Plataforma desconocida"):
        get_publisher("myspace")


def test_get_publisher_planeada_falla_recien_al_publicar():
    publisher = get_publisher("discord")
    debate = Debate(question="q", mode="mcp", style="debate", turns=[])
    with pytest.raises(NotImplementedError):
        publisher.publish(debate)


def _fake_response(message_id: int):
    resp = Mock()
    resp.ok = True
    resp.json.return_value = {"ok": True, "result": {"message_id": message_id}}
    return resp


_BOT_TOKENS = {"barcelona": "TOKEN_JOSEP", "real_madrid": "TOKEN_PACO"}


def test_telegram_publisher_sin_credenciales_lista_lo_que_falta():
    publisher = TelegramPublisher(bot_tokens={"barcelona": "", "real_madrid": ""}, chat_id="")
    debate = Debate(question="q", mode="mcp", style="debate", turns=[])
    with pytest.raises(PublishError, match="TELEGRAM_CHAT_ID"):
        publisher.publish(debate)


def test_telegram_publisher_ensure_ready_sin_un_bot_da_publish_error():
    # Falta solo el bot de Real Madrid: el mensaje debe decirlo puntualmente.
    publisher = TelegramPublisher(
        bot_tokens={"barcelona": "TOKEN_JOSEP", "real_madrid": ""}, chat_id="123"
    )
    with pytest.raises(PublishError, match="TELEGRAM_BOT_TOKEN_REAL_MADRID"):
        publisher.ensure_ready()


def test_telegram_publisher_ensure_ready_con_credenciales_no_lanza():
    publisher = TelegramPublisher(bot_tokens=_BOT_TOKENS, chat_id="123")
    assert publisher.ensure_ready() is None


def test_telegram_publisher_publica_header_y_cada_turno_con_el_bot_de_su_equipo():
    debate = Debate(
        question="Quien tiene mejor delantera?",
        mode="mcp",
        style="debate",
        turns=[
            DebateTurn(team="barcelona", content="Vamos Barca"),
            DebateTurn(team="real_madrid", content="Hala Madrid"),
        ],
    )
    publisher = TelegramPublisher(bot_tokens=_BOT_TOKENS, chat_id="123")

    responses = [_fake_response(1), _fake_response(2), _fake_response(3)]
    with (
        patch("src.social.telegram_publisher.requests.post", side_effect=responses) as post,
        patch("src.social.telegram_publisher.time.sleep"),
    ):
        result = publisher.publish(debate)

    assert result.platform == "telegram"
    assert result.posted == 3
    assert result.references == ["1", "2", "3"]

    assert post.call_count == 3
    first_call, second_call, third_call = post.call_args_list

    # El header lo manda el bot del equipo que habla primero (Barcelona
    # aca), y no responde a ningun mensaje previo.
    assert "TOKEN_JOSEP" in first_call.args[0]
    assert "reply_to_message_id" not in first_call.kwargs["json"]

    # Cada turno lo manda el bot de SU equipo, respondiendo al mensaje
    # anterior (header -> turno 1 -> turno 2), sin importar que bot lo mando.
    assert "TOKEN_JOSEP" in second_call.args[0]
    assert second_call.kwargs["json"]["reply_to_message_id"] == 1
    assert "Vamos Barca" in second_call.kwargs["json"]["text"]

    assert "TOKEN_PACO" in third_call.args[0]
    assert third_call.kwargs["json"]["reply_to_message_id"] == 2
    assert "Hala Madrid" in third_call.kwargs["json"]["text"]


def test_telegram_publisher_error_de_api_da_publish_error():
    debate = Debate(question="q", mode="mcp", style="debate", turns=[])
    publisher = TelegramPublisher(bot_tokens=_BOT_TOKENS, chat_id="123")

    resp = Mock()
    resp.ok = False
    resp.json.return_value = {"ok": False, "description": "chat not found"}
    resp.text = "chat not found"

    with patch("src.social.telegram_publisher.requests.post", return_value=resp):
        with pytest.raises(PublishError, match="chat not found"):
            publisher.publish(debate)


def _rate_limited_response(retry_after: int = 2):
    resp = Mock()
    resp.ok = False
    resp.status_code = 429
    resp.json.return_value = {
        "ok": False,
        "error_code": 429,
        "description": "Too Many Requests",
        "parameters": {"retry_after": retry_after},
    }
    return resp


def test_telegram_publisher_reintenta_tras_rate_limit_429():
    debate = Debate(question="q", mode="mcp", style="debate", turns=[])
    publisher = TelegramPublisher(bot_tokens=_BOT_TOKENS, chat_id="123")

    responses = [_rate_limited_response(retry_after=2), _fake_response(1)]
    with (
        patch("src.social.telegram_publisher.requests.post", side_effect=responses) as post,
        patch("src.social.telegram_publisher.time.sleep") as sleep_mock,
    ):
        result = publisher.publish(debate)

    assert result.posted == 1
    assert post.call_count == 2
    sleep_mock.assert_any_call(2)


def test_telegram_publisher_rate_limit_persistente_agota_reintentos():
    debate = Debate(question="q", mode="mcp", style="debate", turns=[])
    publisher = TelegramPublisher(bot_tokens=_BOT_TOKENS, chat_id="123")

    with (
        patch(
            "src.social.telegram_publisher.requests.post",
            return_value=_rate_limited_response(),
        ) as post,
        patch("src.social.telegram_publisher.time.sleep"),
    ):
        with pytest.raises(PublishError, match="rate-limit"):
            publisher.publish(debate)

    assert post.call_count == 3


def test_telegram_publisher_usa_html_y_el_bot_del_equipo_no_texto():
    debate = Debate(
        question="q",
        mode="mcp",
        style="debate",
        turns=[DebateTurn(team="real_madrid", content="Hala Madrid")],
    )
    publisher = TelegramPublisher(bot_tokens=_BOT_TOKENS, chat_id="123")

    with (
        patch(
            "src.social.telegram_publisher.requests.post",
            side_effect=[_fake_response(1), _fake_response(2)],
        ) as post,
        patch("src.social.telegram_publisher.time.sleep"),
    ):
        publisher.publish(debate)

    header_call, turn_call = post.call_args_list
    assert header_call.kwargs["json"]["parse_mode"] == "HTML"
    assert turn_call.kwargs["json"]["parse_mode"] == "HTML"

    # La identidad la da el bot (Paco/Real Madrid), no una etiqueta en el texto.
    assert "TOKEN_PACO" in turn_call.args[0]
    assert REAL_MADRID_DISPLAY_NAME not in turn_call.kwargs["json"]["text"]


def test_telegram_publisher_incluye_traza_de_tools_y_escapa_html():
    debate = Debate(
        question="q",
        mode="mcp",
        style="debate",
        turns=[
            DebateTurn(
                team="barcelona",
                content="Lewandowski > Vinicius, sin duda <no debate>",
                tool_calls=[
                    {"tool": "compare_players", "args": {"player_a": "A & B", "player_b": "C"}}
                ],
            )
        ],
    )
    publisher = TelegramPublisher(bot_tokens=_BOT_TOKENS, chat_id="123")

    with (
        patch(
            "src.social.telegram_publisher.requests.post",
            side_effect=[_fake_response(1), _fake_response(2)],
        ) as post,
        patch("src.social.telegram_publisher.time.sleep"),
    ):
        publisher.publish(debate)

    turn_text = post.call_args_list[1].kwargs["json"]["text"]
    assert "compare_players(" in turn_text
    assert "A &amp; B" in turn_text
    # El contenido del agente esta escapado: no debe colarse un tag HTML crudo.
    assert "<no debate>" not in turn_text
    assert "&lt;no debate&gt;" in turn_text
