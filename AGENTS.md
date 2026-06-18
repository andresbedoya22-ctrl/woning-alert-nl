# AGENTS.md

Reglas permanentes para cualquier agente que trabaje en este repositorio `WoningAlert NL`.

## Direccion del proyecto

Nueva direccion: `PORTAL-FIRST NATIONAL INVENTORY`.

Objetivo del producto: revisar fuentes nacionales de vivienda una vez al dia, guardar inventario propio, detectar nuevas, removidas y cambiadas, cruzar ese inventario con busquedas de clientes y generar recomendaciones operativas. `Woning Scanner` queda para una fase posterior sobre una base ya estable.

## Reglas hard

- Ejecutar todo en Windows con PowerShell. No asumir Bash.
- Trabajar por fases.
- Hacer cambios pequenos y testeados.
- No mezclar fases en una misma tarea.
- No tocar `PropertyDiscovery`.
- No leer ni escribir en `data/raw` salvo pedido explicito del usuario.
- No construir scrapers en esta fase.
- No dashboard antes de `Daily Sync v1` + `Client Matching v1`.
- No scanner antes de matching.
- No makelaar-by-makelaar como camino principal.
- No CAPTCHA solving.
- No `2Captcha`.
- No proxy rotation.
- No login falso.
- No fingerprint spoofing.
- No anti-bot bypass.
- Funda solo `benchmark-only` sin permiso explicito.
- Pararius solo `benchmark` y `permission-required`, salvo autorizacion explicita.
- Stop si aparece `403`, `429`, CAPTCHA o login wall.
- Registrar `source_status` y continuar con otras fuentes cuando sea seguro hacerlo.
- Si una fuente falla: no borrar propiedades de esa fuente, fijar `safe_to_compare_removals=false` y usar el ultimo inventario exitoso como `stale`.
- No usar `git add .`.
- No hacer commit sin permiso explicito del usuario.
- No modificar codigo si el pedido solo requiere documentacion o instrucciones operativas.

## Orden por fases

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

## Validacion obligatoria

Cuando se modifique codigo, la validacion minima obligatoria es:

```powershell
py -3.12 -m pytest
```

Si el entorno no usa `py -3.12`, al menos correr:

```powershell
python -m pytest tests -o cache_dir=tmp.pytest_cache --basetemp=tmp\pytest_phase0a
```

No declarar una tarea como terminada si hubo cambios de codigo y esa validacion no corrio o no paso, salvo aceptacion explicita del usuario.

## Manejo de fallas por fuente

- Un fallo de una fuente no debe tumbar el run completo.
- No borrar inventario previo de una fuente fallida.
- No asumir removals reales si la captura de una fuente fallo.
- Mantener el ultimo inventario exitoso como referencia `stale` hasta recuperar la fuente.

## Artefactos que no deben commitearse

- `.env`
- `.env.*`
- `tmp/`
- `.pytest_cache/`
- `data/raw/`
- `data/diagnostics/`
- `data/cache/`
- `cache/`
- HTML masivo, cache HTML y artefactos transitorios similares
- outputs generados en `data/property_discovery/`
- outputs generados en `data/discovery/latest/`
- outputs generados en `data/discovery/platform_fingerprint/`
- outputs generados en `data/email_previews/`
- outputs generados en `data/matching/`
- outputs generados en `data/source_debug/`

## Disciplina operativa

- Preferir cambios minimos y trazables.
- Antes de staged o commit, seleccionar archivos de forma explicita.
- Si aparecen outputs generados en `git status`, dejarlos fuera del commit salvo instruccion explicita.
