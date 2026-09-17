"""Bluesky: planeado, no implementado todavia.

Idea (ver docs/ARCHITECTURE.md): un post inicial + un reply por turno via
AT Protocol (`atproto`), alternativa gratuita y sin paywall a X/Twitter.
"""

from src.social.base import DebatePublisher, PublishResult
from src.social.models import Debate


class BlueskyPublisher(DebatePublisher):
    name = "bluesky"

    def publish(self, debate: Debate) -> PublishResult:
        raise NotImplementedError(
            "El publisher de Bluesky todavia no esta implementado. Ver "
            "docs/ARCHITECTURE.md para el diseno planeado."
        )
