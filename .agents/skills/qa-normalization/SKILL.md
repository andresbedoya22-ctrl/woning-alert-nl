# QA Normalization

Cuando usarla:
Usa esta skill para definir o implementar gates de calidad y normalizacion.

Que archivos leer:
- `AGENTS.md`
- `docs/08_QA_AND_NORMALIZATION_GATES.md`
- modelos normalizados relevantes

Objetivo:
Separar inventario limpio, rechazado y `needs_review` de forma consistente.

Workflow:
1. Revisa transaction type, status, address y price.
2. Define reglas de dedupe.
3. Decide criterios de clean, rejected y review.
4. Anade pruebas o fixtures cuando haya runtime code.

Output esperado:
- gates de QA claros
- criterios de rechazo y revision

Reglas:
- No colapsar koop y huur.
- No mezclar `onder bod` con `verkocht`.

Errores comunes:
- normalizar valores ambiguos sin dejar evidencia
- usar match logic como sustituto de QA
