# Source Intelligence

Cuando usarla:
Usa esta skill para convertir fuentes, makelaars, source masters o censos existentes en un dataset medible de source intelligence.

Que archivos leer:
- `AGENTS.md`
- `docs/02_SOURCE_INTELLIGENCE_MODEL.md`
- `docs/04_SOURCE_ONBOARDING_PLAYBOOK.md`
- `docs/12_LEGACY_MAP_AND_CLEANUP_PLAN.md`
- scripts y artefactos de discovery relevantes para la tarea

Objetivo:
Construir o actualizar registros estructurados por fuente con evidencia, prioridad y decision operativa clara.

Workflow:
1. Verifica el estado real de los datasets y docs existentes.
2. Identifica las fuentes y sus URLs relevantes, sobre todo `aanbod_url`.
3. Clasifica acceso, blocking signals y delivery mode candidate.
4. Completa el schema minimo con evidencia y notas.
5. Produce reportes de conteo, backlog de manual review y prioridades.

Output esperado:
- dataset de source intelligence
- resumen de coverage por estado y delivery mode
- cola de manual review

Reglas:
- No inventar senales.
- No asumir que un dominio es allowed solo porque responde.
- Mantener evidencia trazable por fuente.

Errores comunes:
- mezclar nombre comercial con patron tecnico
- omitir `aanbod_url_status`
- saltar directo a parser work sin policy clara
