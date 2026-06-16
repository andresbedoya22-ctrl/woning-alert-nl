# AGENTS.md

Reglas permanentes para cualquier agente que trabaje en este repositorio `Domek Wonen`.

## Objetivo del pipeline

El pipeline de Domek Wonen existe para detectar viviendas nuevas publicadas por makelaars, normalizarlas, deduplicarlas, preparar inventario util para matching con clientes activos y producir resultados antes de que un asesor tenga que buscar manualmente.

## Reglas hard

- Ejecutar todo en Windows con PowerShell. No asumir Bash.
- No usar Funda.
- No usar Pararius salvo pedido explicito del usuario.
- No leer ni escribir en `data/raw` salvo pedido explicito del usuario.
- No borrar outputs generados del pipeline.
- No usar `git add .`.
- No hacer commit sin permiso explicito del usuario.
- No modificar codigo si el pedido solo requiere documentacion o instrucciones operativas.

## Carpetas y artefactos generados que no deben commitearse

No commitear outputs generados por ejecuciones del pipeline, especialmente:

- `data/property_discovery/`
- `data/property_discovery/latest/`
- `data/property_discovery/runs/`
- `data/discovery/latest/`
- `data/discovery/platform_fingerprint/`
- `data/email_previews/`
- `data/matching/`
- `data/diagnostics/`
- `data/source_debug/`

Si un cambio necesita ejemplos o evidencia, referenciar los archivos generados localmente sin agregarlos al commit.

## Validacion obligatoria

Cuando se modifique codigo, la validacion minima obligatoria es:

```powershell
py -3.12 -m pytest
```

No declarar una tarea como terminada si hubo cambios de codigo y esa validacion no corrio o no paso, salvo que el usuario acepte explicitamente esa excepcion.

## Reglas de `clean_available`

- `clean_available` es el unico conjunto permitido como entrada a Matching v1.
- `clean_available` debe representar propiedades normalizadas, deduplicadas y disponibles para matching.
- No mezclar en matching propiedades rechazadas, duplicadas, invalidas o fuera de disponibilidad.
- Si hay dudas entre `property_inventory`, `property_candidates` y `matching_ready_inventory`, usar solo el output que represente `clean_available`.

## Reglas de Matching v1

- Matching v1 debe usar solo `clean_available`.
- No descartar una propiedad solo porque falten campos opcionales.
- `bedrooms_count` puede ser filtro duro cuando el cliente define `min_bedrooms`.
- `rooms_count` no sustituye `bedrooms_count` salvo señal clara.
- ubicacion/zona debe poder ser filtro duro.
- `m2` y `energy_label` siguen siendo scoring/warnings salvo que el cliente los marque como obligatorios.
- `rooms`, `m2` y `energy_label` son opcionales para Matching v1 salvo configuracion explicita del cliente.
- La ausencia de `rooms`, `m2` o `energy_label` no convierte una propiedad en no apta para matching por si sola.
- Los descartes deben basarse en problemas reales de elegibilidad o integridad minima, no en metadata opcional incompleta.

## Disciplina operativa

- Preferir cambios minimos y trazables.
- Antes de staged o commit, seleccionar archivos de forma explicita.
- Si aparecen outputs generados en `git status`, dejarlos fuera del commit salvo instruccion explicita.
