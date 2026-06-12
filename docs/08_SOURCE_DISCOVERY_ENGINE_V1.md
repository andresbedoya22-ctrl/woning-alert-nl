# Source Discovery Engine v1

## 1. Objetivo del motor

El objetivo de Domek Wonen no es mantener una lista manual de makelaars, sino construir un motor de discovery replicable, auditable y automatizable que permita, para cualquier provincia de Holanda:

- encontrar makelaars relevantes;
- identificar sus websites oficiales;
- localizar un `aanbod_url` de compra cuando exista;
- calificar la calidad de ese `aanbod_url`;
- medir cobertura por `gemeente`;
- detectar y consolidar duplicados;
- producir un reporte final reutilizable por operaciones y por producto.

Este motor debe correr primero por CLI y después integrarse en el panel admin para ejecuciones mensuales programadas.

## 2. Inputs

El pipeline debe aceptar estos inputs mínimos:

- `province`
  Valor canónico de provincia, por ejemplo `Noord-Brabant`.
- `gemeenten_list`
  Lista de gemeenten pertenecientes a la provincia objetivo.
- `existing_seed`
  Seed previo opcional o recomendado con oficinas ya conocidas, websites previos, `aanbod_url` previos y señales históricas.
- `search_api_key`
  API key opcional para un proveedor de búsqueda. En MVP se diseña para `Google Custom Search JSON API`.

Inputs auxiliares recomendados:

- `province_config`
  Configuración específica de la provincia, incluyendo aliases, grandes ciudades, dominios frecuentes y límites de rate.
- `run_id`
  Identificador único de ejecución para trazabilidad.
- `output_dir`
  Carpeta donde se escriben artefactos del run.

## 3. Outputs

Cada ejecución debe producir como mínimo:

- `makelaar_sources_master.csv`
  Dataset maestro con candidatos, fuentes, evidencia, score, estado final y atribución.
- `discovery_run_report.md`
  Reporte legible para humanos con resumen ejecutivo, métricas, gaps, cambios y decisiones automáticas.
- `gemeente_coverage_after_discovery.csv`
  Cobertura por gemeente después del proceso de deduplicación y scoring.
- `rejected_candidates.csv`
  Candidatos descartados con razón explícita de rechazo.

Campos mínimos sugeridos para `makelaar_sources_master.csv`:

- `run_id`
- `province`
- `gemeente`
- `office_name`
- `official_website`
- `root_domain`
- `source_adapter`
- `source_origin_url`
- `source_query`
- `membership_hint`
- `aanbod_url`
- `aanbod_url_quality`
- `platform_fingerprint`
- `candidate_score`
- `candidate_status`
- `duplicate_group_id`
- `evidence_count`
- `review_reason`
- `discovered_at`

## 4. Arquitectura por capas

La arquitectura debe separar adquisición, validación, scoring y reporting. Los nombres técnicos de clases o módulos deben mantenerse en inglés.

### `SeedAdapter`

Responsabilidad:

- cargar el seed existente;
- normalizar columnas;
- convertir seeds anteriores en candidatos de entrada;
- preservar histórico y trazabilidad.

No debe:

- sobrescribir la decisión final de otros adapters;
- actuar como única fuente de verdad.

### `SearchApiAdapter`

Responsabilidad:

- ejecutar queries estructuradas por `gemeente`;
- consultar APIs de búsqueda aprobadas;
- devolver candidatos con título, snippet, URL, dominio y query de origen.

No debe:

- scrapear páginas HTML de resultados de Google;
- depender de una sola query por gemeente.

### `DirectoryAdapter`

Responsabilidad:

- consultar directorios públicos y asociaciones relevantes;
- detectar oficinas, webs y señales de membresía;
- generar candidatos con fuerte atribución de origen.

Ejemplos de fuentes esperadas:

- NVM;
- Vastgoed Nederland;
- VBO;
- otros directorios públicos autorizados.

### `AggregatorAttributionAdapter`

Responsabilidad:

- usar agregadores como fuente secundaria de discovery;
- inferir makelaars y websites a partir de listings visibles;
- aportar evidencia adicional sobre actividad real y cobertura geográfica.

Regla clave:

- los agregadores enriquecen y revelan candidatos, pero no son la verdad canónica del `official_website`.

### `WebsiteAnalyzer`

Responsabilidad:

- validar si un dominio parece ser el website oficial de una oficina;
- detectar branding, datos de contacto, geografía visible y señales de consistencia;
- descartar landings ambiguas o micrositios no oficiales.

Señales típicas:

- nombre de oficina en homepage;
- logo, footer o contacto consistente;
- presencia de gemeente o regio;
- enlaces internos relacionados con compra de viviendas.

### `AanbodUrlFinder`

Responsabilidad:

- localizar la URL más probable de compra dentro del website oficial;
- distinguir entre páginas comerciales y páginas reales de inventario;
- clasificar la calidad del `aanbod_url`.

### `CandidateScorer`

Responsabilidad:

- transformar señales heterogéneas en una decisión consistente;
- asignar `valid`, `suspect`, `missing` o `rejected`;
- explicar por qué una fuente quedó en ese estado.

### `DedupeEngine`

Responsabilidad:

- consolidar duplicados entre seeds, búsquedas, directorios y agregadores;
- operar sobre `root_domain`, `office_name`, teléfonos, emails, branding y geografía;
- mantener evidencia agregada por candidato final.

### `CoverageReporter`

Responsabilidad:

- medir cobertura por `gemeente`;
- identificar municipios sin cobertura o con cobertura débil;
- producir comparativas contra seeds y runs anteriores.

## 5. Flujo end-to-end

Flujo objetivo:

`province -> gemeenten -> queries -> candidate domains -> website validation -> aanbod discovery -> scoring -> dedupe -> report`

Desglose operativo:

1. Cargar `province`, `gemeenten_list`, seed previo y configuración.
2. Expandir queries por `gemeente`.
3. Ejecutar discovery multi-fuente mediante `SearchApiAdapter`, `DirectoryAdapter` y `AggregatorAttributionAdapter`.
4. Normalizar URLs, dominios, nombres y atribución.
5. Agrupar candidatos por dominio y oficina probable.
6. Validar websites oficiales con `WebsiteAnalyzer`.
7. Buscar `aanbod_url` con `AanbodUrlFinder`.
8. Asignar score y estado con `CandidateScorer`.
9. Consolidar duplicados con `DedupeEngine`.
10. Medir cobertura final por `gemeente`.
11. Escribir CSVs y `discovery_run_report.md`.

## 6. Search API strategy

El motor debe usar una estrategia de búsqueda basada en APIs oficiales y no en scraping de páginas de resultados.

Proveedor MVP:

- `Google Custom Search JSON API`

Proveedor opcional futuro:

- `Bing/Search provider`

Reglas:

- no scraping de Google result pages;
- conservar la query exacta que produjo cada candidato;
- ejecutar múltiples queries por `gemeente`;
- deduplicar resultados entre queries y entre proveedores;
- degradar con elegancia si no hay API key, usando seed + directorios + agregadores disponibles.

## 7. Query templates

Templates iniciales por `gemeente`:

- `makelaar koopwoningen {gemeente}`
- `woningaanbod makelaar {gemeente}`
- `NVM makelaar {gemeente}`
- `Vastgoed Nederland makelaar {gemeente}`
- `VBO makelaar {gemeente}`
- `site:.nl makelaar {gemeente} koopwoningen`
- `site:.nl {gemeente} makelaardij aanbod`
- `site:.nl {gemeente} makelaar wonen`

Reglas de uso:

- ejecutar varias queries por `gemeente`, no una sola;
- registrar performance por template;
- permitir aliases de `gemeente` y combinaciones con `provincie`;
- priorizar dominios `.nl`, pero no bloquear otros dominios si la oficina es válida.

## 8. Aanbod URL discovery strategy

`AanbodUrlFinder` debe combinar varias técnicas porque no todas las webs usan la misma estructura.

Fuentes de señal:

- `common paths`
- `sitemap.xml`
- `homepage links`
- `internal crawl depth 2`
- `JSON-LD`
- `platform fingerprints`

### Common paths

Probar rutas frecuentes como:

- `/aanbod`
- `/woningaanbod`
- `/koopwoningen`
- `/koop`
- `/wonen`
- `/huizen-aanbod`
- `/objecten`

### Sitemap inspection

Leer `sitemap.xml` y sub-sitemaps para:

- detectar URLs con patrones de aanbod;
- identificar taxonomías internas;
- reducir crawling innecesario.

### Homepage links

Analizar navegación principal, footer y CTAs para encontrar enlaces hacia compra o listings activos.

### Internal crawl depth 2

Permitir un crawl interno acotado a profundidad 2 para:

- explorar categorías hijas;
- seguir enlaces de navegación relevantes;
- evitar crawls abiertos o costosos.

### JSON-LD

Buscar datos estructurados que indiquen:

- `RealEstateAgent`;
- `ItemList`;
- `Offer`;
- breadcrumbs o enlaces canónicos útiles.

### Platform fingerprints

Detectar plataformas y patrones conocidos, por ejemplo:

- Realworks;
- Kolibri;
- Skarabee;
- Pyber;
- EyeMove / Yes-Co;
- WordPress custom.

Esto permite inferir rutas probables y reglas reutilizables sin escribir un scraper distinto por oficina desde el día 1.

## 9. Exclusion rules

El motor debe excluir URLs que parecen contenido comercial, informativo o institucional, no inventario real.

Patrones mínimos de exclusión:

- `verkoopadvies`
- `gratis-verkoopadvies`
- `waardebepaling`
- `taxatie`
- `contact`
- `over-ons`
- `diensten`
- `hypotheek`
- `blog`
- `nieuws`
- `privacy`
- `reviews`
- `aankoopmakelaar`
- `verkoopmakelaar`

Reglas:

- una URL excluida no debe considerarse `aanbod_url`;
- si solo se detectan URLs excluidas, el estado debe tender a `missing` o `suspect`, no a `valid`;
- los patrones deben ser configurables y ampliables por run.

## 10. Scoring model

El modelo inicial debe ser simple, explicable y suficiente para operaciones.

### `valid`

Definición:

- website oficial plausible confirmado;
- `aanbod_url` de compra encontrado;
- evidencia consistente de que la URL apunta a listings reales.

### `suspect`

Definición:

- existe website plausible;
- existe URL candidata;
- la señal es incompleta, ambigua o demasiado comercial.

### `missing`

Definición:

- se confirmó razonablemente la oficina o el website;
- no se logró localizar `aanbod_url` fiable.

### `rejected`

Definición:

- el candidato no es makelaar relevante;
- el dominio no es oficial;
- la evidencia es demasiado débil;
- o el resultado cae en reglas de exclusión duras.

Señales que pueden alimentar el score:

- coincidencia de `office_name` con branding visible;
- consistencia de `gemeente` o regio;
- multiplicidad de fuentes independientes;
- profundidad del enlace hacia aanbod;
- fingerprint de plataforma compatible;
- presencia de listings o `ItemList`;
- conflicto entre fuentes o evidencia contradictoria.

## 11. Monthly automation design

El diseño debe nacer pensando en automatización mensual.

Capacidades esperadas:

- `admin panel trigger`
- `scheduled monthly run`
- `diff vs previous run`
- `new sources`
- `removed/dead sources`
- `changed aanbod_url`

### Admin panel trigger

En el futuro, un usuario interno debe poder lanzar un run por provincia desde el panel admin:

- seleccionando provincia;
- opcionalmente ajustando límites o providers;
- reusando la misma configuración del CLI.

### Scheduled monthly run

Debe existir un job mensual por provincia o por lote de provincias que:

- reutilice seeds del run anterior;
- recalcule cobertura;
- regenere scoring y estados.

### Diff vs previous run

Cada run debe compararse contra el anterior para responder:

- qué fuentes nuevas aparecieron;
- qué fuentes desaparecieron;
- qué dominios dejaron de responder;
- qué `aanbod_url` cambió;
- qué gemeenten mejoraron o empeoraron su cobertura.

## 12. Safety/legal

Restricciones obligatorias:

- `respect robots.txt`
- `rate limits`
- `identifiable user-agent`
- `no Funda scraping`

Interpretación operativa:

- respetar `robots.txt` en website discovery y crawling interno;
- imponer rate limits por dominio y por proveedor;
- usar un `User-Agent` identificable para tráfico automatizado;
- no implementar scraping de Funda;
- no intentar bypass de CAPTCHA;
- limitar profundidad y volumen de requests para reducir riesgo técnico y legal.

## 13. MVP implementation plan

El MVP debe enfocarse en entregar un motor operable, no en cubrir todo Holanda desde el primer día.

Fases:

- `CLI first`
- `Noord-Brabant first`
- `then all provinces`

### Fase 1: CLI first

Entregar un comando único que:

- reciba provincia y configuración;
- ejecute el pipeline completo;
- escriba outputs reproducibles en disco.

### Fase 2: Noord-Brabant first

Usar Noord-Brabant como provincia piloto porque ya existe contexto previo, seed y métricas base.

Objetivo:

- validar arquitectura;
- medir ruido real;
- ajustar scoring, dedupe y coverage.

### Fase 3: then all provinces

Generalizar por configuración, no por código ad hoc:

- swap de `province_config`;
- swap de `gemeenten_list`;
- mismas capas, mismas salidas y misma semántica.

## 14. Acceptance criteria

El diseño de v1 se considera listo para implementación cuando cumpla estas condiciones:

- one command runs the full discovery for Noord-Brabant
- report shows missing/added/valid/suspect/rejected
- can rerun idempotently
- province config can be swapped later

Interpretación práctica:

- el pipeline no depende de listas manuales pequeñas como solución principal;
- usa múltiples fuentes, no solo seed o directorio único;
- produce resultados trazables por query, fuente y evidencia;
- permite reruns sin corromper estados anteriores;
- deja preparado el salto posterior a automatización mensual y panel admin.

## Decisiones explícitas de alcance

- No implementar código todavía.
- No scraping de Funda.
- No CAPTCHA bypass.
- No listas manuales pequeñas como solución principal.
- El motor debe ser replicable por provincia.
- El motor debe usar fuentes múltiples.

## Resumen ejecutivo

`Source Discovery Engine v1` define un pipeline de discovery provincial, multi-fuente y auditable para construir el censo operativo de makelaars y sus `aanbod_url`. La prioridad no es una lista manual más grande, sino una máquina repetible que descubra, valide, puntúe, deduplique y reporte fuentes de forma consistente hoy por CLI y mañana desde el admin panel.
