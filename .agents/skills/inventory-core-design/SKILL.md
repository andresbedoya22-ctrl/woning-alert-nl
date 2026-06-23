# Inventory Core Design

Cuando usarla:
Usa esta skill para disenar snapshots, diffs, stale-source handling y estado durable del inventario.

Que archivos leer:
- `AGENTS.md`
- `docs/06_INVENTORY_CORE_DESIGN.md`
- `docs/08_QA_AND_NORMALIZATION_GATES.md`

Objetivo:
Definir el modelo de inventario sin borrar historial correcto por fallos de fuente.

Workflow:
1. Identifica el contrato de normalized listing.
2. Define snapshot por fuente y por run.
3. Disena diff engine y tipos de cambio.
4. Asegura stale-source handling y `safe_to_compare_removals`.

Output esperado:
- diseno del inventory core
- contrato de diff
- reglas de stale source

Reglas:
- No inferir removals desde runs fallidos.

Errores comunes:
- mezclar snapshot diario con estado canonico
- borrar inventario al primer fallo
