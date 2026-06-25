# V4 Branch Alignment - 2026-06-19

## Situacion
La ejecucion previa ocurrio en la rama `portal-first-national-inventory`.
El Plan Maestro V4 (Bloque 0.2) exige la rama `feature/discovery-pipeline`.
Esta rama fue creada el 2026-06-19 desde `portal-first-national-inventory`
despues de aprobar el diff de alcance documentado en V4_SCOPE_CORRECTION_REPORT.

## Que trae esta rama
- Skeleton V4 de paquetes: compliance/, discovery/, harvest/, changes/,
  matching/, extraction/, validation/, drafts/, storage/
- Tests placeholder de paquetes V4
- runtime_settings.py con gating de LLM y defaults seguros
- .env.example alineado con OpenAI
- requirements.txt con dependencias V4
- docs de gobernanza (README, AGENTS, ARCHITECTURE, ENVIRONMENT, DEPENDENCIES)
  - requieren revision de lenguaje portal-first residual

## Que trae esta rama pero NO es el pipeline V4
Los siguientes artefactos existen en el repo pero quedan clasificados como
legacy/diagnostico. NO deben usarse como base del pipeline V4. Se moveran
a una carpeta legacy/ en un paso posterior con tests verdes:
- scraper/src/domek_wonen/portals/portal_inventory_spike.py
- scraper/src/domek_wonen/portals/huislijn_url_discovery.py
- scraper/src/domek_wonen/portals/huislijn_inventory_spike.py
- scraper/src/domek_wonen/portals/adapters/huislijn.py
- scraper/src/domek_wonen/portals/adapters/funda.py
- scraper/src/domek_wonen/portals/adapters/pararius.py
- scripts/run_portal_inventory_spike.py
- scripts/run_huislijn_url_discovery.py
- scripts/run_huislijn_inventory_spike.py
- scraper/src/domek_wonen/properties/property_discovery_engine.py
- scripts/run_property_discovery.py
- tests/test_portal_inventory_spike.py
- tests/test_huislijn_url_discovery.py
- tests asociados a huislijn_inventory_spike

## Regla operativa desde este punto
Todo el trabajo nuevo del pipeline V4 ocurre en `feature/discovery-pipeline`.
Nunca mas en `portal-first-national-inventory`.

## Proximo paso
Bloque 1A.1 - Compliance Gate minimo (robots_gate.py).
NO entrar al Bloque 1A.1 hasta que Andres apruebe este documento de
alineacion de rama.

## Artefactos legacy - accion pendiente
El movimiento real a legacy/ se hace en el Bloque 0 (paso pendiente),
SOLO despues de verificar que ningun modulo del pipeline nuevo los importa
y con tests verdes confirmados.
