# WoningAlert NL

Base del repo para la estrategia `portal-first national inventory`.

## Estrategia

WoningAlert NL apunta a mantener un inventario nacional propio de vivienda, revisado una vez al dia, para detectar propiedades nuevas, removidas y cambiadas, compararlas contra busquedas de clientes y producir recomendaciones operativas. Mas adelante, `Woning Scanner` podra usar ese inventario como capa de top matches, pero no es la prioridad inicial.

## Fuentes

- Huislijn: candidata principal para el inventario portal-first.
- Pararius: benchmark y `permission-required`.
- Funda: `benchmark-only`.
- Makelaar parsers: fallback, no camino principal.
- Email alerts: entrada complementaria.
- BAG, PDOK y EP-Online: enrichment posterior sobre inventario propio.

## Fases 0-9

| Fase | Nombre |
| --- | --- |
| 0 | GitHub/base limpia |
| 1 | Portal Inventory Spike |
| 2 | Huislijn Adapter v1 |
| 3 | Inventory Core v1 |
| 4 | Daily Sync v1 |
| 5 | Client Matching v1 |
| 6 | Email Draft Generator v1 |
| 7 | Multi-source Strategy v1 |
| 8 | Woning Scanner v1 |
| 9 | MVP operativo |

## Reglas clave

- No construir scrapers en esta fase.
- No CAPTCHA solving.
- No proxies.
- No bypass de anti-bot, login wall o protecciones de plataforma.
- Si una fuente falla, el run completo no debe caerse.
- Si una fuente falla, no borrar inventario previo de esa fuente.
- Correr tests antes de commit.

## Comandos base

Instalar dependencias:

```powershell
python -m pip install -r requirements.txt
```

Ejecutar tests:

```powershell
python -m pytest tests -o cache_dir=tmp.pytest_cache --basetemp=tmp\pytest_phase0a
```
