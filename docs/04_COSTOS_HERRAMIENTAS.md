# Herramientas y Costos — Domek Wonen v6

## Nota

Costos estimados a 12/06/2026. Verificar antes de contratar. Mantener spend caps activados.

## MVP barato

| Componente | Herramienta | Plan sugerido | Coste estimado |
|---|---|---:|---:|
| Repo | GitHub | Free/Pro personal | €0-€4/mes |
| Frontend | Vercel | Hobby al inicio, Pro si equipo | $0-$20/mes |
| DB/Auth | Supabase | Free al inicio, Pro al pasar a uso real | $0-$25/mes |
| Worker scraping | Hetzner CX22 | VPS pequeño | ~€3,79/mes |
| Emails | Resend | Free al inicio | $0/mes hasta límite free |
| IA runtime | Claude Haiku / similar | API usage | €5-€30/mes al inicio |
| Maps | Mapbox o alternativa | Free tier inicial | €0 al inicio |
| Dominio | Domek/subdominio | existente | €0 si usa subdominio |

MVP estimado: **€10-€80/mes**, dependiendo de IA y si activas planes Pro.

## Producción ligera

| Componente | Herramienta | Coste estimado |
|---|---|---:|
| Supabase Pro | DB + backups | $25/mes |
| Vercel Pro | frontend equipo | $20/mes por seat/deploying user |
| Hetzner CX22/CX32 | worker | €3,79-€6,80/mes |
| Resend Pro | si supera free o necesita más dominios | $20/mes |
| IA runtime | extracción + resúmenes | €20-€100/mes |
| Observabilidad | Sentry/Logtail opcional | €0-€30/mes |

Producción ligera estimada: **€70-€200/mes**.

## Costes que no conviene asumir en MVP

- Proxies residenciales.
- Bypass de CAPTCHA.
- Scrapers comerciales de Funda.
- Data providers caros sin prueba de ROI.
- Integraciones complejas con BlinqX antes de validar adopción.

## Coste de Codex

Codex debe usarse para construcción modular, no para ejecutar logs largos. Para ahorrar:

- correr scrapers en terminal local;
- pegar solo reportes;
- usar fixtures HTML;
- cerrar sesión después de cada módulo;
- pedir diffs pequeños;
- no pedir análisis de logs completos;
- no pedir “haz todo el sistema”.
