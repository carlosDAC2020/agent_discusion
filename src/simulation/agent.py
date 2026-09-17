"""Entidades visuales y agentes con soporte de navegación A* en la simulación 2.5D.

Implementa la representación pixel art del agente sobre el plano del mundo:
- Coordenadas lógicas del mundo continuas (X, Y) y ordenamiento por profundidad.
- Navegación hacia puntos de interés o coordenadas lógicas evitando obstáculos con A*.
- Movimiento continuo con tiempo delta (dt) a velocidad configurable.
- Orientación automática y animación de marcha/reposo, sentado y bebiendo.
- Sombra de contacto sobre el suelo y badge de nombre.
- Entidades de ambientación interactivas con espacios delimitados:
  * Manolo (Bartender): detrás del mostrador preparando y sirviendo cócteles.
  * Doña Carmen (Limpiadora): barriendo y desplazándose por las mesas con su cubo.
  * Don Antonio (Señor de la esquina): sentado tosiendo, estirando las piernas e interactuando.
"""

import math
from typing import Any, Dict, List, Optional, Tuple

import pygame

from src.simulation.camera import Camera25D, default_camera
from src.simulation.config import (
    COLOR_DEBUG_PATH,
    COLOR_DEBUG_WAYPOINT,
    DEFAULT_AGENT_SPEED,
    DIALOGUE_BUBBLE_HOLD_SECONDS,
    STATE_IDLE,
    STATE_LOOKING_LEFT,
    STATE_LOOKING_RIGHT,
    STATE_WALKING,
)
from src.simulation.dialogue import ConversationPhase

from src.simulation.navigation import (
    PathFollower,
    PathResult,
    find_path_astar,
    pos_to_cell,
)
from src.simulation.sprites import (
    SCALED_SPRITE_HEIGHT,
    SCALED_SPRITE_WIDTH,
    get_agent_sprite,
    get_bartender_sprite,
    get_cleaner_bucket_sprite,
    get_cleaner_sprite,
    get_counter_drink_sprite,
    get_old_man_sprite,
    render_agent_name_tag,
    render_contact_shadow,
    render_cough_comic_puff,
    render_dialogue_bubble,
)
from src.simulation.world import BarWorld


class VisualAgent:
    """Representa a un agente de debate (Josep o Paco) con navegación 2D y apariencia pixel art."""

    def __init__(
        self,
        agent_id: str,
        team: str,
        name: str,
        spawn_x: float,
        spawn_y: float,
        initial_facing: str = "down",
        speed: float = DEFAULT_AGENT_SPEED,
    ):
        self.agent_id: str = agent_id
        self.team: str = team
        self.name: str = name

        # Coordenadas lógicas del mundo (continuas)
        self.x: float = float(spawn_x)
        self.y: float = float(spawn_y)

        # Velocidad de movimiento y controlador de navegación
        self.speed: float = float(speed)
        self.follower: PathFollower = PathFollower(speed=self.speed)

        # Datos de la ruta activa
        self.active_path: List[Tuple[int, int]] = []
        self.active_waypoints: List[Tuple[float, float]] = []
        self.target_pos: Optional[Tuple[float, float]] = None
        self.last_path_error: Optional[str] = None

        # Orientación y estado visual
        self.facing: str = initial_facing
        self.state: str = STATE_IDLE
        self.set_facing(initial_facing)

        # Controlador BDI opcional (autonomía deliberativa)
        self.bdi_controller: Optional[Any] = None

        # Temporizadores de animación física
        self.anim_timer: float = 0.0
        self.breath_frame: int = 0
        self.walk_timer: float = 0.0
        self.walk_frame: int = 0

        # Estados de interacción ambiental (beber, sentarse, diálogo)
        self.is_sitting: bool = False
        self.is_drinking: bool = False
        self.drink_timer: float = 0.0
        self.drink_frame: int = 0
        self.active_bubble_text: Optional[str] = None
        self.bubble_timer: float = 0.0
        self.last_spoken_npc_timer: float = 0.0
        self.bubble_accent: Tuple[int, int, int] = (
            (0, 77, 152) if team == "barcelona" else (190, 160, 45)
        )

        # Estado de conversación y diálogo real (Fase 5 y Tertulia)
        self.conversation_phase: ConversationPhase = ConversationPhase.IDLE
        self.is_conversation_locked: bool = False
        self.is_thinking: bool = False
        self.thinking_timer: float = 0.0
        self.thinking_frame: int = 0
        self.active_dialogue_text: str = ""
        self.dialogue_hold_timer: float = 0.0

        # Estados visuales de audio (Fase 6)
        self.voice_state: str = "IDLE"
        self.is_speaking_voice: bool = False
        self.voice_segment_text: Optional[str] = None

    def set_voice_state(self, state: str, segment_text: Optional[str] = None) -> None:
        """Actualiza el estado visual de voz del personaje."""
        self.voice_state = state
        self.is_speaking_voice = (state == "VOICE_PLAYING")
        if segment_text is not None:
            self.voice_segment_text = segment_text
    @property
    def depth(self) -> float:
        """Clave de ordenamiento de profundidad Y para el algoritmo del pintor."""
        return self.y

    @property
    def is_navigating(self) -> bool:
        """Indica si el agente se encuentra actualmente desplazándose a lo largo de una ruta."""
        return self.follower.is_active

    @property
    def is_walking(self) -> bool:
        """Indica si el agente se encuentra actualmente caminando."""
        return self.is_navigating

    @property
    def current_cell(self) -> Tuple[int, int]:
        """Retorna los índices de celda (col, row) en la grilla del mundo."""
        return pos_to_cell(self.x, self.y)

    @property
    def target_cell(self) -> Optional[Tuple[int, int]]:
        """Retorna la celda objetivo si existe una ruta activa."""
        if self.target_pos:
            return pos_to_cell(self.target_pos[0], self.target_pos[1])
        return None

    @property
    def collider_rect(self) -> pygame.Rect:
        """Caja delimitadora lógica de 20x20 centrada en los pies para colisiones."""
        return pygame.Rect(int(self.x - 10), int(self.y - 10), 20, 20)

    @property
    def bdi(self) -> Optional[Any]:
        """Propiedad de conveniencia para acceder al controlador BDI."""
        return self.bdi_controller

    def attach_bdi(self, controller: Any) -> None:
        """Asocia un controlador BDI para comportamiento autónomo."""
        self.bdi_controller = controller

    def detach_bdi(self) -> None:
        """Desconecta el controlador BDI regresando al modo manual/estático."""
        self.bdi_controller = None
        self.cancel_navigation()

    def set_speed(self, speed: float) -> None:
        """Ajusta la velocidad de desplazamiento en píxeles lógicos por segundo."""
        self.speed = float(speed)
        self.follower.speed = self.speed

    def say(self, text: str, duration: float = 3.5) -> None:
        """Despliega un bocadillo cómic con diálogo sobre la cabeza del personaje."""
        self.active_bubble_text = text
        self.bubble_timer = float(duration)

    def sit(self, val: bool = True) -> None:
        """Activa o desactiva la postura de sentado."""
        self.is_sitting = val

    def drink(self, val: bool = True) -> None:
        """Activa o desactiva la animación de beber."""
        self.is_drinking = val
        if not val:
            self.drink_timer = 0.0
            self.drink_frame = 0

    def set_thinking(self, val: bool = True) -> None:
        """Activa o desactiva el estado visual de espera/pensamiento del LLM."""
        self.is_thinking = val
        if not val:
            self.thinking_timer = 0.0
            self.thinking_frame = 0

    def set_dialogue_text(self, text: str, append: bool = False) -> None:
        """Actualiza el texto en streaming para el bocadillo de diálogo."""
        if append:
            self.active_dialogue_text += text
        else:
            self.active_dialogue_text = text
        self.is_thinking = False

    def complete_dialogue_message(
        self, text: str, hold_duration: float = DIALOGUE_BUBBLE_HOLD_SECONDS
    ) -> None:
        """Fija el mensaje final completado del turno con temporizador de retención."""
        self.active_dialogue_text = text
        self.dialogue_hold_timer = float(hold_duration)
        self.is_thinking = False

    def clear_dialogue(self) -> None:
        """Limpia inmediatamente los textos de diálogo y pensamiento."""
        self.active_dialogue_text = ""
        self.dialogue_hold_timer = 0.0
        self.is_thinking = False


    def navigate_to(self, world: BarWorld, target_x: float, target_y: float) -> PathResult:
        """Calcula una ruta ortogonal mediante A* hacia el destino y activa el desplazamiento.

        Si el destino es inválido o no transitable, el agente no se mueve y reporta el error.
        """
        # Si estaba sentado o bebiendo, se levanta para caminar
        self.is_sitting = False
        self.is_drinking = False

        result = find_path_astar(world, self.x, self.y, target_x, target_y)
        if result.success:
            self.active_path = list(result.path)
            self.active_waypoints = list(result.waypoints)
            self.target_pos = (float(target_x), float(target_y))
            self.last_path_error = None

            if len(self.active_waypoints) > 1:
                follower_waypoints = self.active_waypoints[1:]
            else:
                follower_waypoints = self.active_waypoints

            self.follower.set_path(follower_waypoints)
            self.state = STATE_WALKING
        else:
            self.last_path_error = result.error_reason
        return result

    def navigate_to_poi(self, world: BarWorld, poi_name: str) -> PathResult:
        """Calcula y sigue una ruta hacia las coordenadas de un punto de interés registrado."""
        poi = world.get_poi(poi_name)
        if poi is None:
            return PathResult(success=False, error_reason="poi_not_found")
        return self.navigate_to(world, poi.x, poi.y)

    def cancel_navigation(self) -> None:
        """Interrumpe y cancela la ruta actual, deteniendo al agente inmediatamente."""
        self.follower.cancel()
        self.active_path.clear()
        self.active_waypoints.clear()
        self.target_pos = None
        self.set_facing(self.facing)

    def update(
        self,
        dt: float,
        world: Optional[BarWorld] = None,
        other_agent: Optional[Any] = None,
    ) -> None:
        """Actualiza el controlador BDI (si existe) y el movimiento físico en función de dt."""
        # 1. Ciclo deliberativo BDI local (si está habilitado)
        if self.bdi_controller is not None and world is not None:
            self.bdi_controller.update(self, world, other_agent, dt)

        # Temporizador de bocadillos de diálogo
        if self.bubble_timer > 0.0:
            self.bubble_timer -= dt
            if self.bubble_timer <= 0.0:
                self.active_bubble_text = None

        if self.last_spoken_npc_timer > 0.0:
            self.last_spoken_npc_timer -= dt

        # Animación de pensamiento del LLM (...)
        if self.is_thinking:
            self.thinking_timer += dt
            self.thinking_frame = int(self.thinking_timer / 0.35)
        else:
            self.thinking_timer = 0.0
            self.thinking_frame = 0

        # Temporizador de retención de mensaje de diálogo completado
        if self.dialogue_hold_timer > 0.0:
            self.dialogue_hold_timer -= dt
            if self.dialogue_hold_timer <= 0.0:
                self.dialogue_hold_timer = 0.0
                self.active_dialogue_text = ""

        # Animación de trago si está bebiendo
        if self.is_drinking:
            self.drink_timer += dt
            self.drink_frame = int(self.drink_timer / 0.45) % 2


        # 2. Avance físico y seguimiento de ruta
        if self.is_navigating:
            new_x, new_y, new_facing, new_state, arrived = self.follower.update(self.x, self.y, dt)

            # Validación de colisiones antes de confirmar la nueva posición
            if world is not None and world.collides(new_x - 10, new_y - 10, 20, 20):
                self.cancel_navigation()
                self.last_path_error = "obstacle_collision_blocked"
                return

            self.x = new_x
            self.y = new_y
            self.facing = new_facing
            self.state = new_state

            # Ciclo de marcha
            self.walk_timer += dt
            self.walk_frame = int(self.walk_timer / 0.18) % 2

            if arrived:
                self.active_path.clear()
                self.active_waypoints.clear()
                self.target_pos = None
                self.set_facing(self.facing)
        else:
            # En reposo: ciclo suave de respiración
            self.anim_timer += dt
            self.breath_frame = int(self.anim_timer / 0.8) % 2
            self.walk_frame = 0

            # Detección contextual de asientos si no está deliberando con BDI
            if world is not None and (self.bdi_controller is None or self.bdi_controller.current_intention is None):
                nearby_poi = world.get_poi_at(self.x, self.y, max_dist=24.0)
                if nearby_poi:
                    if nearby_poi.category == "bar":
                        self.sit(True)
                        self.set_facing("left")
                    elif nearby_poi.category == "tv_seat":
                        self.sit(True)
                        self.set_facing("up")
                    elif nearby_poi.category == "table_seat":
                        self.sit(True)
                        # Orientarse hacia el centro de la mesa
                        if "west" in nearby_poi.name:
                            self.set_facing("right")
                        elif "east" in nearby_poi.name:
                            self.set_facing("left")
                        elif "north" in nearby_poi.name:
                            self.set_facing("down")
                        elif "south" in nearby_poi.name:
                            self.set_facing("up")
                else:
                    if self.is_sitting:
                        self.sit(False)

            # Interacción con Don Antonio si está en su rincón
            if math.hypot(self.x - 800.0, self.y - 544.0) <= 90.0:
                if self.last_spoken_npc_timer <= 0.0 and not self.active_bubble_text:
                    self.last_spoken_npc_timer = 20.0
                    if self.team == "barcelona":
                        self.say("¿Tot bé, Don Antonio? ¿Li cal una mica d'aigua?", duration=3.0)
                    else:
                        self.say("¿Se encuentra bien, Don Antonio? ¿Le traigo algo?", duration=3.0)


    def set_facing(self, facing: str) -> None:
        """Ajusta la orientación visual del personaje ('down', 'left', 'right', 'up')."""
        self.facing = facing
        if not self.is_navigating:
            if facing == "left":
                self.state = STATE_LOOKING_LEFT
            elif facing == "right":
                self.state = STATE_LOOKING_RIGHT
            else:
                self.state = STATE_IDLE

    def draw(
        self,
        surface: pygame.Surface,
        camera: Optional[Camera25D] = None,
        font: Optional[pygame.font.Font] = None,
        debug: bool = False,
    ) -> None:
        """Renderiza el personaje proyectado en la perspectiva oblicua con sombra y badge."""
        cam = camera or default_camera
        screen_x, screen_y = cam.world_to_screen(self.x, self.y)

        # 1. Sombra de contacto elíptica en la base del suelo
        render_contact_shadow(surface, screen_x, screen_y)

        # 2. Sprite Pixel Art con selección de estado (marcha, reposo, sentado o bebiendo)
        frame = self.walk_frame if self.is_navigating else self.breath_frame
        sprite_surf = get_agent_sprite(
            self.team,
            self.facing,
            frame,
            is_walking=self.is_navigating,
            is_sitting=self.is_sitting,
            is_drinking=self.is_drinking,
            drink_frame=self.drink_frame,
        )
        sprite_topleft_x = int(screen_x - SCALED_SPRITE_WIDTH // 2)
        sprite_topleft_y = int(screen_y - SCALED_SPRITE_HEIGHT + 4)
        surface.blit(sprite_surf, (sprite_topleft_x, sprite_topleft_y))

        # 3. Badge de nombre sobre la cabeza (si no hay bocadillo o pensamiento activo)
        has_bubble = bool(self.active_bubble_text or self.active_dialogue_text or self.is_thinking)
        if font is not None and not has_bubble:
            tag_y = sprite_topleft_y - 8
            render_agent_name_tag(surface, screen_x, tag_y, self.name, self.team, font)

        # 4. Bocadillo cómic de diálogo emergente, texto en streaming o pensamiento
        display_text: Optional[str] = None
        if self.active_bubble_text:
            display_text = self.active_bubble_text
        elif self.active_dialogue_text:
            display_text = self.active_dialogue_text
        elif self.is_thinking:
            dots = "." * (self.thinking_frame % 3 + 1)
            display_text = f"Pensando{dots}"

        if display_text and font is not None:
            render_dialogue_bubble(
                surface,
                screen_x,
                sprite_topleft_y,
                self.name,
                display_text,
                font,
                self.bubble_accent,
                max_width=220,
            )


        # 5. Capa de depuración técnica de navegación
        if debug:
            if self.is_navigating and self.active_waypoints:
                pts = [cam.world_to_screen(self.x, self.y)]
                idx = self.follower.current_waypoint_idx
                for wx, wy in self.active_waypoints[idx:]:
                    pts.append(cam.world_to_screen(wx, wy))
                if len(pts) >= 2:
                    pygame.draw.lines(surface, COLOR_DEBUG_PATH, False, pts, 2)
                for px, py in pts[1:]:
                    pygame.draw.circle(surface, COLOR_DEBUG_WAYPOINT, (int(px), int(py)), 3)

            pygame.draw.circle(surface, (0, 255, 255), (int(screen_x), int(screen_y)), 3)

            collider_rect = pygame.Rect(
                int(screen_x - 10), int(screen_y - 10), 20, 20
            )
            pygame.draw.rect(surface, (60, 255, 60), collider_rect, width=1)

            if font is not None:
                status_txt = f"{self.state} | {self.current_cell}"
                if self.is_navigating and self.target_cell:
                    status_txt += f" -> {self.target_cell} ({self.speed:.0f}px/s)"
                elif self.last_path_error:
                    status_txt += f" [{self.last_path_error}]"
                lbl = font.render(status_txt, True, (255, 255, 120))
                surface.blit(lbl, (sprite_topleft_x - 8, sprite_topleft_y - 18))


class BartenderNPC:
    """NPC de ambientación: Manolo, el barman detrás de la barra preparando y sirviendo cócteles.
    
    Espacio delimitado: Pasillo interior detrás de la barra (X=80, Y entre 160 y 420).
    """

    def __init__(self, x: float = 80.0, y: float = 240.0, name: str = "Manolo [Barman]"):
        self.agent_id: str = "bartender_manolo"
        self.name: str = name
        self.x: float = x
        self.y: float = y
        self.speed: float = 60.0

        # Límites estrictos del pasillo de la barra
        self.min_y: float = 160.0
        self.max_y: float = 420.0

        # Temporizadores y animación
        self.shake_timer: float = 0.0
        self.shake_frame: int = 0
        self.action: str = "wipe"  # "wipe", "shake", "serve", "walk"

        # Estados de la rutina de Manolo
        self.state: str = "WIPING"  # "WIPING", "PREPARING", "DELIVERING", "SERVING", "RETURNING"
        self.state_timer: float = 0.0
        self.patrol_dir: float = 1.0

        # Gestión de pedidos y bebidas servidas en la barra
        self.current_customer: Optional[Any] = None
        self.counter_drinks: List[Dict[str, Any]] = []
        self.served_cooldown: Dict[str, float] = {}

        # Diálogo cómic
        self.active_bubble_text: Optional[str] = None
        self.bubble_timer: float = 0.0

        # Audio y voz (Fase 6)
        self.voice_state: str = "IDLE"
        self.is_speaking_voice: bool = False

    @property
    def depth(self) -> float:
        return self.y

    def set_voice_state(self, state: str, segment_text: Optional[str] = None) -> None:
        self.voice_state = state
        self.is_speaking_voice = (state == "VOICE_PLAYING")

    def say(self, text: str, duration: float = 3.0) -> None:
        """Despliega un bocadillo cómic del camarero."""
        self.active_bubble_text = text
        self.bubble_timer = float(duration)

    def moderate_question(self, question: str, duration: float = 3.5) -> None:
        """Modera y formula visualmente al público del bar la pregunta del usuario."""
        self.state = "MODERATING"
        self.action = "idle"
        self.state_timer = 0.0
        self.current_question_text = question
        self.say(f"Manolo: {question}", duration=duration)

    def order_drink(self, customer: Any) -> None:
        """Inicia la preparación de un trago para un cliente en un taburete."""
        if self.state in ("PREPARING", "DELIVERING", "SERVING"):
            return
        self.current_customer = customer
        self.state = "PREPARING"
        self.state_timer = 0.0
        self.action = "shake"
        self.say("¡Un cóctel de la casa marchando!", duration=2.2)

    def _serve_drink(self) -> None:
        """Coloca la copa en el mostrador e invita al cliente a tomar."""
        if self.current_customer and not any(d["customer"] == self.current_customer for d in self.counter_drinks):
            self.counter_drinks.append({
                "x": 128.0,
                "y": self.y,
                "level": 1.0,
                "customer": self.current_customer,
                "drinking": True,
            })
            self.say("¡Aquí tienes, recién servido!", duration=2.5)
            if hasattr(self.current_customer, "drink"):
                self.current_customer.drink(True)
            if hasattr(self.current_customer, "say") and not getattr(self.current_customer, "active_bubble_text", None):
                team = getattr(self.current_customer, "team", "")
                if team == "barcelona":
                    self.current_customer.say("¡Moltes gràcies, Manolo! ¡Salud!", duration=3.0)
                else:
                    self.current_customer.say("¡Muchas gracias, Manolo! ¡Salud!", duration=3.0)

    def update(self, dt: float, customers: Optional[List[Any]] = None) -> None:
        """Actualiza la rutina de trabajo de Manolo dentro de su pasillo delimitado."""
        self.shake_timer += dt
        self.shake_frame = int(self.shake_timer / 0.2) % 2

        if self.bubble_timer > 0.0:
            self.bubble_timer -= dt
            if self.bubble_timer <= 0.0:
                self.active_bubble_text = None

        # Cooldown de servicio a clientes
        for k in list(self.served_cooldown.keys()):
            self.served_cooldown[k] -= dt
            if self.served_cooldown[k] <= 0.0:
                del self.served_cooldown[k]

        # Reducir nivel de copas en la barra si el cliente está bebiendo
        for d in self.counter_drinks:
            if d.get("drinking", False):
                d["level"] = max(0.0, d["level"] - 0.25 * dt)
                if d["level"] <= 0.05:
                    cust = d.get("customer")
                    if cust and hasattr(cust, "drink"):
                        cust.drink(False)
                        if hasattr(cust, "say") and not getattr(cust, "active_bubble_text", None):
                            cust.say("¡Ahhh, qué bien entra!", duration=2.5)
        self.counter_drinks = [d for d in self.counter_drinks if d["level"] > 0.05]

        # Detección automática de cliente en taburete
        if customers and self.state == "WIPING" and not self.current_customer:
            for c in customers:
                if hasattr(c, "x") and 140.0 <= c.x <= 200.0 and 140.0 <= c.y <= 460.0:
                    if getattr(c, "is_navigating", False) is False:
                        if hasattr(c, "sit"):
                            c.sit(True)
                        if hasattr(c, "set_facing"):
                            c.set_facing("left")
                        cid = getattr(c, "agent_id", str(id(c)))
                        if self.served_cooldown.get(cid, 0.0) <= 0.0 and not any(d.get("customer") == c for d in self.counter_drinks):
                            self.order_drink(c)
                            self.served_cooldown[cid] = 16.0
                            break


        self.state_timer += dt

        # Máquina de estados con movimientos delimitados en el eje Y
        if self.state == "WIPING":
            self.action = "wipe"
            self.y += self.patrol_dir * 18.0 * dt
            if self.y >= 360.0:
                self.y = 360.0
                self.patrol_dir = -1.0
            elif self.y <= 200.0:
                self.y = 200.0
                self.patrol_dir = 1.0

        elif self.state == "PREPARING":
            self.action = "shake"
            # Desplazamiento hacia la zona de botellas en Y=192
            if abs(self.y - 192.0) > 4.0:
                step = math.copysign(min(abs(self.y - 192.0), self.speed * dt), 192.0 - self.y)
                self.y += step
            if self.state_timer >= 1.6:
                self.state = "DELIVERING"
                self.state_timer = 0.0

        elif self.state == "DELIVERING":
            target_y = self.current_customer.y if self.current_customer else 240.0
            target_y = max(self.min_y, min(self.max_y, target_y))
            dist = target_y - self.y
            if abs(dist) > 2.0:
                self.action = "walk"
                self.y += math.copysign(min(abs(dist), self.speed * dt), dist)
            if abs(target_y - self.y) <= 2.0:
                self.y = target_y
                self.state = "SERVING"
                self.action = "serve"
                self.state_timer = 0.0
                self._serve_drink()

        elif self.state == "SERVING":
            self.action = "serve"
            self._serve_drink()

            if self.state_timer >= 2.0:
                self.state = "RETURNING"
                self.state_timer = 0.0

        elif self.state == "RETURNING":
            self.action = "wipe"
            if self.state_timer >= 2.5:
                self.state = "WIPING"
                self.current_customer = None
                self.state_timer = 0.0

    def draw(
        self,
        surface: pygame.Surface,
        camera: Optional[Camera25D] = None,
        font: Optional[pygame.font.Font] = None,
        debug: bool = False,
    ) -> None:
        cam = camera or default_camera
        screen_x, screen_y = cam.world_to_screen(self.x, self.y)

        # 1. Copas colocadas sobre el mostrador de la barra
        for d in self.counter_drinks:
            dx, dy = cam.world_to_screen(d["x"], d["y"])
            drink_surf = get_counter_drink_sprite(d["level"])
            surface.blit(drink_surf, (int(dx - 12), int(dy - 20)))

        # 2. Sombra de contacto
        render_contact_shadow(surface, screen_x, screen_y)

        # 3. Sprite de Manolo según acción actual
        sprite_surf = get_bartender_sprite(self.shake_frame, action=self.action)
        sprite_topleft_x = int(screen_x - SCALED_SPRITE_WIDTH // 2)
        sprite_topleft_y = int(screen_y - SCALED_SPRITE_HEIGHT + 4)
        surface.blit(sprite_surf, (sprite_topleft_x, sprite_topleft_y))

        # 4. Badge o Bocadillo
        if font is not None and not self.active_bubble_text:
            tag_y = sprite_topleft_y - 8
            render_agent_name_tag(surface, screen_x, tag_y, self.name, "bartender", font)

        if self.active_bubble_text and font is not None:
            render_dialogue_bubble(
                surface,
                screen_x,
                sprite_topleft_y,
                "Manolo",
                self.active_bubble_text,
                font,
                accent_color=(190, 120, 20),
            )

        if debug:
            pygame.draw.circle(surface, (0, 255, 255), (int(screen_x), int(screen_y)), 3)


class CleanerNPC:
    """NPC de ambientación: Doña Carmen, limpiando con fregona y cubo por las mesas.
    
    Espacio delimitado: Área central y zona de mesas (X en [260, 580], Y en [360, 550]).
    """

    def __init__(self, x: float = 416.0, y: float = 512.0, name: str = "Dña. Carmen [Limpieza]"):
        self.agent_id: str = "cleaner_carmen"
        self.name: str = name
        self.x: float = x
        self.y: float = y
        self.speed: float = 28.0

        # Puntos de limpieza delimitados en pasillos abiertos (fuera de mesas y obstáculos)
        self.waypoints: List[Tuple[float, float]] = [
            (416.0, 512.0),
            (280.0, 490.0),
            (440.0, 520.0),
            (540.0, 500.0),
            (500.0, 420.0),
            (460.0, 490.0),
        ]

        self.current_wp_idx: int = 0

        self.mop_timer: float = 0.0
        self.mop_frame: int = 0
        self.is_walking: bool = False

        self.state: str = "CLEANING"  # "CLEANING", "RESTING", "WALKING"
        self.state_timer: float = 0.0

        self.active_bubble_text: Optional[str] = None
        self.bubble_timer: float = 0.0

    @property
    def depth(self) -> float:
        return self.y

    def say(self, text: str, duration: float = 3.0) -> None:
        self.active_bubble_text = text
        self.bubble_timer = float(duration)

    def update(self, dt: float) -> None:
        self.mop_timer += dt
        self.mop_frame = int(self.mop_timer / 0.45) % 2

        if self.bubble_timer > 0.0:
            self.bubble_timer -= dt
            if self.bubble_timer <= 0.0:
                self.active_bubble_text = None

        self.state_timer += dt

        if self.state == "CLEANING":
            self.is_walking = False
            if self.state_timer >= 5.0:
                self.state = "RESTING"
                self.state_timer = 0.0
                if (int(self.mop_timer) % 4) == 0:
                    self.say("¡Dejo esto reluciente!", duration=2.5)

        elif self.state == "RESTING":
            self.is_walking = False
            if self.state_timer >= 2.0:
                self.state = "WALKING"
                self.is_walking = True
                self.state_timer = 0.0
                self.current_wp_idx = (self.current_wp_idx + 1) % len(self.waypoints)

        elif self.state == "WALKING":
            self.is_walking = True
            tx, ty = self.waypoints[self.current_wp_idx]
            dist = math.hypot(tx - self.x, ty - self.y)
            if dist > 3.0:
                step = min(dist, self.speed * dt)
                self.x += (tx - self.x) / dist * step
                self.y += (ty - self.y) / dist * step
            else:
                self.x = tx
                self.y = ty
                self.state = "CLEANING"
                self.is_walking = False
                self.state_timer = 0.0

    def draw(
        self,
        surface: pygame.Surface,
        camera: Optional[Camera25D] = None,
        font: Optional[pygame.font.Font] = None,
        debug: bool = False,
    ) -> None:
        cam = camera or default_camera
        screen_x, screen_y = cam.world_to_screen(self.x, self.y)

        # 1. Cubo de fregar acompañando a la señora
        bucket_off_x = 24 if not self.is_walking else 16
        bucket_screen_x, bucket_screen_y = cam.world_to_screen(self.x + bucket_off_x, self.y + 4)
        render_contact_shadow(surface, bucket_screen_x, bucket_screen_y)
        bucket_surf = get_cleaner_bucket_sprite()
        surface.blit(bucket_surf, (int(bucket_screen_x - 12), int(bucket_screen_y - 20)))

        # 2. Sombra y personaje de la limpiadora
        render_contact_shadow(surface, screen_x, screen_y)
        sprite_surf = get_cleaner_sprite(self.mop_frame, is_walking=self.is_walking)
        sprite_topleft_x = int(screen_x - SCALED_SPRITE_WIDTH // 2)
        sprite_topleft_y = int(screen_y - SCALED_SPRITE_HEIGHT + 4)
        surface.blit(sprite_surf, (sprite_topleft_x, sprite_topleft_y))

        # 3. Badge o Bocadillo
        if font is not None and not self.active_bubble_text:
            tag_y = sprite_topleft_y - 8
            render_agent_name_tag(surface, screen_x, tag_y, self.name, "cleaner", font)

        if self.active_bubble_text and font is not None:
            render_dialogue_bubble(
                surface,
                screen_x,
                sprite_topleft_y,
                "Dña. Carmen",
                self.active_bubble_text,
                font,
                accent_color=(170, 70, 110),
            )

        if debug:
            pygame.draw.circle(surface, (0, 255, 255), (int(screen_x), int(screen_y)), 3)


class CoughingManNPC:
    """NPC de ambientación: Don Antonio, señor en la esquina que tose e interactúa si se le acercan.
    
    Espacio delimitado: Rincón sur-este (X en [770, 840], Y en [515, 560]).
    """

    def __init__(self, x: float = 800.0, y: float = 544.0, name: str = "D. Antonio"):
        self.agent_id: str = "oldman_antonio"
        self.name: str = name
        self.x: float = x
        self.y: float = y
        self.base_x: float = x
        self.base_y: float = y

        self.cough_timer: float = 0.0
        self.is_coughing: bool = False
        self.is_standing: bool = False

        self.state: str = "SITTING"  # "SITTING", "STRETCHING", "TALKING"
        self.state_timer: float = 0.0
        self.stretch_timer: float = 0.0

        self.active_bubble_text: Optional[str] = None
        self.bubble_timer: float = 0.0

    @property
    def depth(self) -> float:
        return self.y

    def say(self, text: str, duration: float = 3.5) -> None:
        self.active_bubble_text = text
        self.bubble_timer = float(duration)

    def respond_to_agent(self, agent_name: str) -> None:
        """Reacciona agradecido cuando un agente se le acerca a preguntar por su salud."""
        self.state = "TALKING"
        self.state_timer = 0.0
        self.say("¡Cof! Gracias por preocuparte, hijo... es la humedad.", duration=3.5)

    def update(self, dt: float, nearby_agents: Optional[List[Any]] = None) -> None:
        self.cough_timer += dt
        cycle_pos = self.cough_timer % 5.0
        self.is_coughing = cycle_pos > 3.2

        if self.bubble_timer > 0.0:
            self.bubble_timer -= dt
            if self.bubble_timer <= 0.0:
                self.active_bubble_text = None

        self.state_timer += dt
        self.stretch_timer += dt

        # Detección de agentes cercanos que le hayan hablado
        if nearby_agents and self.state != "TALKING":
            for a in nearby_agents:
                dist = math.hypot(a.x - self.x, a.y - self.y)
                if dist <= 96.0 and getattr(a, "active_bubble_text", None):
                    txt = a.active_bubble_text.lower()
                    if "antonio" in txt or "bien" in txt or "aigua" in txt:
                        self.respond_to_agent(a.name)
                        break

        if self.state == "TALKING":
            self.is_standing = True
            if self.state_timer >= 3.8:
                self.state = "SITTING"
                self.is_standing = False
                self.state_timer = 0.0

        elif self.state == "SITTING":
            self.is_standing = False
            self.x = self.base_x
            self.y = self.base_y
            # Cada 14 segundos se levanta a estirar las piernas en su rincón
            if self.stretch_timer >= 14.0:
                self.state = "STRETCHING"
                self.state_timer = 0.0
                self.stretch_timer = 0.0
                self.is_standing = True

        elif self.state == "STRETCHING":
            self.is_standing = True
            if self.state_timer < 3.0:
                self.x = min(825.0, self.base_x + self.state_timer * 7.0)
            elif self.state_timer < 6.0:
                self.x = max(self.base_x, 825.0 - (self.state_timer - 3.0) * 7.0)
            else:
                self.x = self.base_x
                self.state = "SITTING"
                self.state_timer = 0.0

    def draw(
        self,
        surface: pygame.Surface,
        camera: Optional[Camera25D] = None,
        font: Optional[pygame.font.Font] = None,
        debug: bool = False,
    ) -> None:
        cam = camera or default_camera
        screen_x, screen_y = cam.world_to_screen(self.x, self.y)

        # 1. Sombra de contacto
        render_contact_shadow(surface, screen_x, screen_y)

        # 2. Sprite de Don Antonio (de pie o sentado, tosiendo o tranquilo)
        sprite_surf = get_old_man_sprite(is_coughing=self.is_coughing, is_standing=self.is_standing)
        sprite_topleft_x = int(screen_x - SCALED_SPRITE_WIDTH // 2)
        sprite_topleft_y = int(screen_y - SCALED_SPRITE_HEIGHT + 4)
        surface.blit(sprite_surf, (sprite_topleft_x, sprite_topleft_y))

        # 3. Bocadillo de diálogo o nube de tos
        if self.active_bubble_text and font is not None:
            render_dialogue_bubble(
                surface,
                screen_x,
                sprite_topleft_y,
                "D. Antonio",
                self.active_bubble_text,
                font,
                accent_color=(120, 80, 40),
            )
        elif self.is_coughing and font is not None:
            render_cough_comic_puff(surface, screen_x, screen_y, font)
        elif font is not None:
            tag_y = sprite_topleft_y - 8
            render_agent_name_tag(surface, screen_x, tag_y, self.name, "oldman", font)

        if debug:
            pygame.draw.circle(surface, (0, 255, 255), (int(screen_x), int(screen_y)), 3)
