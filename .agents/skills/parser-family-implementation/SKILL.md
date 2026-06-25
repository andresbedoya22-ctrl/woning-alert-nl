# Parser Family Implementation

Cuando usarla:
Usa esta skill para implementar una familia reutilizable cuando varias fuentes comparten el mismo patron tecnico.

Que archivos leer:
- `AGENTS.md`
- `docs/03_MAKELAAR_DELIVERY_MODES.md`
- `docs/07_PARSER_FAMILY_ARCHITECTURE.md`
- `docs/08_QA_AND_NORMALIZATION_GATES.md`

Objetivo:
Construir una interfaz y logica compartida que soporte muchas fuentes via config.

Workflow:
1. Verifica que la necesidad no se resuelva con config sobre una familia existente.
2. Define contrato de entrada y salida normalizada.
3. Implementa la logica comun minima.
4. Anade fixtures o tests focalizados.
5. Documenta riesgos y limites de la familia.

Output esperado:
- nueva familia reutilizable
- contrato claro
- tests o fixtures asociados

Reglas:
- No crear parser por makelaar.
- Mantener separada la logica compartida de la config del dominio.

Errores comunes:
- codificar excepciones de un solo dominio dentro de la familia
- mezclar parsing con policy decisions
