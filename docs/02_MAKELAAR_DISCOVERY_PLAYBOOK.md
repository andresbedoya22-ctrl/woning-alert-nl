# Makelaar & Aanbod Discovery Playbook v6

## 1. Diagnóstico del cuello de botella

El resultado del harvester actual:

- 55 gemeenten procesadas
- 417 oficinas únicas
- 399 con web propia
- 327 con koopaanbod localizado

Esto es bueno como base NVM, pero insuficiente como cobertura total. El problema no es solo “faltan makelaars”; el problema es que no todas las viviendas aparecen primero en webs propias ni todos los makelaars están en NVM.

## 2. Cambio estructural

Separar:

### A. Makelaar discovery

Objetivo: saber qué oficinas existen y dónde están sus webs.

Fuentes:

1. NVM directory
2. Vastgoed Nederland / VBO / Vastgoedpro cuando haya directorio o listado explotable
3. Google/Bing search manual-asistido por gemeente
4. KvK/website search manual post-MVP
5. Sources importadas desde agregadores

### B. Property discovery

Objetivo: encontrar viviendas disponibles aunque todavía no conozcamos el makelaar.

Fuentes:

1. Webs propias de makelaars
2. Huislijn
3. Huispedia
4. Pararius koopwoningen
5. Vastgoed Nederland aanbod
6. Platform endpoints detectables: Realworks, Kolibri, Skarabee, Pyber, EyeMove/Yes-Co
7. Manual URL seeds que Sander/Laura/Andres agreguen desde dashboard

## 3. Por qué esto resuelve el cuello de botella

Una vivienda detectada en un agregador puede revelar:

- URL de la vivienda
- nombre del makelaar
- website del makelaar
- plataforma técnica
- zona activa

Esto permite alimentar el censo de makelaars desde las viviendas, no solo al revés.

## 4. Pipeline nuevo

### Stage 1 — Seeds iniciales

Importar el CSV actual del harvester NVM.

Tabla: `sources`

Marcar:

- `discovery_source = nvm_harvester_2026_06`
- `source_type = makelaar_site`
- `confidence = 0.8` si koopaanbod_url existe
- `needs_review = true` si no hay koopaanbod_url

### Stage 2 — Agregadores por provincia/gemeente

Crear fuentes agregadoras:

- Huislijn Noord-Brabant
- Huispedia Noord-Brabant
- Vastgoed Nederland koopwoningen Noord-Brabant
- Pararius koopwoningen por ciudad grande

No usarlas como única verdad. Usarlas para:

- detectar viviendas
- detectar makelaars faltantes
- enriquecer cobertura
- comparar duplicados

### Stage 3 — Plataforma-first scraping

No escribir 300 scrapers. Detectar plataforma técnica y usar parsers reutilizables.

Plataformas iniciales:

- Realworks / Tiara
- Kolibri / Wazzup
- Skarabee
- Pyber
- EyeMove / Yes-Co
- WordPress custom
- Static HTML generic

### Stage 4 — Source validator

Cada source debe tener health:

- last_success
- last_error
- count_today
- count_yesterday
- pct_change
- consecutive_errors
- robots_allowed
- parser_level
- status: `ok`, `warning`, `down`, `blocked`, `manual_review`

### Stage 5 — Enriquecimiento desde viviendas

Si una propiedad viene de agregador y no existe source para su makelaar:

1. Crear office candidate.
2. Intentar resolver website.
3. Intentar encontrar koopaanbod_url.
4. Enviar a revisión si confidence < 0.7.

## 5. Fuentes priorizadas

### Tier 1 — Alta prioridad MVP

1. NVM harvester actual.
2. Huislijn koopwoningen Noord-Brabant.
3. Vastgoed Nederland aanbod koopwoningen Noord-Brabant.
4. Huispedia Noord-Brabant.
5. Webs propias con koopaanbod_url ya resuelto.

### Tier 2 — Después de MVP básico

1. Pararius por ciudad.
2. Platform-specific parsers.
3. Search engine assisted discovery por gemeente.
4. Import manual desde dashboard.

### Tier 3 — Post-MVP

1. Partnerships/API formal.
2. Integración con CRM/BlinqX/Elements.
3. Aprendizaje de preferencias.

## 6. Métricas de cobertura

No medir solo “número de makelaars”. Medir:

- sources activas
- viviendas disponibles únicas
- viviendas nuevas por día
- porcentaje con BAG-ID
- porcentaje con prijs/m²/label
- matches útiles por cliente
- rechazo por fuente
- bezichtigingen por fuente
- deals por fuente

## 7. Objetivo numérico inicial

Para MVP Noord-Brabant:

- 300+ sources propias útiles es aceptable.
- 500+ sources total incluyendo agregadores/plataformas es fuerte.
- 1.500-3.000 viviendas disponibles normalizadas sería usable.
- Menos de 500 viviendas activas sería débil.

El objetivo no es encontrar “todos los makelaars” el día 1; es detectar suficientes viviendas relevantes antes que el asesor tenga que buscarlas manualmente.
