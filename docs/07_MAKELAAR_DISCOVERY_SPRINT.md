\# Makelaar Discovery Sprint — Noord-Brabant



\## Objetivo



Construir la base más completa posible de makelaars y fuentes de woningaanbod en Noord-Brabant antes de avanzar al motor de scraping de viviendas.



El seed actual del harvester NVM es útil, pero no suficiente. La meta no es empezar con 295 koopaanbod\_url válidos, sino ampliar cobertura usando varias capas.



\## Estado inicial



Seed actual:

\- Registros limpios: 413

\- Koopaanbod URL valid: 295

\- Koopaanbod URL suspect: 28

\- Koopaanbod URL missing: 90

\- Needs review: 118



\## Meta de cobertura



Meta mínima antes de pasar a scraping de viviendas:

\- 500+ oficinas/candidatos únicos en Noord-Brabant.

\- 400+ websites identificadas.

\- 350+ sources con posible aanbod propio o fuente agregadora útil.

\- 90%+ de gemeenten de Noord-Brabant con cobertura.

\- Reporte claro de fuentes faltantes y razones.



\## Capas de discovery



\### Capa 1 — Seed NVM existente

Archivo:

data/processed/sources\_seed\_noord\_brabant.csv



Uso:

Base inicial. No se borra. Se enriquece.



\### Capa 2 — Directorios regionales NVM

Buscar páginas regionales NVM, por ejemplo:

\- NVM Brabant Noord-Oost

\- NVM Brabant Zuidoost

\- NVM West-Brabant

\- NVM Midden-Brabant



Objetivo:

Extraer oficinas, plaats, website, email/teléfono si aparece.



\### Capa 3 — Brancheverenigingen no-NVM

Buscar miembros/candidatos de:

\- Vastgoed Nederland

\- VBO / antiguos miembros VBO

\- VastgoedPro si aplica

\- otros directorios públicos relevantes



Objetivo:

Encontrar makelaars no presentes en NVM.



\### Capa 4 — Agregadores con makelaar visible

Fuentes:

\- Huislijn

\- Huispedia

\- Vastgoed Nederland aanbod

\- Pararius koopwoningen



Objetivo:

Descubrir makelaars a partir de propiedades reales publicadas.



\### Capa 5 — Search queries controladas

Usar búsquedas web por gemeente:

\- "makelaar koopwoningen \[gemeente]"

\- "NVM makelaar \[gemeente]"

\- "VBO makelaar \[gemeente]"

\- "woningaanbod makelaar \[gemeente]"

\- "site:.nl makelaar \[gemeente] koopwoningen"



Objetivo:

Encontrar oficinas que no aparezcan en directorios.



\### Capa 6 — Descubrimiento de aanbod dentro de website

Para cada website:

\- buscar rutas como /aanbod, /woningaanbod, /koopwoningen, /wonen, /huizen, /objecten.

\- marcar calidad: valid, suspect, missing.

\- no asumir que una página comercial es aanbod.



\## Reglas legales y técnicas



\- No hacer scraping de Funda.

\- No evadir CAPTCHA.

\- Respetar robots.txt y delays.

\- Guardar fuente y método de discovery.

\- Marcar confidence por cada dato.

\- No borrar candidatos; marcar review.

\- Separar makelaar discovery de property discovery.



\## Output esperado



Archivos:

\- data/discovery/processed/makelaar\_candidates\_noord\_brabant.csv

\- data/discovery/processed/makelaar\_sources\_expanded.csv

\- data/discovery/reports/discovery\_report.md



Columnas mínimas:

\- office\_name

\- website

\- root\_domain

\- plaats

\- gemeente

\- provincie

\- source\_origin

\- source\_origin\_url

\- membership\_type

\- aanbod\_url

\- aanbod\_url\_quality

\- confidence

\- needs\_review

\- review\_reason

\- discovered\_at



\## Criterio de hecho



No avanzamos al scraper de viviendas hasta tener:

\- reporte de cobertura por gemeente;

\- deduplicación razonable por root\_domain + plaats + office\_name;

\- lista de missing websites;

\- lista de missing aanbod\_url;

\- lista de agregadores útiles;

\- benchmark frente al seed inicial.

