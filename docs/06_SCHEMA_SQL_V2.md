# SQL Schema v2 — Domek Wonen

```sql
create extension if not exists pgcrypto;

create table offices (
  id uuid primary key default gen_random_uuid(),
  naam text not null,
  adres text,
  postcode text,
  plaats text,
  provincie text,
  lat double precision,
  lng double precision,
  website text,
  discovery_source text,
  confidence numeric default 0,
  needs_review boolean default false,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table sources (
  id uuid primary key default gen_random_uuid(),
  office_id uuid references offices(id),
  naam text not null,
  source_type text not null check (source_type in ('makelaar_site','aggregator','platform_endpoint','manual_seed')),
  website text,
  koopaanbod_url text,
  plaats text,
  provincie text,
  platform_hint text,
  parser_name text,
  parse_level smallint default 3,
  requires_js boolean default false,
  robots_allowed boolean,
  active boolean default true,
  last_hash text,
  last_success timestamptz,
  last_error text,
  consecutive_errors int default 0,
  coverage_score numeric default 0,
  notes text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table properties (
  id uuid primary key default gen_random_uuid(),
  source_id uuid references sources(id),
  external_id text,
  url text not null,
  bag_id text,
  adres text,
  postcode text,
  huisnummer text,
  plaats text,
  provincie text,
  lat double precision,
  lng double precision,
  prijs int,
  woonoppervlakte int,
  perceeloppervlakte int,
  kamers smallint,
  slaapkamers smallint,
  type text,
  bouwjaar int,
  energy_label text,
  energy_label_num smallint,
  erfpacht boolean,
  beschrijving text,
  kenmerken jsonb default '{}'::jsonb,
  status text default 'beschikbaar' check (status in ('beschikbaar','onder_bod','verkocht','verkocht_ov','verdwenen')),
  gepubliceerd_op date,
  first_seen timestamptz default now(),
  last_seen timestamptz default now(),
  confidence_score smallint default 0,
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  unique(url)
);

create index idx_properties_pool on properties(provincie, plaats, prijs) where status='beschikbaar';
create index idx_properties_bag on properties(bag_id);
create index idx_properties_postcode on properties(postcode, huisnummer);
create index idx_properties_source on properties(source_id);

create table property_history (
  id uuid primary key default gen_random_uuid(),
  property_id uuid references properties(id),
  field text not null,
  old_value text,
  new_value text,
  detected_at timestamptz default now()
);

create table property_health (
  id uuid primary key default gen_random_uuid(),
  source_id uuid references sources(id),
  run_date date not null,
  count_today int default 0,
  count_yesterday int default 0,
  pct_change numeric,
  alert boolean default false,
  status text default 'ok' check (status in ('ok','warning','down','blocked','manual_review')),
  created_at timestamptz default now(),
  unique(source_id, run_date)
);

create table clients (
  id uuid primary key default gen_random_uuid(),
  dossiernr text not null,
  achternaam text not null,
  taal text default 'nl' check (taal in ('nl','es','pl','en')),
  adviseur text,
  status text default 'actief' check (status in ('actief','gepauzeerd','wil_niet_kopen','deal','gesloten')),
  deal_op date,
  deal_notitie text,
  max_hypotheek int,
  max_zoekprijs int not null,
  gezinssamenstelling smallint,
  type text,
  type_is_must boolean default true,
  min_slaapkamers smallint default 0,
  slaapkamers_is_must boolean default true,
  min_energy_label_num smallint default 0,
  label_is_must boolean default false,
  pref_tuin boolean default false,
  pref_balkon boolean default false,
  pref_tuin_of_balkon boolean default false,
  pref_garage boolean default false,
  renoveren text check (renoveren in ('nee','cosmetisch','alles')),
  intake_raw text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table client_zones (
  id uuid primary key default gen_random_uuid(),
  client_id uuid references clients(id) on delete cascade,
  plaats text,
  lat double precision,
  lng double precision,
  radius_km numeric default 10,
  is_must boolean default true
);

create table matches (
  id uuid primary key default gen_random_uuid(),
  client_id uuid references clients(id),
  property_id uuid references properties(id),
  match_score numeric not null,
  explanation jsonb default '{}'::jsonb,
  sent_at timestamptz,
  created_at timestamptz default now(),
  unique(client_id, property_id)
);

create table match_outcomes (
  id uuid primary key default gen_random_uuid(),
  match_id uuid references matches(id),
  outcome text not null check (outcome in ('sent','opened','interested','afgewezen','bezichtiging','bod_gedaan','deal')),
  reason text,
  notes text,
  created_by text,
  created_at timestamptz default now()
);

create table source_discovery_events (
  id uuid primary key default gen_random_uuid(),
  property_id uuid references properties(id),
  office_candidate text,
  website_candidate text,
  source_created_id uuid references sources(id),
  confidence numeric default 0,
  status text default 'pending' check (status in ('pending','accepted','rejected','needs_review')),
  created_at timestamptz default now()
);
```
