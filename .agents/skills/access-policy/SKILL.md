# Access Policy

Cuando usarla:
Usa esta skill para decidir `allowed`, `limited`, `permission_required`, `legal_review` o `blocked`.

Que archivos leer:
- `AGENTS.md`
- `docs/05_ACCESS_POLICY.md`
- `scraper/src/domek_wonen/compliance/robots_gate.py`

Objetivo:
Tomar decisiones de acceso consistentes y justificadas antes de cualquier parser u orchestracion.

Workflow:
1. Verifica robots, terms y senales de bloqueo.
2. Registra login, CAPTCHA, `403`, paywall o dependencias externas.
3. Aplica la taxonomia de estados.
4. Documenta la razon y el comportamiento permitido.

Output esperado:
- decision de policy
- justificacion
- restricciones operativas

Reglas:
- `blocked` significa stop.
- Funda y Pararius no pasan al pipeline operativo por defecto.

Errores comunes:
- tratar `403` como error temporal sin evidencia
- asumir que renderizar una pagina publica equivale a permiso operativo
