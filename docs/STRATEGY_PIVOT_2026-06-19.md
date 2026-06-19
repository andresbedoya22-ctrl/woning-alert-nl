# Strategy Pivot 2026-06-19

## Por que se abandona makelaar-by-makelaar como camino principal

El camino makelaar-by-makelaar escala mal para un objetivo nacional, aumenta mantenimiento por parser, y mezcla cobertura comercial con deuda tecnica demasiado temprano. Para V4, esa capa queda como fallback reutilizable, no como estrategia central.

## Por que Funda y Pararius no son camino operativo

Funda y Pararius no son base operativa para V4 porque el proyecto no va a depender de scraping automatico sobre fuentes con mayor sensibilidad legal, tecnica o anti-bot. Quedan como benchmark, manual review, reference, o permission track.

## Por que Huislijn y portal-first se usan como linea de investigacion inicial

Huislijn ofrece una linea mas prometedora para portal probing e inventario inicial: permite investigar cobertura, estructura, bloqueo y costo operativo con una superficie mas acotada. El enfoque portal-first facilita medir antes de construir parsers adicionales.

## Piezas legacy que se conservan como fallback o reutilizables

- `properties/` como parsing fallback reutilizable
- `matching/` para coarse y fine match local
- `diagnostics/` para audits y observabilidad
- `discovery/` para source census, fingerprinting y coverage analysis
- `portals/` como base de probes y adapters

## Piezas legacy que no se tocan todavia

- `property_discovery_engine` y CLIs relacionadas
- `recommendations/`
- `woning_scanner/`
- docs o artefactos historicos fuera del scope de gobierno V4

En Fase 0.3 no se archiva ni mueve nada. Solo se aclara el gobierno del repo.

## Condicion de muerte del proyecto

Si despues del `Discovery Census / Portal Spike` no aparece cobertura suficiente, costo razonable, o capacidad real de generar matches utiles para clientes, el proyecto debe detenerse o redefinirse comercialmente en lugar de seguir acumulando complejidad tecnica.

## Principio final

Construir menos, medir mas, y avanzar solo por gates.
