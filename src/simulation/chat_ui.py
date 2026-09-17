"""Panel lateral de tertulia, historial de debate y entrada interactiva de usuario.

Renderiza un panel UI desacoplado de 380x640 px fuera del lienzo del Bar, con:
1. Historial persistente con scroll vertical y auto-scroll inteligente.
2. Tarjetas visuales diferenciadas por personaje (Tú, Manolo, Josep, Paco, Sistema).
3. Streaming en vivo de tokens con indicador de cursor parpadeante.
4. Caja de texto interactiva con foco, cursor, edición y envío por Enter o botón.
"""

from typing import List, Optional, Tuple
import pygame

from src.simulation.config import CHAT_PANEL_WIDTH, WINDOW_HEIGHT
from src.simulation.conversation import ChatMessage, ConversationCoordinator


# Paleta de colores temáticos de la UI del panel
COLOR_PANEL_BG = (22, 20, 26)
COLOR_PANEL_BORDER = (46, 40, 52)
COLOR_HEADER_BG = (28, 25, 34)
COLOR_INPUT_BG = (32, 29, 39)
COLOR_INPUT_BORDER_IDLE = (58, 52, 68)
COLOR_INPUT_BORDER_FOCUS = (212, 175, 55)  # Dorado brass
COLOR_BUTTON_BG = (212, 175, 55)
COLOR_BUTTON_HOVER = (230, 198, 80)
COLOR_BUTTON_DISABLED = (55, 50, 42)
COLOR_TEXT_WHITE = (240, 238, 245)
COLOR_TEXT_DIM = (140, 134, 150)
COLOR_TEXT_MUTED = (95, 90, 105)

# Colores de tarjetas de autor
CARD_THEMES = {
    "user": {
        "bg": (38, 34, 48),
        "border": (70, 60, 92),
        "author": (165, 148, 225),
        "badge": "👤 Tú",
    },
    "manolo": {
        "bg": (42, 33, 20),
        "border": (115, 82, 35),
        "author": (230, 170, 60),
        "badge": "🍺 Manolo [Barman]",
    },
    "josep": {
        "bg": (20, 30, 50),
        "border": (35, 75, 135),
        "author": (80, 155, 255),
        "badge": "🔵🔴 Josep (Barça)",
    },
    "paco": {
        "bg": (38, 36, 30),
        "border": (110, 100, 70),
        "author": (240, 230, 170),
        "badge": "⚪👑 Paco (Madrid)",
    },
    "system": {
        "bg": (28, 26, 32),
        "border": (50, 46, 56),
        "author": (130, 125, 138),
        "badge": "ℹ️ Sistema",
    },
}


class ChatUI:
    """Interfaz gráfica lateral para la transcripción y control de debates."""

    def __init__(
        self,
        width: int = CHAT_PANEL_WIDTH,
        height: int = WINDOW_HEIGHT,
    ) -> None:
        self.width = width
        self.height = height
        self.surface = pygame.Surface((width, height))

        # Estado del campo de entrada
        self.input_text: str = ""
        self.input_active: bool = False
        self.cursor_timer: float = 0.0
        self.cursor_visible: bool = True

        # Desplazamiento de scroll vertical
        self.scroll_y: float = 0.0
        self.max_scroll: float = 0.0
        self.auto_scroll_enabled: bool = True

        # Geometría de zonas
        self.header_height = 54
        self.input_area_height = 68
        self.viewport_height = height - self.header_height - self.input_area_height

        self.input_rect = pygame.Rect(12, height - 56, width - 100, 42)
        self.send_btn_rect = pygame.Rect(width - 82, height - 56, 70, 42)

    def handle_event(
        self, event: pygame.event.Event, offset_x: int = 960
    ) -> Optional[str]:
        """Procesa eventos de ratón y teclado dentro del panel lateral.

        Retorna la pregunta enviada si el usuario pulsa Enter o hace clic en Enviar.
        """
        if event.type == pygame.MOUSEBUTTONDOWN:
            mouse_x, mouse_y = event.pos
            # Si el clic ocurre en el área del bar (fuera del panel), liberar foco inmediatamente
            if mouse_x < offset_x:
                self.input_active = False
            else:
                panel_x = mouse_x - offset_x
                panel_y = mouse_y

                # Clic en campo de entrada
                if self.input_rect.collidepoint(panel_x, panel_y):
                    self.input_active = True
                else:
                    self.input_active = False

                # Clic en botón de envío
                if self.send_btn_rect.collidepoint(panel_x, panel_y):
                    return self._submit_input()

                # Clic con rueda (scroll hacia arriba o abajo en SDL clásico)
                if event.button == 4:  # Scroll arriba
                    self.scroll(-36)
                elif event.button == 5:  # Scroll abajo
                    self.scroll(36)

        elif event.type == pygame.MOUSEWHEEL:
            # Evento nativo de rueda
            self.scroll(-event.y * 36)

        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.input_active = False
            elif self.input_active:
                if event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                    return self._submit_input()
                elif event.key == pygame.K_BACKSPACE:
                    self.input_text = self.input_text[:-1]
                else:
                    # Filtrar caracteres imprimibles
                    if event.unicode and len(event.unicode) > 0:
                        if event.unicode.isprintable():
                            self.input_text += event.unicode

        return None

    def _submit_input(self) -> Optional[str]:
        """Envía el contenido actual del input y limpia el campo liberando foco."""
        text = self.input_text.strip()
        self.input_active = False
        if text:
            self.input_text = ""
            self.auto_scroll_enabled = True
            return text
        return None

    def scroll(self, delta_y: float) -> None:
        """Ajusta el desplazamiento de scroll del historial."""
        new_scroll = self.scroll_y + delta_y
        if new_scroll < 0:
            new_scroll = 0
        elif new_scroll > self.max_scroll:
            new_scroll = self.max_scroll

        # Si el usuario hace scroll manual hacia arriba, desactivar auto-scroll
        if delta_y < 0:
            self.auto_scroll_enabled = False
        # Si llega al fondo, reactivar auto-scroll
        if new_scroll >= self.max_scroll - 5:
            self.auto_scroll_enabled = True

        self.scroll_y = new_scroll

    def update(self, dt: float) -> None:
        """Actualiza animaciones (parpadeo de cursor de entrada)."""
        self.cursor_timer += dt
        if self.cursor_timer >= 0.5:
            self.cursor_timer = 0.0
            self.cursor_visible = not self.cursor_visible

    def render(
        self,
        coordinator: ConversationCoordinator,
        font: pygame.font.Font,
        font_bold: pygame.font.Font,
        font_small: pygame.font.Font,
    ) -> pygame.Surface:
        """Dibuja el panel lateral completo y retorna su superficie."""
        surf = self.surface
        surf.fill(COLOR_PANEL_BG)

        # ---------------------------------------------------------------------
        # 1. Cabecera con título e indicador de estado
        # ---------------------------------------------------------------------
        header_rect = pygame.Rect(0, 0, self.width, self.header_height)
        pygame.draw.rect(surf, COLOR_HEADER_BG, header_rect)
        pygame.draw.line(surf, COLOR_PANEL_BORDER, (0, self.header_height - 1), (self.width, self.header_height - 1), 1)

        title_surf = font_bold.render("🎙️ TERTULIA DE EL CLÁSICO", True, (230, 198, 110))
        surf.blit(title_surf, (12, 8))

        # Subtítulo / Estado en vivo
        status_text = coordinator.status_message
        if len(status_text) > 48:
            status_text = status_text[:46] + "..."
        status_surf = font_small.render(status_text, True, COLOR_TEXT_DIM)
        surf.blit(status_surf, (14, 30))

        # ---------------------------------------------------------------------
        # 2. Historial de mensajes (área scrollable)
        # ---------------------------------------------------------------------
        viewport_rect = pygame.Rect(0, self.header_height, self.width, self.viewport_height)
        # Creamos una subsuperficie para aislar el clip
        messages_surf = pygame.Surface((self.width, self.viewport_height))
        messages_surf.fill(COLOR_PANEL_BG)

        line_height = font.get_linesize()
        card_margin = 8
        card_width = self.width - 24
        text_max_width = card_width - 16

        total_content_height = 8
        rendered_cards: List[Tuple[ChatMessage, int, int, List[str]]] = []

        for msg in coordinator.messages:
            # Dividir texto por palabras para ajuste
            words = msg.text.split(" ") if msg.text else ["..."]
            lines = []
            curr_line = ""
            for w in words:
                test_line = (curr_line + " " + w).strip()
                if font.size(test_line)[0] <= text_max_width:
                    curr_line = test_line
                else:
                    if curr_line:
                        lines.append(curr_line)
                    curr_line = w
            if curr_line:
                lines.append(curr_line)

            card_h = 24 + len(lines) * line_height + 8
            rendered_cards.append((msg, total_content_height, card_h, lines))
            total_content_height += card_h + card_margin

        self.max_scroll = max(0.0, float(total_content_height - self.viewport_height + 12))

        # Auto-scroll si está activado
        if self.auto_scroll_enabled:
            self.scroll_y = self.max_scroll

        # Dibujar tarjetas de mensajes desplazadas por scroll_y
        for msg, card_top, card_h, lines in rendered_cards:
            draw_y = int(card_top - self.scroll_y)
            # Descartar si cae fuera del viewport
            if draw_y + card_h < 0 or draw_y > self.viewport_height:
                continue

            theme = CARD_THEMES.get(msg.role, CARD_THEMES["system"])
            card_rect = pygame.Rect(12, draw_y, card_width, card_h)

            # Fondo y borde de la tarjeta
            pygame.draw.rect(messages_surf, theme["bg"], card_rect, border_radius=6)
            pygame.draw.rect(messages_surf, theme["border"], card_rect, width=1, border_radius=6)

            # Badge del autor
            author_surf = font_small.render(theme["badge"], True, theme["author"])
            messages_surf.blit(author_surf, (card_rect.x + 8, card_rect.y + 4))

            # Líneas de texto
            for idx, line in enumerate(lines):
                # Si es el mensaje en streaming activo y la última línea, añadir cursor
                if not msg.complete and msg.role in ("josep", "paco") and idx == len(lines) - 1:
                    display_line = line + (" ▌" if self.cursor_visible else "")
                else:
                    display_line = line

                txt_surf = font.render(display_line, True, COLOR_TEXT_WHITE)
                messages_surf.blit(txt_surf, (card_rect.x + 8, card_rect.y + 20 + idx * line_height))

        # Barra de scroll si el contenido supera el viewport
        if self.max_scroll > 0:
            sb_track_h = self.viewport_height - 12
            sb_thumb_h = max(24, int(sb_track_h * (self.viewport_height / total_content_height)))
            sb_scroll_pct = self.scroll_y / self.max_scroll
            sb_thumb_y = int(6 + sb_scroll_pct * (sb_track_h - sb_thumb_h))
            sb_x = self.width - 8
            pygame.draw.rect(messages_surf, (40, 36, 46), (sb_x, 6, 4, sb_track_h), border_radius=2)
            pygame.draw.rect(messages_surf, (100, 92, 115), (sb_x, sb_thumb_y, 4, sb_thumb_h), border_radius=2)

        # Blit del viewport al panel
        surf.blit(messages_surf, (0, self.header_height))

        # ---------------------------------------------------------------------
        # 3. Zona inferior de entrada de texto y botón
        # ---------------------------------------------------------------------
        input_area_rect = pygame.Rect(0, self.height - self.input_area_height, self.width, self.input_area_height)
        pygame.draw.rect(surf, COLOR_HEADER_BG, input_area_rect)
        pygame.draw.line(surf, COLOR_PANEL_BORDER, (0, input_area_rect.y), (self.width, input_area_rect.y), 1)

        # Caja de entrada
        box_border = COLOR_INPUT_BORDER_FOCUS if self.input_active else COLOR_INPUT_BORDER_IDLE
        pygame.draw.rect(surf, COLOR_INPUT_BG, self.input_rect, border_radius=5)
        pygame.draw.rect(surf, box_border, self.input_rect, width=1, border_radius=5)

        if self.input_text:
            text_str = self.input_text
            # Truncar visualmente si desborda la caja
            while font.size(text_str)[0] > (self.input_rect.width - 20) and len(text_str) > 1:
                text_str = text_str[1:]

            txt_surf = font.render(text_str, True, COLOR_TEXT_WHITE)
            surf.blit(txt_surf, (self.input_rect.x + 8, self.input_rect.y + 11))

            if self.input_active and self.cursor_visible:
                cx = self.input_rect.x + 8 + font.size(text_str)[0] + 1
                pygame.draw.line(surf, COLOR_INPUT_BORDER_FOCUS, (cx, self.input_rect.y + 10), (cx, self.input_rect.y + 32), 2)
        else:
            placeholder = "Escribe tu pregunta para Manolo..."
            ph_surf = font_small.render(placeholder, True, COLOR_TEXT_MUTED)
            surf.blit(ph_surf, (self.input_rect.x + 8, self.input_rect.y + 14))

        # Botón Enviar
        btn_bg = COLOR_BUTTON_BG
        btn_label = "Enviar"
        if coordinator.has_pending_question:
            btn_bg = COLOR_BUTTON_DISABLED
            btn_label = "En cola"

        pygame.draw.rect(surf, btn_bg, self.send_btn_rect, border_radius=5)
        btn_txt = font_bold.render(btn_label, True, (20, 18, 22) if not coordinator.has_pending_question else (160, 150, 140))
        bw, bh = font_bold.size(btn_label)
        surf.blit(btn_txt, (self.send_btn_rect.x + (self.send_btn_rect.width - bw) // 2, self.send_btn_rect.y + (self.send_btn_rect.height - bh) // 2))

        return surf
