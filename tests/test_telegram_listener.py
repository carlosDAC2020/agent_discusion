"""Tests de TelegramListener: `requests.get` mockeado, sin red real ni loop."""

from unittest.mock import Mock, patch

import pytest

from src.social.base import PublishError
from src.social.telegram_listener import TelegramListener


def _publisher_free_listener(**overrides) -> TelegramListener:
    kwargs = {"bot_token": "TOKEN", "chat_id": "123"}
    kwargs.update(overrides)
    return TelegramListener(**kwargs)


def _updates_response(results: list[dict]):
    resp = Mock()
    resp.ok = True
    resp.json.return_value = {"ok": True, "result": results}
    return resp


def _message_update(update_id: int, chat_id, text: str) -> dict:
    return {
        "update_id": update_id,
        "message": {"chat": {"id": chat_id}, "text": text},
    }


def test_ensure_ready_sin_credenciales_da_publish_error():
    listener = _publisher_free_listener(bot_token="", chat_id="")
    with pytest.raises(PublishError, match="Faltan credenciales"):
        listener.ensure_ready()


def test_ensure_ready_con_credenciales_no_lanza():
    assert _publisher_free_listener().ensure_ready() is None


def test_poll_once_detecta_pregunta_con_el_prefijo():
    listener = _publisher_free_listener()
    updates = [_message_update(1, 123, "/debate Quien tiene mejor cantera?")]

    with patch(
        "src.social.telegram_listener.requests.get", return_value=_updates_response(updates)
    ):
        questions = listener.poll_once()

    assert questions == ["Quien tiene mejor cantera?"]


def test_poll_once_ignora_mensajes_sin_el_prefijo():
    listener = _publisher_free_listener()
    updates = [_message_update(1, 123, "hola, como andan?")]

    with patch(
        "src.social.telegram_listener.requests.get", return_value=_updates_response(updates)
    ):
        questions = listener.poll_once()

    assert questions == []


def test_poll_once_ignora_mensajes_de_otro_chat():
    listener = _publisher_free_listener(chat_id="123")
    updates = [_message_update(1, 999, "/debate esto es de otro chat")]

    with patch(
        "src.social.telegram_listener.requests.get", return_value=_updates_response(updates)
    ):
        questions = listener.poll_once()

    assert questions == []


def test_poll_once_ignora_updates_sin_mensaje():
    listener = _publisher_free_listener()
    updates = [{"update_id": 1, "my_chat_member": {}}]

    with patch(
        "src.social.telegram_listener.requests.get", return_value=_updates_response(updates)
    ):
        questions = listener.poll_once()

    assert questions == []


def test_poll_once_ignora_debate_sin_pregunta():
    listener = _publisher_free_listener()
    updates = [_message_update(1, 123, "/debate")]

    with patch(
        "src.social.telegram_listener.requests.get", return_value=_updates_response(updates)
    ):
        questions = listener.poll_once()

    assert questions == []


def test_poll_once_avanza_el_offset_para_la_siguiente_llamada():
    listener = _publisher_free_listener()
    updates = [_message_update(5, 123, "/debate primera"), _message_update(7, 123, "/debate segunda")]

    with patch(
        "src.social.telegram_listener.requests.get", return_value=_updates_response(updates)
    ) as get:
        questions = listener.poll_once()
        listener.poll_once()

    assert questions == ["primera", "segunda"]
    # La segunda llamada a getUpdates debe pedir offset = ultimo update_id + 1.
    assert get.call_args_list[1].kwargs["params"]["offset"] == 8


def test_poll_once_error_de_api_da_publish_error():
    listener = _publisher_free_listener()
    resp = Mock()
    resp.ok = False
    resp.json.return_value = {"ok": False, "description": "Unauthorized"}
    resp.text = "Unauthorized"

    with patch("src.social.telegram_listener.requests.get", return_value=resp):
        with pytest.raises(PublishError, match="Unauthorized"):
            listener.poll_once()
