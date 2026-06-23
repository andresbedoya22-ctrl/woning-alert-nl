# N8N Orchestration

Cuando usarla:
Usa esta skill para disenar workflows n8n alrededor del backend del repo.

Que archivos leer:
- `AGENTS.md`
- `docs/10_N8N_ORCHESTRATION.md`
- docs de inventory y matching si aplica

Objetivo:
Disenar orquestacion segura y comprensible sin convertir n8n en el scraper.

Workflow:
1. Define el backend job exacto que n8n dispara.
2. Disena schedule, error workflow y notificaciones.
3. Marca limites de retry y policy.
4. Separa triggers de logica de negocio.

Output esperado:
- diseno de workflow n8n
- triggers
- manejo de errores

Reglas:
- n8n no reemplaza parser families ni policy logic.

Errores comunes:
- meter scraping o decisiones de policy directamente en nodos n8n
- usar AI para extraccion masiva
