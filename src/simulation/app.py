"""Punto de entrada ejecutable para la simulación 2.5D del Bar con agentes estáticos.

Inicializa Pygame, ejecuta el bucle a 60 FPS, proyecta la escena oblicua con profundidad
y renderiza los avatares pixel art de Josep y Paco en sus puntos de spawn.
"""

import os
import sys
from typing import Any, List, Optional

import pygame

from src.simulation.agent import (
    BartenderNPC,
    CleanerNPC,
    CoughingManNPC,
    VisualAgent,
)
from src.simulation.audio import AudioManager
from src.simulation.audio_events import AudioEventType
from src.simulation.camera import default_camera
from src.simulation.chat_ui import ChatUI
from src.simulation.config import (
    CHAT_PANEL_WIDTH,
    LOGICAL_HEIGHT,
    LOGICAL_WIDTH,
    TARGET_FPS,
    WINDOW_HEIGHT,
    WINDOW_TITLE,
    WINDOW_WIDTH,
)
from src.simulation.conversation import (
    ConversationCoordinator,
)
from src.simulation.bdi import (
    BDIController,
    create_josep_personality,
    create_paco_personality,
)
from src.simulation.dialogue import (
    ConversationPhase,
    DialogueAdapter,
    DialogueEventType,
)
from src.simulation.navigation import cell_to_pos, pos_to_cell
from src.simulation.rendering import render_debug_overlay, render_scene
from src.simulation.world import BarWorld


def create_initial_agents(world: BarWorld) -> List[VisualAgent]:
    """Crea los agentes visuales Josep y Paco en sus posiciones oficiales de spawn."""
    spawns = world.get_spawn_points()
    bx, by = spawns.get("barcelona_spawn", (6 * 32 + 16, 7 * 32 + 16))
    rx, ry = spawns.get("real_madrid_spawn", (22 * 32 + 16, 8 * 32 + 16))

    josep = VisualAgent(
        agent_id="josep_barca",
        team="barcelona",
        name="Josep",
        spawn_x=bx,
        spawn_y=by,
        initial_facing="right",
    )
    paco = VisualAgent(
        agent_id="paco_madrid",
        team="real_madrid",
        name="Paco",
        spawn_x=rx,
        spawn_y=ry,
        initial_facing="left",
    )
    return [josep, paco]


def create_atmosphere_npcs(world: Optional[BarWorld] = None) -> List[Any]:
    """Crea los personajes de ambientación solicitados:
    - Bartender (Manolo): detrás de la barra preparando y agitando cócteles.
    - Señora de limpieza (Doña Carmen): con fregona y cubo limpiando el bar.
    - Señor en la esquina (Don Antonio): con boina tosiendo periódicamente.
    """
    bartender = BartenderNPC(x=2 * 32 + 16, y=7 * 32 + 16, name="Manolo [Barman]")
    cleaner = CleanerNPC(x=13 * 32, y=16 * 32, name="Dña. Carmen [Limpieza]")
    old_man = CoughingManNPC(x=25 * 32, y=17 * 32, name="D. Antonio")
    return [bartender, cleaner, old_man]


def run_simulation(
    debug: bool = False,
    demo_movement: bool = False,
    bdi: bool = False,
    dialogue: bool = False,
    dialogue_adapter: Optional[Any] = None,
    audio_manager: Optional[Any] = None,
    audio_enabled: bool = True,
    tts_enabled: bool = True,
    max_frames: Optional[int] = None,
    seed: Optional[int] = None,
) -> None:
    """Ejecuta el bucle principal de la escena 2.5D en Pygame con navegación, BDI y síntesis de audio.

    Args:
        debug: Si True, arranca mostrando la cuadrícula, celdas bloqueadas, colisiones y rutas.
        demo_movement: Si True, activa la demostración cíclica de patrulla controlada sin BDI.
        bdi: Si True, activa el comportamiento autónomo deliberativo BDI para Josep y Paco.
        dialogue: Si True, inicia el sistema de debate real con LangGraph en segundo plano.
        dialogue_adapter: Adaptador de diálogo opcional (permite inyectar mocks en pruebas).
        audio_manager: Gestor de audio opcional (permite inyectar mock TTS en pruebas).
        audio_enabled: Si False, desactiva la inicialización del subsistema de audio.
        tts_enabled: Si False, arranca con la generación de voz TTS desactivada.
        max_frames: Si se especifica, corre N frames y sale (útil para pruebas automatizadas).
        seed: Semilla pseudoaleatoria determinista para el controlador BDI.
    """
    pygame.init()
    pygame.font.init()

    window_surface = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.RESIZABLE)
    pygame.display.set_caption(WINDOW_TITLE)

    # Superficie lógica de resolución fija (960x640)
    logical_surface = pygame.Surface((LOGICAL_WIDTH, LOGICAL_HEIGHT))

    clock = pygame.time.Clock()
    font_small = pygame.font.SysFont("Arial", 11)
    font_small_bold = pygame.font.SysFont("Arial", 11, bold=True)
    font_tiny = pygame.font.SysFont("Arial", 9)

    chat_ui = ChatUI(width=CHAT_PANEL_WIDTH, height=LOGICAL_HEIGHT)
    coordinator = ConversationCoordinator()

    # 1. Instanciar el mundo del bar
    world = BarWorld()

    # 2. Instanciar cámara, agentes principales y NPCs de ambientación
    camera = default_camera
    agents = create_initial_agents(world)
    atmosphere_npcs = create_atmosphere_npcs(world)
    all_characters: List[Any] = agents + atmosphere_npcs
    bartender_npc = next((n for n in atmosphere_npcs if isinstance(n, BartenderNPC)), None)

    debug_mode = debug
    # El debate requiere que el BDI esté activo para coordinar los encuentros
    bdi_active = bdi or dialogue
    # El modo BDI tiene precedencia sobre el modo demo de patrulla
    demo_active = demo_movement and not bdi_active
    selected_agent_idx = 0
    running = True
    frame_count = 0

    # Inicializar adaptador de diálogo si fue solicitado
    from src.config.settings import MODEL_PROVIDER
    from src.simulation.debug_logger import debug_log

    debug_log(
        "APP_INIT",
        "CONFIGURATION_CHECK",
        f"model_provider={MODEL_PROVIDER}, has_gemini_key={bool(os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY'))}, has_openai_key={bool(os.getenv('OPENAI_API_KEY'))}",
    )

    if dialogue and dialogue_adapter is None:
        dialogue_adapter = DialogueAdapter()
        debug_log("APP_INIT", "ADAPTER_CREATED", f"adapter_instance_id={id(dialogue_adapter)}")
        dialogue_adapter.start()
        debug_log(
            "APP_INIT",
            "WORKER_STARTED",
            f"worker_thread_id={dialogue_adapter.worker.ident if dialogue_adapter.worker else None}, worker_alive={dialogue_adapter.worker.is_alive() if dialogue_adapter.worker else False}",
        )

    if audio_manager is None:
        audio_manager = AudioManager()
    if not audio_enabled:
        audio_manager.audio_available = False
    if not tts_enabled:
        audio_manager.tts_enabled = False
    audio_manager.start()

    # Inicializar controladores BDI para Josep y Paco con personalidades diferenciadas
    bdi_controllers = [
        BDIController("josep_barca", "barcelona", "Josep", create_josep_personality(), seed=seed),
        BDIController("paco_madrid", "real_madrid", "Paco", create_paco_personality(), seed=seed),
    ]
    debug_log(
        "APP_INIT",
        "BDI_CONTROLLERS_CREATED",
        f"josep_bdi={id(bdi_controllers[0])}, paco_bdi={id(bdi_controllers[1])}, bdi_active={bdi_active}",
    )

    if bdi_active:
        agents[0].attach_bdi(bdi_controllers[0])
        agents[1].attach_bdi(bdi_controllers[1])
        if dialogue_adapter is not None:
            bdi_controllers[0].attach_dialogue_adapter(dialogue_adapter)
            bdi_controllers[1].attach_dialogue_adapter(dialogue_adapter)
            same_adapter = bdi_controllers[0].dialogue_adapter is bdi_controllers[1].dialogue_adapter
            debug_log(
                "APP_INIT",
                "ADAPTER_ATTACHED_TO_BDI",
                f"attached_to_both={same_adapter}, adapter_busy={dialogue_adapter.is_busy()}",
            )

    # Puntos de interés para el modo de demostración cíclica controlada
    demo_patrols = {
        0: ["bar_stool_2", "table_central_1_seat_west", "tv_lounge_seat_22", "barcelona_spawn"],
        1: ["bar_stool_4", "tv_lounge_seat_24", "table_side_1_seat_north", "real_madrid_spawn"],
    }
    demo_indices = {0: 0, 1: 0}
    demo_pause_timers = {0: 0.5, 1: 1.0}

    try:
        while running:
            # Control de tiempo a 60 FPS estables (dt en segundos)
            dt = clock.tick(TARGET_FPS) / 1000.0

            # 1. Eventos de entrada
            current_window_size = window_surface.get_size()
            win_w, win_h = current_window_size
            bar_screen_w = int(win_w * (LOGICAL_WIDTH / WINDOW_WIDTH))

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.VIDEORESIZE:
                    window_surface = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
                else:
                    # Enrutamiento al panel lateral de chat con controles de audio
                    submitted_q = chat_ui.handle_event(event, offset_x=bar_screen_w, audio_manager=audio_manager)
                    if submitted_q:
                        if dialogue_adapter is None:
                            dialogue_adapter = DialogueAdapter()
                            dialogue_adapter.start()
                            if bdi_active:
                                bdi_controllers[0].attach_dialogue_adapter(dialogue_adapter)
                                bdi_controllers[1].attach_dialogue_adapter(dialogue_adapter)

                        if (
                            dialogue_adapter.is_busy()
                            and dialogue_adapter.active_conversation_id != coordinator.active_conversation_id
                        ):
                            dialogue_adapter.cancel_conversation()

                        coordinator.submit_question(submitted_q, world=world, agents=agents)

                    # Si el campo de texto tiene foco y es tecla, no procesar atajos del simulador
                    if chat_ui.input_active and event.type == pygame.KEYDOWN:
                        continue

                    if event.type == pygame.KEYDOWN:
                        if event.key in (pygame.K_ESCAPE, pygame.K_q):
                            running = False
                        elif event.key == pygame.K_d:
                            debug_mode = not debug_mode
                        elif event.key == pygame.K_b:
                            bdi_active = not bdi_active
                            if bdi_active:
                                demo_active = False
                                agents[0].attach_bdi(bdi_controllers[0])
                                agents[1].attach_bdi(bdi_controllers[1])
                                if dialogue_adapter is not None:
                                    bdi_controllers[0].attach_dialogue_adapter(dialogue_adapter)
                                    bdi_controllers[1].attach_dialogue_adapter(dialogue_adapter)
                            else:
                                agents[0].detach_bdi()
                                agents[1].detach_bdi()
                                bdi_controllers[0].detach_dialogue_adapter()
                                bdi_controllers[1].detach_dialogue_adapter()
                        elif event.key == pygame.K_m:
                            if audio_manager is not None:
                                audio_manager.toggle_mute()
                        elif event.key == pygame.K_k:
                            if audio_manager is not None:
                                audio_manager.toggle_pause()
                        elif event.key in (pygame.K_x, pygame.K_s):
                            if audio_manager is not None:
                                audio_manager.cancel_current_speech()
                        elif event.key == pygame.K_t:
                            if audio_manager is not None:
                                audio_manager.toggle_tts()
                        elif event.key == pygame.K_p:
                            demo_active = not demo_active
                            if demo_active and bdi_active:
                                bdi_active = False
                                agents[0].detach_bdi()
                                agents[1].detach_bdi()
                                bdi_controllers[0].detach_dialogue_adapter()
                                bdi_controllers[1].detach_dialogue_adapter()
                        elif event.key in (pygame.K_TAB, pygame.K_SPACE):
                            selected_agent_idx = (selected_agent_idx + 1) % len(agents)
                        elif event.key == pygame.K_1:
                            selected_agent_idx = 0
                        elif event.key == pygame.K_2 and len(agents) > 1:
                            selected_agent_idx = 1
                        elif event.key == pygame.K_c:
                            agents[selected_agent_idx].cancel_navigation()

                    elif event.type == pygame.MOUSEBUTTONDOWN and event.pos[0] < bar_screen_w:
                        # Conversión de coordenadas de ventana a lógicas exclusivamente dentro del bar
                        bar_px = event.pos[0] * (LOGICAL_WIDTH / max(1, bar_screen_w))
                        bar_py = event.pos[1] * (LOGICAL_HEIGHT / max(1, win_h))
                        lx, ly = camera.window_to_logical(bar_px, bar_py, (LOGICAL_WIDTH, LOGICAL_HEIGHT))
                        if event.button == 1:
                            col, row = pos_to_cell(lx, ly)
                            if world.is_tile_walkable(col, row):
                                target_x, target_y = cell_to_pos(col, row)
                                agents[selected_agent_idx].navigate_to(world, target_x, target_y)
                        elif event.button == 3:
                            agents[selected_agent_idx].cancel_navigation()

            # 2. Rutina de demostración cíclica (solo si demo_active está habilitado y BDI apagado)
            if demo_active and not bdi_active:
                for a_idx, agent in enumerate(agents):
                    if not agent.is_navigating:
                        if agent.is_drinking:
                            demo_pause_timers[a_idx] = max(demo_pause_timers[a_idx], 2.5)
                        demo_pause_timers[a_idx] -= dt
                        if demo_pause_timers[a_idx] <= 0:
                            patrol = demo_patrols[a_idx]
                            poi_key = patrol[demo_indices[a_idx]]
                            agent.navigate_to_poi(world, poi_key)
                            demo_indices[a_idx] = (demo_indices[a_idx] + 1) % len(patrol)
                            demo_pause_timers[a_idx] = 4.0

            # 2.2. Actualizar tertulia, máquina de estados y UI lateral
            chat_ui.update(dt)
            if audio_manager is not None:
                audio_manager.update(dt)

            coordinator.update(
                dt,
                world=world,
                agents=agents,
                manolo=bartender_npc,
                dialogue_adapter=dialogue_adapter,
                audio_manager=audio_manager,
            )

            # 2.5. Procesar eventos del worker de LangGraph si el adaptador de diálogo está activo
            if dialogue_adapter is not None:
                drained_events = dialogue_adapter.poll_events()
                for ev in drained_events:
                    coordinator.process_dialogue_event(ev, agents, audio_manager=audio_manager)
                    speaker = next((a for a in agents if a.team == ev.speaker_team), None)
                    listener = next((a for a in agents if a.team != ev.speaker_team), None) if speaker else None

                    if ev.event_type == DialogueEventType.STARTED:
                        for a in agents:
                            a.conversation_phase = ConversationPhase.WAITING_RESPONSE

                    elif ev.event_type == DialogueEventType.TURN_STARTED:
                        if speaker:
                            speaker.clear_dialogue()
                            speaker.set_thinking(True)
                            speaker.conversation_phase = ConversationPhase.WAITING_RESPONSE
                        if listener:
                            listener.set_thinking(False)
                            listener.conversation_phase = ConversationPhase.WAITING_RESPONSE

                    elif ev.event_type == DialogueEventType.TEXT_CHUNK:
                        if speaker:
                            speaker.set_dialogue_text(ev.text, append=True)
                            speaker.conversation_phase = ConversationPhase.SPEAKING
                        if listener and getattr(listener, "active_dialogue_text", None):
                            listener.clear_dialogue()

                    elif ev.event_type == DialogueEventType.TOOL_STARTED:
                        if speaker:
                            speaker.set_thinking(True)

                    elif ev.event_type == DialogueEventType.MESSAGE_COMPLETED:
                        if speaker:
                            speaker.complete_dialogue_message(ev.text)
                            speaker.conversation_phase = ConversationPhase.WAITING_RESPONSE

                    elif ev.event_type in (
                        DialogueEventType.FINISHED,
                        DialogueEventType.ERROR,
                        DialogueEventType.CANCELLED,
                    ):
                        for a in agents:
                            a.set_thinking(False)
                            a.conversation_phase = ConversationPhase.IDLE
                        if ev.event_type == DialogueEventType.ERROR and ev.error_message:
                            if speaker:
                                speaker.say("... (sin conexión con el modelo)", duration=2.5)

            # 2.8. Procesar eventos del subsistema de audio y reflejar estados visuales
            if audio_manager is not None:
                for aev in audio_manager.poll_events():
                    target = None
                    if aev.speaker in ("manolo", "bartender"):
                        target = bartender_npc
                    elif aev.speaker in ("josep", "barcelona", "josep_barca"):
                        target = agents[0] if len(agents) > 0 else None
                    elif aev.speaker in ("paco", "real_madrid", "paco_madrid"):
                        target = agents[1] if len(agents) > 1 else None

                    if target is not None:
                        if aev.event_type == AudioEventType.VOICE_STARTED:
                            target.set_voice_state("VOICE_PLAYING")
                        elif aev.event_type in (
                            AudioEventType.VOICE_FINISHED,
                            AudioEventType.VOICE_ERROR,
                            AudioEventType.VOICE_CANCELLED,
                        ):
                            target.set_voice_state("IDLE")

            # 3. Actualización de agentes con dt, mundo y referencia al otro agente
            for idx, agent in enumerate(agents):
                other = agents[1 - idx] if len(agents) > 1 else None
                agent.update(dt, world=world, other_agent=other)

            # Actualización interactiva de NPCs de ambientación (delimitados a sus zonas)
            for npc in atmosphere_npcs:
                if isinstance(npc, BartenderNPC):
                    npc.update(dt, customers=agents)
                elif isinstance(npc, CoughingManNPC):
                    npc.update(dt, nearby_agents=agents)
                else:
                    npc.update(dt)

            # 4. Renderizado de la escena 2.5D con ordenamiento de profundidad
            render_scene(logical_surface, world, font_small, agents=all_characters, camera=camera)

            if debug_mode:
                render_debug_overlay(
                    logical_surface,
                    world,
                    font_small,
                    agents=agents,
                    selected_agent_idx=selected_agent_idx,
                    camera=camera,
                )

            # Renderizado del panel lateral de tertulia con barra de control de audio
            panel_surface = chat_ui.render(
                coordinator, font_small, font_small_bold, font_tiny, audio_manager=audio_manager
            )

            # 5. Escalado y presentación en la ventana
            if current_window_size == (WINDOW_WIDTH, WINDOW_HEIGHT):
                window_surface.blit(logical_surface, (0, 0))
                window_surface.blit(panel_surface, (LOGICAL_WIDTH, 0))
            else:
                full_canvas = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
                full_canvas.blit(logical_surface, (0, 0))
                full_canvas.blit(panel_surface, (LOGICAL_WIDTH, 0))
                scaled_surface = pygame.transform.scale(full_canvas, current_window_size)
                window_surface.blit(scaled_surface, (0, 0))

            pygame.display.flip()

            frame_count += 1
            if max_frames is not None and frame_count >= max_frames:
                break

    finally:
        if audio_manager is not None:
            audio_manager.shutdown()
        if dialogue_adapter is not None:
            dialogue_adapter.shutdown()
        pygame.quit()


if __name__ == "__main__":
    cli_debug = "--debug" in sys.argv or "-d" in sys.argv
    cli_demo = "--demo-movement" in sys.argv or "--demo" in sys.argv
    cli_bdi = "--bdi" in sys.argv or "-b" in sys.argv
    cli_dialogue = "--dialogue" in sys.argv
    cli_no_audio = "--no-audio" in sys.argv
    cli_no_tts = "--no-tts" in sys.argv
    run_simulation(
        debug=cli_debug,
        demo_movement=cli_demo,
        bdi=cli_bdi,
        dialogue=cli_dialogue,
        audio_enabled=not cli_no_audio,
        tts_enabled=not cli_no_tts,
    )
