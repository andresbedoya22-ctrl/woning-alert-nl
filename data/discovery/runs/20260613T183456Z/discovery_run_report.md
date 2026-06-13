# Discovery Run Report

## Summary
- Province: Noord-Brabant
- Run timestamp: 20260613T183456Z
- Seed count: 413
- Generated queries count: 448
- Free external discovery enabled: true
- Live aanbod enabled: false
- Audit aanbod enabled: true
- Overpass status: ok_fallback
- Overpass cache used: false
- Overpass cache timestamp: (none)
- Overpass source: fallback
- Overpass raw candidates: 132
- Overpass candidates with website: 94
- Overpass candidates without website: 38
- Overpass new domains added: 48
- Overpass duplicates vs seed: 41
- External candidates found: 132
- Analyzed candidates count: 550
- Valid aanbod_url after Overpass: 303
- Suspect after Overpass: 35
- Missing aanbod_url after Overpass: 212
- Live sites attempted: 0
- Live sites success: 0
- Live sites failed: 0
- Audited sites count: 204
- Browser audit valid found: 8
- Browser audit suspect found: 14
- Browser audit missing/failed: 182
- Browser audit unique valid domains: 7
- Browser audit unique valid URLs: 7
- Browser audit duplicate valid rows: 1
- Existing valid aanbod_url kept: 295
- New valid aanbod_url found: 0
- New suspect aanbod_url found: 0
- Valid aanbod_url after audit: 303
- Missing aanbod_url after audit: 212
- Active official sources count: 303
- Suspect review queue count: 35
- Missing website review count: 33
- Still missing aanbod_url: 212
- Rejected count: 51
- Discovered sources count: 438
- Rejected candidates count: 50
- Deduped candidates count: 62
- Skipped candidates count: 0
- Reconciliation check: analyzed=550, discovered+rejected+deduped+skipped=550

## Overpass Status Explanation
Overpass primary mirror failed; external discovery completed using the fallback mirror.

## Overpass Errors
- https://overpass-api.de/api/interpreter: Overpass request failed after 3 attempts: Client error '406 Not Acceptable' for url 'https://overpass-api.de/api/interpreter'
For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/406

## Overpass Place Normalization Summary
- alias: 13
- current_gemeente: 69
- former_gemeente: 18
- locality_to_gemeente: 14
- needs_review: 12

## Overpass unmapped places
- (empty): 12

## Live Aanbod Repair Summary
### Live Aanbod Attempts Breakdown
- None

### Top failure reasons
- None

### Top domains repaired
- None

### Top failed domains
- None

### Top successful detections
- None

### New valid URLs table
| office_name | root_domain | aanbod_url | method | score |
| --- | --- | --- | --- | --- |
| None | - | - | - | - |

### New suspect URLs table
| office_name | root_domain | aanbod_url | method | score |
| --- | --- | --- | --- | --- |
| None | - | - | - | - |

## Aanbod Auditor Summary
- Audit aanbod enabled: true
- Audited sites count: 204
- Browser audit valid found: 8
- Browser audit suspect found: 14
- Browser audit missing: 17
- Browser audit failed_fetch: 165
- Browser audit unique valid domains: 7
- Browser audit unique valid URLs: 7
- Browser audit duplicate valid rows: 1
- Average confidence: 10.6

### Top valid detections
- vhno.nl: score=100 type=listing_index url=https://vhno.nl/aanbod
- hofstedelandvanheusden.nl: score=100 type=listing_index url=https://hofstedelandvanheusden.nl/aanbod
- hofstedemakelaardij.nl: score=100 type=listing_index url=https://hofstedemakelaardij.nl/aanbod
- wernersandersmakelaardij.nl: score=100 type=listing_index url=https://www.wernersandersmakelaardij.nl/aanbod/woningaanbod
- biemansmakelaardij.nl: score=100 type=listing_index url=https://www.biemansmakelaardij.nl/makelaardij/qualis/qualis-woningaanbod-via-biemans
- vanhelvoortmakelaardij.nl: score=100 type=listing_index url=https://www.vanhelvoortmakelaardij.nl/aanbod-beek-en-donk
- hofstedelandvanheusden.nl: score=100 type=listing_index url=https://hofstedelandvanheusden.nl/aanbod
- tsas.nl: score=100 type=listing_index url=https://www.tsas.nl/aanbod

### Top suspect detections
- pradium.nl: score=100 type=property_detail url=https://pradium.nl/aanbod
- biemansmade.nl: score=100 type=project_page url=https://www.biemansmade.nl/nl/woningaanbod
- bogaersmakelaardij.nl: score=100 type=project_page url=https://bogaersmakelaardij.nl/woningaanbod
- kruijswijkmakelaardij.nl: score=100 type=project_page url=https://www.kruijswijkmakelaardij.nl/aanbod
- hartvanbrabantmakelaardij.nl: score=100 type=project_page url=https://hartvanbrabantmakelaardij.nl
- vandenboschmakelaars.com: score=100 type=property_detail url=https://www.vandenboschmakelaars.com/woning-dongen
- atenzijlstra.nl: score=100 type=project_page url=https://atenzijlstra.nl/aanbod
- vanakenmakelaardij.nl: score=100 type=property_detail url=https://vanakenmakelaardij.nl/woningen
- hj-makelaars.nl: score=95 type=property_detail url=https://www.hj-makelaars.nl/huis-kopen-tilburg
- debontmakelaardij.nl: score=91 type=project_page url=https://debontmakelaardij.nl/Nieuws/1200/Hulp-nodig-bij-aankoop-.html

### Top failed domains
- brabantmakelaardij.nl: 5
- erafocus.nl: 3
- atenzijlstra.nl: 3
- taxanja.nl: 2
- berkerstaxaties.nl: 2
- lommersmakelaars.nl: 2
- devierwindenmakelaardij.nl: 2
- nuyensmakelaars.nl: 2
- storimansenpartners.nl: 2
- vandenboschmakelaars.com: 2

## Source Master Summary
- Active official sources count: 303
- Suspect review queue count: 35
- Total source master rows: 550

## Overpass Cache Status
- Overpass cache used: false
- Overpass cache timestamp: (none)
- Overpass source: fallback

## WebsiteResolver Summary
- WebsiteResolver resolved count: 5
- WebsiteResolver unresolved count: 33
- Missing website review count: 33

## Aggregator Fallback Registry Status
- Registry rows: 3
- Disabled adapters count: 3
- Huispedia: adapter_enabled=false, permission_status=needs_review
- Huislijn: adapter_enabled=false, permission_status=needs_review
- Funda: adapter_enabled=false, permission_status=not_allowed_for_scraping

## Coverage By Gemeente
| gemeente | total | valid | suspect | missing | rejected | valid_aanbod | weak_score |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 's-Hertogenbosch | 27 | 13 | 6 | 4 | 4 | 14 | 40 |
| (unknown) | 14 | 0 | 4 | 0 | 10 | 0 | 53 |
| Alphen-Chaam | 2 | 2 | 0 | 0 | 0 | 2 | 0 |
| Altena | 20 | 12 | 4 | 3 | 1 | 13 | 21 |
| Asten | 4 | 3 | 0 | 1 | 0 | 3 | 3 |
| Baarle-Nassau | 1 | 1 | 0 | 0 | 0 | 1 | 0 |
| Bergeijk | 4 | 1 | 2 | 0 | 1 | 1 | 8 |
| Bergen op Zoom | 7 | 4 | 2 | 0 | 1 | 4 | 8 |
| Bernheze | 4 | 4 | 0 | 0 | 0 | 4 | 0 |
| Best | 3 | 2 | 1 | 0 | 0 | 2 | 2 |
| Bladel | 2 | 2 | 0 | 0 | 0 | 2 | 0 |
| Boekel | 1 | 1 | 0 | 0 | 0 | 1 | 0 |
| Boxtel | 5 | 2 | 1 | 0 | 2 | 2 | 10 |
| Breda | 25 | 13 | 7 | 2 | 3 | 13 | 32 |
| Cranendonck | 2 | 2 | 0 | 0 | 0 | 2 | 0 |
| Deurne | 6 | 4 | 1 | 1 | 0 | 4 | 5 |
| Dongen | 3 | 1 | 2 | 0 | 0 | 1 | 4 |
| Drimmelen | 12 | 7 | 2 | 2 | 1 | 7 | 14 |
| Eersel | 3 | 3 | 0 | 0 | 0 | 3 | 0 |
| Eindhoven | 27 | 13 | 5 | 8 | 1 | 12 | 38 |
| Etten-Leur | 6 | 5 | 0 | 1 | 0 | 5 | 3 |
| Geertruidenberg | 12 | 10 | 1 | 0 | 1 | 8 | 6 |
| Geldrop-Mierlo | 5 | 4 | 1 | 0 | 0 | 4 | 2 |
| Gemert-Bakel | 5 | 4 | 1 | 0 | 0 | 4 | 2 |
| Gilze en Rijen | 5 | 1 | 1 | 0 | 3 | 1 | 14 |
| Goirle | 4 | 3 | 1 | 0 | 0 | 3 | 2 |
| Halderberge | 5 | 5 | 0 | 0 | 0 | 5 | 0 |
| Heeze-Leende | 4 | 3 | 1 | 0 | 0 | 3 | 2 |
| Helmond | 17 | 14 | 2 | 1 | 0 | 14 | 7 |
| Heusden | 17 | 12 | 2 | 3 | 0 | 13 | 13 |
| Hilvarenbeek | 5 | 4 | 0 | 1 | 0 | 4 | 3 |
| Laarbeek | 6 | 5 | 1 | 0 | 0 | 5 | 2 |
| Land van Cuijk | 20 | 9 | 3 | 4 | 4 | 9 | 34 |
| Loon op Zand | 1 | 1 | 0 | 0 | 0 | 1 | 0 |
| Maashorst | 13 | 9 | 4 | 0 | 0 | 11 | 8 |
| Meierijstad | 21 | 16 | 4 | 1 | 0 | 16 | 11 |
| Moerdijk | 9 | 5 | 1 | 2 | 1 | 6 | 12 |
| Nuenen, Gerwen en Nederwetten | 9 | 5 | 3 | 1 | 0 | 6 | 9 |
| Oirschot | 6 | 4 | 0 | 2 | 0 | 4 | 6 |
| Oisterwijk | 12 | 9 | 2 | 1 | 0 | 9 | 7 |
| Oosterhout | 15 | 8 | 3 | 2 | 2 | 8 | 20 |
| Oss | 12 | 9 | 2 | 1 | 0 | 10 | 7 |
| Reusel-De Mierden | 4 | 1 | 1 | 1 | 1 | 1 | 9 |
| Roosendaal | 14 | 5 | 9 | 0 | 0 | 5 | 18 |
| Rucphen | 1 | 1 | 0 | 0 | 0 | 1 | 0 |
| Sint-Michielsgestel | 3 | 2 | 0 | 0 | 1 | 2 | 4 |
| Someren | 4 | 3 | 0 | 1 | 0 | 3 | 3 |
| Son en Breugel | 5 | 1 | 2 | 1 | 1 | 1 | 11 |
| Steenbergen | 1 | 1 | 0 | 0 | 0 | 1 | 0 |
| Tilburg | 38 | 16 | 14 | 4 | 4 | 16 | 56 |
| Veldhoven | 3 | 0 | 0 | 0 | 3 | 0 | 17 |
| Vught | 10 | 6 | 1 | 0 | 3 | 5 | 14 |
| Waalre | 6 | 5 | 1 | 0 | 0 | 4 | 2 |
| Waalwijk | 9 | 7 | 1 | 0 | 1 | 7 | 6 |
| Woensdrecht | 7 | 4 | 2 | 0 | 1 | 4 | 8 |
| Zundert | 2 | 2 | 0 | 0 | 0 | 2 | 0 |

## Missing Expected Gemeenten After Overpass
### Expected gemeenten with rejected-only candidates
- Veldhoven

### Expected gemeenten still with zero candidates
- Valkenswaard

## Deduplication Summary
- Unique sources after dedupe: 488
- Deduped candidates removed from final outputs: 62
- Skipped candidates during analysis: 0

## Top 15 Gemeenten Still Weak
- Tilburg: weak_score=56, valid=16, suspect=14, missing=4, rejected=4
- (unknown): weak_score=53, valid=0, suspect=4, missing=0, rejected=10
- 's-Hertogenbosch: weak_score=40, valid=13, suspect=6, missing=4, rejected=4
- Eindhoven: weak_score=38, valid=13, suspect=5, missing=8, rejected=1
- Land van Cuijk: weak_score=34, valid=9, suspect=3, missing=4, rejected=4
- Breda: weak_score=32, valid=13, suspect=7, missing=2, rejected=3
- Altena: weak_score=21, valid=12, suspect=4, missing=3, rejected=1
- Oosterhout: weak_score=20, valid=8, suspect=3, missing=2, rejected=2
- Roosendaal: weak_score=18, valid=5, suspect=9, missing=0, rejected=0
- Veldhoven: weak_score=17, valid=0, suspect=0, missing=0, rejected=3
- Drimmelen: weak_score=14, valid=7, suspect=2, missing=2, rejected=1
- Gilze en Rijen: weak_score=14, valid=1, suspect=1, missing=0, rejected=3
- Vught: weak_score=14, valid=6, suspect=1, missing=0, rejected=3
- Heusden: weak_score=13, valid=12, suspect=2, missing=3, rejected=0
- Moerdijk: weak_score=12, valid=5, suspect=1, missing=2, rejected=1

## Top Recommended Query Targets
- Valkenswaard: priority=150, discovered=0, total=0, valid=0
- Veldhoven: priority=147, discovered=0, total=3, valid=0
- Baarle-Nassau: priority=69, discovered=1, total=1, valid=1
- Boekel: priority=69, discovered=1, total=1, valid=1
- Loon op Zand: priority=69, discovered=1, total=1, valid=1
- Rucphen: priority=69, discovered=1, total=1, valid=1
- Steenbergen: priority=69, discovered=1, total=1, valid=1
- Gilze en Rijen: priority=45, discovered=2, total=5, valid=1
- Alphen-Chaam: priority=38, discovered=2, total=2, valid=2
- Bladel: priority=38, discovered=2, total=2, valid=2
- Cranendonck: priority=38, discovered=2, total=2, valid=2
- Zundert: priority=38, discovered=2, total=2, valid=2
- Sint-Michielsgestel: priority=37, discovered=2, total=3, valid=2
- Dongen: priority=27, discovered=3, total=3, valid=1
- Bergeijk: priority=26, discovered=3, total=4, valid=1

## Next Recommended Actions
- Investigate expected gemeenten with zero discovered sources after Overpass: Valkenswaard.
- Review rejected-only gemeenten where candidates were found but none were accepted: Veldhoven.
- Review offices with missing aanbod_url and validate suggested common paths on official websites.
- Manually verify suspect aanbod_url pages that look commercial or ambiguous.
- Prioritize weak gemeenten first: Tilburg, (unknown), 's-Hertogenbosch, Eindhoven, Land van Cuijk.
