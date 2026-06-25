# Test Repair Loop

Cuando usarla:
Usa esta skill para reparar tests con cambios minimos despues de un cambio focalizado.

Que archivos leer:
- `AGENTS.md`
- tests fallidos
- runtime code relacionado

Objetivo:
Restaurar el verde sin introducir refactors innecesarios.

Workflow:
1. Reproduce el fallo.
2. Identifica si el problema es test, fixture o contrato real.
3. Aplica el cambio mas pequeno coherente.
4. Reejecuta la parte afectada y luego la suite requerida.

Output esperado:
- tests reparados
- explicacion minima del ajuste

Reglas:
- No reescribir grandes bloques por comodidad.
- No cambiar comportamiento valido para complacer un test malo sin justificarlo.

Errores comunes:
- arreglar tests sin entender el contrato
- mezclar reparacion de tests con rediseno
