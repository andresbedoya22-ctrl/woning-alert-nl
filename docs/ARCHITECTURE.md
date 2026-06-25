# WoningAlert NL V4 Architecture

## Objetivo del sistema

WoningAlert NL V4 busca detectar oportunidades accionables de koopwoningen para clientes activos de Domek. El sistema prioriza cobertura maxima de fuentes tecnicamente descubribles, un censo honesto de huecos y un pipeline operativo que mida bloqueo, cambio y utilidad comercial antes de crecer en complejidad.

## Diagrama A-H

- `A. Compliance Gate`
  Aplica robots, crawl-delay, rate limits, y politica de uso antes de cualquier captura.
- `B. Discovery Census / Strategy Classification`
  Clasifica fuentes como portal, fallback, benchmark, js_deferred, blocked, o manual_review.
- `C. Card Harvest`
  Captura listados o tarjetas desde fuentes aprobadas con el menor costo posible.
- `D. Change Detection`
  Compara contra inventario previo valido para detectar nuevas, removidas y cambiadas.
- `E. Coarse Match`
  Filtra barato por presupuesto, geografia y perfil antes de cualquier enrichment costoso.
- `F. OpenAI Extraction`
  Usa OpenAI solo para los candidatos que sobrevivieron al coarse match.
- `G. Validation + Confidence`
  Valida consistencia, faltantes y confianza de la extraccion.
- `H. Normalization + Fine Match + Advisor Draft`
  Normaliza salida final, calcula match fino y prepara drafts posteriores para advisor.

## Responsabilidades por paquete

| Paquete | Responsabilidad |
| --- | --- |
| `compliance` | robots, legal gates, crawl policy, rate limiting |
| `discovery` | source census y strategy classification |
| `harvest` | capture de cards y listados ligeros |
| `changes` | fingerprinting y change detection |
| `inventory` | inventario canonico y persistencia de estado operativo |
| `matching` | coarse y fine match |
| `extraction` | enriquecimiento con OpenAI despues del coarse match |
| `validation` | confidence, field validation, missing data handling |
| `drafts` | drafts para advisor en fases posteriores |
| `storage` | SQLite/Postgres o capas futuras de persistencia |
| `portals` | probes y adapters portal, especialmente Huislijn |
| `properties` | legacy reusable/fallback property parsing |
| `diagnostics` | audits, reports, observabilidad y coverage checks |

## Debilidades y mitigaciones

| Debilidad | Mitigacion |
| --- | --- |
| `Ningun makelaar` o 100% coverage imposible | coverage maxima + censo explicito de huecos y razones |
| Discovery varia por sitio | strategy classification por dominio y por fuente |
| Coste token alto | card harvest + change detection + coarse match antes del LLM |
| Tarjeta incompleta | coarse match barato + detalle solo para candidatos |
| Robots, rate-limit o anti-bot | compliance gate + `blocked` / `stale` / `manual_review` |
| Fallo silencioso de extraccion | validation, confidence, y deteccion de missing fields |

## Politica de Funda y Pararius

- `Funda`
  Fuera del pipeline operativo con scraping automatico. Solo benchmark, manual review, reference, o permission track.
- `Pararius`
  Fuera del pipeline operativo con scraping automatico. Solo benchmark, manual review, o permission track.

## Politica de LLM OpenAI

- Provider objetivo: OpenAI.
- El LLM no se invoca antes del coarse match.
- La extraccion detallada solo corre sobre candidatos priorizados.

## Regla de inventario previo

Si una fuente falla, el sistema no debe borrar el inventario previo de esa fuente. En ese caso, la fuente queda como `stale`, `blocked`, o `needs_manual_review`, y `safe_to_compare_removals=false` hasta recuperarla.
