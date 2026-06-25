# Phase 1.2 Implementation Plan - 2026-06-19

## Objetivo

Proponer la implementacion minima de Fase 1.2 para ejecutar un Discovery Census / Portal Inventory Spike Huislijn-only, sin tocar todavia codigo funcional en esta tarea.

## Principios de implementacion

- Reusar antes que duplicar
- Huislijn-only para el camino operativo de Fase 1
- Sin OpenAI
- Sin Funda/Pararius operativos
- Sin Playwright
- Sin `data/raw`
- Sin commits de outputs generados
- Sin tocar `property_discovery_engine`

## Comando CLI propuesto

Opcion preferida:

```powershell
py -3.12 scripts/run_huislijn_inventory_spike.py --cities Tilburg "'s-Hertogenbosch" Eindhoven Breda Waalwijk --max-pages 2 --max-requests-per-city 2 --delay-seconds 3 --timeout-seconds 20 --output-dir data/diagnostics/portal_inventory/<run_id>
```

Si se decide no crear un CLI nuevo, segunda opcion:

- extender un wrapper Huislijn-only nuevo que reutilice `live_fetch.py`, `adapters/huislijn.py`, y `portal_inventory_spike.py`
- evitar ampliar `scripts/run_portal_inventory_spike.py` como CLI principal porque hoy mezcla portales benchmark-only

## Archivos probables a crear o modificar

### Opcion recomendada

- crear `scripts/run_huislijn_inventory_spike.py`
- crear `tests/test_run_huislijn_inventory_spike.py`
- modificar `scraper/src/domek_wonen/portals/portal_inventory_spike.py`
- modificar `scraper/src/domek_wonen/portals/adapters/huislijn.py` solo si hace falta exponer mejor el parser o la URL builder

### Opcion conservadora

- crear `scraper/src/domek_wonen/portals/huislijn_inventory_spike.py`
- crear `scripts/run_huislijn_inventory_spike.py`
- crear `tests/test_huislijn_inventory_spike.py`

## Archivos a NO tocar

- `scraper/src/domek_wonen/properties/property_discovery_engine.py`
- `scripts/run_property_discovery.py`
- `data/raw/`
- adapters o rutas operativas de Funda/Pararius
- `matching/`
- `drafts/`
- `recommendations/`
- `woning_scanner/`

## Reutilizacion exacta recomendada

| Componente | Reuso propuesto | Motivo |
| --- | --- | --- |
| `portals/live_fetch.py` | usar tal cual | ya resuelve fetch bounded y status mapping |
| `portals/huislijn_url_discovery.py` | reutilizar para gate previo de URL discovery | evita inventar URL patterns nuevas sin evidencia |
| `portals/adapters/huislijn.py` | reutilizar parser y search URL | ya existe parser HTML barato |
| `portals/models/listing.py` | reutilizar enums y modelos base | evita duplicar contratos de estado |
| `portals/portal_inventory_spike.py` | reutilizar fill rate, dedupe y writer utilities | ya produce resumen util |

## Request budget inicial recomendado

- `max_requests` para URL discovery: `10`
- `max_requests_per_city` para inventory spike: `2`
- `max_pages` por ciudad: `2`
- delay live: `3` segundos
- timeout: `20` segundos

Presupuesto piloto estimado:

- 5 ciudades x 2 pages = 10 requests de inventory
- mas hasta 10 requests del URL discovery si se ejecuta como gate previo
- total inicial recomendado: `20` requests o menos por ciclo de validacion tecnica

## Output esperado

### Archivos live generados

- `phase_1_inventory_report.md`
- `phase_1_city_summary.csv`
- `phase_1_listing_sample.csv` o `phase_1_inventory_sample.csv`
- opcional `phase_1_summary.json`

### Campos minimos del summary

- `run_id`
- `generated_at`
- `city`
- `source_name`
- `source_url`
- `source_status`
- `http_status`
- `requests_used`
- `listing_count`
- `unique_listing_url_count`
- `duplicate_url_rate`
- `fields_available_without_llm`
- `sample_listing_urls`
- `blocker_reason`
- `recommendation`

## Tests probables a crear

- test de CLI Huislijn-only con sample HTML local y sin red real
- test de request budget por ciudad
- test de stop temprano en `403`, `429`, CAPTCHA, `permission_required`
- test de contrato de salida del city summary
- test de `sample_listing_urls` truncado a maximo 5
- test de `fields_available_without_llm`
- test de `safe_to_compare_removals=false` cuando el status no es `success`

## Ejemplo de ejecucion segura

Preflight de tests:

```powershell
$stamp = Get-Date -Format "yyyyMMddHHmmss"
$pytestCache = Join-Path $env:TEMP "domek_wonen_pytest_cache_$stamp"
$pytestBase = Join-Path $env:TEMP "domek_wonen_pytest_base_$stamp"
py -3.12 -m pytest -o cache_dir=$pytestCache --basetemp=$pytestBase
```

Gate de URL discovery:

```powershell
py -3.12 scripts/run_huislijn_url_discovery.py --cities Tilburg "'s-Hertogenbosch" Eindhoven Breda Waalwijk --max-requests 10 --delay-seconds 3
```

Spike Huislijn-only:

```powershell
py -3.12 scripts/run_huislijn_inventory_spike.py --cities Tilburg "'s-Hertogenbosch" Eindhoven Breda Waalwijk --max-pages 2 --max-requests-per-city 2 --delay-seconds 3 --timeout-seconds 20
```

## Secuencia de implementacion propuesta

1. Crear CLI Huislijn-only pequeno y explicito.
2. Reusar `live_fetch` + parser Huislijn + summary helpers.
3. Anadir request accounting por ciudad y run.
4. Anadir contrato de salida pequeno y reproducible.
5. Cubrir con tests offline.
6. Ejecutar `pytest`.
7. Validar uno o dos sample runs acotados sin commitear outputs.

## Riesgos conocidos

- El parser actual depende de markup `listing-card` y puede romperse con cambios de HTML.
- `portal_inventory_spike.py` no expone hoy todo el contrato deseado para Fase 1.2.
- El CLI actual mezcla portales benchmark-only, lo que puede abrir alcance indebido si se reutiliza sin encapsular.
- El URL discovery puede confirmar que una URL es incorrecta (`410`) sin demostrar todavia un inventario estable.

## Criterio de salida esperado para Fase 1.2

Fase 1.2 debe terminar con:

- `pytest` verde
- un CLI Huislijn-only claro
- output bounded por ciudad
- request budget documentado
- status y recommendation por ciudad
- evidencia suficiente para recomendar go/no-go a Fase 2
