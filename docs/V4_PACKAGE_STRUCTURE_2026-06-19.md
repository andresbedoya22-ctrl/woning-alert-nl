# V4 Package Structure 2026-06-19

## Decision

- Fase 0.2 crea solo la estructura base V4.
- No se archiva nada en Fase 0.2.
- No se mueve código legacy en Fase 0.2.
- Los paquetes existentes se mantienen en su lugar mientras se define la migración de Fase 0.3+.

## New V4 Packages Created

- `scraper/src/domek_wonen/compliance/`
- `scraper/src/domek_wonen/harvest/`
- `scraper/src/domek_wonen/changes/`
- `scraper/src/domek_wonen/extraction/`
- `scraper/src/domek_wonen/validation/`
- `scraper/src/domek_wonen/drafts/`
- `scraper/src/domek_wonen/storage/`

## Existing Packages Kept For Now

- `scraper/src/domek_wonen/discovery/`
- `scraper/src/domek_wonen/matching/`
- `scraper/src/domek_wonen/inventory/`
- `scraper/src/domek_wonen/portals/`
- `scraper/src/domek_wonen/properties/`
- `scraper/src/domek_wonen/diagnostics/`
- `scraper/src/domek_wonen/recommendations/`
- `scraper/src/domek_wonen/woning_scanner/`

## Legacy Packages Not Moved Yet

- `discovery/`
- `matching/`
- `inventory/`
- `portals/`
- `properties/`
- `diagnostics/`
- `recommendations/`
- `woning_scanner/`

La decisión explícita de Fase 0.2 es mantenerlos intactos hasta que exista un plan de archivado o migración por fases.

## Provisional V4 Map

| Package | Provisional responsibility |
| --- | --- |
| `compliance` | robots/legal gates |
| `discovery` | source census / discovery strategy |
| `harvest` | card harvester source-agnostic |
| `changes` | fingerprint/change detection |
| `matching` | coarse/fine match |
| `extraction` | OpenAI extraction after coarse match |
| `validation` | validation/confidence |
| `drafts` | advisor drafts later |
| `storage` | SQLite/Postgres memory later |
| `inventory` | future inventory core |
| `portals` | portal probes/adapters, especially Huislijn |
| `properties` | reusable legacy/fallback property parsing |
| `diagnostics` | audits/reports |

## Notes

- `compliance`, `harvest`, `changes`, `extraction`, `validation`, `drafts`, and `storage` are package skeletons only.
- No functional behavior was added in this step.
- Minimal import-only tests were added to reserve these package names safely inside the repo.
