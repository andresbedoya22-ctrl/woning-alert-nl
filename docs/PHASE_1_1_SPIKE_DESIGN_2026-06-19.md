# Phase 1.1 Spike Design - 2026-06-19

## Objetivo

Disenar el Discovery Census / Portal Inventory Spike antes de implementar cambios.

Fase 1 debe medir si el enfoque portal-first / discovery-first produce cobertura util, segura y accionable antes de construir `Inventory Core`.

## Preguntas de Fase 1

- Huislijn expone URLs y listings suficientemente estables?
- Que cobertura se obtiene en ciudades piloto?
- Que campos salen sin LLM?
- Que queda `blocked`, `js_deferred`, o `manual_review`?
- Que coste de requests tendria un daily run?
- Hay evidencia suficiente para seguir a Fase 2?

## Confirmaciones del marco de Fase 1

Los documentos base confirman lo siguiente:

- Fase 1 no debe usar OpenAI ni habilitar `ENABLE_LLM_EXTRACTION`.
- Funda y Pararius quedan fuera del pipeline operativo; solo benchmark, manual, reference, o permission track.
- JS no debe resolverse con Playwright como camino MVP.
- Fase 1 debe medir primero y construir despues.
- El Huislijn probe actual no equivale todavia a un adapter productivo ni a `Inventory Core`.

## Ciudades piloto

- Tilburg
- Den Bosch / 's-Hertogenbosch
- Eindhoven
- Breda
- Waalwijk

## Alcance permitido

- Huislijn probe / inventory spike con request budget explicito
- HTTP bounded fetch
- HTML parsing barato si ya esta permitido
- outputs pequenos de resumen
- reportes reproducibles
- `source_status` claro

## Alcance prohibido

- Funda/Pararius operativo
- OpenAI
- Playwright como solucion JS
- dashboard
- Woning Scanner
- emails/drafts
- mover legacy
- reescribir `property_discovery_engine`
- scraping real masivo

## Diseno operativo del spike

### Forma del spike

- Portal inicial: solo Huislijn
- Nivel de captura: listing/search pages, no detail extraction masiva
- Tipo de run: bounded, reproducible, con stop temprano ante `403`, `429`, CAPTCHA, o login wall
- Entrega principal: resumen por ciudad y por fuente, no inventario operativo permanente

### Hipotesis a validar

1. Huislijn expone una URL de busqueda suficientemente estable por ciudad.
2. La captura bounded devuelve enough listings/URLs sin requerir JS o bypass.
3. El parser barato recupera al menos `url`, `address`, `price`, y `status` con fill rate util.
4. El coste por ciudad cabe en un daily run acotado.

### Request budget inicial de Fase 1

- Discovery URL probe: maximo `10` requests totales por run
- Inventory spike por ciudad: partir con `max_pages=2` y un tope explicito de listings
- Delay entre requests live: mantener delay explicito y configurable
- Hard stop ante `403`, `429`, CAPTCHA, login wall, o `permission_required`

## Codigo existente reutilizable

| Archivo | Que hace | Se puede usar tal cual? | Limitaciones | Riesgos | Recomendacion |
| --- | --- | --- | --- | --- | --- |
| `scraper/src/domek_wonen/portals/live_fetch.py` | Fetch HTTP bounded y clasificacion de `source_status` | Si | Usa `urllib`, clasificacion HTML simple | Acopla utilidades de `portal_inventory_spike` | reuse |
| `scraper/src/domek_wonen/portals/huislijn_url_discovery.py` | Prueba URLs candidatas de Huislijn, resume evidencia y corta por budget/blocked status | Si, para Fase 1 | Solo diagnostico de URL shape; no produce inventario por ciudad | Puede confundir probe de URL con adapter real si se amplifica scope | reuse |
| `scraper/src/domek_wonen/portals/adapters/huislijn.py` | Construye URL de busqueda y parsea listing cards de Huislijn | Si, como parser inicial | Parser HTML barato, sin contratos de detalle ni paginacion sofisticada | Fragil ante cambios de markup | wrap |
| `scraper/src/domek_wonen/portals/models/listing.py` | Define `SourceStatus`, `PortalMode`, y shapes de listing/city/spike result | Si | Nombres orientados a spike, no a inventory canonico | Puede quedarse corto para futuras metricas y request accounting | reuse |
| `scraper/src/domek_wonen/portals/portal_inventory_spike.py` | Normalizacion, dedupe, fill rates, reporte markdown y CSVs del spike | Parcialmente | Contrato actual no incluye request cost ni muestras de URLs | Modelo/reporting todavia muy spike-oriented | wrap |
| `scripts/run_huislijn_url_discovery.py` | CLI bounded para URL discovery con output reproducible | Si | Solo aplica al probe de URL discovery | No cubre el inventory spike por ciudad | reuse |
| `scripts/run_portal_inventory_spike.py` | CLI sample/live bounded del spike portal | Parcialmente | Mezcla Huislijn con Funda/Pararius legacy/benchmark | Riesgo de abrir scope de portales prohibidos en Fase 1.1 | avoid |
| `tests/test_huislijn_url_discovery.py` | Valida budget, stop conditions, recommendations y outputs del URL probe | Si | Cobertura centrada en diagnostico, no en cobertura por ciudad | No prueba contrato final de Fase 1.2 | reuse |
| `tests/test_portal_inventory_spike.py` | Valida parser de samples, outputs y continuidad por fuente | Parcialmente | Incluye Funda/Pararius como benchmark-only en el mismo CLI | Puede sesgar el diseno hacia multi-portal antes de tiempo | wrap |
| `tests/test_live_fetch.py` | Valida clasificacion HTTP y fetch bounded offline | Si | No cubre request accounting por ciudad | Cobertura razonable para transporte bounded | reuse |

## Decision de reutilizacion

- Reusar sin cambios como base: `live_fetch.py`, `huislijn_url_discovery.py`, `listing.py`, `test_live_fetch.py`, `test_huislijn_url_discovery.py`
- Envolver sin duplicar logica: `adapters/huislijn.py`, `portal_inventory_spike.py`
- Evitar como base directa de Fase 1.2: `scripts/run_portal_inventory_spike.py` porque mezcla portales benchmark-only con el camino Huislijn

## Contrato de salida propuesto para el spike

El spike debe producir un output pequeno, reproducible y versionable como contrato documental/fixture. Los outputs live generados deben quedar en `data/diagnostics/...` o `tmp/...` y no commitearse.

### Registro minimo por ciudad y fuente

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
- `sample_listing_urls` con maximo 5
- `blocker_reason`
- `recommendation`

### Campos derivados recomendados

- `portal_mode`
- `safe_to_compare_removals`
- `fill_rate_address`
- `fill_rate_price`
- `fill_rate_status`
- `fill_rate_url`
- `js_signal_detected`
- `manual_review_reason`

### Formatos propuestos

- `docs/`:
  - contrato y ejemplos estaticos pequenos
- `data/diagnostics/portal_inventory/<run_id>/`:
  - `phase_1_city_summary.csv`
  - `phase_1_inventory_report.md`
  - opcional `sample_listing_urls.json` o `phase_1_summary.json`

## Metricas minimas

- listings por ciudad
- unique URL rate
- duplicate URL rate
- fill rate de `address` / `price` / `status` / `url`
- count de `blocked` / `manual_review` / `js_deferred`
- requests por ciudad
- estimated daily request budget

## Interpretacion de estados

- `success`: hay evidencia de captura util sin bypass
- `requires_js`: no seguir por MVP; clasificar como `js_deferred` o `manual_review`
- `http_403`, `http_429`, `blocked_captcha`, `permission_required`: stop y no automatizar
- `parser_broken`: no asumir bloqueo; revisar si es markup drift o URL incorrecta
- `wrong_url_410`: URL candidata incorrecta; no equivale a bloqueo del portal

## Criterio go / no-go hacia Fase 2

### Go

- Huislijn muestra al menos una URL de busqueda estable para varias ciudades piloto
- El parser barato devuelve URLs de listing unicas y fields minimos con fill rate aceptable
- El request budget proyectado cabe en un daily run bounded
- No se requiere Playwright, bypass, ni detalle costoso para obtener senal util

### No-go o pivot

- La mayoria de ciudades quedan en `manual_review`, `requires_js`, o `blocked`
- Las URLs son inestables o se rompen por cambios menores
- El fill rate util sin LLM es demasiado bajo
- El coste por ciudad obliga a un run caro o fragil

## Definition of Done Fase 1.2

Fase 1.2 solo puede empezar si el diseno deja definido:

- comando exacto a crear o reutilizar
- output esperado
- tests minimos
- request budget
- ciudades piloto
- regla de no commit de outputs pesados
- criterio go/no-go

## Propuesta concreta para Fase 1.2

- Reutilizar `scripts/run_huislijn_url_discovery.py` para validar URL shape primero
- Crear o ajustar un CLI Huislijn-only para inventory spike bounded por ciudad
- Mantener fuera del CLI final cualquier ruta operativa de Funda/Pararius
- Mantener outputs live en `data/diagnostics/portal_inventory/<run_id>/`
- Agregar un resumen pequeno y estable del contrato esperado para tests

## Nota de trazabilidad

- Fase 0 cerro con commit `42cb1a5` `docs: close phase 0 and define phase 1 gate`
- El primer intento de Fase 1.1 se detuvo por `PermissionError` ambiental en `tmp\pytest`
- El preflight se reintento con `cache_dir` y `basetemp` fuera del repo y `pytest` paso
