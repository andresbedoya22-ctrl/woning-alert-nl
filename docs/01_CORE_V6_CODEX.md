# Domek Wonen — Core v6 Codex Edition

## 1. Producto

Domek Wonen es un sistema interno para asesores de Domek que detecta viviendas nuevas, las normaliza, las compara con criterios de clientes activos y envía matches útiles antes de que el asesor tenga que buscar manualmente.

## 2. Principio de diseño

El sistema debe ahorrar tiempo real al asesor. Todo lo que aumente fricción operacional se elimina o se deja post-MVP.

## 3. Estados principales

### Vivienda

- `beschikbaar`: entra al pool y puede ser enviada.
- `onder_bod`: se archiva; no se ofrece.
- `verkocht`: se archiva; no se ofrece.
- `verkocht_ov`: se archiva; no se ofrece.
- `verdwenen`: no vista durante 2 pasadas; se archiva hasta reaparición.

### Cliente

- `actief`: recibe búsquedas.
- `gepauzeerd`: no recibe búsquedas temporalmente.
- `wil_niet_kopen`: no recibe búsquedas, pero conserva ficha.
- `deal`: compró; sale definitivamente de todas las búsquedas.
- `gesloten`: proceso cerrado/cancelado.

## 4. Módulos del sistema

### 4.1 Sources

Contiene webs de makelaars, agregadores y plataformas conocidas.

Campos mínimos:

- naam
- type: `makelaar_site`, `aggregator`, `platform_endpoint`, `manual_seed`
- website
- koopaanbod_url
- platform_hint
- plaats
- provincie
- active
- last_success
- consecutive_errors
- coverage_score

### 4.2 Properties

Tabla normalizada de viviendas.

Campos mínimos:

- id
- source_id
- url
- bag_id
- adres
- postcode
- plaats
- provincie
- lat/lng
- prijs
- woonoppervlakte
- perceeloppervlakte
- slaapkamers
- kamers
- type
- bouwjaar
- energy_label
- energy_label_num
- beschrijving
- kenmerken JSONB
- status
- gepubliceerd_op
- first_seen
- last_seen
- confidence_score

### 4.3 Clients

Ficha de búsqueda del cliente.

Debe permitir filtros obligatorios y preferencias blandas:

- max_zoekprijs
- zonas/radios
- type + must/soft
- dormitorios + must/soft
- energy label + must/soft
- tuin/balkon/tuin_of_balkon
- garage
- renoveren: `nee`, `cosmetisch`, `alles`
- distancia al trabajo
- idioma
- asesor responsable
- status

### 4.4 Matching

Reglas explícitas, no IA.

Filtros duros:

- vivienda `beschikbaar`
- cliente `actief`
- precio ≤ max_zoekprijs
- distancia dentro de zona/radio obligatorio
- dormitorios mínimos si es must
- tipo si es must
- energy label si es must

Scoring blando:

- holgura de precio
- cercanía a zona ideal
- m² extra
- habitaciones extra
- jardín/balcón
- garaje
- estado de renovación
- energy label superior
- penalización por datos desconocidos

### 4.5 Outcomes

Cada match debe tener outcome:

- `sent`
- `opened`
- `interested`
- `afgewezen`
- `bezichtiging`
- `bod_gedaan`
- `deal`

Razones de rechazo:

- precio
- ubicación
- estado vivienda
- demasiado pequeña
- sin jardín/balcón
- energy label
- no gusta visualmente
- otra razón

## 5. IA en MVP

Permitida:

- Resumen corto de vivienda para email.
- Extracción de kenmerken desde descripción.
- Prefill de cliente desde intake/PDF/texto con revisión humana.

No permitida en MVP:

- Decidir si una vivienda debe enviarse.
- Reemplazar reglas de matching.
- Inventar datos no presentes.
- Scraping evasivo.

## 6. Arquitectura técnica recomendada

### Frontend

- Next.js + TypeScript
- Tailwind o CSS modules
- Vercel para frontend

### Backend

- Python 3.12 para scraping/enrichment/matching
- FastAPI opcional si se necesita API propia
- Supabase Postgres como base central
- Scheduler en Hetzner con cron/systemd

### Scraping

- Playwright solo cuando sea necesario
- httpx + BeautifulSoup como primera opción
- delays 3-8 s
- User-Agent identificable
- robots.txt respetado
- fixtures HTML para tests

### IA

- Haiku para extracción barata y estructurada
- GPT/Codex para construcción de código, no runtime principal

## 7. Criterio de MVP real

El MVP no es “dashboard bonito”. El MVP real existe cuando:

1. Hay 500+ sources activas o cobertura suficiente por agregadores.
2. Hay viviendas disponibles normalizadas.
3. Se pueden crear 2-3 clientes reales.
4. El sistema genera matches útiles.
5. El asesor puede marcar outcomes.
6. Al menos 1 bezichtiging nace de un match automático.
