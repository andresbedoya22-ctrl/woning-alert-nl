# WoningAlert NL - Discovery-first Opportunity Pipeline

## Objetivo

WoningAlert NL busca detectar oportunidades accionables de koopwoningen para clientes activos de Domek. El objetivo no es prometer un inventario nacional perfecto, sino lograr cobertura maxima de fuentes tecnicamente descubribles y mantener un censo explicito de las fuentes no descubribles con su razon.

El alcance es nacional por diseno, pero honesto en sus huecos. Funda y Pararius no forman parte del pipeline operativo con scraping automatico: quedan en benchmark, manual review, reference, o permission track.

## Principio de producto

El valor del producto no es "scrapear todo". El valor es reducir busqueda manual, detectar propiedades nuevas, removidas o cambiadas, y cruzarlas con perfiles reales de clientes para producir acciones utiles.

Para el MVP, un daily run es suficiente. La prioridad es una operacion confiable y medible antes que una cobertura teoricamente total.

## Arquitectura V4

- `A. Compliance Gate`
  Aplica robots, crawl-delay, rate limiting y politicas de uso antes de cualquier intento de captura.
- `B. Discovery Census / Strategy Classification`
  Clasifica cada fuente o dominio como descubrible, bloqueado, js_deferred, manual_review, benchmark, o fallback.
- `C. Card Harvest`
  Captura tarjetas o listados livianos desde fuentes aprobadas sin entrar todavia en extraccion detallada costosa.
- `D. Change Detection`
  Detecta nuevas, removidas y cambiadas contra el ultimo inventario valido sin borrar inventario previo de fuentes fallidas.
- `E. Coarse Match`
  Filtra barato contra perfiles reales de clientes para decidir que candidatos merecen detalle adicional.
- `F. OpenAI Extraction`
  Invoca OpenAI solo despues del coarse match para enriquecer el subconjunto candidato.
- `G. Validation + Confidence`
  Valida campos, faltantes y consistencia para separar datos confiables de manual_review.
- `H. Normalization + Fine Match + Advisor Draft`
  Normaliza los datos finales, recalcula el match fino y prepara insumos para drafts operativos posteriores.

## Fuentes y politica de uso

- `Huislijn`
  Candidata y prioridad para portal probing e inventario inicial.
- `Funda`
  Benchmark, manual, reference, o permission track only. No scraping automatico.
- `Pararius`
  Benchmark, manual, o permission track only. No scraping automatico.
- `Makelaar parsers`
  Capa fallback o extra. No camino principal.
- `BAG`, `PDOK`, `EP-Online`
  Enrichment posterior sobre inventario ya priorizado.
- `Email alerts`
  Fuera del core inicial salvo decision posterior.

## Fases

| Fase | Nombre |
| --- | --- |
| 0 | Base limpia y gobierno del repo |
| 1 | Discovery Census / Portal Inventory Spike |
| 2 | Huislijn Adapter v1 |
| 3 | Inventory Core v1 |
| 4 | Daily Sync v1 |
| 5 | Client Matching v1 |
| 6 | Detail Extraction + Validation |
| 7 | Advisor Draft Generator |
| 8 | Multi-source Strategy + fallback makelaars |
| 9 | MVP operativo |

## Reglas duras

- No scraping automatico de Funda o Pararius.
- No anti-bot bypass, stealth, proxies residenciales, CAPTCHA solving, login falso, ni fingerprint spoofing.
- Respetar robots.txt, crawl-delay, y rate limiting por dominio y por host/IP cuando aplique.
- Ante `403`, `429`, CAPTCHA, o login wall: marcar `blocked`, `stale`, o `needs_manual_review` y continuar cuando sea seguro hacerlo.
- El run completo no debe caer por la falla de una sola fuente.
- Si una fuente falla, no borrar inventario previo de esa fuente.
- El LLM objetivo es OpenAI y no se invoca antes del coarse match.
- Ningun componente nuevo sin tests.
- No tocar `data/raw` ni commitear outputs generados.

## Environment

Use `.env.example` as the local template for runtime settings. See [docs/ENVIRONMENT.md](/C:/Projects/domek-wonen/docs/ENVIRONMENT.md) for variables, defaults, secret policy, and the default-disabled LLM and Playwright settings.

## Comandos base

Instalar dependencias:

```powershell
python -m pip install -r requirements.txt
```

Ejecutar tests:

```powershell
py -3.12 -m pytest
```
