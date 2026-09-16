"""Tests de src/social: adaptador de datos, registry y TelegramPublisher.

TelegramPublisher se prueba con `requests.post` mockeado, sin red real.
"""

from unittest.mock import Mock, patch

import pytest

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
    assert DebateTurn(team="barcelona", content="x").team_label == "FC Barcelona"
    assert DebateTurn(team="real_madrid", content="x").team_label == "Real Madrid"
    assert DebateTurn(team="otro", content="x").team_label == "otro"


def test_registry_conoce_las_4_plataformas():
    assert available_platforms() == ["bluesky", "discord", "reddit", "telegram"]
    assert IMPLEMENTED_PLATFORMS == {"telegram"}
    assert PLANNED_PLATFORMS == {"bluesky", "discord", "reddit"}


def test_get_publisher_plataforma_desconocida_da_value_error():
    with pytest.raises(ValueError, match="Plataforma desconocida"):
        get_publisher("myspace")


def test_get_publisher_planeada_falla_recien_al_publicar():
    publisher = get_publisher("reddit")
    debate = Debate(question="q", mode="mcp", style="debate", turns=[])
    with pytest.raises(NotImplementedError):
        publisher.publish(debate)


def _fake_response(message_id: int):
    resp = Mock()
    resp.ok = True
    resp.json.return_value = {"ok": True, "result": {"message_id": message_id}}
    return resp


def test_telegram_publisher_sin_credenciales_da_publish_error():
    publisher = TelegramPublisher(bot_token="", chat_id="")
    debate = Debate(question="q", mode="mcp", style="debate", turns=[])
    with pytest.raises(PublishError, match="Faltan credenciales"):
        publisher.publish(debate)


def test_telegram_publisher_publica_header_y_cada_turno_encadenado():
    debate = Debate(
        question="Quien tiene mejor delantera?",
        mode="mcp",
        style="debate",
        turns=[
            DebateTurn(team="barcelona", content="Vamos Barca"),
            DebateTurn(team="real_madrid", content="Hala Madrid"),
        ],
    )
    publisher = TelegramPublisher(bot_token="TOKEN", chat_id="123")

    responses = [_fake_response(1), _fake_response(2), _fake_response(3)]
    with patch("src.social.telegram_publisher.requests.post", side_effect=responses) as post:
        result = publisher.publish(debate)

    assert result.platform == "telegram"
    assert result.posted == 3
    assert result.references == ["1", "2", "3"]

    assert post.call_count == 3
    first_call, second_call, third_call = post.call_args_list

    # El header no responde a ningun mensaje previo.
    assert "reply_to_message_id" not in first_call.kwargs["json"]

    # Cada turno responde al mensaje anterior (header -> turno 1 -> turno 2).
    assert second_call.kwargs["json"]["reply_to_message_id"] == 1
    assert third_call.kwargs["json"]["reply_to_message_id"] == 2
    assert "Vamos Barca" in second_call.kwargs["json"]["text"]
    assert "Hala Madrid" in third_call.kwargs["json"]["text"]


def test_telegram_publisher_error_de_api_da_publish_error():
    debate = Debate(question="q", mode="mcp", style="debate", turns=[])
    publisher = TelegramPublisher(bot_token="TOKEN", chat_id="123")

    resp = Mock()
    resp.ok = False
    resp.json.return_value = {"ok": False, "description": "chat not found"}
    resp.text = "chat not found"

    with patch("src.social.telegram_publisher.requests.post", return_value=resp):
        with pytest.raises(PublishError, match="chat not found"):
            publisher.publish(debate)
