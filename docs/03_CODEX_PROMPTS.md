# Codex Prompt Pack — Domek Wonen v6

## Reglas de uso

1. Un prompt = una tarea pequeña.
2. No permitir cambios masivos sin diff revisable.
3. Pedir tests en cada módulo.
4. Pedir que no borre archivos existentes salvo autorización explícita.
5. Pedir summary final con archivos modificados y comandos ejecutados.

## Prompt 0 — Auditoría inicial del repo

```text
Lee todo el repo y los documentos en /docs. No modifiques nada.

Devuélveme:
1. estructura actual del proyecto;
2. qué módulos existen y cuáles faltan;
3. riesgos técnicos;
4. errores obvios de código;
5. plan de cambios en pasos pequeños para construir Domek Wonen v6.

No ejecutes scrapers largos. Solo inspección, tests rápidos y lectura de archivos.
```

## Prompt 1 — Crear documentación base Codex

```text
Crea una carpeta /docs si no existe y añade estos documentos:
- 00_PROJECT_BRIEF.md
- 01_ARCHITECTURE.md
- 02_DATA_MODEL.md
- 03_DISCOVERY_STRATEGY.md
- 04_CODEX_WORKFLOW.md

Usa el contenido de Domek Wonen v6 como fuente de verdad. No implementes lógica todavía.
```

## Prompt 2 — Normalizar CSV actual del harvester

```text
Construye un script Python en /scripts/import_sources.py que lea output/makelaars_noord_brabant.csv y genere un CSV limpio para importar en Supabase.

Requisitos:
- validar columnas esperadas;
- normalizar URLs;
- deduplicar por root_domain + plaats;
- marcar source_type='makelaar_site';
- discovery_source='nvm_harvester_2026_06';
- needs_review=true si no hay koopaanbod_url;
- generar report de calidad.

Añade tests con un fixture pequeño. No conectes aún a Supabase.
```

## Prompt 3 — Migración Supabase

```text
Crea migración SQL para Domek Wonen v6.

Tablas mínimas:
- offices
- sources
- properties
- property_history
- property_health
- clients
- client_zones
- matches
- match_outcomes
- source_discovery_events

Requisitos:
- checks para estados de vivienda y cliente;
- índice parcial en properties WHERE status='beschikbaar';
- índices por bag_id, postcode, source_id, status;
- timestamps created_at/updated_at;
- comentarios SQL claros.

No construyas frontend. Devuelve comandos para aplicar y verificar.
```

## Prompt 4 — Parser genérico de sources

```text
Construye /scraper/source_fetcher.py y /scraper/parsers/generic_listing_parser.py.

Objetivo:
- leer sources activas desde CSV/JSON local por ahora;
- descargar koopaanbod_url respetando robots.txt y delays;
- detectar links de viviendas;
- devolver PropertyRaw con url, title, prijs, adres aproximado, status, beschrijving.

Requisitos:
- httpx primero;
- Playwright solo si requires_js=true;
- fixtures HTML en /tests/fixtures;
- tests unitarios;
- logs estructurados;
- no usar IA.
```

## Prompt 5 — Agregador Huislijn

```text
Implementa un parser específico para Huislijn como fuente agregadora.

Requisitos:
- entrada: URL de búsqueda/provincia/gemeente;
- salida: PropertyRaw[];
- extraer url, adres, plaats, prijs, type, m² si está disponible;
- detectar makelaar si aparece;
- marcar source_type='aggregator';
- tests con fixture HTML guardado localmente;
- no hacer scraping agresivo;
- no saltarse robots ni bloqueos.
```

## Prompt 6 — Source discovery desde propiedades

```text
Implementa /scraper/source_discovery.py.

Si una propiedad agregadora contiene nombre o URL de makelaar no existente:
1. crear OfficeCandidate;
2. intentar resolver website desde links presentes;
3. si hay website, buscar koopaanbod_url con reglas existentes;
4. asignar confidence_score;
5. guardar evento en source_discovery_events.

No uses Google scraping. No uses Funda. Tests con fixtures.
```

## Prompt 7 — Enrichment PDOK/BAG/EP-Online

```text
Construye /enrichment/enricher.py.

Requisitos:
- resolver dirección con PDOK/BAG si hay postcode/huisnummer;
- guardar bag_id, lat/lng, bouwjaar, oppervlakte si disponible;
- consultar EP-Online por energielabel si hay datos suficientes;
- calcular confidence_score con pesos:
  BAG 25, dirección exacta 25, parser nivel 1 20, precio 15, EP-Online 15;
- tests con mocks, no llamadas reales en tests.
```

## Prompt 8 — Matching

```text
Construye /matching/matching.py.

Requisitos:
- solo properties.status='beschikbaar';
- solo clients.status='actief';
- filtros must;
- score soft;
- guardar matches idempotentes;
- no reenviar el mismo match al mismo cliente;
- explicar score en JSON para auditoría.

Añade tests con 3 clientes y 10 propiedades sintéticas.
```

## Prompt 9 — Emails internos

```text
Construye /notifications/email_renderer.py.

Requisitos:
- email en NL y ES;
- máximo 5 viviendas por cliente por pasada;
- incluir por vivienda: precio, plaats, m², label, días en mercado, confidence_score, razón de match, link;
- CTA interno para marcar outcome;
- no enviar emails reales en tests.
```

## Prompt 10 — Dashboard mínimo

```text
Construye dashboard Next.js mínimo con:
- overview de sources health;
- clientes activos;
- matches enviados;
- afgewezen;
- bezichtigingen;
- ROI por fuente;
- tabla de sources con estado ok/warning/down/manual_review.

Usa componentes simples. Prioriza funcionalidad sobre animaciones.
```
