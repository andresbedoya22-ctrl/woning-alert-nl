# Advisor Email Generation

Cuando usarla:
Usa esta skill para preparar drafts o recomendaciones para asesores despues de matching estable.

Que archivos leer:
- `AGENTS.md`
- `docs/06_INVENTORY_CORE_DESIGN.md`
- `docs/08_QA_AND_NORMALIZATION_GATES.md`
- docs de matching y roadmap

Objetivo:
Generar salidas para asesores basadas solo en inventario limpio y matching validado.

Workflow:
1. Confirma que el inventario ya paso QA.
2. Confirma que matching ya produjo candidatos aprobados.
3. Define estructura del draft o review pack.
4. Mantiene minimizacion de datos y trazabilidad al source record.

Output esperado:
- draft de email o review pack
- campos de soporte y razon del match

Reglas:
- No usar listings crudos ni no validados.
- No anticipar advisor emails antes de matching estable.

Errores comunes:
- usar descripcion larga de la fuente
- omitir trazabilidad del match
