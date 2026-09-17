"""Publicacion del debate en redes sociales.

Responsabilidad del Dev Harold: este paquete consume el debate ya
generado por `src/orchestrator/` (no reimplementa logica de turnos) y lo
publica en una red social externa.

Arquitectura: `DebatePublisher` (`base.py`) define el contrato comun;
cada red social es una implementacion en su propio modulo, registrada en
`registry.py`. Agregar una red social nueva no requiere tocar el CLI ni
el orquestador.
"""
