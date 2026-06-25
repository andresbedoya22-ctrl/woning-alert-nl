# Delivery Mode Fingerprint

Cuando usarla:
Usa esta skill para clasificar una fuente por su delivery mode tecnico.

Que archivos leer:
- `AGENTS.md`
- `docs/03_MAKELAAR_DELIVERY_MODES.md`
- `docs/05_ACCESS_POLICY.md`
- artefactos o scripts de fingerprint relevantes

Objetivo:
Determinar con evidencia si una fuente encaja en un parser family reutilizable o debe quedar bloqueada o en manual review.

Workflow:
1. Revisa acceso permitido antes de interpretar estructura.
2. Busca evidencia de cards, JSON-LD, XHR, iframes, WordPress, Realworks u otros patrones.
3. Asigna un delivery mode con confianza y evidencia.
4. Propone parser family candidate y accion recomendada.

Output esperado:
- delivery mode clasificado
- confidence
- evidencia concreta
- siguiente accion recomendada

Reglas:
- No usar marca del makelaar como sustituto del patron tecnico.
- `funda_iframe_blocked` y `pararius_external_blocked` no son rutas operativas.

Errores comunes:
- clasificar `iframe_external` sin revisar el dominio embebido
- asumir XHR usable sin policy review
