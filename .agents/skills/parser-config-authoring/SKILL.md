# Parser Config Authoring

Cuando usarla:
Usa esta skill para crear o ajustar configs por dominio sin crear parser nuevo.

Que archivos leer:
- `AGENTS.md`
- `docs/07_PARSER_FAMILY_ARCHITECTURE.md`
- `docs/08_QA_AND_NORMALIZATION_GATES.md`
- family code o fixtures existentes si ya existen

Objetivo:
Onboardear nuevas fuentes usando config sobre una familia reutilizable.

Workflow:
1. Confirma que la fuente ya tiene family candidate.
2. Identifica campos configurables del dominio.
3. Define selectors, paths y reglas de normalizacion especificas.
4. Anade fixtures o evidencia minima para validar.

Output esperado:
- config por dominio
- fixture o caso de prueba
- nota de compatibilidad con la familia

Reglas:
- Crear parser nuevo solo si config no basta y la familia ya fue descartada.

Errores comunes:
- meter logica especifica del dominio en la familia compartida
- ignorar diferencias de status y transaction_type
