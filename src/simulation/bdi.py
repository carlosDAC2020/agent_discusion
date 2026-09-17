"""Módulo de Arquitectura BDI (Beliefs - Desires - Intentions) local para los agentes del Bar.

Responsabilidades:
1. Creencias (Beliefs): Estado interno explícito, tipado y serializable, percibido del mundo físico.
2. Deseos (Desires): Objetivos potenciales (Beber, Descansar, Explorar, Socializar, Recuperarse de error).
3. Intenciones (Intentions): Compromiso activo del agente con un plan concreto y persistente.
4. Personalidades diferenciadas: Preferencias locales y no conversacionales para Josep y Paco.
5. Prevención de oscilaciones: Duración mínima de intención, umbral de preempción y cooldowns.
6. Interacción espacial: Respeto de distancia social e inhibición de superposiciones.
7. Frecuencia de decisión limitada: El ciclo deliberativo se ejecuta a frecuencia fija (4 Hz por defecto),
   desacoplado del framerate de renderizado de Pygame.
"""

from dataclasses import asdict, dataclass, field
from enum import Enum
import math
import random
from typing import Any, Dict, List, Optional, Tuple

from src.simulation.config import (
    BDI_DECISION_FREQUENCY,
    BDI_DECISION_INTERVAL,
    BDI_DEFAULT_SEED,
    BDI_DESIRE_COOLDOWN,
    BDI_DRINK_DURATION,
    BDI_ENERGY_DECAY_RATE,
    BDI_ENERGY_RECOVERY_AMOUNT,
    BDI_EXPLORE_DURATION,
    BDI_INITIAL_ENERGY,
    BDI_INITIAL_SOCIABILITY,
    BDI_INITIAL_THIRST,
    BDI_MAX_SOCIAL_DISTANCE,
    BDI_MIN_INTENTION_DURATION,
    BDI_MIN_SOCIAL_DISTANCE,
    BDI_REST_DURATION,
    BDI_SOCIALIZE_DURATION,
    BDI_SOCIABILITY_GROWTH_RATE,
    BDI_SOCIABILITY_SATISFY_AMOUNT,
    BDI_THIRST_GROWTH_RATE,
    BDI_THIRST_QUENCH_AMOUNT,
    BDI_UTILITY_PREEMPT_THRESHOLD,
    DIALOGUE_POST_COOLDOWN,
    TILE_SIZE,
)

from src.simulation.navigation import cell_to_pos, find_nearest_walkable_cell, pos_to_cell
from src.simulation.world import BarWorld


# =============================================================================
# 1. MODELO DE CREENCIAS (BELIEFS)
# =============================================================================

@dataclass
class AgentBeliefs:
    """Modelo explícito, tipado y serializable de las creencias del agente sobre sí mismo y el entorno."""

    agent_id: str
    team: str
    name: str

    # Estado espacial percibido
    x: float = 0.0
    y: float = 0.0
    col: int = 0
    row: int = 0
    facing: str = "down"
    speed: float = 0.0
    is_navigating: bool = False

    # Percepción de puntos de interés
    is_at_poi: bool = False
    current_poi_name: Optional[str] = None

    # Percepción del rival / otro agente
    other_agent_id: Optional[str] = None
    other_agent_pos: Optional[Tuple[float, float]] = None
    other_agent_cell: Optional[Tuple[int, int]] = None
    other_agent_distance: float = float("inf")
    other_agent_visible: bool = False

    # Necesidades internas normalizadas [0.0 = mínimo, 1.0 = máximo]
    # Energía: 1.0 = descansado al 100%, 0.0 = agotado físicamente
    energy: float = BDI_INITIAL_ENERGY
    # Sed: 0.0 = saciado, 1.0 = sed extrema (requiere ir a la barra)
    thirst: float = BDI_INITIAL_THIRST
    # Sociabilidad: 0.0 = necesidad social satisfecha, 1.0 = deseo alto de aproximación
    sociability: float = BDI_INITIAL_SOCIABILITY

    # Temporizadores y telemetría cognitiva
    time_since_last_interaction: float = 0.0
    time_since_last_decision: float = 0.0
    simulation_mode: str = "bdi"
    conversation_active: bool = False  # Reservado para fase posterior
    has_navigation_error: bool = False
    last_navigation_error: Optional[str] = None
    last_intention_result: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serializa las creencias a un diccionario estructurado para inspección o telemetría."""
        return asdict(self)

    def clamp_needs(self) -> None:
        """Asegura que los valores de necesidades se mantengan estrictamente en [0.0, 1.0]."""
        self.energy = max(0.0, min(1.0, float(self.energy)))
        self.thirst = max(0.0, min(1.0, float(self.thirst)))
        self.sociability = max(0.0, min(1.0, float(self.sociability)))


# =============================================================================
# 2. MODELO DE DESEOS (DESIRES) Y PERSONALIDADES
# =============================================================================

class DesireType(str, Enum):
    """Tipos de deseos u objetivos posibles en el bar."""
    DRINK = "DRINK"            # Ir a la barra a saciar la sed
    REST = "REST"              # Sentarse en mesa o sofá a recuperar energía
    EXPLORE = "EXPLORE"        # Inspeccionar zonas del bar según personalidad
    SOCIALIZE = "SOCIALIZE"    # Acercarse al otro agente manteniendo distancia social
    RECOVER = "RECOVER"        # Recuperarse de un atasco o error de navegación


@dataclass
class Desire:
    """Representa un deseo candidato evaluado en cada ciclo de deliberación."""
    desire_type: DesireType
    intensity: float = 0.0      # Intensidad/utilidad calculada [0.0 a 1.0+]
    priority: float = 1.0
    cooldown_timer: float = 0.0  # Temporizador activo de cooldown


@dataclass
class AgentPersonality:
    """Perfil comportamental local que diferencia las preferencias espaciales de cada agente."""
    bar_affinity: float         # Afinidad por la barra y taburetes
    tv_affinity: float          # Afinidad por la zona deportiva y TV
    explore_affinity: float     # Tendencia general a explorar mesas
    sociability_affinity: float # Tendencia a buscar proximidad social
    preferred_pois: List[str]   # POIs de mayor predilección individual


def create_josep_personality() -> AgentPersonality:
    """Josep (Barça): Disfruta de la barra para su caña, de charlar en las mesas centrales y ver el fútbol."""
    return AgentPersonality(
        bar_affinity=0.70,
        tv_affinity=0.60,
        explore_affinity=0.65,
        sociability_affinity=0.70,
        preferred_pois=[
            "bar_stool_1",
            "bar_stool_2",
            "bar_stool_3",
            "table_central_1_seat_west",
            "table_central_2_seat_west",
            "tv_lounge_seat_22",
            "barcelona_spawn",
        ],
    )


def create_paco_personality() -> AgentPersonality:
    """Paco (Real Madrid): Tertuliano y madridista, disfruta tanto de la barra como de la TV y tertulia."""
    return AgentPersonality(
        bar_affinity=0.70,
        tv_affinity=0.85,
        explore_affinity=0.55,
        sociability_affinity=0.65,
        preferred_pois=[
            "bar_stool_4",
            "bar_stool_5",
            "tv_lounge_seat_22",
            "tv_lounge_seat_23",
            "tv_lounge_seat_24",
            "tv_lounge_seat_25",
            "table_side_1_seat_north",
            "real_madrid_spawn",
        ],
    )



# =============================================================================
# 3. MODELO DE INTENCIONES (INTENTIONS) Y ESTADOS
# =============================================================================

class IntentionState(str, Enum):
    """Estados del ciclo de vida de una intención activa."""
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    INTERRUPTED = "INTERRUPTED"


@dataclass
class Intention:
    """Intención activa seleccionada por el agente, respaldada por un plan de acción concreto."""
    intention_id: str
    desire_type: DesireType
    plan_name: str
    state: IntentionState = IntentionState.PENDING

    # Metas espaciales
    target_pos: Optional[Tuple[float, float]] = None
    target_poi_name: Optional[str] = None

    # Métrica de compromiso
    priority: float = 1.0
    utility: float = 0.5
    start_time: float = 0.0
    elapsed_time: float = 0.0
    min_duration: float = BDI_MIN_INTENTION_DURATION
    action_timer: float = 0.0
    action_duration: float = 2.0
    retry_count: int = 0
    completion_reason: Optional[str] = None
    cooldown: float = BDI_DESIRE_COOLDOWN

    # Fase interna de ejecución del plan: "NAVIGATING", "ACTION", "FINISHED"
    execution_phase: str = "NAVIGATING"


# =============================================================================
# 4. CONTROLADOR BDI Y CICLO COGNITIVO
# =============================================================================

class BDIController:
    """Controlador cognitivo desacoplado que gobierna el ciclo de deliberación y ejecución BDI."""

    def __init__(
        self,
        agent_id: str,
        team: str,
        name: str,
        personality: Optional[AgentPersonality] = None,
        seed: Optional[int] = None,
    ):
        self.agent_id: str = agent_id
        self.team: str = team
        self.name: str = name

        # Personalidad
        if personality is not None:
            self.personality: AgentPersonality = personality
        elif team == "barcelona":
            self.personality = create_josep_personality()
        else:
            self.personality = create_paco_personality()

        # Generador pseudoaleatorio determinista con semilla fija
        used_seed = BDI_DEFAULT_SEED if seed is None else seed
        if team == "real_madrid":
            used_seed += 100
        self.random: random.Random = random.Random(used_seed)

        # Creencias
        self.beliefs: AgentBeliefs = AgentBeliefs(
            agent_id=agent_id,
            team=team,
            name=name,
        )

        # Diccionario de deseos
        self.desires: Dict[DesireType, Desire] = {
            d_type: Desire(desire_type=d_type) for d_type in DesireType
        }

        # Intención actualmente en curso
        self.current_intention: Optional[Intention] = None

        # Adaptador de diálogo opcional para debates reales (Fase 5)
        self.dialogue_adapter: Optional[Any] = None

        # Bloqueo de deliberación durante tertulia/debate activo
        self.is_locked: bool = False
        self.is_conversation_locked: bool = False

        # Temporizador de control para la frecuencia de decisión (4 Hz)

        self.decision_timer: float = 0.0
        self.decision_interval: float = BDI_DECISION_INTERVAL
        self.intention_counter: int = 0
        self.replan_count: int = 0

        # Historial de POIs visitados para evitar oscilación en bucle inmediato
        self.recent_pois: List[str] = []

    def lock_for_conversation(self, plan_name: str = "DEBATE_AT_BAR") -> None:
        """Bloquea deliberación y selección de intenciones durante un debate."""
        self.is_locked = True
        self.is_conversation_locked = True

    def release_conversation_lock(self) -> None:
        """Libera el bloqueo de conversación permitiendo al BDI deliberar de nuevo."""
        self.is_locked = False
        self.is_conversation_locked = False
        if self.current_intention and self.current_intention.plan_name == "DEBATE_AT_BAR":
            self.current_intention.state = IntentionState.COMPLETED
            self.current_intention = None

    def command_debate_at_bar(self, agent: Any, world: BarWorld, poi_name: str) -> None:
        """Ordena navegación hacia el POI semántico de debate en la barra y bloquea deliberación."""
        poi = world.pois.get(poi_name)
        if not poi:
            return
        self.lock_for_conversation("DEBATE_AT_BAR")
        agent.is_conversation_locked = True
        self.intention_counter += 1
        intention = Intention(
            intention_id=f"intent_{self.intention_counter}_debate",
            desire_type=DesireType.SOCIALIZE,
            plan_name="DEBATE_AT_BAR",
            state=IntentionState.ACTIVE,
            target_pos=(poi.x, poi.y),
            target_poi_name=poi_name,
            priority=2.0,
            action_duration=9999.0,
            execution_phase="NAVIGATING",
        )
        self.current_intention = intention
        agent.navigate_to(world, poi.x, poi.y)

    def attach_dialogue_adapter(self, adapter: Any) -> None:
        """Conecta un adaptador de diálogo para gestionar debates reales con el LLM."""
        self.dialogue_adapter = adapter

    def detach_dialogue_adapter(self) -> None:
        """Desconecta el adaptador de diálogo regresando al modo BDI local."""
        self.dialogue_adapter = None


    # -------------------------------------------------------------------------
    # PASO 1: PERCEPCIÓN DEL MUNDO Y ACTUALIZACIÓN DE CREENCIAS
    # -------------------------------------------------------------------------
    def perceive(
        self,
        agent: Any,
        world: BarWorld,
        other_agent: Optional[Any],
        dt: float,
    ) -> None:
        """Actualiza las creencias basándose en el estado físico del agente y el entorno."""
        b = self.beliefs

        # 1. Posición física y orientación
        b.x = agent.x
        b.y = agent.y
        b.col, b.row = pos_to_cell(agent.x, agent.y)
        b.facing = agent.facing
        b.speed = getattr(agent, "speed", 0.0)
        b.is_navigating = getattr(agent, "is_navigating", False)

        # 2. Detección de POI actual
        b.is_at_poi = False
        b.current_poi_name = None
        for poi_name, poi in world.pois.items():
            dist = math.hypot(agent.x - poi.x, agent.y - poi.y)
            if dist <= 18.0:
                b.is_at_poi = True
                b.current_poi_name = poi_name
                break

        # 3. Percepción del otro agente (rival)
        if other_agent is not None:
            b.other_agent_id = getattr(other_agent, "agent_id", None)
            b.other_agent_pos = (other_agent.x, other_agent.y)
            b.other_agent_cell = pos_to_cell(other_agent.x, other_agent.y)
            b.other_agent_distance = math.hypot(agent.x - other_agent.x, agent.y - other_agent.y)
            b.other_agent_visible = True
        else:
            b.other_agent_id = None
            b.other_agent_pos = None
            b.other_agent_cell = None
            b.other_agent_distance = float("inf")
            b.other_agent_visible = False

        # 4. Evolución temporal de necesidades fisiológicas y sociales
        b.energy -= BDI_ENERGY_DECAY_RATE * dt
        b.thirst += BDI_THIRST_GROWTH_RATE * dt
        b.sociability += BDI_SOCIABILITY_GROWTH_RATE * dt
        b.clamp_needs()

        # 5. Temporizadores
        b.time_since_last_decision += dt
        if b.other_agent_distance <= BDI_MAX_SOCIAL_DISTANCE:
            b.time_since_last_interaction = 0.0
        else:
            b.time_since_last_interaction += dt

        # 6. Comprobación de errores de navegación
        if getattr(agent, "last_path_error", None):
            b.has_navigation_error = True
            b.last_navigation_error = agent.last_path_error
        else:
            b.has_navigation_error = False

    # -------------------------------------------------------------------------
    # PASO 2: EVALUACIÓN DE DESEOS
    # -------------------------------------------------------------------------
    def evaluate_desires(self, dt: float) -> None:
        """Calcula la intensidad o utilidad de cada deseo candidate en función de creencias y personalidad."""
        # Decrementar cooldowns activos
        for d in self.desires.values():
            if d.cooldown_timer > 0.0:
                d.cooldown_timer = max(0.0, d.cooldown_timer - dt)

        b = self.beliefs
        p = self.personality

        # 1. DESEO: RECUPERARSE DE ERROR (Prioridad absoluta de emergencia)
        if b.has_navigation_error:
            self.desires[DesireType.RECOVER].intensity = 1.5
        else:
            self.desires[DesireType.RECOVER].intensity = 0.0

        # 2. DESEO: BEBER (Impulsado por sed + afinidad de barra)
        drink_cd = self.desires[DesireType.DRINK].cooldown_timer
        if drink_cd > 0.0:
            self.desires[DesireType.DRINK].intensity = 0.0
        else:
            thirst_weight = b.thirst ** 1.2
            self.desires[DesireType.DRINK].intensity = (
                thirst_weight * 1.20 + p.bar_affinity * 0.25
            )


        # 3. DESEO: DESCANSAR (Impulsado por fatiga / baja energía + afinidad de asiento/TV)
        rest_cd = self.desires[DesireType.REST].cooldown_timer
        if rest_cd > 0.0:
            self.desires[DesireType.REST].intensity = 0.0
        else:
            fatigue = (1.0 - b.energy) ** 1.5
            # Paco tiene un bono si va a descansar a la zona de TV
            self.desires[DesireType.REST].intensity = (
                fatigue * 1.15 + p.tv_affinity * 0.30
            )

        # 4. DESEO: SOCIALIZAR / ACERCARSE AL OTRO AGENTE
        soc_cd = self.desires[DesireType.SOCIALIZE].cooldown_timer
        if soc_cd > 0.0 or not b.other_agent_visible:
            self.desires[DesireType.SOCIALIZE].intensity = 0.0
        else:
            # Se activa cuando la sociabilidad es moderada y el rival no está ya encima
            if b.other_agent_distance > BDI_MIN_SOCIAL_DISTANCE:
                dialogue_bonus = 0.35 if self.dialogue_adapter is not None else 0.0
                self.desires[DesireType.SOCIALIZE].intensity = (
                    b.sociability * 0.90 + p.sociability_affinity * 0.20 + dialogue_bonus
                )
            else:
                self.desires[DesireType.SOCIALIZE].intensity = 0.10

        # 5. DESEO: EXPLORAR (Deseo por defecto de fondo si no hay urgencias)
        exp_cd = self.desires[DesireType.EXPLORE].cooldown_timer
        if exp_cd > 0.0:
            self.desires[DesireType.EXPLORE].intensity = 0.0
        else:
            self.desires[DesireType.EXPLORE].intensity = 0.35 + p.explore_affinity * 0.25

    # -------------------------------------------------------------------------
    # PASO 3: SELECCIÓN DE INTENCIÓN (PREVENCIÓN DE OSCILACIÓN)
    # -------------------------------------------------------------------------
    def select_intention(self, world: BarWorld, other_agent: Optional[Any]) -> None:
        """Selecciona la mejor intención respetando la persistencia y umbrales de preempción."""
        # 1. Encontrar el deseo de mayor intensidad
        best_type, best_desire = max(
            self.desires.items(), key=lambda item: item[1].intensity
        )

        # 2. Si ya hay una intención activa, evaluar si puede ser interrumpida o debe persistir
        if self.current_intention is not None and self.current_intention.state == IntentionState.ACTIVE:
            # Caso A: Emergencia por error de navegación
            if best_type == DesireType.RECOVER and self.current_intention.desire_type != DesireType.RECOVER:
                self.cancel_intention("navigation_error_preemption")
            # Caso B: Regla de Persistencia mínima de intención (evita oscilaciones rápidas)
            elif self.current_intention.elapsed_time < self.current_intention.min_duration:
                return  # Mantener la intención actual
            # Caso C: Solo reemplazar si el nuevo deseo supera significativamente la utilidad actual
            elif (best_desire.intensity - self.current_intention.utility) < BDI_UTILITY_PREEMPT_THRESHOLD:
                return  # No supera el umbral de preempción
            else:
                self.cancel_intention("preempted_by_higher_utility")

        # 3. Construir nueva intención y plan
        if best_desire.intensity <= 0.05:
            return  # Ningún deseo con suficiente intensidad

        self.intention_counter += 1
        new_int = self._create_intention_for_desire(
            best_type, best_desire.intensity, world, other_agent
        )
        if new_int is not None:
            self.current_intention = new_int
            self.beliefs.time_since_last_decision = 0.0
            from src.simulation.debug_logger import debug_log
            debug_log(
                "BDI",
                "INTENTION_SELECTED",
                f"desire={new_int.desire_type.value}, plan={new_int.plan_name}, target={new_int.target_pos}, utility={new_int.utility:.2f}, rival_dist={self.beliefs.other_agent_distance:.1f}",
                agent_id=self.agent_id,
            )

    def _create_intention_for_desire(
        self,
        desire_type: DesireType,
        utility: float,
        world: BarWorld,
        other_agent: Optional[Any],
    ) -> Optional[Intention]:
        """Genera una intención con destino y duración según el tipo de deseo seleccionado."""
        int_id = f"int_{self.agent_id}_{desire_type.value.lower()}_{self.intention_counter}"

        if desire_type == DesireType.DRINK:
            # Elegir taburete de la barra (bar_stool_1 a bar_stool_5)
            stools = [f"bar_stool_{i}" for i in range(1, 6)]
            # Filtrar el más reciente para variedad
            candidates = [s for s in stools if s not in self.recent_pois[-2:]]
            poi_choice = self.random.choice(candidates if candidates else stools)
            poi = world.get_poi(poi_choice)
            if poi:
                return Intention(
                    intention_id=int_id,
                    desire_type=desire_type,
                    plan_name="plan_drink_at_bar",
                    state=IntentionState.ACTIVE,
                    target_pos=(poi.x, poi.y),
                    target_poi_name=poi_choice,
                    utility=utility,
                    action_duration=BDI_DRINK_DURATION,
                )

        elif desire_type == DesireType.REST:
            # Si es Paco o afín a TV, preferir sofá de TV; de lo contrario sillas de mesas
            if self.personality.tv_affinity > 0.60:
                tv_seats = [f"tv_lounge_seat_{c}" for c in range(22, 27)]
                candidates = [s for s in tv_seats if s not in self.recent_pois[-2:]]
                poi_choice = self.random.choice(candidates if candidates else tv_seats)
            else:
                table_seats = [
                    "table_central_1_seat_west", "table_central_1_seat_east",
                    "table_central_2_seat_west", "table_side_1_seat_north"
                ]
                candidates = [s for s in table_seats if s not in self.recent_pois[-2:]]
                poi_choice = self.random.choice(candidates if candidates else table_seats)

            poi = world.get_poi(poi_choice)
            if poi:
                return Intention(
                    intention_id=int_id,
                    desire_type=desire_type,
                    plan_name="plan_rest_at_seat",
                    state=IntentionState.ACTIVE,
                    target_pos=(poi.x, poi.y),
                    target_poi_name=poi_choice,
                    utility=utility,
                    action_duration=BDI_REST_DURATION,
                )

        elif desire_type == DesireType.EXPLORE:
            # Seleccionar según los preferidos de la personalidad
            prefs = [p for p in self.personality.preferred_pois if p not in self.recent_pois[-3:]]
            if not prefs:
                prefs = self.personality.preferred_pois
            poi_choice = self.random.choice(prefs)
            poi = world.get_poi(poi_choice)
            if poi:
                return Intention(
                    intention_id=int_id,
                    desire_type=desire_type,
                    plan_name="plan_explore_area",
                    state=IntentionState.ACTIVE,
                    target_pos=(poi.x, poi.y),
                    target_poi_name=poi_choice,
                    utility=utility,
                    action_duration=BDI_EXPLORE_DURATION,
                )

        elif desire_type == DesireType.SOCIALIZE:
            if other_agent is not None:
                # Buscar una celda transitable adyacente al rival que respete MIN_SOCIAL_DISTANCE
                target_xy = self._find_social_position_near(other_agent, world)
                if target_xy:
                    return Intention(
                        intention_id=int_id,
                        desire_type=desire_type,
                        plan_name="plan_approach_rival",
                        state=IntentionState.ACTIVE,
                        target_pos=target_xy,
                        target_poi_name="social_spot",
                        utility=utility,
                        action_duration=BDI_SOCIALIZE_DURATION,
                        cooldown=DIALOGUE_POST_COOLDOWN,
                    )


        elif desire_type == DesireType.RECOVER:
            # Cancelar y retirarse al spawn personal
            spawn_name = f"{self.team}_spawn"
            poi = world.get_poi(spawn_name)
            target = (poi.x, poi.y) if poi else (208.0, 240.0)
            return Intention(
                intention_id=int_id,
                desire_type=desire_type,
                plan_name="plan_recover_error",
                state=IntentionState.ACTIVE,
                target_pos=target,
                target_poi_name=spawn_name,
                utility=1.5,
                action_duration=1.0,
            )

        return None

    def _find_social_position_near(
        self, other_agent: Any, world: BarWorld
    ) -> Optional[Tuple[float, float]]:
        """Encuentra una celda transitable que mantenga la distancia social y no solape con el rival."""
        from src.simulation.debug_logger import debug_log

        dist = math.hypot(self.beliefs.x - other_agent.x, self.beliefs.y - other_agent.y)
        debug_log(
            "BDI_SPATIAL",
            "EVALUATING_SOCIAL_POSITION",
            f"my_pos=({self.beliefs.x:.1f}, {self.beliefs.y:.1f}), rival_pos=({other_agent.x:.1f}, {other_agent.y:.1f}), current_dist={dist:.1f}, min_range={BDI_MIN_SOCIAL_DISTANCE}, max_range={BDI_MAX_SOCIAL_DISTANCE}",
            agent_id=self.agent_id,
        )

        oc, orow = pos_to_cell(other_agent.x, other_agent.y)
        # Buscar en un radio de 2 a 3 celdas (~64px a 96px)
        best_pos = None
        best_score = float("inf")

        for dr in (-3, -2, -1, 0, 1, 2, 3):
            for dc in (-3, -2, -1, 0, 1, 2, 3):
                if dc == 0 and dr == 0:
                    continue  # Nunca la misma celda
                nc, nr = oc + dc, orow + dr
                if world.is_tile_walkable(nc, nr):
                    cand_x, cand_y = cell_to_pos(nc, nr)
                    dist = math.hypot(cand_x - other_agent.x, cand_y - other_agent.y)
                    if (BDI_MIN_SOCIAL_DISTANCE - 4.0) <= dist <= (BDI_MAX_SOCIAL_DISTANCE + 4.0):
                        # Evaluar cercanía a la posición actual del agente
                        my_dist = math.hypot(cand_x - self.beliefs.x, cand_y - self.beliefs.y)
                        if my_dist < best_score:
                            best_score = my_dist
                            best_pos = (cand_x, cand_y)

        debug_log(
            "BDI_SPATIAL",
            "SOCIAL_POSITION_RESULT",
            f"found_pos={best_pos}",
            agent_id=self.agent_id,
        )
        return best_pos

    # -------------------------------------------------------------------------
    # PASO 4: EJECUCIÓN DEL PLAN Y PROGRESO
    # -------------------------------------------------------------------------
    def execute_plan(
        self,
        agent: Any,
        world: BarWorld,
        other_agent: Optional[Any],
        dt: float,
    ) -> None:
        """Avanza la ejecución del plan de la intención activa."""
        if self.current_intention is None or self.current_intention.state != IntentionState.ACTIVE:
            return

        cur = self.current_intention
        cur.elapsed_time += dt

        # FASE 1: NAVEGACIÓN HACIA EL DESTINO
        if cur.execution_phase == "NAVIGATING":
            # Si el agente aún no está navegando y tiene destino, ordenar navegación
            if not agent.is_navigating and cur.target_pos is not None:
                # Comprobar si ya estamos en el destino
                dist_to_target = math.hypot(agent.x - cur.target_pos[0], agent.y - cur.target_pos[1])
                if dist_to_target <= 16.0:
                    cur.execution_phase = "ACTION"
                    cur.action_timer = 0.0
                else:
                    # Iniciar navegación con el sistema A* existente
                    res = agent.navigate_to(world, cur.target_pos[0], cur.target_pos[1])
                    if not res.success:
                        # Fallo de ruta -> Replanificar o abortar
                        cur.retry_count += 1
                        self.replan_count += 1
                        if cur.retry_count > 2:
                            self._fail_intention("pathfinding_failed")
                        return

            # Si ya terminó de navegar en este frame
            if not agent.is_navigating and cur.target_pos is not None:
                dist_to_target = math.hypot(agent.x - cur.target_pos[0], agent.y - cur.target_pos[1])
                if dist_to_target <= 20.0:
                    if cur.desire_type == DesireType.SOCIALIZE and other_agent:
                        dist_to_rival = math.hypot(agent.x - other_agent.x, agent.y - other_agent.y)
                        if dist_to_rival > (BDI_MAX_SOCIAL_DISTANCE + 20.0):
                            new_spot = self._find_social_position_near(other_agent, world)
                            if new_spot:
                                cur.target_pos = new_spot
                                agent.navigate_to(world, new_spot[0], new_spot[1])
                                return
                    cur.execution_phase = "ACTION"
                    cur.action_timer = 0.0

        # FASE 2: REALIZAR ACCIÓN EN EL DESTINO (espera, consumo, descanso)
        elif cur.execution_phase == "ACTION":
            cur.action_timer += dt

            # Orientación situacional y animación durante la acción
            if cur.desire_type == DesireType.DRINK:
                agent.set_facing("left")  # Mirar hacia la barra
                if hasattr(agent, "sit"):
                    agent.sit(True)
                # En el primer instante pide su trago
                if cur.action_timer < 0.35 and not getattr(agent, "active_bubble_text", None):
                    if hasattr(agent, "say"):
                        agent.say("¡Manolo, una cañita bien fría!")
                # Pasado un segundo, Manolo ya le ha servido y empieza a beber
                elif cur.action_timer >= 1.0:
                    if hasattr(agent, "drink") and not agent.is_drinking:
                        agent.drink(True)


            elif cur.desire_type == DesireType.REST:
                if self.personality.tv_affinity > 0.6:
                    agent.set_facing("up")    # Mirar hacia el televisor
                if hasattr(agent, "sit"):
                    agent.sit(True)
                if cur.action_timer < 0.35 and not getattr(agent, "active_bubble_text", None):
                    if hasattr(agent, "say"):
                        if self.team == "barcelona":
                            agent.say("Un descansito merecido...")
                        else:
                            agent.say("A descansar y ver el partido.")

            elif cur.desire_type == DesireType.SOCIALIZE and other_agent:
                from src.simulation.debug_logger import debug_log, debug_log_state

                dist_now = math.hypot(agent.x - other_agent.x, agent.y - other_agent.y)
                # Mirar hacia el otro agente cara a cara
                dx = other_agent.x - agent.x
                agent.set_facing("right" if dx > 0 else "left")
                if hasattr(other_agent, "set_facing"):
                    other_agent.set_facing("left" if dx > 0 else "right")

                in_social_range = (dist_now <= BDI_MAX_SOCIAL_DISTANCE + 16.0)
                both_stopped = (not agent.is_navigating and not other_agent.is_navigating)

                debug_log_state(
                    f"{self.agent_id}_social_action",
                    (
                        f"timer_{int(cur.action_timer * 10)}",
                        f"busy_{self.dialogue_adapter.is_busy() if self.dialogue_adapter else False}",
                        f"range_{in_social_range}",
                        f"stop_{both_stopped}",
                    ),
                    "BDI_SOCIALIZE",
                    "ACTION_TICK",
                    f"action_timer={cur.action_timer:.2f}, dist={dist_now:.1f}, in_range={in_social_range}, both_stopped={both_stopped}, facing=({agent.facing}, {other_agent.facing}), adapter_busy={self.dialogue_adapter.is_busy() if self.dialogue_adapter else False}",
                    agent_id=self.agent_id,
                )

                # Si hay un adaptador de diálogo real conectado
                if self.dialogue_adapter is not None:
                    # Si el rival se encuentra demasiado lejos, volver a navegar hacia él
                    if not in_social_range and dist_now > (BDI_MAX_SOCIAL_DISTANCE + 24.0):
                        cur.execution_phase = "NAVIGATING"
                        cur.action_timer = 0.0
                        new_spot = self._find_social_position_near(other_agent, world)
                        if new_spot:
                            cur.target_pos = new_spot
                            agent.navigate_to(world, new_spot[0], new_spot[1])
                        return

                    if not self.dialogue_adapter.is_busy():
                        if in_social_range and both_stopped:
                            if cur.action_timer < 0.35:
                                debug_log(
                                    "BDI_SOCIALIZE",
                                    "REQUESTING_CONVERSATION",
                                    f"initiator={agent.team}, receiver={other_agent.team}, action_timer={cur.action_timer:.3f}, dist={dist_now:.1f}, in_range={in_social_range}, both_stopped={both_stopped}",
                                    agent_id=self.agent_id,
                                )
                                req_result = self.dialogue_adapter.request_conversation(
                                    initiator_team=agent.team,
                                    receiver_team=other_agent.team,
                                )
                                debug_log(
                                    "BDI_SOCIALIZE",
                                    "REQUEST_CONVERSATION_RETURNED",
                                    f"accepted={req_result is not None}, conv_id={req_result.conversation_id if req_result else None}",
                                    agent_id=self.agent_id,
                                )
                        elif not in_social_range or not both_stopped:
                            # Esperar a que el rival se aproxime y se detenga
                            cur.action_timer = 0.05
                    # Mantener a los agentes debatiendo mientras el adaptador esté ocupado
                    if self.dialogue_adapter.is_busy():
                        cur.action_timer = 0.5
                    elif cur.action_timer > 0.4:
                        # Debate completado en el adaptador
                        debug_log(
                            "BDI_SOCIALIZE",
                            "DEBATE_FINISHED_COMPLETING_INTENTION",
                            "adapter is no longer busy",
                            agent_id=self.agent_id,
                        )
                        self._complete_intention(agent)
                        return
                else:
                    debug_log(
                        "BDI_SOCIALIZE",
                        "NO_ADAPTER_ATTACHED",
                        "dialogue_adapter is None, using fallback local phrases",
                        agent_id=self.agent_id,
                    )
                    # Sin adaptador (modo BDI puramente local sin LLM)
                    if cur.action_timer < 0.35 and not getattr(agent, "active_bubble_text", None):
                        if hasattr(agent, "say"):
                            if self.team == "barcelona":
                                agent.say("—¡Hola Paco! ¿Cómo ves al Barça hoy?")
                            else:
                                agent.say("—¡Qué tal Josep! Todo listo para debatir.")


            elif cur.desire_type == DesireType.EXPLORE:
                # Si está cerca de la esquina de Don Antonio (X > 720, Y > 480)
                if agent.x >= 720.0 and agent.y >= 480.0:
                    if cur.action_timer < 0.35 and not getattr(agent, "active_bubble_text", None):
                        if hasattr(agent, "say"):
                            if self.team == "barcelona":
                                agent.say("—¿Tot bé, Don Antonio? ¿Li cal aigua?")
                            else:
                                agent.say("—¿Se encuentra bien, Don Antonio?")

            # Cuando se cumple la duración de la acción
            if cur.action_timer >= cur.action_duration:
                self._complete_intention(agent)

    def _complete_intention(self, agent: Any) -> None:
        """Aplica los efectos de satisfacción sobre las necesidades y cierra la intención con éxito."""
        if self.current_intention is None:
            return

        cur = self.current_intention
        cur.state = IntentionState.COMPLETED
        cur.completion_reason = "action_finished_successfully"
        self.beliefs.last_intention_result = f"COMPLETED ({cur.plan_name})"

        # Limpiar estados visuales de sentado o bebida
        if hasattr(agent, "sit") and agent.is_sitting:
            agent.sit(False)
        if hasattr(agent, "drink") and agent.is_drinking:
            if hasattr(agent, "say"):
                agent.say("¡Ahhh, qué bien entra! Gracias.")
            agent.drink(False)

        # Aplicar efectos sobre las creencias según el deseo satisfecho
        if cur.desire_type == DesireType.DRINK:
            self.beliefs.thirst = max(0.0, self.beliefs.thirst - BDI_THIRST_QUENCH_AMOUNT)
        elif cur.desire_type == DesireType.REST:
            self.beliefs.energy = min(1.0, self.beliefs.energy + BDI_ENERGY_RECOVERY_AMOUNT)
        elif cur.desire_type == DesireType.SOCIALIZE:
            self.beliefs.sociability = max(0.0, self.beliefs.sociability - BDI_SOCIABILITY_SATISFY_AMOUNT)
        elif cur.desire_type == DesireType.EXPLORE:
            self.beliefs.sociability = min(1.0, self.beliefs.sociability + 0.10)
        elif cur.desire_type == DesireType.RECOVER:
            self.beliefs.has_navigation_error = False
            self.beliefs.last_navigation_error = None

        self.beliefs.clamp_needs()

        # Activar cooldown en el deseo satisfecho
        if cur.desire_type in self.desires:
            self.desires[cur.desire_type].cooldown_timer = cur.cooldown

        # Registrar en el historial de POIs para evitar repeticiones consecutivas
        if cur.target_poi_name:
            self.recent_pois.append(cur.target_poi_name)
            if len(self.recent_pois) > 6:
                self.recent_pois.pop(0)

        self.current_intention = None

    def _fail_intention(self, reason: str) -> None:
        """Marca la intención como fallida y libera el compromiso."""
        if self.current_intention is None:
            return
        self.current_intention.state = IntentionState.FAILED
        self.current_intention.completion_reason = reason
        self.beliefs.last_intention_result = f"FAILED ({reason})"
        self.current_intention = None

    def cancel_intention(self, reason: str) -> None:
        """Cancela la intención activa de forma controlada."""
        if self.current_intention is not None and self.current_intention.state == IntentionState.ACTIVE:
            self.current_intention.state = IntentionState.CANCELLED
            self.current_intention.completion_reason = reason
            self.beliefs.last_intention_result = f"CANCELLED ({reason})"
            self.current_intention = None

    # -------------------------------------------------------------------------
    # PASO 5: BUCLE PRINCIPAL DEL CONTROLADOR (update con limitador 4 Hz)
    # -------------------------------------------------------------------------
    def update(
        self,
        agent: Any,
        world: BarWorld,
        other_agent: Optional[Any],
        dt: float,
    ) -> None:
        """Ejecuta el ciclo completo BDI periódicamente respetando la frecuencia de decisión."""
        # 1. Percepción física en cada paso para mantener la telemetría al día
        self.perceive(agent, world, other_agent, dt)

        # Si el controlador está bloqueado por debate activo, no evaluar otros deseos
        if self.is_locked:
            if self.current_intention and self.current_intention.plan_name == "DEBATE_AT_BAR":
                if not agent.is_navigating and self.current_intention.execution_phase == "NAVIGATING":
                    self.current_intention.execution_phase = "ACTION"
            return

        # 2. Control de frecuencia deliberativa (ejecuta razonamiento cada 0.25 segundos)
        self.decision_timer += dt
        if self.decision_timer >= self.decision_interval:
            self.decision_timer = 0.0
            self.evaluate_desires(self.decision_interval)
            self.select_intention(world, other_agent)

        # 3. Avance de la ejecución del plan activo
        self.execute_plan(agent, world, other_agent, dt)
