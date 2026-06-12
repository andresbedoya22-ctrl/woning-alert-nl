# MVP 14 Días — Domek Wonen v6

## Objetivo

Tener un MVP usable por Andres/Sander/Laura con 2-3 clientes reales, aunque el dashboard sea básico.

## Día 1 — Repositorio y docs

- Crear repo.
- Añadir /docs.
- Añadir core v6.
- Añadir reglas Codex.
- Confirmar comandos de setup.

Hecho cuando: `README`, `.env.example`, estructura y docs existen.

## Día 2 — Import sources

- Limpiar CSV del harvester.
- Deduplicar domains.
- Marcar sources incompletas.
- Importar a Supabase o CSV intermedio.

Hecho cuando: sources limpias y reporte de calidad.

## Día 3 — DB

- Migración SQL.
- Índices.
- Tablas de health, matches, outcomes.

Hecho cuando: seed local + queries funcionan.

## Día 4 — Fetcher genérico

- Fetch sources activas.
- Hash/diff.
- robots/delays.
- health básico.

Hecho cuando: 10 sources reales procesadas sin romper.

## Día 5 — Parser genérico

- Extraer links de propiedades.
- Detectar status básico.
- Guardar PropertyRaw.

Hecho cuando: 5 webs propias producen propiedades.

## Día 6 — Agregador 1: Huislijn

- Parser dedicado.
- Detectar propiedades.
- Detectar makelaar si aparece.

Hecho cuando: propiedades NB desde agregador entran al flujo.

## Día 7 — Agregador 2: Vastgoed Nederland aanbod o Huispedia

- Parser dedicado.
- Comparar duplicados.

Hecho cuando: segunda fuente agregadora funciona.

## Día 8 — Dedup + enrichment básico

- Dedup por postcode/huisnummer.
- PDOK/BAG si disponible.
- confidence_score.

Hecho cuando: propiedades duplicadas se fusionan.

## Día 9 — Clientes

- Crear 2-3 clientes manuales.
- Estados actief/deal/wil_niet_kopen.
- Zonas y preferencias.

Hecho cuando: cliente activo entra a matching.

## Día 10 — Matching

- Filtros must.
- Score soft.
- Match explanation.

Hecho cuando: lista ordenada de viviendas por cliente.

## Día 11 — Email preview

- Render NL/ES.
- Preview local.
- No envío real todavía.

Hecho cuando: asesor puede leer matches en formato útil.

## Día 12 — Outcomes

- Marcar interesado/rechazado/bezichtiging.
- Guardar razones.

Hecho cuando: funnel empieza a llenarse.

## Día 13 — Dashboard básico

- Sources health.
- Matches.
- Afgewezen.
- Bezichtigingen.
- ROI por fuente inicial.

Hecho cuando: Sander entiende si el sistema funciona.

## Día 14 — Prueba real controlada

- 2-3 clientes reales.
- 1 pasada diaria.
- Revisión humana antes de enviar.
- Registrar outcomes.

Hecho cuando: sistema genera matches reales revisables.
