"""Discord: planeado, no implementado todavia.

Idea (ver docs/ARCHITECTURE.md): un mensaje por turno en un canal via
webhook (mas simple que un bot completo), sin necesitar que el proceso
quede corriendo de forma persistente.
"""

from src.social.base import DebatePublisher, PublishResult
from src.social.models import Debate


class DiscordPublisher(DebatePublisher):
    name = "discord"

    def publish(self, debate: Debate) -> PublishResult:
        raise NotImplementedError(
            "El publisher de Discord todavia no esta implementado. Ver "
            "docs/ARCHITECTURE.md para el diseno planeado."
        )
