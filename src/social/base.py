"""Contrato comun que debe cumplir cada red social soportada."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from src.social.models import Debate


class PublishError(Exception):
    """Error al publicar (credenciales invalidas, red social caida, etc.).

    El CLI la atrapa para mostrar un mensaje claro, sin traceback crudo.
    """


@dataclass(frozen=True)
class PublishResult:
    platform: str
    posted: int
    references: list[str] = field(default_factory=list)


class DebatePublisher(ABC):
    """Publica un `Debate` completo en una red social externa."""

    name: str = "base"

    @abstractmethod
    def publish(self, debate: Debate) -> PublishResult:
        """Publica el debate y devuelve un resumen de lo publicado.

        Implementaciones deben lanzar `PublishError` (no dejar pasar
        excepciones de bajo nivel del cliente HTTP) ante cualquier fallo.
        """
        raise NotImplementedError
