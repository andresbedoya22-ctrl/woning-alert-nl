# Failure Triage

Cuando usarla:
Usa esta skill para diagnosticar fallos de una fuente, familia, script o pipeline sin ampliar scope.

Que archivos leer:
- `AGENTS.md`
- logs, tests, artefactos y scripts exactos del fallo
- docs de policy, parser o inventory segun corresponda

Objetivo:
Encontrar la capa real del problema antes de proponer cambios.

Workflow:
1. Verifica si el fallo es policy, transport, parsing, QA o inventory.
2. Busca evidencia exacta en tests, logs o artefactos.
3. Aisla la causa minima.
4. Propone la correccion mas pequena posible.

Output esperado:
- capa del fallo
- evidencia
- fix minimo propuesto o aplicado

Reglas:
- No culpar parsers si policy o source-state es la causa.
- No mezclar arreglos de varias capas en un solo cambio.

Errores comunes:
- especular sin artefactos
- saltar directo a refactor amplio
