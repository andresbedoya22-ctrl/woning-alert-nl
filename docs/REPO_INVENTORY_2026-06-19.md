# REPO INVENTORY 2026-06-19

## A. Resumen ejecutivo

- Estado general del repo: base Python funcional, con `pytest` verde (`252 passed`) y una mezcla de tres líneas de trabajo: `portal-first national inventory`, discovery de fuentes/makelaars, y un pipeline legacy de property discovery + matching.
- Rama actual: `portal-first-national-inventory`.
- Estado git al inicio: tres archivos no trackeados ajenos a esta tarea:
  - `scraper/src/domek_wonen/portals/huislijn_url_discovery.py`
  - `scripts/run_huislijn_url_discovery.py`
  - `tests/test_huislijn_url_discovery.py`
- Último commit: `8c21f7b feat: add live bounded CLI for portal inventory spike`.
- Python detectado: `Python 3.12.10` vía `py -3.12 --version` y `python --version`.
- Validación ejecutada sin cambios: `py -3.12 -m pytest` => `252 passed in 100.21s`.
- Qué parece pertenecer al proyecto viejo:
  - seed/import basado en `NVM harvester` (`scripts/import_sources.py`, `data/processed/sources_seed_noord_brabant.csv`, varias docs viejas);
  - pipeline `property discovery` makelaar-by-makelaar;
  - módulos de `email preview` y `matching` que parten de inventario ya generado;
  - placeholders `recommendations` y `woning_scanner`.
- Qué piezas parecen reutilizables para WoningAlert NL V4:
  - clasificación de bloqueo/HTTP y fetch acotado;
  - normalización de URLs, ciudades y deduplicación;
  - modelos/tablas de inventario;
  - source registry/legal registry/overrides;
  - auditorías de fingerprint/delivery mode y coverage;
  - parser Realworks y clasificadores de property/detail URLs.
- Riesgos inmediatos antes de modificar código:
  - el repo combina dirección nueva en `README.md` con bastante lógica heredada de `PropertyDiscovery`, que AGENTS prohíbe tocar en esta fase;
  - hay outputs y CSVs heredados que todavía condicionan decisiones de diseño;
  - existen módulos portal-spike/Huislijn no integrados con un core de inventario diario;
  - la separación entre artefactos reutilizables y legacy todavía no está explicitada en el código.

## B. Árbol de carpetas relevante

### `scraper/src/domek_wonen/`

```text
scraper/src/domek_wonen/
├─ diagnostics/
│  ├─ delivery_mode_evidence_enrichment.py
│  ├─ delivery_mode_fingerprint_audit.py
│  ├─ property_discovery_selection_quality_audit.py
│  ├─ source_coverage_map.py
│  └─ source_recovery_tracker.py
├─ discovery/
│  ├─ aanbod_auditor.py
│  ├─ aanbod_finder.py
│  ├─ config.py
│  ├─ dedupe.py
│  ├─ discovery_artifacts.py
│  ├─ engine.py
│  ├─ models.py
│  ├─ overpass_adapter.py
│  ├─ place_mapper.py
│  ├─ platform_fingerprint.py
│  ├─ query_generator.py
│  ├─ reporter.py
│  ├─ scorer.py
│  ├─ search_api_adapter.py
│  ├─ seed_adapter.py
│  ├─ source_master_builder.py
│  ├─ website_analyzer.py
│  └─ website_resolver.py
├─ inventory/
│  └─ __init__.py
├─ matching/
│  ├─ email_preview.py
│  └─ matching_v1.py
├─ portals/
│  ├─ adapters/
│  │  ├─ funda.py
│  │  ├─ huislijn.py
│  │  └─ pararius.py
│  ├─ models/
│  │  └─ listing.py
│  ├─ huislijn_url_discovery.py
│  ├─ live_fetch.py
│  └─ portal_inventory_spike.py
├─ properties/
│  ├─ platform_parsers/
│  │  └─ realworks_parser.py
│  ├─ address_quality.py
│  ├─ detail_page_extractor.py
│  ├─ listing_page_crawler.py
│  ├─ models.py
│  ├─ platform_parser_registry.py
│  ├─ property_card_extractor.py
│  ├─ property_dedupe.py
│  ├─ property_discovery_engine.py
│  ├─ property_reporter.py
│  ├─ property_status_classifier.py
│  ├─ property_url_classifier.py
│  ├─ source_capture_audit.py
│  ├─ source_loader.py
│  └─ source_parser_config.py
├─ recommendations/
│  └─ __init__.py
└─ woning_scanner/
   └─ __init__.py
```

### `scripts/`

```text
scripts/
├─ analyze_coverage.py
├─ build_source_master.py
├─ compare_expected_gemeenten.py
├─ debug_kin_source.py
├─ import_sources.py
├─ normalize_places.py
├─ property_discovery_worker.py
├─ run_delivery_mode_evidence_enrichment.py
├─ run_delivery_mode_fingerprint_audit.py
├─ run_email_preview_v1.py
├─ run_huislijn_url_discovery.py
├─ run_matching_v1.py
├─ run_platform_fingerprint_audit.py
├─ run_portal_inventory_spike.py
├─ run_property_discovery.py
├─ run_property_discovery_selection_quality_audit.py
├─ run_source_coverage_map.py
├─ run_source_discovery.py
├─ run_source_recovery_tracker.py
├─ run_target_area_platform_fingerprint.py
└─ run_target_area_source_capture_audit.py
```

### `tests/`

```text
tests/
├─ test_address_quality.py
├─ test_aggregator_registry.py
├─ test_analyze_coverage.py
├─ test_debug_kin_source.py
├─ test_delivery_mode_evidence_enrichment.py
├─ test_delivery_mode_fingerprint_audit.py
├─ test_detail_page_extractor.py
├─ test_discovery_aanbod_auditor.py
├─ test_discovery_aanbod_finder.py
├─ test_discovery_artifacts.py
├─ test_discovery_dedupe.py
├─ test_discovery_engine.py
├─ test_discovery_overpass_adapter.py
├─ test_discovery_place_mapper.py
├─ test_discovery_query_generator.py
├─ test_discovery_reporter.py
├─ test_discovery_scorer.py
├─ test_discovery_search_api_adapter.py
├─ test_email_preview.py
├─ test_huislijn_url_discovery.py
├─ test_import_sources.py
├─ test_listing_page_crawler.py
├─ test_live_fetch.py
├─ test_matching_v1.py
├─ test_normalize_places.py
├─ test_platform_fingerprint_audit.py
├─ test_portal_inventory_spike.py
├─ test_property_card_extractor.py
├─ test_property_dedupe.py
├─ test_property_discovery_engine.py
├─ test_property_discovery_selection_quality_audit.py
├─ test_property_source_loader.py
├─ test_property_status_classifier.py
├─ test_property_url_classifier.py
├─ test_realworks_parser.py
├─ test_run_property_discovery_cli.py
├─ test_run_source_discovery_cli.py
├─ test_source_coverage_map.py
├─ test_source_master_builder.py
├─ test_source_recovery_tracker.py
├─ test_target_area_platform_fingerprint.py
├─ test_target_area_source_capture_audit.py
└─ test_website_resolver.py
```

### `fixtures/`

```text
fixtures/
├─ benchmarks/
│  └─ kin_tilburg_250k_expected.csv
└─ matching/
   └─ clients/
      ├─ client_test_apartment_260k_001.json
      └─ client_test_brabant_001.json
```

### `data/` solo carpetas + tamaños aproximados

```text
data/
├─ config/                  ~0 MB
├─ diagnostics/            ~0.20 MB
├─ discovery/              ~5.80 MB
├─ email_previews/         ~0.08 MB
├─ matching/               ~0.12 MB
├─ platform_fingerprint/   ~0.05 MB
├─ processed/              ~0.12 MB
├─ properties/             ~0.80 MB
├─ property_discovery/     ~5.54 MB
├─ raw/                    ~0.09 MB
├─ source_capture_audit/   ~0.03 MB
└─ source_debug/           ~1.69 MB
```

### Módulos Python bajo `scraper/src/domek_wonen/`

| Ruta | Propósito probable | Dependencias internas evidentes | Clasificación |
| --- | --- | --- | --- |
| `scraper/src/domek_wonen/__init__.py` | Entry point del paquete. | Ninguna. | reusable |
| `diagnostics/delivery_mode_evidence_enrichment.py` | Enriquecer inventario de delivery mode con evidencia HTML/fetch. | `discovery_artifacts`, `website_fetcher`. | reusable |
| `diagnostics/delivery_mode_fingerprint_audit.py` | Auditar modo de entrega y bloqueos por fuente. | `discovery_artifacts`, `platform_fingerprint`, `website_fetcher`. | reusable |
| `diagnostics/property_discovery_selection_quality_audit.py` | Auditar calidad de selección del pipeline de property discovery. | `matching_v1`, `platform_parser_registry`. | legacy |
| `diagnostics/source_coverage_map.py` | Mapear cobertura por fuente/plataforma y cuellos de botella. | `discovery_artifacts`, `platform_fingerprint`, `platform_parser_registry`. | reusable |
| `diagnostics/source_recovery_tracker.py` | Rastrear benchmark esperado a través del funnel candidates/rejected/matching-ready. | `matching_v1`. | reusable |
| `discovery/aanbod_auditor.py` | Auditar si una web tiene URL de aanbod residencial válida. | `discovery.models` implícito por tipo de uso. | reusable |
| `discovery/aanbod_finder.py` | Clasificar y derivar aanbod/listing URLs. | `website_fetcher` en tests/uso. | reusable |
| `discovery/config.py` | Constantes de paths y queries de discovery. | Consumido por `engine.py`. | review |
| `discovery/dedupe.py` | Deduplicar source candidates. | `discovery.models`. | reusable |
| `discovery/discovery_artifacts.py` | Resolver/restaurar artefactos `makelaar_sources_master`. | `engine.py`, diagnósticos. | reusable |
| `discovery/engine.py` | Motor principal de source discovery. | casi todo `discovery/*`, `source_master_builder`. | review |
| `discovery/models.py` | Modelos de candidates, queries y audit attempts. | Usado por todo `discovery/*`. | reusable |
| `discovery/overpass_adapter.py` | Adaptador Overpass para descubrir oficinas. | `discovery.models`. | review |
| `discovery/place_mapper.py` | Normalización de ciudades/gemeenten. | `query_generator`, `engine`. | reusable |
| `discovery/platform_fingerprint.py` | Detectar plataforma target por HTML/url. | `website_fetcher`. | reusable |
| `discovery/query_generator.py` | Generar queries tipo market-search. | `config`, CSVs de referencia. | legacy |
| `discovery/reporter.py` | Construir markdown/reportes de discovery. | `discovery.models`. | reusable |
| `discovery/scorer.py` | Puntuar source candidates. | `discovery.models`. | reusable |
| `discovery/search_api_adapter.py` | Adaptador opcional a search API externa. | `discovery.models`. | review |
| `discovery/seed_adapter.py` | Convertir seed CSV heredado a `SourceCandidate`. | `discovery.models`. | legacy |
| `discovery/source_master_builder.py` | Construir `makelaar_sources_master.csv`. | `discovery.models`. | reusable |
| `discovery/website_analyzer.py` | Señales simples sobre sitio web candidato. | `discovery.models`. | review |
| `discovery/website_fetcher.py` | Fetch HTML liviano y extracción de links. | Base para discovery/fingerprint. | reusable |
| `discovery/website_resolver.py` | Resolver websites faltantes desde seed/manual review. | `discovery.models`. | review |
| `inventory/__init__.py` | Placeholder de paquete inventory. | Ninguna. | unclear |
| `matching/__init__.py` | Reexport de matching. | `matching_v1`. | reusable |
| `matching/email_preview.py` | Generar previews HTML ES/NL y advisor report. | `matching_v1`. | legacy |
| `matching/matching_v1.py` | Matching local contra inventario. | Consumido por diagnósticos y CLI. | reusable |
| `portals/__init__.py` | Namespace portal-facing. | Ninguna. | reusable |
| `portals/adapters/__init__.py` | Reexport de adapters portal. | `funda`, `huislijn`, `pararius`. | review |
| `portals/adapters/funda.py` | Parser de cards Funda para benchmark-only. | `portals.models`, `portal_inventory_spike`. | legacy |
| `portals/adapters/huislijn.py` | Parser de cards Huislijn para spike. | `portals.models`, `portal_inventory_spike`. | reusable |
| `portals/adapters/pararius.py` | Parser de cards Pararius para benchmark/permiso. | `portals.models`, `portal_inventory_spike`. | legacy |
| `portals/huislijn_url_discovery.py` | Probar URLs/caminos de Huislijn y registrar señales. | `live_fetch`, `portal_inventory_spike`. | reusable |
| `portals/live_fetch.py` | Fetch HTTP acotado con clasificación de errores/bloqueos. | `portals.models`, `portal_inventory_spike`. | reusable |
| `portals/models/__init__.py` | Reexport de modelos portal. | `listing.py`. | reusable |
| `portals/models/listing.py` | Enums y dataclasses de listings/resultados portal. | Base de `portals/*`. | reusable |
| `portals/portal_inventory_spike.py` | Utilidades/reporting del spike portal por ciudad. | `portals.models`. | review |
| `properties/__init__.py` | Namespace property pipeline. | Ninguna. | reusable |
| `properties/address_quality.py` | Validar calidad de address extraída. | Usado por extractores/reporting. | reusable |
| `properties/detail_page_extractor.py` | Extraer address/status/energy/type desde detail page. | `properties.models` en tests. | reusable |
| `properties/listing_page_crawler.py` | Wrapper Playwright para crawling de listing pages. | Consumido por property discovery. | review |
| `properties/models.py` | Modelos de source/candidate/inventory/rejected/run output. | Base de `properties/*`. | reusable |
| `properties/platform_parser_registry.py` | Resolver parser por plataforma detectada. | `source_coverage_map`, `property discovery`. | reusable |
| `properties/platform_parsers/realworks_parser.py` | Parser específico de Realworks. | `website_fetcher`. | reusable |
| `properties/property_card_extractor.py` | Extraer cards genéricas desde listing pages HTML. | `properties.models`. | reusable |
| `properties/property_dedupe.py` | Deduplicar propiedades por URL/fallback key. | `properties.models`. | reusable |
| `properties/property_discovery_engine.py` | Motor principal de property discovery por fuente. | `source_loader`, parsers, reporter, crawler. | legacy |
| `properties/property_reporter.py` | Serializar CSV/reportes del pipeline property discovery. | `properties.models`. | reusable |
| `properties/property_status_classifier.py` | Normalizar estados y precios. | `properties.models`. | reusable |
| `properties/property_url_classifier.py` | Clasificar si una URL parece detail property o ruido. | `properties.models`. | reusable |
| `properties/source_capture_audit.py` | Auditar capture health por fuente/target area. | `matching_v1`, discovery artifacts implícitos. | reusable |
| `properties/source_loader.py` | Cargar/filter/merge source master + overrides. | `property_discovery_engine`. | reusable |
| `properties/source_parser_config.py` | Validar JSON config de parsers por fuente. | independiente. | review |
| `recommendations/__init__.py` | Placeholder futuro. | Ninguna. | unclear |
| `woning_scanner/__init__.py` | Placeholder de scanner futuro. | Ninguna. | legacy |

## C. Modelos de datos existentes

### Discovery

| Archivo | Modelo | Campos principales | Uso probable | Encaje V4 |
| --- | --- | --- | --- | --- |
| `discovery/models.py` | `SourceCandidate` | `office_name`, `website`, `root_domain`, `gemeente`, `aanbod_url`, `source_origin`, `needs_review` | fila canónica de source discovery | encaja |
| `discovery/models.py` | `GeneratedQuery` | `gemeente`, `query`, `template`, `provincie` | trazabilidad de búsquedas | revisar |
| `discovery/models.py` | `DiscoveryResult` | `candidate`, `score`, `status`, `reasons` | scoring/decision por candidato | encaja |
| `discovery/models.py` | `LiveAanbodAttempt` | `office_name`, `website`, `final_status`, `final_aanbod_url`, `detection_method` | log de intento live aanbod | encaja |
| `discovery/models.py` | `AanbodAuditAttempt` | `office_name`, `website`, `final_status`, `confidence`, `homepage_status`, `candidates_found_count` | auditoría profunda de aanbod | encaja |
| `discovery/engine.py` | `DiscoveryEngineOutput` | `run_timestamp`, `run_dir`, `report_path`, `seed_count`, `discovered_sources_count`, `source_master_rows` implícitos | output agregado del run | revisar |
| `discovery/overpass_adapter.py` | `OverpassDiscoveryResponse` | `status`, `candidates`, `errors`, `cache_used`, `endpoint_used` | respuesta de adaptador geográfico | revisar |
| `discovery/search_api_adapter.py` | `SearchResult` | `title`, `snippet`, `url`, `root_domain`, `source_query` | respuesta de search API | revisar |
| `discovery/search_api_adapter.py` | `SearchApiResponse` | `status`, `results` | wrapper de respuesta externa | revisar |
| `discovery/website_analyzer.py` | `WebsiteAnalysis` | `website_exists`, `makelaar_signals`, `signal_count` | señal simple de website válido | encaja |
| `discovery/website_fetcher.py` | `FetchResponse` | `url`, `status_code`, `text`, `content_type`, `error` | fetch HTTP reusable | encaja |
| `discovery/website_resolver.py` | `WebsiteResolverOutput` | `resolved_candidates`, `unresolved_candidates`, `manual_review_rows` | resolución de websites faltantes | revisar |
| `discovery/aanbod_finder.py` | `AanbodClassification` | `status`, `reason`, `url`, `url_type`, `score`, `matched_signals` | decisión sobre una URL de aanbod | encaja |
| `discovery/aanbod_finder.py` | `LiveAanbodResult` | `classification`, `attempted`, `succeeded`, `failure_stage`, `http_status_homepage` | outcome operativo de probing | encaja |
| `discovery/aanbod_auditor.py` | `_PageAssessment` y helpers | `page_type`, `confidence`, `rejection_reason`, `commercial_hard_block` | estructura interna de auditoría | revisar |

### Portals

| Archivo | Modelo | Campos principales | Uso probable | Encaje V4 |
| --- | --- | --- | --- | --- |
| `portals/models/listing.py` | `SourceStatus` (`Enum`) | `SUCCESS`, `HTTP_403`, `HTTP_429`, `CAPTCHA`, etc. | estado de fuente/bloqueo | encaja fuerte |
| `portals/models/listing.py` | `PortalMode` (`Enum`) | `NORMAL`, `BENCHMARK_ONLY_PERMISSION_REQUIRED`, etc. | política de uso por portal | encaja fuerte |
| `portals/models/listing.py` | `PortalListing` | `portal`, `city_query`, `property_url`, `address_raw`, `price_raw`, `status_raw` | fila de inventario/spike de portal | encaja |
| `portals/models/listing.py` | `PortalCityResult` | `portal`, `city_query`, `source_status`, `listings`, `duplicate_url_rate`, `fill_rates` | resultado por ciudad/portal | encaja |
| `portals/models/listing.py` | `PortalSpikeResult` | `city_results`, `generated_at`, `report_title` | bundle de spike | revisar |
| `portals/live_fetch.py` | `FetchResult` | `url`, `status_code`, `html`, `source_status`, `error_message`, `elapsed_ms` | fetch live acotado | encaja |
| `portals/huislijn_url_discovery.py` | `HuislijnUrlProbe` | `label`, `city_query`, `url` | input probe Huislijn | encaja |
| `portals/huislijn_url_discovery.py` | `HuislijnUrlProbeResult` | `status_code`, `source_status`, `content_length`, señales HTML | diagnóstico de endpoint | encaja |
| `portals/huislijn_url_discovery.py` | `HuislijnUrlDiscoveryResult` | `generated_at`, `max_requests`, `requests_used`, `stop_reason`, `probe_results` | resultado agregado de discovery | encaja |

### Properties / matching / diagnostics

| Archivo | Modelo | Campos principales | Uso probable | Encaje V4 |
| --- | --- | --- | --- | --- |
| `properties/models.py` | `PropertySource` | `source_id`, `office_name`, `root_domain`, `aanbod_url`, `legal_status`, `is_active` | fuente lista para crawling | revisar |
| `properties/models.py` | `CrawlResult` | `source`, `ok`, `final_url`, `error`, `timed_out`, `parser_used` | outcome por fuente | encaja parcialmente |
| `properties/models.py` | `PropertyCandidate` | `source_id`, `property_url`, `candidate_type`, `excluded_reason`, `is_property_like` | candidato intermedio | encaja |
| `properties/models.py` | `PropertyInventoryRecord` | `property_id`, `source_id`, `property_url`, `address_raw`, `city_raw`, `price_eur`, `status` | inventario de propiedades | encaja fuerte |
| `properties/models.py` | `PropertyRejectedRecord` | `source_id`, `property_url`, `excluded_reason`, `price_raw`, `status_raw` | rejected diagnostics | encaja |
| `properties/models.py` | `PropertyDiscoveryRunOutput` | `run_id`, `run_dir`, `run_status`, `sources_loaded`, `inventory_rows_written` implícito | output del run | revisar |
| `properties/property_url_classifier.py` | `PropertyUrlClassification` | `classification`, `is_property_like`, `excluded_reason` | filtro temprano de URLs | encaja |
| `properties/source_parser_config.py` | `ParserConfigValidationResult` | `ok`, `errors` | validar config parser | revisar |
| `matching/matching_v1.py` | `ClientProfile` | `client_id`, `max_budget_eur`, `target_cities`, `property types`, mínimos opcionales | perfil cliente | encaja |
| `matching/matching_v1.py` | `MatchingRunResult` | `run_id`, `inventory_csv_path`, `client_id`, `total_hard_filter_passed`, `results_path`, `top_matches` | resultado matching | encaja |
| `matching/email_preview.py` | `EmailPreviewRunResult` | `run_id`, `results_csv_path`, `html_es_path`, `html_nl_path`, `report_path` | draft artifacts | legacy |
| `diagnostics/source_coverage_map.py` | `SourceCoverageRunResult` | `run_id`, `source_master_path`, `report_path`, conteos soportadas/no soportadas | auditoría cobertura | encaja |
| `diagnostics/source_recovery_tracker.py` | `SourceRecoveryRunResult` | `benchmark_csv_path`, `candidates_csv_path`, `matching_ready_csv_path`, `found_in_candidates_count` | recovery/funnel audit | encaja |
| `diagnostics/property_discovery_selection_quality_audit.py` | `PropertyDiscoverySelectionQualityAuditResult` | `source_master_path`, `property_discovery_run_dir`, `recommended_decision` | quality audit del pipeline viejo | legacy |
| `diagnostics/delivery_mode_fingerprint_audit.py` | `DeliveryModeAuditResult` | `run_dir`, `report_path`, `inventory_path`, `inventory_rows` | audit de modo de entrega | encaja |
| `diagnostics/delivery_mode_evidence_enrichment.py` | `DeliveryModeEvidenceResult` | `run_dir`, `report_path`, `inventory_path`, `inventory_rows` | enrich audit con evidencia | encaja |
| `diagnostics/delivery_mode_evidence_enrichment.py` | `PageSignals` | WordPress/card/json-ld/xhr/iframe signals | clasificación enriquecida por fuente | encaja |

## D. Tests existentes

Cobertura actual: 43 archivos de test, 252 tests totales.

| Archivo | Qué cubre | Legacy o reutilizable |
| --- | --- | --- |
| `tests/test_address_quality.py` | calidad de address y slug fallback | reutilizable |
| `tests/test_aggregator_registry.py` | registry legal de agregadores deshabilitados | reutilizable |
| `tests/test_analyze_coverage.py` | métricas y prioridad de coverage | reutilizable |
| `tests/test_debug_kin_source.py` | diagnóstico puntual KIN/HTML markers | legacy útil |
| `tests/test_delivery_mode_evidence_enrichment.py` | clasificación enriquecida por señales HTML/XHR/iframe | reutilizable |
| `tests/test_delivery_mode_fingerprint_audit.py` | fingerprint de delivery mode por fuente | reutilizable |
| `tests/test_detail_page_extractor.py` | extracción detail page | reutilizable |
| `tests/test_discovery_aanbod_auditor.py` | auditoría de aanbod residencial/comercial | reutilizable |
| `tests/test_discovery_aanbod_finder.py` | clasificación/derivación de listing URLs | reutilizable |
| `tests/test_discovery_artifacts.py` | resolución y restore de `makelaar_sources_master` | reutilizable |
| `tests/test_discovery_dedupe.py` | dedupe de source candidates | reutilizable |
| `tests/test_discovery_engine.py` | run de source discovery y artefactos | revisar |
| `tests/test_discovery_overpass_adapter.py` | parse/cache de Overpass | revisar |
| `tests/test_discovery_place_mapper.py` | normalización de place/gemeente | reutilizable |
| `tests/test_discovery_query_generator.py` | generación de queries de market search | legacy |
| `tests/test_discovery_reporter.py` | reportes de discovery | reutilizable |
| `tests/test_discovery_scorer.py` | score de candidates | reutilizable |
| `tests/test_discovery_search_api_adapter.py` | desactivación sin credenciales | revisar |
| `tests/test_email_preview.py` | preview ES/NL sin incluir excluidos | legacy |
| `tests/test_huislijn_url_discovery.py` | probing bounded de Huislijn URLs | reutilizable |
| `tests/test_import_sources.py` | importación del seed heredado | legacy |
| `tests/test_listing_page_crawler.py` | cierre seguro del crawler | revisar |
| `tests/test_live_fetch.py` | HTTP/bloqueos/captcha/login wall | reutilizable |
| `tests/test_matching_v1.py` | hard filters y scoring local | reutilizable |
| `tests/test_normalize_places.py` | alias y enriquecimiento de lugares | reutilizable |
| `tests/test_platform_fingerprint_audit.py` | detección de plataformas HTML/url | reutilizable |
| `tests/test_portal_inventory_spike.py` | spike portal, parsers y stop conditions | revisar |
| `tests/test_property_card_extractor.py` | extracción genérica de listing cards | reutilizable |
| `tests/test_property_dedupe.py` | dedupe de propiedades | reutilizable |
| `tests/test_property_discovery_engine.py` | pipeline property discovery completo | legacy |
| `tests/test_property_discovery_selection_quality_audit.py` | quality audit del pipeline viejo | legacy |
| `tests/test_property_source_loader.py` | filtrado y merge de source master/overrides | reutilizable |
| `tests/test_property_status_classifier.py` | normalización de estado | reutilizable |
| `tests/test_property_url_classifier.py` | filtro de URLs property-like | reutilizable |
| `tests/test_realworks_parser.py` | parser Realworks + KIN city normalization | reutilizable |
| `tests/test_run_property_discovery_cli.py` | CLI de property discovery | legacy |
| `tests/test_run_source_discovery_cli.py` | CLI de source discovery | revisar |
| `tests/test_source_coverage_map.py` | coverage map y recomendaciones | reutilizable |
| `tests/test_source_master_builder.py` | construcción de source master | reutilizable |
| `tests/test_source_recovery_tracker.py` | tracking de benchmark a través del funnel | reutilizable |
| `tests/test_target_area_platform_fingerprint.py` | fingerprint focalizado por target area | reutilizable |
| `tests/test_target_area_source_capture_audit.py` | audit de capture health por source | reutilizable |
| `tests/test_website_resolver.py` | resolución de website faltante | revisar |

## E. Source registry / configuración de fuentes

| Ruta | Formato | Campos principales | N aproximado | Contiene | Uso actual |
| --- | --- | --- | --- | --- | --- |
| `data/discovery/discovery_sources_registry.csv` | CSV | `source_id`, `source_name`, `source_type`, `url`, `province_scope`, `allowed_use`, `priority` | 13 filas | Sí: Funda, Pararius, Huislijn, agregadores; no vi Jaap | registry manual de fuentes base para discovery |
| `data/discovery/reference/aggregator_legal_registry.csv` | CSV | `aggregator_name`, `base_url`, `adapter_name`, `robots_status`, `permission_status`, `allowed_use`, `adapter_enabled` | 3 filas | Sí: Funda y Huislijn; Pararius no aparece | guardrail legal/operativo para agregadores |
| `data/discovery/reference/property_discovery_source_overrides.csv` | CSV | `source_id`, `office_name`, `root_domain`, `aanbod_url`, `legal_status`, `run_id` | 10 filas | No vi Funda/Pararius/Huislijn directos | overrides puntuales sobre source master |
| `data/processed/sources_seed_noord_brabant.csv` | CSV | `office_name`, `website`, `root_domain`, `koopaanbod_url`, `plaats`, `source_type`, `discovery_source`, `confidence` | 413 filas | Sí: referencias Funda dentro del seed | baseline heredado de import/harvester |
| `data/discovery/latest/makelaar_sources_master.csv` | CSV esperado, actualmente ausente | normalmente `source_id`, `office_name`, `root_domain`, `aanbod_url`, `source_quality_status`, `legal_status`, etc. | n/a | n/a | artefacto canónico esperado por loaders/diagnósticos, hoy no está en `latest/` |
| `scraper/src/domek_wonen/discovery/source_master_builder.py` | código | mapea score/legal status/active flags | n/a | puede clasificar agregadores y seeds | genera `makelaar_sources_master.csv` |
| `scraper/src/domek_wonen/properties/source_loader.py` | código | filtra `is_active`, `legal_status`, `source_domain`, overrides | n/a | depende del master ya generado | punto de carga del pipeline property discovery |

## F. Detección de módulos del enfoque viejo

| Ruta | Por qué parece legacy | Qué lo importa | Riesgo de archivarlo ahora |
| --- | --- | --- | --- |
| `scripts/import_sources.py` | importa seed `NVM harvester` heredado | `tests/test_import_sources.py` | medium |
| `discovery/seed_adapter.py` | acopla el seed heredado a `SourceCandidate` | `discovery.engine` | medium |
| `data/processed/sources_seed_noord_brabant.csv` | baseline explícito `nvm_harvester_2026_06_12` | consumido por import/build scripts | high |
| `matching/email_preview.py` | email drafts y advisor review son fase posterior en V4 | `scripts/run_email_preview_v1.py`, tests | low |
| `scripts/run_email_preview_v1.py` | CLI de previews legacy | tests | low |
| `portals/adapters/funda.py` | Funda es `benchmark-only` y no debe ser camino operativo | `run_portal_inventory_spike.py`, tests | low |
| `portals/adapters/pararius.py` | Pararius es `benchmark/permission-required` | `run_portal_inventory_spike.py`, tests | low |
| `portals/portal_inventory_spike.py` | spike puntual, no daily sync ni inventory core | adapters, `live_fetch`, Huislijn probe, CLI, tests | medium |
| `scripts/run_portal_inventory_spike.py` | ejecuta el spike portal antiguo | tests | low |
| `properties/property_discovery_engine.py` | pipeline makelaar-by-makelaar prohibido como camino principal | `run_property_discovery.py`, worker, tests | high |
| `scripts/property_discovery_worker.py` | worker del pipeline anterior | `run_property_discovery.py` | high |
| `scripts/run_property_discovery.py` | CLI del pipeline anterior | tests | high |
| `diagnostics/property_discovery_selection_quality_audit.py` | depende del pipeline viejo y su selección de fuentes | CLI, tests | medium |
| `scripts/run_property_discovery_selection_quality_audit.py` | CLI atada al pipeline viejo | tests | medium |
| `discovery/query_generator.py` | market-search query generation, menos alineado con portal-first puro | `engine.py`, tests | medium |
| `discovery/search_api_adapter.py` | search API externa para descubrir fuentes, no inventario portal-first diario | tests opcionales | medium |
| `woning_scanner/__init__.py` | placeholder de fase futura expresamente bloqueada | nadie | low |
| docs varios (`docs/01_*`, `02_*`, `03_*`, `05_*`, `07_*`, `08_*`, `10_*`) | reflejan etapa V6/NVM/discovery anterior | nadie en runtime | low |

### Notas específicas pedidas

- `NVM harvester`: vive sobre todo en `scripts/import_sources.py`, `discovery/seed_adapter.py`, `data/processed/sources_seed_noord_brabant.csv` y docs de discovery sprint.
- `Huislijn`: `portals/adapters/huislijn.py`, `portals/huislijn_url_discovery.py`, `run_huislijn_url_discovery.py`, parte de `discovery_sources_registry.csv`.
- `Pararius`: `portals/adapters/pararius.py`, referencias en `live_fetch` tests y registry.
- `Funda`: `portals/adapters/funda.py`, flags `benchmark-only` en tests y registry.
- `portal inventory spike`: `portals/portal_inventory_spike.py`, `run_portal_inventory_spike.py`, tests asociados.
- `market search engine`: `discovery/query_generator.py`, `discovery/search_api_adapter.py`, parte de `discovery/engine.py`.
- `email alerts`: no hay envío real; sí hay drafts/previews en `matching/email_preview.py`.
- `dashboards`: no hay código de dashboard en runtime; sí hay referencias legacy en docs.

## G. Piezas potencialmente reutilizables para V4

| Ruta | Utilidad probable para V4 | Riesgos / limitaciones | Recomendación |
| --- | --- | --- | --- |
| `portals/live_fetch.py` | base común para fetch bounded, stop on 403/429/CAPTCHA/login wall | hoy depende de helpers del spike | CONSERVAR |
| `portals/models/listing.py` | estados, modos y shape de listing portal | naming todavía spike-oriented | CONSERVAR |
| `portals/huislijn_url_discovery.py` | descubrir endpoints/shape antes de un adapter estable | hoy está no trackeado y acoplado a output del spike | REVISAR |
| `discovery/platform_fingerprint.py` | identificar CMS/plataforma para decidir estrategia segura | mezcla target-area y discovery anterior | CONSERVAR |
| `diagnostics/delivery_mode_fingerprint_audit.py` | detectar si una fuente requiere JS, iframe o bloqueo | produce inventarios diagnósticos más que core runtime | CONSERVAR |
| `diagnostics/delivery_mode_evidence_enrichment.py` | enriquecer decisiones con evidencia concreta | sigue muy orientado a source master previo | REVISAR |
| `discovery/aanbod_finder.py` | derivar listing index URL segura | nace del mundo makelaar-site, no portal-first | CONSERVAR |
| `discovery/aanbod_auditor.py` | separar residential/commercial y detectar falsas aanbod URLs | algo específica a websites de oficina | CONSERVAR |
| `discovery/source_master_builder.py` | consolidar registry canónico de fuentes | naming actual `makelaar_sources_master` puede quedar chico para V4 | REESCRIBIR |
| `properties/source_loader.py` | filtrar y mergear fuentes activas + overrides | depende de formato heredado del source master | REESCRIBIR |
| `properties/platform_parser_registry.py` | selector de parser por plataforma | útil si sobrevive un fallback no-portal | CONSERVAR |
| `properties/platform_parsers/realworks_parser.py` | fallback valioso para Realworks cuando una fuente oficial es necesaria | forma parte de `PropertyDiscovery`, fase no principal | CONSERVAR |
| `properties/property_url_classifier.py` | filtrar detail/property URLs | heurísticas pueden requerir ampliación por portales | CONSERVAR |
| `properties/property_card_extractor.py` | extracción genérica de listing cards HTML | puede fallar en sitios JS pesados | CONSERVAR |
| `properties/detail_page_extractor.py` | extracción de detalle para enrichment posterior | acoplado a HTML estático | CONSERVAR |
| `properties/property_status_classifier.py` | normalizar status/precios | buen bloque canónico transversal | CONSERVAR |
| `properties/property_dedupe.py` | dedupe de URLs/keys | necesita extensión cross-portal | CONSERVAR |
| `properties/address_quality.py` | quality gate de direcciones | simple y reusable | CONSERVAR |
| `properties/models.py` | shape de source/candidate/inventory | algunos nombres muy ligados a property discovery | REVISAR |
| `matching/matching_v1.py` | coarse match local después del inventario | parte de supuestos de `clean_available` heredado | CONSERVAR |
| `diagnostics/source_recovery_tracker.py` | auditar pérdidas entre benchmark e inventario | muy útil para coverage control | CONSERVAR |
| `diagnostics/source_coverage_map.py` | mapa por fuente/plataforma/soporte | hoy mira `PropertyDiscovery` como downstream | REESCRIBIR |
| `properties/source_capture_audit.py` | estado capture por fuente sin borrar previos | depende de artifacts viejos pero la lógica encaja | REVISAR |
| `discovery/discovery_artifacts.py` | resolver `latest` y runs válidos | naming/hardcoded paths requieren revisión | REVISAR |
| `discovery/place_mapper.py` | normalización territorial | reusable directa | CONSERVAR |
| `discovery/dedupe.py` | dedupe de fuentes candidatas | reusable directa | CONSERVAR |
| `discovery/reporter.py` | reportes markdown de runs | útil para observabilidad interna | CONSERVAR |
| `discovery/scorer.py` | score heurístico de candidates | probablemente necesite recalibración | REVISAR |
| `discovery/website_fetcher.py` | fetch HTML y links para discovery | reusable directa | CONSERVAR |
| `discovery/website_resolver.py` | resolver domains faltantes en seeds/manuals | puede seguir sirviendo en censo de fuentes | REVISAR |

## H. Tabla final de decisión propuesta

| Módulo / archivo / carpeta | Acción propuesta | Justificación breve | Dependencias / riesgo | Bloque V4 posible |
| --- | --- | --- | --- | --- |
| `portals/live_fetch.py` | CONSERVAR | ya implementa políticas de stop seguras | depende de `portal_inventory_spike.normalize_text` | Fase 1-2 portal fetch |
| `portals/models/listing.py` | CONSERVAR | buen shape base para portal inventory | nombres de spike | Fase 1 inventory schema |
| `portals/adapters/huislijn.py` | CONSERVAR | candidato principal actual | parser aún de spike | Fase 2 Huislijn Adapter |
| `portals/huislijn_url_discovery.py` | REVISAR | diagnóstico útil pero todavía no integrado | hoy no trackeado | Fase 1-2 |
| `portals/adapters/funda.py` | ARCHIVAR | benchmark-only, fuera del camino principal | tests/CLI del spike | Benchmark manual |
| `portals/adapters/pararius.py` | ARCHIVAR | permission-required | tests/CLI del spike | Benchmark manual |
| `portals/portal_inventory_spike.py` | REESCRIBIR | contiene utilidades buenas pero orientadas a spike | varios imports internos | Fase 1 Inventory Spike |
| `discovery/platform_fingerprint.py` | CONSERVAR | gran valor para strategy routing | naming aún discovery-heavy | Fase 1 source census |
| `diagnostics/delivery_mode_fingerprint_audit.py` | CONSERVAR | observabilidad útil antes de adaptar fuentes | depende de source master | Fase 1 audit |
| `diagnostics/delivery_mode_evidence_enrichment.py` | REVISAR | evidencia útil, pero más acoplada a pipeline viejo | paths/artefactos heredados | Fase 1 audit |
| `discovery/aanbod_finder.py` | CONSERVAR | heurísticas valiosas para listing URLs | enfoque makelaar-site | Fase 7 fallback |
| `discovery/aanbod_auditor.py` | CONSERVAR | evita falsos positivos/comercial | específica a websites de oficina | Fase 7 fallback |
| `discovery/source_master_builder.py` | REESCRIBIR | central, pero nombre/formato deben subir a V4 | usado por engine | Fase 0.3 registry redesign |
| `properties/source_loader.py` | REESCRIBIR | loader útil, contrato actual heredado | depende de master viejo | Fase 3 inventory core |
| `properties/models.py` | REVISAR | buenos shapes, pero varios son de property discovery | base amplia | Fase 3-5 |
| `properties/platform_parser_registry.py` | CONSERVAR | fallback parser routing claro | ligado a parsers heredados | Fase 7 |
| `properties/platform_parsers/realworks_parser.py` | CONSERVAR | parser específico ya probado | útil solo en fallback | Fase 7 |
| `properties/property_card_extractor.py` | CONSERVAR | extractor genérico reusable | HTML-only | Fase 2-7 |
| `properties/detail_page_extractor.py` | CONSERVAR | enrichment detallado futuro | HTML-only | Fase 4-6 |
| `properties/property_status_classifier.py` | CONSERVAR | normalización transversal | simple | Fase 3-6 |
| `properties/property_url_classifier.py` | CONSERVAR | reduce ruido temprano | requerirá más casos | Fase 2-7 |
| `properties/property_dedupe.py` | CONSERVAR | dedupe básico ya resuelto | ampliar cross-source | Fase 3-4 |
| `properties/address_quality.py` | CONSERVAR | quality gate simple y útil | poca cobertura multiidioma | Fase 3-4 |
| `properties/property_discovery_engine.py` | ARCHIVAR | camino principal prohibido por AGENTS | muchos tests/scripts dependen | Legacy archive candidate |
| `scripts/run_property_discovery.py` | ARCHIVAR | CLI del camino viejo | tests CLI | Legacy archive candidate |
| `scripts/property_discovery_worker.py` | ARCHIVAR | worker del camino viejo | run_property_discovery | Legacy archive candidate |
| `diagnostics/property_discovery_selection_quality_audit.py` | ARCHIVAR | audit solo del pipeline viejo | CLI/tests | Legacy archive candidate |
| `discovery/engine.py` | REVISAR | motor valioso, pero mezcla source discovery con vías viejas | amplio acoplamiento | Fase 1 census/discovery |
| `discovery/query_generator.py` | ARCHIVAR | market-search discovery de fase anterior | engine/tests | Legacy archive candidate |
| `discovery/search_api_adapter.py` | REVISAR | puede servir para censo, no para core | credenciales externas | Fase 0.x census |
| `discovery/seed_adapter.py` | ARCHIVAR | puente del seed viejo | `engine.py` | Legacy seed compatibility |
| `scripts/import_sources.py` | ARCHIVAR | NVM harvester import bridge | tests import_sources | Legacy seed compatibility |
| `matching/matching_v1.py` | CONSERVAR | coarse match local ya probado | contrato de inventory heredado | Fase 5 Client Matching |
| `matching/email_preview.py` | ARCHIVAR | fase posterior, no necesaria ahora | scripts/tests | Fase 6 only |
| `scripts/run_email_preview_v1.py` | ARCHIVAR | CLI fase posterior | tests | Fase 6 only |
| `diagnostics/source_recovery_tracker.py` | CONSERVAR | muy útil para coverage regressions | depende de artifacts | Fase 4-5 audit |
| `diagnostics/source_coverage_map.py` | REESCRIBIR | diagnóstico útil, downstream equivocado | mira parser/property discovery | Fase 0.x census |
| `properties/source_capture_audit.py` | REVISAR | buen audit por fuente | depende de inventory actual | Fase 4 |
| `discovery/place_mapper.py` | CONSERVAR | base territorial reutilizable | bajo riesgo | Fase 0.x-5 |
| `discovery/dedupe.py` | CONSERVAR | dedupe de fuentes | bajo riesgo | Fase 0.x-1 |
| `discovery/reporter.py` | CONSERVAR | reporting útil | bajo riesgo | Fase 1-4 |
| `discovery/website_fetcher.py` | CONSERVAR | fetch base reusable | bajo riesgo | Fase 0.x-7 |
| `discovery/website_resolver.py` | REVISAR | sigue siendo útil para fuentes manuales | heurística limitada | Fase 0.x |
| `inventory/` | REVISAR | paquete vacío, buen lugar para V4 real | hoy placeholder | Fase 3 Inventory Core |
| `recommendations/` | ARCHIVAR | placeholder sin uso actual | ninguno | Fase 6+ |
| `woning_scanner/` | ARCHIVAR | explícitamente fuera de fase | ninguno | Fase 8 futura |

## I. Estado de archivos rectores

| Archivo | Estado actual | Problema frente a V4 | Cambio recomendado para Fase 0.3 / 0.4 |
| --- | --- | --- | --- |
| `README.md` | actualizado a `portal-first national inventory` y fases 0-9 | todavía no inventaría ni delimita claramente qué código es legacy | ampliar con mapa de módulos vigentes vs legacy |
| `AGENTS.md` | alineado con portal-first, daily sync, matching y restricciones duras | el código aún no refleja completamente esas restricciones | usarlo como base para plan de archivado y scope gates |
| `.gitignore` | bastante correcto: excluye `data/raw`, outputs, caches, previews | no excluye necesariamente todo `__pycache__` anidado con patrón estándar (`**/__pycache__/`) aunque sí cubre mucho | endurecer reglas de pycache y artefactos transitorios |
| `requirements.txt` | mínimo y claro: `pytest`, `httpx`, `playwright` | no explica qué dependencias son runtime vs tooling | separar runtime/dev o documentarlo |
| `pytest.ini` | simple y correcto, ignora `data/`, `tmp/`, caches | no configura marcadores/fases ni reportes | opcional: añadir markers por fase o capa |
| `pyproject.toml` | no existe | falta lugar canónico para metadata/tooling moderno | evaluar creación futura si se reorganiza el paquete |
| `setup.cfg` | no existe | sin problema inmediato | crear solo si hace falta centralizar tooling |
| `setup.py` | no existe | sin problema inmediato | no necesario salvo empaquetado real |

## Preflight documentado

- Branch actual: `portal-first-national-inventory`
- `git status -s` inicial:
  - `?? scraper/src/domek_wonen/portals/huislijn_url_discovery.py`
  - `?? scripts/run_huislijn_url_discovery.py`
  - `?? tests/test_huislijn_url_discovery.py`
- Último commit corto: `8c21f7b feat: add live bounded CLI for portal inventory spike`
- Python:
  - `py -3.12 --version` => `Python 3.12.10`
  - `python --version` => `Python 3.12.10`
- Pytest:
  - comando: `py -3.12 -m pytest`
  - resultado: `252 passed in 100.21s (0:01:40)`

## Validación de esta tarea

- Se creó solo este documento nuevo: `docs/REPO_INVENTORY_2026-06-19.md`.
- No se modificó código funcional.
- No se leyó ni escribió `data/raw`.
- No se modificaron outputs generados.
- No se hizo `git add`.
- No se hizo commit.
- Limitación para la regla “único cambio en git status”:
  - ya existían tres archivos no trackeados antes de esta tarea;
  - por eso al final el `git status -s` esperado es esos tres archivos previos más este documento.
