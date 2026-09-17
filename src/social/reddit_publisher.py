"""Reddit: planeado, no implementado todavia.

Idea (ver docs/ARCHITECTURE.md): post inicial con la pregunta + un
comentario por turno, encadenado como reply al comentario anterior, via
`praw`. Requeriria un subreddit propio y una app tipo "script" en Reddit
(client_id/secret + user/pass del bot).
"""

from src.social.base import DebatePublisher, PublishResult
from src.social.models import Debate


class RedditPublisher(DebatePublisher):
    name = "reddit"

    def publish(self, debate: Debate) -> PublishResult:
        raise NotImplementedError(
            "El publisher de Reddit todavia no esta implementado. Ver "
            "docs/ARCHITECTURE.md para el diseno planeado."
        )
