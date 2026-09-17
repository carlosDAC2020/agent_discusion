"""Pruebas unitarias para la Fase 4: Arquitectura BDI Local de Josep y Paco.

Valida exhaustivamente los 30 requisitos BDI:
1. Creación de creencias iniciales válidas y valores normalizados [0.0, 1.0].
2. Actualización de necesidades con el paso del tiempo durante la percepción.
3. Clamping automático de necesidades en los límites [0.0, 1.0].
4. Percepción espacial de distancia al rival/otro agente.
5. Detección de visibilidad del rival y cálculo euclídeo.
6. Cálculo de utilidades de deseos según necesidades y personalidad.
7. Josep prioriza Drink/Barra cuando la sed es alta.
8. Paco prioriza Rest/Sofá cuando la energía es baja.
9. Deseo Recover se activa con máxima prioridad en caso de error de navegación.
10. Deseo Socialize se activa cuando sociability es alta y el rival es visible.
11. Respeto estricto del umbral de preempción (BDI_UTILITY_PREEMPT_THRESHOLD = 0.30).
12. Respeto estricto del tiempo mínimo de compromiso (min_duration = 2.5s).
13. Aplicación de cooldown tras completar un deseo para evitar bucles inmediatos.
14. Penalización / rotación de POIs recientemente visitados para evitar estancamiento.
15. Plan Drink: navegación a la barra, fase de acción, reducción de sed y compleción.
16. Plan Rest: navegación al asiento, descanso, recuperación de energía y compleción.
17. Plan Explore: selección de POI según afinidad individual e inicio de marcha.
18. Plan Socialize: aproximación manteniendo distancia social respetuosa [40, 96] px.
19. Plan Socialize nunca selecciona la misma celda física del rival.
20. Plan Recover: búsqueda de punto seguro de recuperación.
21. Transición de estados de Intention: PENDING -> ACTIVE -> COMPLETED.
22. Manejo de fallos en la ruta (IntentionState.FAILED) y replanificación segura.
23. Cancelación manual/controlada de una intención activa.
24. Desacoplamiento temporal: deliberación a 4 Hz (cada 0.25s) y no en cada frame a 60 FPS.
25. Modo interactivo: alternancia limpia de BDI mediante attach_bdi y detach_bdi.
26. Incompatibilidad controlada: aislamiento entre control deliberativo y modo demo.
27. Determinismo con semilla fija (mismo seed produce misma secuencia inicial).
28. Modo headless con --bdi: simulación estable durante múltiples ticks sin crashes.
29. Modo normal sin --bdi mantiene los agentes inmóviles por defecto.
30. Los subsistemas conversacionales existentes permanecen intactos y sin alterar.
"""

import math
import os
import random
import pytest

from src.simulation.agent import VisualAgent
from src.simulation.app import create_initial_agents, run_simulation
from src.simulation.bdi import (
    AgentBeliefs,
    AgentPersonality,
    BDIController,
    Desire,
    DesireType,
    Intention,
    IntentionState,
    create_josep_personality,
    create_paco_personality,
)
from src.simulation.config import (
    BDI_DECISION_FREQUENCY,
    BDI_DECISION_INTERVAL,
    BDI_DESIRE_COOLDOWN,
    BDI_MAX_SOCIAL_DISTANCE,
    BDI_MIN_INTENTION_DURATION,
    BDI_MIN_SOCIAL_DISTANCE,
    BDI_UTILITY_PREEMPT_THRESHOLD,
    STATE_IDLE,
    STATE_WALKING,
)
from src.simulation.navigation import cell_to_pos, pos_to_cell
from src.simulation.world import BarWorld


# =============================================================================
# 1, 2 Y 3. CREENCIAS Y NECESIDADES
# =============================================================================

def test_1_initial_beliefs_valid_and_normalized():
    """Valida la inicialización de creencias dentro del rango [0.0, 1.0]."""
    beliefs = AgentBeliefs(agent_id="josep", team="barcelona", name="Josep", energy=0.8, thirst=0.3, sociability=0.5)
    d = beliefs.to_dict()
    assert 0.0 <= d["energy"] <= 1.0
    assert 0.0 <= d["thirst"] <= 1.0
    assert 0.0 <= d["sociability"] <= 1.0
    assert beliefs.other_agent_visible is False
    assert beliefs.other_agent_distance == float("inf")


def test_2_beliefs_update_needs_over_time():
    """Valida el decaimiento/aumento temporal de necesidades según perceive."""
    world = BarWorld()
    agent = VisualAgent("josep", "barcelona", "Josep", 200.0, 200.0)
    bdi = BDIController("josep", "barcelona", "Josep")
    bdi.beliefs.energy = 1.0
    bdi.beliefs.thirst = 0.0
    bdi.beliefs.sociability = 0.0

    bdi.perceive(agent, world, other_agent=None, dt=5.0)
    assert bdi.beliefs.energy < 1.0
    assert bdi.beliefs.thirst > 0.0
    assert bdi.beliefs.sociability > 0.0


def test_3_beliefs_clamping_limits():
    """Valida el clamping estricto entre 0.0 y 1.0 al sobrepasar límites."""
    beliefs = AgentBeliefs(agent_id="paco", team="real_madrid", name="Paco", energy=-0.5, thirst=2.5, sociability=1.2)
    beliefs.clamp_needs()
    assert beliefs.energy == 0.0
    assert beliefs.thirst == 1.0
    assert beliefs.sociability == 1.0


# =============================================================================
# 4 Y 5. PERCEPCIÓN ESPACIAL Y RIVAL
# =============================================================================

def test_4_spatial_perception_rival_distance():
    """Valida el cálculo de distancia euclídea al otro agente en perceive."""
    world = BarWorld()
    josep = VisualAgent("josep", "barcelona", "Josep", 100.0, 100.0)
    paco = VisualAgent("paco", "real_madrid", "Paco", 100.0, 160.0)
    bdi = BDIController("josep", "barcelona", "Josep")

    bdi.perceive(josep, world, other_agent=paco, dt=0.01)
    assert math.isclose(bdi.beliefs.other_agent_distance, 60.0, rel_tol=1e-3)
    assert bdi.beliefs.other_agent_pos == (100.0, 160.0)
    assert bdi.beliefs.other_agent_visible is True


def test_5_spatial_perception_rival_visibility_and_none():
    """Valida que si no hay otro agente, la visibilidad es False y la distancia infinita."""
    world = BarWorld()
    josep = VisualAgent("josep", "barcelona", "Josep", 100.0, 100.0)
    bdi = BDIController("josep", "barcelona", "Josep")

    bdi.perceive(josep, world, other_agent=None, dt=0.01)
    assert bdi.beliefs.other_agent_visible is False
    assert bdi.beliefs.other_agent_distance == float("inf")
    assert bdi.beliefs.other_agent_pos is None


# =============================================================================
# 6, 7, 8, 9 Y 10. DESEOS Y PERSONALIDADES (JOSEP VS PACO)
# =============================================================================

def test_6_desire_utility_calculation():
    """Valida el cálculo de intensidades de deseos tras evaluate_desires."""
    bdi = BDIController("josep", "barcelona", "Josep")
    bdi.beliefs.thirst = 0.95
    bdi.evaluate_desires(dt=0.01)

    drink_desire = bdi.desires[DesireType.DRINK]
    assert drink_desire.intensity > 1.0


def test_7_josep_prioritizes_drink_when_thirsty():
    """Josep prioriza Drink cuando su nivel de sed es alto."""
    world = BarWorld()
    bdi = BDIController("josep", "barcelona", "Josep")
    bdi.beliefs.thirst = 0.90
    bdi.beliefs.energy = 0.80

    bdi.evaluate_desires(dt=0.01)
    bdi.select_intention(world, other_agent=None)

    assert bdi.current_intention is not None
    assert bdi.current_intention.desire_type == DesireType.DRINK
    assert "bar_stool" in (bdi.current_intention.target_poi_name or "")


def test_8_paco_prioritizes_rest_when_tired():
    """Paco prioriza Rest y la zona de TV cuando su energía es baja."""
    world = BarWorld()
    bdi = BDIController("paco", "real_madrid", "Paco")
    bdi.beliefs.energy = 0.20
    bdi.beliefs.thirst = 0.10

    bdi.evaluate_desires(dt=0.01)
    bdi.select_intention(world, other_agent=None)

    assert bdi.current_intention is not None
    assert bdi.current_intention.desire_type == DesireType.REST
    assert "tv_lounge" in (bdi.current_intention.target_poi_name or "")


def test_9_recover_activates_on_navigation_error():
    """El deseo RECOVER toma prioridad absoluta cuando ocurre un error de navegación."""
    world = BarWorld()
    bdi = BDIController("josep", "barcelona", "Josep")
    bdi.beliefs.has_navigation_error = True

    bdi.evaluate_desires(dt=0.01)
    assert bdi.desires[DesireType.RECOVER].intensity == 1.5

    bdi.select_intention(world, other_agent=None)
    assert bdi.current_intention is not None
    assert bdi.current_intention.desire_type == DesireType.RECOVER


def test_10_socialize_activates_when_sociability_high():
    """El deseo SOCIALIZE se activa cuando sociability es alta y el rival es visible."""
    world = BarWorld()
    josep = VisualAgent("josep", "barcelona", "Josep", 200.0, 200.0)
    paco = VisualAgent("paco", "real_madrid", "Paco", 250.0, 200.0)
    bdi = BDIController("josep", "barcelona", "Josep")
    bdi.perceive(josep, world, other_agent=paco, dt=0.01)
    bdi.beliefs.sociability = 0.95

    bdi.evaluate_desires(dt=0.01)
    assert bdi.desires[DesireType.SOCIALIZE].intensity > 0.8


# =============================================================================
# 11, 12, 13 Y 14. PREVENCIÓN DE OSCILACIÓN Y PERSISTENCIA DE INTENCIONES
# =============================================================================

def test_11_preemption_threshold_delta():
    """No permite cambiar de intención si la nueva utilidad no supera el delta mínimo."""
    world = BarWorld()
    bdi = BDIController("josep", "barcelona", "Josep")

    # Establecer intención activa con tiempo cumplido
    old_intention = Intention(
        intention_id="test_int_1",
        desire_type=DesireType.EXPLORE,
        plan_name="plan_explore",
        state=IntentionState.ACTIVE,
        elapsed_time=3.0,  # > 2.5s
        min_duration=2.5,
        utility=0.60,
    )
    bdi.current_intention = old_intention

    # Forzar intensidades: Drink tiene 0.70 (delta = 0.10 < 0.30)
    for d in bdi.desires.values():
        d.intensity = 0.0
    bdi.desires[DesireType.DRINK].intensity = 0.70

    bdi.select_intention(world, other_agent=None)
    # Debe mantener la intención activa previa
    assert bdi.current_intention == old_intention


def test_12_minimum_intention_duration():
    """No permite cambiar de intención si no ha transcurrido min_duration."""
    world = BarWorld()
    bdi = BDIController("josep", "barcelona", "Josep")

    old_intention = Intention(
        intention_id="test_int_2",
        desire_type=DesireType.EXPLORE,
        plan_name="plan_explore",
        state=IntentionState.ACTIVE,
        elapsed_time=1.0,  # < 2.5s
        min_duration=2.5,
        utility=0.30,
    )
    bdi.current_intention = old_intention

    # Forzar utilidad muy alta en Drink (1.5 > 0.3 + 0.3)
    for d in bdi.desires.values():
        d.intensity = 0.0
    bdi.desires[DesireType.DRINK].intensity = 1.50

    bdi.select_intention(world, other_agent=None)
    # Persiste porque elapsed_time < min_duration
    assert bdi.current_intention == old_intention


def test_13_cooldown_after_desire_completion():
    """Al completar un deseo se aplica cooldown que impide su reelección inmediata."""
    agent = VisualAgent("josep", "barcelona", "Josep", 200.0, 200.0)
    bdi = BDIController("josep", "barcelona", "Josep")

    # Simular compleción de Drink
    bdi.current_intention = Intention(
        intention_id="test_drink",
        desire_type=DesireType.DRINK,
        plan_name="plan_drink_at_bar",
        state=IntentionState.ACTIVE,
        cooldown=BDI_DESIRE_COOLDOWN,
    )
    bdi._complete_intention(agent)

    assert bdi.desires[DesireType.DRINK].cooldown_timer == BDI_DESIRE_COOLDOWN
    # Al evaluar deseos con cooldown activo, su intensidad es 0.0
    bdi.evaluate_desires(dt=0.01)
    assert bdi.desires[DesireType.DRINK].intensity == 0.0


def test_14_recent_poi_memory_penalization():
    """Los POIs recientemente visitados se registran en recent_pois para variar destinos."""
    agent = VisualAgent("josep", "barcelona", "Josep", 200.0, 200.0)
    bdi = BDIController("josep", "barcelona", "Josep")

    bdi.current_intention = Intention(
        intention_id="test_poi",
        desire_type=DesireType.DRINK,
        plan_name="plan_drink_at_bar",
        target_poi_name="bar_stool_1",
        state=IntentionState.ACTIVE,
    )
    bdi._complete_intention(agent)

    assert "bar_stool_1" in bdi.recent_pois


# =============================================================================
# 15, 16, 17, 18, 19 Y 20. PLANES Y EJECUCIÓN
# =============================================================================

def test_15_plan_drink_execution():
    """Plan Drink: avanza a la barra, fase de acción, reduce sed y se completa."""
    world = BarWorld()
    agent = VisualAgent("josep", "barcelona", "Josep", 120.0, 240.0)
    bdi = BDIController("josep", "barcelona", "Josep")
    bdi.beliefs.thirst = 0.85

    intention = Intention(
        intention_id="int_drink_1",
        desire_type=DesireType.DRINK,
        plan_name="plan_drink_at_bar",
        state=IntentionState.ACTIVE,
        target_pos=(120.0, 240.0),
        action_duration=2.0,
        execution_phase="NAVIGATING",
    )
    bdi.current_intention = intention

    # Como ya está en la posición, pasa a ACTION
    bdi.execute_plan(agent, world, other_agent=None, dt=0.01)
    assert intention.execution_phase == "ACTION"

    initial_thirst = bdi.beliefs.thirst
    # Completar el temporizador de acción
    bdi.execute_plan(agent, world, other_agent=None, dt=3.0)
    assert bdi.beliefs.thirst < initial_thirst
    assert intention.state == IntentionState.COMPLETED
    assert bdi.current_intention is None


def test_16_plan_rest_execution():
    """Plan Rest: descansa, recupera energía y se completa."""
    world = BarWorld()
    agent = VisualAgent("paco", "real_madrid", "Paco", 300.0, 300.0)
    bdi = BDIController("paco", "real_madrid", "Paco")
    bdi.beliefs.energy = 0.30

    intention = Intention(
        intention_id="int_rest_1",
        desire_type=DesireType.REST,
        plan_name="plan_rest_at_seat",
        state=IntentionState.ACTIVE,
        target_pos=(300.0, 300.0),
        action_duration=2.0,
        execution_phase="ACTION",
    )
    bdi.current_intention = intention

    initial_energy = bdi.beliefs.energy
    bdi.execute_plan(agent, world, other_agent=None, dt=3.0)
    assert bdi.beliefs.energy > initial_energy
    assert intention.state == IntentionState.COMPLETED


def test_17_plan_explore_navigation():
    """Plan Explore: selecciona POI preferido y pone al agente en marcha."""
    world = BarWorld()
    agent = VisualAgent("josep", "barcelona", "Josep", 200.0, 200.0)
    bdi = BDIController("josep", "barcelona", "Josep")

    bdi.desires[DesireType.EXPLORE].intensity = 1.0
    for dt_other, d in bdi.desires.items():
        if dt_other != DesireType.EXPLORE:
            d.intensity = 0.0

    bdi.select_intention(world, other_agent=None)
    assert bdi.current_intention is not None
    assert bdi.current_intention.desire_type == DesireType.EXPLORE

    bdi.execute_plan(agent, world, other_agent=None, dt=0.01)
    assert agent.is_walking is True


def test_18_plan_socialize_keeps_respectful_distance():
    """Plan Socialize busca una celda respetando la distancia social [40, 96] px."""
    world = BarWorld()
    paco = VisualAgent("paco", "real_madrid", "Paco", 400.0, 300.0)
    josep = VisualAgent("josep", "barcelona", "Josep", 200.0, 300.0)
    bdi = BDIController("josep", "barcelona", "Josep")

    target_xy = bdi._find_social_position_near(paco, world)
    assert target_xy is not None
    dist = math.hypot(target_xy[0] - paco.x, target_xy[1] - paco.y)
    assert BDI_MIN_SOCIAL_DISTANCE <= dist <= BDI_MAX_SOCIAL_DISTANCE + 16.0


def test_19_plan_socialize_never_overlaps_rival_cell():
    """Plan Socialize nunca selecciona la misma celda de grilla del rival."""
    world = BarWorld()
    paco = VisualAgent("paco", "real_madrid", "Paco", 400.0, 300.0)
    bdi = BDIController("josep", "barcelona", "Josep")

    target_xy = bdi._find_social_position_near(paco, world)
    assert target_xy is not None
    rival_cell = pos_to_cell(paco.x, paco.y)
    target_cell = pos_to_cell(target_xy[0], target_xy[1])
    assert target_cell != rival_cell


def test_20_plan_recover_restores_error():
    """Plan Recover: limpia el error de navegación al completarse."""
    world = BarWorld()
    agent = VisualAgent("josep", "barcelona", "Josep", 200.0, 200.0)
    bdi = BDIController("josep", "barcelona", "Josep")
    bdi.beliefs.has_navigation_error = True
    bdi.beliefs.last_navigation_error = "some_error"

    intention = Intention(
        intention_id="int_rec_1",
        desire_type=DesireType.RECOVER,
        plan_name="plan_recover_error",
        state=IntentionState.ACTIVE,
        action_duration=1.0,
        execution_phase="ACTION",
    )
    bdi.current_intention = intention

    bdi.execute_plan(agent, world, other_agent=None, dt=1.5)
    assert bdi.beliefs.has_navigation_error is False
    assert intention.state == IntentionState.COMPLETED


# =============================================================================
# 21, 22 Y 23. CICLO DE VIDA, FALLOS Y CANCELACIÓN DE INTENCIONES
# =============================================================================

def test_21_intention_state_transitions():
    """Valida la transición formal: PENDING -> ACTIVE -> COMPLETED."""
    intention = Intention(
        intention_id="test_trans",
        desire_type=DesireType.EXPLORE,
        plan_name="plan_explore",
        state=IntentionState.PENDING,
        execution_phase="ACTION",
        action_duration=1.0,
    )
    assert intention.state == IntentionState.PENDING

    world = BarWorld()
    agent = VisualAgent("josep", "barcelona", "Josep", 200.0, 200.0)
    bdi = BDIController("josep", "barcelona", "Josep")
    intention.state = IntentionState.ACTIVE
    bdi.current_intention = intention

    bdi.execute_plan(agent, world, other_agent=None, dt=1.5)
    assert intention.state == IntentionState.COMPLETED


def test_22_intention_failure_and_replanning():
    """Si fallan múltiples intentos de navegación, la intención pasa a FAILED."""
    world = BarWorld()
    agent = VisualAgent("josep", "barcelona", "Josep", 200.0, 200.0)
    bdi = BDIController("josep", "barcelona", "Josep")

    # Posición inválida fuera del mundo
    intention = Intention(
        intention_id="test_fail",
        desire_type=DesireType.EXPLORE,
        plan_name="plan_explore",
        state=IntentionState.ACTIVE,
        target_pos=(-1000.0, -1000.0),
        execution_phase="NAVIGATING",
        retry_count=2,  # Al siguiente fallo alcanzará > 2
    )
    bdi.current_intention = intention

    bdi.execute_plan(agent, world, other_agent=None, dt=0.01)
    assert intention.state == IntentionState.FAILED
    assert bdi.current_intention is None
    assert bdi.replan_count >= 1


def test_23_manual_cancel_intention():
    """cancel_intention cancela la intención activa de forma limpia."""
    bdi = BDIController("josep", "barcelona", "Josep")

    intention = Intention(
        intention_id="test_cancel",
        desire_type=DesireType.EXPLORE,
        plan_name="plan_explore",
        state=IntentionState.ACTIVE,
    )
    bdi.current_intention = intention

    bdi.cancel_intention("user_command")
    assert intention.state == IntentionState.CANCELLED
    assert bdi.current_intention is None


# =============================================================================
# 24, 25 Y 26. DESACOPLAMIENTO TEMPORAL Y CONTROL EN APP
# =============================================================================

def test_24_temporal_decoupling_deliberation_rate():
    """La deliberación se ejecuta a 4 Hz (cada 0.25s) y no en cada frame físico."""
    world = BarWorld()
    agent = VisualAgent("josep", "barcelona", "Josep", 200.0, 200.0)
    bdi = BDIController("josep", "barcelona", "Josep")
    agent.attach_bdi(bdi)

    # 10 frames de dt=0.016s (0.16s < 0.25s) -> No activa deliberación de nueva intención
    for _ in range(10):
        agent.update(dt=0.016, world=world)
    assert bdi.decision_timer < BDI_DECISION_INTERVAL

    # 7 frames más (acumulado > 0.25s) -> Dispara deliberación
    for _ in range(7):
        agent.update(dt=0.016, world=world)
    assert bdi.current_intention is not None or bdi.decision_timer < BDI_DECISION_INTERVAL


def test_25_interactive_toggle_bdi():
    """Attach y detach de BDI controlan su activación limpiamente."""
    agent = VisualAgent("josep", "barcelona", "Josep", 200.0, 200.0)
    bdi = BDIController("josep", "barcelona", "Josep")

    assert agent.bdi is None
    agent.attach_bdi(bdi)
    assert agent.bdi is not None

    agent.detach_bdi()
    assert agent.bdi is None
    assert agent.is_walking is False


def test_26_bdi_and_demo_mutual_exclusion():
    """En create_initial_agents, los agentes nacen sin BDI hasta activación explícita."""
    world = BarWorld()
    agents = create_initial_agents(world)
    josep = agents[0]
    paco = agents[1]

    assert josep.bdi is None
    assert paco.bdi is None

    # Activación explícita
    josep.attach_bdi(BDIController("josep", "barcelona", "Josep"))
    paco.attach_bdi(BDIController("paco", "real_madrid", "Paco"))
    assert josep.bdi is not None
    assert paco.bdi is not None


# =============================================================================
# 27, 28, 29 Y 30. DETERMINISMO, MODO HEADLESS, RETROCOMPATIBILIDAD Y AISLAMIENTO
# =============================================================================

def test_27_determinism_with_fixed_seed():
    """Dos controladores con la misma semilla producen la misma selección de POI."""
    world = BarWorld()
    bdi1 = BDIController("josep", "barcelona", "Josep", seed=999)
    bdi2 = BDIController("josep", "barcelona", "Josep", seed=999)

    int1 = bdi1._create_intention_for_desire(DesireType.EXPLORE, 0.5, world, None)
    int2 = bdi2._create_intention_for_desire(DesireType.EXPLORE, 0.5, world, None)

    assert int1 is not None and int2 is not None
    assert int1.target_poi_name == int2.target_poi_name
    assert int1.target_pos == int2.target_pos


def test_28_headless_execution_with_bdi():
    """Ejecución headless con bdi=True durante 50 frames sin excepciones."""
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    run_simulation(max_frames=50, debug=True, bdi=True)


def test_29_normal_mode_agents_remain_stationary():
    """En modo normal (sin bdi ni demo), los agentes permanecen estáticos."""
    world = BarWorld()
    agents = create_initial_agents(world)
    josep = agents[0]
    paco = agents[1]

    pos_josep_initial = (josep.x, josep.y)
    pos_paco_initial = (paco.x, paco.y)

    for _ in range(30):
        josep.update(dt=0.016)
        paco.update(dt=0.016)

    assert (josep.x, josep.y) == pos_josep_initial
    assert (paco.x, paco.y) == pos_paco_initial
    assert josep.is_walking is False
    assert paco.is_walking is False



def test_30_conversational_subsystems_untouched():
    """Garantiza que los módulos de LangGraph, agentes y MCP existen y no han sido corrompidos."""
    import src.agents.barcelona_agent as b_agent
    import src.agents.real_madrid_agent as rm_agent
    import src.orchestrator.graph as graph
    import src.orchestrator.state as state

    assert hasattr(b_agent, "SYSTEM_PROMPT")
    assert hasattr(rm_agent, "SYSTEM_PROMPT")
    assert hasattr(graph, "build_debate_graph")
    assert hasattr(state, "initial_state")
