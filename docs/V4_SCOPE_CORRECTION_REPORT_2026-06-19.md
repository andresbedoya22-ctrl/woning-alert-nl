# V4 Scope Correction Report - 2026-06-19

## 1. Estado actual del repo

- Rama actual: `portal-first-national-inventory`
- Ultimo commit corto: `e2ba977`
- `git status -s` inicial: limpio, sin cambios
- `pytest` inicial:
  `277 passed in 50.69s` usando cache y `--basetemp` fuera del repo
- Estado frente a V4:
  el repo esta hoy en `portal-first-national-inventory`, no en `feature/discovery-pipeline`
- Por que trabajar en `portal-first-national-inventory` es incorrecto segun V4 Bloque 0.2:
  porque esa rama ya incorpora decisiones, docs y artefactos que empujan el proyecto hacia `portal-first national inventory`, `portal spike`, y `Huislijn` como linea core, mientras que el Bloque 1A real exige `Compliance + Discovery Census` sobre una muestra de dominios de makelaars individuales, con gate de `robots.txt` antes del primer request real y clasificacion por estrategia de descubribilidad.

## 2. Desvio detectado

El desvio principal es que el repo quedo orientado a medir un `portal-first national inventory` con un spike de portal y una linea `Huislijn`-only, en lugar de preparar el Bloque 1A real del V4: `Compliance + Discovery Census` sobre dominios de makelaars individuales.

Que se construyo o documento alrededor de `Huislijn inventory spike`:

- Rama de trabajo `portal-first-national-inventory`
- Commits recientes:
  - `d09cf0f` `feat: add portal inventory spike phase 1a skeleton`
  - `cc0452e` `feat: add offline live fetch foundation for portal inventory spike`
  - `8c21f7b` `feat: add live bounded CLI for portal inventory spike`
  - `dca3803` `feat: add bounded Huislijn URL discovery probe`
  - `e2ba977` `docs: design phase 1 discovery spike`
- Codigo y scripts orientados a portal spike:
  - `scraper/src/domek_wonen/portals/portal_inventory_spike.py`
  - `scraper/src/domek_wonen/portals/huislijn_url_discovery.py`
  - `scraper/src/domek_wonen/portals/adapters/huislijn.py`
  - `scraper/src/domek_wonen/portals/adapters/funda.py`
  - `scraper/src/domek_wonen/portals/adapters/pararius.py`
  - `scripts/run_portal_inventory_spike.py`
  - `scripts/run_huislijn_url_discovery.py`
- Tests asociados:
  - `tests/test_portal_inventory_spike.py`
  - `tests/test_huislijn_url_discovery.py`

Que piezas apuntan a `portal-first national inventory`:

- `README.md` describe `Huislijn` como "candidata y prioridad para portal probing e inventario inicial" y define Fase 1 como `Discovery Census / Portal Inventory Spike`.
- `docs/WONING_ALERT_NL_ROADMAP.md` abre con `portal-first national housing inventory`, marca `Huislijn` como `Primary candidate`, y ata Fase 2 a `Huislijn Adapter v1`.
- `docs/STRATEGY_PIVOT_2026-06-19.md` justifica explicitamente `Huislijn y portal-first` como linea de investigacion inicial.
- `docs/PHASE_1_ENTRY_GATE_2026-06-19.md`, `docs/PHASE_1_1_SPIKE_DESIGN_2026-06-19.md` y `docs/PHASE_1_2_IMPLEMENTATION_PLAN_2026-06-19.md` redefinen la Fase 1 alrededor de un `portal spike` y un CLI `Huislijn`-only.
- `docs/REPO_INVENTORY_2026-06-19.md` inventaria el repo desde el supuesto de la rama `portal-first-national-inventory`.

Por que esto contradice el V4:

- El V4 real ya no permite tomar `Huislijn`, `Funda` o `Pararius` como base de inventario nacional.
- El Bloque 1A real mide dominios de makelaars individuales, no `city + portal`.
- El gate correcto es `robots.txt` por dominio antes de cualquier request real, no un bounded fetch de portal como objeto central del experimento.
- La salida esperada del Bloque 1A es una distribucion de estrategias de descubribilidad en una muestra de aproximadamente 30 dominios de makelaars, no un conteo de listings por ciudad en un portal.

Por que el codigo existente arrastro la ejecucion hacia el camino viejo:

- Ya existia un paquete `portals/` con spike, adapters y fetch bounded, lo que hizo mas facil extender esa superficie que preparar un censo por dominio.
- Los docs de gobernanza de la propia rama reforzaron la decision equivocada con lenguaje `portal-first`.
- El repo mantiene tambien un pipeline `properties/property_discovery_engine.py`; al intentar evitar el camino makelaar-by-makelaar, la ejecucion se desvio hacia portales en vez de redefinir el discovery sobre dominios individuales con clasificacion por estrategia.

Referencias relevantes encontradas:

- `README.md`
- `AGENTS.md`
- `docs/WONING_ALERT_NL_ROADMAP.md`
- `docs/STRATEGY_PIVOT_2026-06-19.md`
- `docs/REPO_INVENTORY_2026-06-19.md`
- `docs/PHASE_1_ENTRY_GATE_2026-06-19.md`
- `docs/PHASE_1_1_SPIKE_DESIGN_2026-06-19.md`
- `docs/PHASE_1_2_IMPLEMENTATION_PLAN_2026-06-19.md`
- `scripts/run_portal_inventory_spike.py`
- `scripts/run_property_discovery.py`
- `scraper/src/domek_wonen/portals/portal_inventory_spike.py`
- `scraper/src/domek_wonen/portals/huislijn_url_discovery.py`
- `scraper/src/domek_wonen/portals/adapters/huislijn.py`
- `scraper/src/domek_wonen/portals/adapters/funda.py`
- `scraper/src/domek_wonen/portals/adapters/pararius.py`
- `tests/test_portal_inventory_spike.py`
- `tests/test_property_discovery_engine.py`

Observacion importante:

- `feature/discovery-pipeline` no existe ni en local ni en remoto en el estado actual inspeccionado.
- `scripts/run_huislijn_inventory_spike.py`, `scraper/src/domek_wonen/portals/huislijn_inventory_spike.py` y `tests/test_huislijn_inventory_spike.py` no existen hoy; aparecen solo como direccion propuesta en docs recientes del desvio.

## 3. Diff de alcance: V4 Bloque 1A vs implementacion desviada

| Tema | V4 Bloque 1A real | Implementacion desviada | Impacto | Correccion necesaria |
| --- | --- | --- | --- | --- |
| Fuente principal | Dominios de makelaars individuales | `Huislijn` y portal spike | Se mide el objeto equivocado | Volver a una muestra de aproximadamente 30 dominios de makelaars |
| Unidad de analisis | Dominio de makelaar | Ciudad + portal | La cobertura queda sesgada por un agregador | Recentrar la unidad de trabajo en dominio individual |
| Gate de compliance | `robots.txt` antes del primer request real por dominio | Fetch bounded de portal como paso central | El gate no protege el flujo correcto | Implementar primero el gate de compliance por dominio |
| Estrategias de clasificacion | `sitemap_with_listings`, `wp_json`, `listing_html`, `listing_js`, `iframe_only`, `blocked`, `no_signal` | Estados y resultados de portal/Huislijn | La salida no responde la pregunta V4 | Redefinir el census para clasificar dominios por estrategia |
| Parser base | Parser source-agnostic validado sobre familias makelaar/CMS | Adapter Huislijn y parser de portal | El parser base del V4 queda desplazado | Reusar y endurecer el parser source-agnostic y sus configs |
| Resultado esperado | Distribucion real de aproximadamente 30 makelaars por estrategia | Listings por ciudad en Huislijn | No sirve como gate de color del proyecto | Emitir un reporte de distribuccion por estrategia y descubribilidad |
| Decision de gate | Verde/amarillo/rojo segun porcentaje de makelaars descubribles | Go/no-go de Huislijn | El proyecto podria avanzar o morir por el proxy equivocado | Basar el gate en descubribilidad sobre dominios individuales |
| Rama | `feature/discovery-pipeline` | `portal-first-national-inventory` | La rama ya arrastra naming, docs y commits desviados | Realinear la rama antes de entrar al Bloque 1A real |

## 4. Artefactos que se CONSERVAN

| Ruta | Conservar | Por que | Condicion de uso en V4 |
| --- | --- | --- | --- |
| `scraper/src/domek_wonen/compliance/` | si | Skeleton compatible con el paquete V4 | Solo como base para el gate de compliance por dominio |
| `scraper/src/domek_wonen/discovery/` | si | Ya contiene base de discovery, resolver, analyzer y reporting | Reorientar a census de dominios individuales, no portal-first |
| `scraper/src/domek_wonen/harvest/` | si | Skeleton alineado con Card Harvest | Usar despues del census y de compliance |
| `scraper/src/domek_wonen/changes/` | si | Skeleton alineado con Change Detection | No activar como foco antes del Bloque 1A |
| `scraper/src/domek_wonen/matching/` | si | Base reutilizable para coarse/fine match posterior | Queda fuera del trabajo inmediato del Bloque 1A |
| `scraper/src/domek_wonen/extraction/` | si | Skeleton alineado con extraccion posterior | Mantener con LLM apagado hasta despues del coarse match |
| `scraper/src/domek_wonen/validation/` | si | Skeleton alineado con Validation + Confidence | Fase posterior |
| `scraper/src/domek_wonen/drafts/` | si | Skeleton alineado con drafts futuros | Fase posterior |
| `scraper/src/domek_wonen/storage/` | si | Skeleton alineado con persistencia futura | No reabrir el alcance del storage todavia |
| `scraper/src/domek_wonen/inventory/` | si | Skeleton valido para un inventory core futuro | No usar para justificar portal spike como base |
| `tests/test_compliance_package.py` | si | Placeholder de paquete V4 | Mantener como test minimo de estructura |
| `tests/test_harvest_package.py` | si | Placeholder de paquete V4 | Mantener como test minimo de estructura |
| `tests/test_changes_package.py` | si | Placeholder de paquete V4 | Mantener como test minimo de estructura |
| `tests/test_extraction_package.py` | si | Placeholder de paquete V4 | Mantener como test minimo de estructura |
| `tests/test_validation_package.py` | si | Placeholder de paquete V4 | Mantener como test minimo de estructura |
| `tests/test_drafts_package.py` | si | Placeholder de paquete V4 | Mantener como test minimo de estructura |
| `tests/test_storage_package.py` | si | Placeholder de paquete V4 | Mantener como test minimo de estructura |
| `scraper/src/domek_wonen/runtime_settings.py` | si | Defaults seguros, OpenAI deshabilitado por defecto y `MAX_LLM_CALLS_PER_RUN=0` | Mantener si se corrige el typo `WNA_RESPECT_ROBOTS_TX` antes de usarlo como contrato definitivo |
| `.env.example` | si | Alineado con OpenAI como provider objetivo, sin secretos y con LLM apagado | Mantener mientras siga sin secretos ni activacion por defecto |
| `docs/ENVIRONMENT.md` | si | Documenta politicas seguras de OpenAI, Playwright y secretos | Mantener, pero sin usarlo para legitimar Playwright como camino MVP |
| `requirements.txt` | si | Contiene dependencias utiles: `httpx`, `selectolax`, `pydantic`, `python-dotenv`, `tenacity`, `openai`, `pytest` | Mantener; `playwright` queda solo como legacy/deshabilitado |
| `scraper/src/domek_wonen/properties/property_card_extractor.py` | si | Es el parser source-agnostic mas cercano a la base V4 para tarjetas HTML | Reusar sobre dominios de makelaars/CMS, no sobre un portal como centro del pipeline |
| `scraper/src/domek_wonen/properties/source_parser_config.py` | si | Encaja con una capa de configuracion por familia/parser source-agnostic | Reusar para familias CMS del census y harvest |
| `docs/ARCHITECTURE.md` | si, con correccion | La direccion general `compliance -> discovery -> harvest -> matching -> extraction` sigue siendo util | Corregir lenguaje `portals`, especialmente donde se privilegia Huislijn |
| `docs/DISCOVERY_SOURCES.md` | si, con correccion | Conserva politicas utiles sobre Funda/Pararius y discovery | Quitar cualquier lectura que reinstale agregadores como base operativa |
| Patron de pytest con `$env:TEMP` | si | Es un aprendizaje operativo valido en Windows | Usar siempre para evitar `PermissionError [WinError 5]` |

## 5. Artefactos que quedan FUERA del pipeline V4

| Ruta | Motivo de exclusion del pipeline V4 | Estado recomendado | Riesgo si se reutiliza por accidente |
| --- | --- | --- | --- |
| `scraper/src/domek_wonen/portals/huislijn_inventory_spike.py` | No existe hoy, pero su propia direccion seria desviada | no crear dentro del pipeline V4 | Reabriria el camino Huislijn-only ya descartado |
| `scripts/run_huislijn_inventory_spike.py` | No existe hoy, pero aparece propuesto en docs del desvio | no crear dentro del pipeline V4 | Consolidaria el spike equivocado como entrypoint |
| `tests/test_huislijn_inventory_spike.py` | No existe hoy, pero aparece propuesto en docs del desvio | no crear dentro del pipeline V4 | Haria pasar por valido un alcance incorrecto |
| `scraper/src/domek_wonen/portals/portal_inventory_spike.py` | Modela un spike portal por ciudad, no un census por dominio individual | conservar como legacy/diagnostico | Sesga la arquitectura y los reportes hacia portal-first |
| `scripts/run_portal_inventory_spike.py` | Ejecuta el spike portal antiguo | conservar como legacy/diagnostico | Ofrece un CLI que mezcla el camino viejo con el repo vivo |
| `scraper/src/domek_wonen/portals/adapters/huislijn.py` | Adapter especifico de un agregador descartado como base operativa | conservar como legacy/diagnostico | Reinstala Huislijn como parser central |
| `scraper/src/domek_wonen/portals/adapters/funda.py` | Funda no puede ser camino operativo automatizado | conservar como legacy/diagnostico | Puede normalizar un uso prohibido de Funda |
| `scraper/src/domek_wonen/portals/adapters/pararius.py` | Pararius no puede ser camino operativo automatizado | conservar como legacy/diagnostico | Puede normalizar un uso prohibido de Pararius |
| `tests/test_portal_inventory_spike.py` | Valida el spike portal y fixtures Funda/Pararius/Huislijn en el mismo flujo | conservar como legacy/diagnostico | Mantiene verde un flujo que no responde al Bloque 1A real |
| `tests/test_huislijn_url_discovery.py` | Valida un probe Huislijn bounded, no el census objetivo | conservar como legacy/diagnostico | Puede volver a orientar trabajo hacia URL probing de agregador |
| `scraper/src/domek_wonen/portals/huislijn_url_discovery.py` | Diagnostica URLs de Huislijn, no discovery por dominio de makelaar | conservar como legacy/diagnostico | Confunde un probe acotado con la estrategia V4 |
| `docs/WONING_ALERT_NL_ROADMAP.md` | Define el proyecto como `portal-first national housing inventory` | revisar y corregir | Sigue empujando la estrategia muerta |
| `docs/STRATEGY_PIVOT_2026-06-19.md` | Justifica `Huislijn y portal-first` como linea inicial | revisar y corregir | Deja como vigente una decision ya invalidada |
| `docs/PHASE_1_ENTRY_GATE_2026-06-19.md` | Define el gate de Fase 1 alrededor de portal-first y Huislijn | revisar y corregir | Haria medir el gate con el proxy equivocado |
| `docs/PHASE_1_1_SPIKE_DESIGN_2026-06-19.md` | Disena un spike portal/Huislijn para Fase 1 | revisar y corregir | Baja la barra del Bloque 1A real |
| `docs/PHASE_1_2_IMPLEMENTATION_PLAN_2026-06-19.md` | Propone un CLI `Huislijn`-only y extensiones del spike | revisar y corregir | Podria disparar implementacion del camino descartado |
| `README.md` | Aun define Fase 1 como `Discovery Census / Portal Inventory Spike` y presenta Huislijn como prioridad portal | revisar y corregir | El documento principal seguiria sembrando prompts incorrectos |
| `scraper/src/domek_wonen/properties/property_discovery_engine.py` | Si se toma como camino principal, contradice el V4 por ser el pipeline legacy `makelaar-by-makelaar` | conservar como legacy/diagnostico o revisar como fallback | Puede desviar otra vez el repo fuera del discovery-first correcto |
| `scripts/run_property_discovery.py` | Si se toma como camino principal, revive el pipeline legacy | conservar como legacy/diagnostico o revisar como fallback | Reabre el camino anterior como entrypoint operativo |
| `tests/test_property_discovery_engine.py` | Valida el pipeline legacy extenso | conservar como legacy/diagnostico | Puede ocultar la falta de base del Bloque 1A real |

## 6. Rama incorrecta y correccion necesaria

- Rama actual real: `portal-first-national-inventory`
- Rama exigida por V4: `feature/discovery-pipeline`
- Estado de `feature/discovery-pipeline`: no existe ni en local ni en remoto en la inspeccion realizada

Commits relevantes hoy en `portal-first-national-inventory`:

- `cc5a4fa` `chore: add v4 pipeline package skeleton`
- `efef513` `docs: align repo governance with v4 pipeline`
- `268afa2` `chore: add v4 environment and dependency contracts`
- `d09cf0f` `feat: add portal inventory spike phase 1a skeleton`
- `cc0452e` `feat: add offline live fetch foundation for portal inventory spike`
- `8c21f7b` `feat: add live bounded CLI for portal inventory spike`
- `dca3803` `feat: add bounded Huislijn URL discovery probe`
- `42cb1a5` `docs: close phase 0 and define phase 1 gate`
- `e2ba977` `docs: design phase 1 discovery spike`

Lectura de riesgo:

- La rama actual mezcla base reusable del V4 con artefactos y docs ya desviados.
- Crear trabajo nuevo directamente aqui hace mas probable seguir reforzando el modelo `portal-first`.

Recomendacion segura para realinear:

- Opcion preferida:
  crear `feature/discovery-pipeline` desde el punto correcto mas limpio posible, idealmente desde un commit que ya tenga skeleton V4, environment y governance utiles, pero antes de consolidar el spike `portal-first`/`Huislijn`.
- Opcion alternativa:
  crear `feature/discovery-pipeline` desde la rama actual, pero documentando desde el primer commit que contiene artefactos legacy que deben quedar aislados y fuera del pipeline V4.
- No hacer `cherry-pick`, rebase ni limpieza de rama todavia sin aprobacion explicita del usuario.

## 7. Recomendacion de correccion de rumbo

Antes de entrar al Bloque 1A real se debe:

1. Corregir la fuente de verdad visible del repo para que Fase 1/Bloque 1A deje de significar `portal spike` o `Huislijn-only`.
2. Decidir la estrategia de rama para `feature/discovery-pipeline`.
3. Marcar explicitamente como legacy/diagnostico todo lo ligado a `portal_inventory_spike`, `Huislijn URL discovery`, adapters de portales, y `property_discovery_engine` cuando se use como camino principal.
4. Confirmar que el Bloque 1A real mide una muestra de aproximadamente 30 dominios de makelaars individuales con gate de `robots.txt` previo y clasificacion por estrategia:
   `sitemap_with_listings`, `wp_json`, `listing_html`, `listing_js`, `iframe_only`, `blocked`, `no_signal`.
5. Acordar que el parser base V4 es source-agnostic sobre familias makelaar/CMS y no un adapter de agregador.

Docs que deben corregirse:

- `README.md`
- `docs/WONING_ALERT_NL_ROADMAP.md`
- `docs/STRATEGY_PIVOT_2026-06-19.md`
- `docs/PHASE_1_ENTRY_GATE_2026-06-19.md`
- `docs/PHASE_1_1_SPIKE_DESIGN_2026-06-19.md`
- `docs/PHASE_1_2_IMPLEMENTATION_PLAN_2026-06-19.md`

Artefactos que deben marcarse como legacy/diagnostico:

- `scraper/src/domek_wonen/portals/portal_inventory_spike.py`
- `scraper/src/domek_wonen/portals/huislijn_url_discovery.py`
- `scraper/src/domek_wonen/portals/adapters/huislijn.py`
- `scraper/src/domek_wonen/portals/adapters/funda.py`
- `scraper/src/domek_wonen/portals/adapters/pararius.py`
- `scripts/run_portal_inventory_spike.py`
- `tests/test_portal_inventory_spike.py`
- `tests/test_huislijn_url_discovery.py`
- `scraper/src/domek_wonen/properties/property_discovery_engine.py`
- `scripts/run_property_discovery.py`
- `tests/test_property_discovery_engine.py`

Base valida que si debe quedar:

- Skeleton de paquetes V4
- `runtime_settings.py` y `.env.example` con defaults seguros
- Dependencias utiles para fetch/parsing/config/tests
- Parser source-agnostic y config validation reutilizable
- Docs de arquitectura y environment una vez corregidos
- Patron de `pytest` con cache y base fuera del repo

Debe quedar prohibido en prompts futuros:

- Proponer `portal-first` como direccion operativa vigente
- Proponer `Huislijn-only` como Bloque 1A real
- Proponer `Funda` o `Pararius` como fuente operativa automatizada
- Proponer Playwright como camino MVP
- Reabrir `property_discovery_engine` como camino principal
- Mezclar el Bloque 1A real con `inventory spike`, `daily sync`, matching o extraccion

NO entrar al Bloque 1A hasta que Andres apruebe este diff de alcance y la estrategia de realineacion de rama.
