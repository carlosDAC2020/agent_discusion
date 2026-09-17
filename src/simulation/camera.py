"""Sistema de cámara y transformación de coordenadas 2.5D oblicuas.

Separa formalmente:
1. Coordenadas lógicas del mundo (Cartesianas 960x640, usadas para física, cuadrícula y colisiones).
2. Coordenadas de renderizado (con elevación Z para superficies superiores y caras frontales).
3. Coordenadas de pantalla (escalado en caso de redimensionamiento de ventana).
4. Conversión de puntero / ratón a coordenadas lógicas del mundo.
"""

from typing import Tuple

from src.simulation.config import LOGICAL_HEIGHT, LOGICAL_WIDTH


class Camera25D:
    """Gestiona la perspectiva oblicua y el ordenamiento de profundidad de la escena."""

    def __init__(self, offset_x: float = 0.0, offset_y: float = 0.0, zoom: float = 1.0):
        self.offset_x: float = offset_x
        self.offset_y: float = offset_y
        self.zoom: float = zoom

    def world_to_screen(
        self, world_x: float, world_y: float, world_z: float = 0.0
    ) -> Tuple[float, float]:
        """Convierte coordenadas lógicas (X, Y) y elevación Z a coordenadas de renderizado en pantalla.

        En la proyección oblicua retro (3/4 top-down):
        - X_pantalla coincide con X_mundo (horizontal).
        - Y_pantalla se proyecta según la posición en el suelo Y_mundo menos la altura Z (verticalidad).
        """
        screen_x = (world_x + self.offset_x) * self.zoom
        screen_y = (world_y - world_z + self.offset_y) * self.zoom
        return screen_x, screen_y

    def screen_to_world(
        self, screen_x: float, screen_y: float, world_z: float = 0.0
    ) -> Tuple[float, float]:
        """Convierte coordenadas de pantalla a coordenadas lógicas del mundo asumiendo elevación Z.

        Operación inversa determinista de world_to_screen.
        """
        world_x = (screen_x / self.zoom) - self.offset_x
        world_y = ((screen_y / self.zoom) + world_z) - self.offset_y
        return world_x, world_y

    def get_render_depth(self, world_y: float, world_z: float = 0.0) -> float:
        """Calcula la clave de profundidad para el algoritmo del pintor (Painter's Algorithm).

        En perspectiva oblicua 2.5D, los objetos con mayor Y (más cercanos al espectador / hacia abajo)
        se dibujan por delante de los objetos con menor Y (hacia arriba / fondo).
        """
        return world_y + (world_z * 0.001)

    def window_to_logical(
        self, window_x: float, window_y: float, window_size: Tuple[int, int]
    ) -> Tuple[float, float]:
        """Convierte coordenadas de ventana física (posibles por redimensionamiento) a resolución lógica interna."""
        win_w, win_h = window_size
        if win_w <= 0 or win_h <= 0:
            return window_x, window_y

        scale_x = LOGICAL_WIDTH / win_w
        scale_y = LOGICAL_HEIGHT / win_h
        logical_x = window_x * scale_x
        logical_y = window_y * scale_y
        return logical_x, logical_y


# Instancia global por defecto para transformaciones estándar
default_camera = Camera25D()


def world_to_screen(
    world_x: float, world_y: float, world_z: float = 0.0
) -> Tuple[float, float]:
    """Función de utilidad directa para transformar coordenadas del mundo a pantalla."""
    return default_camera.world_to_screen(world_x, world_y, world_z)


def screen_to_world(
    screen_x: float, screen_y: float, world_z: float = 0.0
) -> Tuple[float, float]:
    """Función de utilidad directa para transformar coordenadas de pantalla al mundo."""
    return default_camera.screen_to_world(screen_x, screen_y, world_z)


def get_render_depth(world_y: float, world_z: float = 0.0) -> float:
    """Función de utilidad directa para calcular la profundidad de renderizado."""
    return default_camera.get_render_depth(world_y, world_z)
