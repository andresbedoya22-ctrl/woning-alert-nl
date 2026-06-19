# Phase 1 Entry Gate - Discovery Census / Portal Inventory Spike

## Objetivo de Fase 1

Medir empiricamente si el enfoque portal-first y discovery-first puede producir cobertura util, segura y accionable antes de construir `Inventory Core`.

## Preguntas que Fase 1 debe responder

- Huislijn expone URLs y listings suficientemente estables?
- Que cobertura real se obtiene en 3-5 ciudades piloto?
- Que campos salen sin LLM?
- Que fuentes quedan `blocked`, `js_deferred`, o `manual_review`?
- Cuantos listings utiles aparecen para perfiles reales o ficticios?
- Que coste operativo y de requests tendria un daily run?
- Que parte requiere fallback makelaar?
- Hay evidencia suficiente para seguir a Fase 2?

## Ciudades piloto sugeridas

- Tilburg
- Den Bosch / 's-Hertogenbosch
- Eindhoven
- Breda
- Waalwijk

Estas ciudades son piloto tecnico, no alcance definitivo del producto.

## Definition of Done de Fase 1

- no Funda o Pararius operativo
- no evasion anti-bot
- request budget explicito
- output reproducible en data permitida o docs, sin commitear outputs pesados
- reporte con cobertura por ciudad
- clasificacion de `source_status`
- listado de campos disponibles sin LLM
- decision clara: seguir, pivotar o detener
- pytest verde
- git status limpio

## Criterios de muerte / stop

- Huislijn no entrega listings utiles o URLs estables
- cobertura demasiado baja para generar matches
- mayoria de senales quedan bloqueadas o `manual_review`
- coste o request budget incompatible con un daily run
- se requiere evasion anti-bot para que funcione
- no hay camino claro hacia matches reales

## Que esta prohibido en Fase 1

- construir dashboard
- construir Woning Scanner
- construir emails o drafts
- llamar OpenAI
- scraping Funda o Pararius
- Playwright como solucion JS
- mover legacy
- reescribir property discovery completo

## Entregables esperados de Fase 1

- reporte tecnico de portal o discovery spike
- CSV o JSON pequeno permitido si es fixture o resumen
- recomendaciones para Fase 2
- decision de go/no-go
