# AGENTS.md

## Direccion del proyecto

- Proyecto: `WoningAlert NL V4`
- Direccion: `Discovery-first Opportunity Pipeline`
- Objetivo: detectar oportunidades accionables de koopwoningen para clientes activos de Domek con cobertura maxima de fuentes tecnicamente descubribles y un censo explicito de fuentes no descubribles con su razon.
- El proyecto no es:
  - un scraper total de todo el mercado;
  - un pipeline operativo basado en Funda o Pararius;
  - una estrategia principal makelaar-by-makelaar;
  - un dashboard o Woning Scanner antes de que matching estable exista.

## Reglas hard

- Ejecutar todo en Windows con PowerShell. No asumir Bash.
- Trabajar por fases.
- Hacer cambios pequenos, trazables y testeados.
- No mezclar fases en una misma tarea.
- No scraping automatico de Funda.
- No scraping automatico de Pararius.
- Funda y Pararius solo benchmark, manual, reference, o permission track, fuera del pipeline operativo.
- No stealth.
- No proxies.
- No CAPTCHA solving.
- No anti-bot bypass.
- No login falso.
- No fingerprint spoofing.
- Stop ante `403`, `429`, CAPTCHA, o login wall.
- Registrar `source_status` y continuar cuando sea seguro hacerlo.
- Respetar robots.txt y crawl-delay.
- Aplicar rate limit por dominio y por host/IP cuando aplique.
- No Playwright como camino MVP para fuentes JS.
- Las fuentes JS se clasifican como `js_deferred` o `manual_review` salvo decision futura explicita.
- No makelaar-by-makelaar como camino principal.
- No dashboard antes de `Daily Sync v1` y `Client Matching v1`.
- No `Woning Scanner` antes de matching estable.
- No LLM antes de coarse match.
- LLM provider objetivo: OpenAI.
- No modificar `data/raw` salvo instruccion explicita del usuario.
- No imprimir secrets.
- No commitear `.env`.
- No commitear outputs generados.
- No activar `ENABLE_LLM_EXTRACTION` por defecto.
- No subir `MAX_LLM_CALLS_PER_RUN` por encima de `0` salvo instruccion explicita de la tarea.
- No llamar OpenAI en tests unitarios.
- No usar `git add .`.
- No hacer push.
- No hacer commit sin permiso explicito, salvo cuando la tarea autorice commits atomicos.
- No modificar codigo funcional si el pedido solo requiere documentacion o gobierno del repo.

## Paquetes V4

- `compliance`
  - robots, legal gates, rate limiting, source policy.
- `discovery`
  - source census y strategy classification.
- `harvest`
  - card harvester source-agnostic.
- `changes`
  - fingerprinting y change detection.
- `inventory`
  - future inventory core.
- `matching`
  - coarse y fine match.
- `extraction`
  - extraccion con OpenAI despues del coarse match.
- `validation`
  - validation, confidence, missing fields.
- `drafts`
  - advisor drafts futuros.
- `storage`
  - SQLite/Postgres u otra persistencia futura.
- `portals`
  - LEGACY/DIAGNOSTICO. Portal probes y adapters del enfoque viejo
    (Huislijn/Funda/Pararius). NO es el camino V4. No construir sobre ellos.
    Pendiente de mover a legacy/ en paso futuro.
- `properties`
  - LEGACY/DIAGNOSTICO. property_discovery_engine y parsers asociados del
    enfoque viejo. Solo el parser source-agnostic validado se rescata, en
    el paquete harvest/. No construir sobre properties/.
- `diagnostics`
  - audits y reports.
- `recommendations` y `woning_scanner`
  - no tocar hasta fase futura salvo instruccion explicita.

## Bloques del pipeline V4

| Bloque | Nombre |
| --- | --- |
| 0 | Preparar la mesa (limpieza repo, rama, deps) |
| 1A | Compliance + Discovery Census (gate mayor) |
| 1B | Client Profile Audit |
| 2 | Card Harvester source-agnostic + extractor LLM (sin cablear) |
| 3 | Discovery productivo por estrategia |
| 4 | Storage + Change Detection + dedupe canonico |
| 5 | Coarse Matching (clientes activos) |
| 6 | Detail Extraction + Validation + Fine Match |
| 7 | Advisor Draft + Daily Run + Demo |

Los bloques son gate-driven: no se avanza sin pasar la Definition of Done
del anterior. El Bloque 1A es el gate mayor: su census decide si el
proyecto sigue como software (verde/amarillo) o pasa a track comercial (rojo).

## Validacion obligatoria

- Si cambia codigo: `py -3.12 -m pytest` es obligatorio.
- Si cambia solo documentacion: `py -3.12 -m pytest` sigue recomendado; si no se corre, debe justificarse.
- No declarar una tarea terminada si hubo cambios de codigo y la validacion no corrio o no paso, salvo aceptacion explicita del usuario.

## Manejo de fallas por fuente

- Un fallo de una fuente no debe tumbar el run completo.
- No borrar inventario previo de una fuente fallida.
- No asumir removals reales si la captura de una fuente fallo.
- Fijar `safe_to_compare_removals=false` cuando la fuente falla.
- Mantener el ultimo inventario exitoso como referencia `stale` hasta recuperar la fuente.

## Artefactos que no deben commitearse

- `.env`
- `.env.*`
- `tmp/`
- `.pytest_cache/`
- `cache/`
- `data/raw/`
- `data/diagnostics/`
- `data/cache/`
- `data/discovery/latest/`
- `data/discovery/runs/`
- `data/discovery/platform_fingerprint/`
- `data/email_previews/`
- `data/matching/`
- `data/property_discovery/`
- `data/properties/latest/`
- `data/properties/runs/`
- `data/source_debug/`
- `*.sqlite`
- `*.sqlite3`
- `*.db`
- `*.sqlite-wal`
- `*.sqlite-shm`
- HTML masivo, HAR, previews y runs generados.

## Disciplina operativa

- Usar rutas explicitas para `git add`.
- Hacer commits atomicos.
- Reportar en el cierre: rama, cambios, validacion, git status final, y riesgos o limites.
- No mezclar fases.

## Compliance Gate - Regla vinculante
El modulo `scraper/src/domek_wonen/compliance/robots_gate.py` es el
guardian unico de la red en el pipeline V4. NINGUN modulo puede hacer
requests HTTP sin llamar primero a `can_fetch(domain, path)` y recibir
`True`. Esta regla es vinculante en todos los bloques del pipeline.
