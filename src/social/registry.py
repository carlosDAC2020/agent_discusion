"""Registro de publishers disponibles, por nombre de plataforma.

Agregar una red social nueva = crear su `XPublisher(DebatePublisher)` y
sumar una linea aca. El CLI y el resto del codigo no necesitan cambios.
"""

from src.social.base import DebatePublisher
from src.social.bluesky_publisher import BlueskyPublisher
from src.social.discord_publisher import DiscordPublisher
from src.social.reddit_publisher import RedditPublisher
from src.social.telegram_publisher import TelegramPublisher

_PUBLISHERS: dict[str, type[DebatePublisher]] = {
    "telegram": TelegramPublisher,
    "reddit": RedditPublisher,
    "discord": DiscordPublisher,
    "bluesky": BlueskyPublisher,
}

# Subset de _PUBLISHERS cuya implementacion funciona de punta a punta hoy.
IMPLEMENTED_PLATFORMS = frozenset({"telegram"})
PLANNED_PLATFORMS = frozenset(_PUBLISHERS) - IMPLEMENTED_PLATFORMS


def available_platforms() -> list[str]:
    return sorted(_PUBLISHERS)


def get_publisher(platform: str) -> DebatePublisher:
    """Instancia el publisher de `platform`.

    Lanza `ValueError` si el nombre no esta registrado (ni siquiera como
    planeado). Las plataformas planeadas pero no implementadas se
    instancian igual: fallan recien al llamar `.publish(...)`, con un
    mensaje claro de que todavia no estan listas.
    """
    cls = _PUBLISHERS.get(platform.lower())
    if cls is None:
        raise ValueError(
            f"Plataforma desconocida: '{platform}'. Opciones: {', '.join(available_platforms())}."
        )
    return cls()
