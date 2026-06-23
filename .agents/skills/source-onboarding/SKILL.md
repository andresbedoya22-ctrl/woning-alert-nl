# Source Onboarding

Cuando usarla:
Usa esta skill para llevar una fuente desde `candidate` hasta `production eligible`.

Que archivos leer:
- `AGENTS.md`
- `docs/04_SOURCE_ONBOARDING_PLAYBOOK.md`
- `docs/05_ACCESS_POLICY.md`
- `docs/07_PARSER_FAMILY_ARCHITECTURE.md`
- `docs/08_QA_AND_NORMALIZATION_GATES.md`

Objetivo:
Definir el camino completo de onboarding de una fuente sin improvisar pasos.

Workflow:
1. Crea o valida el registro base de la fuente.
2. Determina el access status.
3. Clasifica el delivery mode.
4. Elige parser family o marca la fuente para manual review.
5. Define config, fixture y QA gates.
6. Decide si queda production eligible o bloqueada.

Output esperado:
- checklist de onboarding
- estado final de la fuente
- dependencias pendientes

Reglas:
- No marcar production eligible sin policy, family y QA definidos.

Errores comunes:
- saltar directo a runtime code
- ignorar estados `permission_required` o `legal_review`
