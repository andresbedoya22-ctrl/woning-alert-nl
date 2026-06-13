# Discovery Run Report

## Summary
- Province: Noord-Brabant
- Run timestamp: 20260613T192452Z
- Seed count: 413
- Generated queries count: 448
- Free external discovery enabled: false
- Live aanbod enabled: false
- Audit aanbod enabled: true
- Overpass status: skipped_cli
- Overpass cache used: false
- Overpass cache timestamp: (none)
- Overpass source: none
- Overpass raw candidates: 0
- Overpass candidates with website: 0
- Overpass candidates without website: 0
- Overpass new domains added: 0
- Overpass duplicates vs seed: 0
- External candidates found: 0
- Analyzed candidates count: 413
- Valid aanbod_url after Overpass: 303
- Suspect after Overpass: 35
- Missing aanbod_url after Overpass: 75
- Live sites attempted: 0
- Live sites success: 0
- Live sites failed: 0
- Audited sites count: 100
- Browser audit valid found: 8
- Browser audit suspect found: 14
- Browser audit missing/failed: 78
- Browser audit unique valid domains: 7
- Browser audit unique valid URLs: 7
- Browser audit duplicate valid rows: 1
- Existing valid aanbod_url kept: 295
- New valid aanbod_url found: 0
- New suspect aanbod_url found: 0
- Valid aanbod_url after audit: 303
- Missing aanbod_url after audit: 75
- Active official sources count: 292
- Suspect review queue count: 35
- Missing website review count: 0
- Still missing aanbod_url: 75
- Rejected count: 18
- Discovered sources count: 384
- Rejected candidates count: 18
- Deduped candidates count: 11
- Skipped candidates count: 0
- Reconciliation check: analyzed=413, discovered+rejected+deduped+skipped=413

## Overpass Status Explanation
Overpass discovery was skipped because --skip-overpass was provided.

## Overpass Errors
- None

## Overpass Place Normalization Summary
- none: 0

## Overpass unmapped places
- None

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
- Audited sites count: 100
- Browser audit valid found: 8
- Browser audit suspect found: 14
- Browser audit missing: 17
- Browser audit failed_fetch: 61
- Browser audit unique valid domains: 7
- Browser audit unique valid URLs: 7
- Browser audit duplicate valid rows: 1
- Average confidence: 21.6

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
- erafocus.nl: 3
- taxanja.nl: 2
- berkerstaxaties.nl: 2
- lommersmakelaars.nl: 2
- brabantmakelaardij.nl: 2
- devierwindenmakelaardij.nl: 2
- biemansmakelaardij.nl: 2
- biemansmade.nl: 2
- bogaersmakelaardij.nl: 2
- hoogveldtmakelaardij.nl: 2

## Source Master Summary
- Total master sources: 402
- Active official sources count: 292
- Suspect review queue count: 35
- Inactive/missing count: 110

## Overpass Cache Status
- Overpass cache used: false
- Overpass cache timestamp: (none)
- Overpass source: none

## WebsiteResolver Summary
- WebsiteResolver resolved count: 0
- WebsiteResolver unresolved count: 0
- Missing website review count: 0

## Aggregator Fallback Registry Status
- Registry rows: 3
- Disabled adapters count: 3
- Huispedia: adapter_enabled=false, permission_status=needs_review
- Huislijn: adapter_enabled=false, permission_status=needs_review
- Funda: adapter_enabled=false, permission_status=not_allowed_for_scraping

## Coverage By Gemeente
| gemeente | total | valid | suspect | missing | rejected | valid_aanbod | weak_score |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 's-Hertogenbosch | 20 | 13 | 4 | 3 | 0 | 14 | 17 |
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
| Breda | 20 | 13 | 3 | 2 | 2 | 13 | 20 |
| Cranendonck | 2 | 2 | 0 | 0 | 0 | 2 | 0 |
| Deurne | 6 | 4 | 1 | 1 | 0 | 4 | 5 |
| Dongen | 3 | 1 | 1 | 1 | 0 | 1 | 5 |
| Drimmelen | 12 | 7 | 2 | 2 | 1 | 7 | 14 |
| Eersel | 3 | 3 | 0 | 0 | 0 | 3 | 0 |
| Eindhoven | 20 | 13 | 3 | 4 | 0 | 12 | 18 |
| Etten-Leur | 6 | 5 | 0 | 1 | 0 | 5 | 3 |
| Geertruidenberg | 12 | 10 | 1 | 0 | 1 | 8 | 6 |
| Geldrop-Mierlo | 4 | 4 | 0 | 0 | 0 | 4 | 0 |
| Gemert-Bakel | 4 | 4 | 0 | 0 | 0 | 4 | 0 |
| Gilze en Rijen | 3 | 1 | 1 | 0 | 1 | 1 | 6 |
| Goirle | 3 | 3 | 0 | 0 | 0 | 3 | 0 |
| Halderberge | 5 | 5 | 0 | 0 | 0 | 5 | 0 |
| Heeze-Leende | 4 | 3 | 1 | 0 | 0 | 3 | 2 |
| Helmond | 17 | 14 | 2 | 1 | 0 | 14 | 7 |
| Heusden | 17 | 12 | 2 | 3 | 0 | 13 | 13 |
| Hilvarenbeek | 4 | 4 | 0 | 0 | 0 | 4 | 0 |
| Laarbeek | 6 | 5 | 1 | 0 | 0 | 5 | 2 |
| Land van Cuijk | 16 | 9 | 2 | 2 | 3 | 9 | 22 |
| Loon op Zand | 1 | 1 | 0 | 0 | 0 | 1 | 0 |
| Maashorst | 11 | 9 | 2 | 0 | 0 | 11 | 4 |
| Meierijstad | 18 | 16 | 2 | 0 | 0 | 16 | 4 |
| Moerdijk | 9 | 5 | 1 | 2 | 1 | 6 | 12 |
| Nuenen, Gerwen en Nederwetten | 9 | 5 | 3 | 1 | 0 | 6 | 9 |
| Oirschot | 6 | 4 | 0 | 2 | 0 | 4 | 6 |
| Oisterwijk | 10 | 9 | 0 | 1 | 0 | 9 | 3 |
| Oosterhout | 12 | 8 | 2 | 1 | 1 | 8 | 11 |
| Oss | 11 | 9 | 1 | 1 | 0 | 10 | 5 |
| Reusel-De Mierden | 4 | 1 | 1 | 1 | 1 | 1 | 9 |
| Roosendaal | 9 | 5 | 4 | 0 | 0 | 5 | 8 |
| Rucphen | 1 | 1 | 0 | 0 | 0 | 1 | 0 |
| Sint-Michielsgestel | 2 | 2 | 0 | 0 | 0 | 2 | 0 |
| Someren | 4 | 3 | 0 | 1 | 0 | 3 | 3 |
| Son en Breugel | 3 | 1 | 1 | 1 | 0 | 1 | 5 |
| Steenbergen | 1 | 1 | 0 | 0 | 0 | 1 | 0 |
| Tilburg | 20 | 16 | 3 | 1 | 0 | 16 | 9 |
| Vught | 8 | 6 | 1 | 0 | 1 | 5 | 6 |
| Waalre | 6 | 5 | 1 | 0 | 0 | 4 | 2 |
| Waalwijk | 8 | 7 | 1 | 0 | 0 | 7 | 2 |
| Woensdrecht | 7 | 4 | 2 | 0 | 1 | 4 | 8 |
| Zundert | 2 | 2 | 0 | 0 | 0 | 2 | 0 |

## Missing Expected Gemeenten After Overpass
### Expected gemeenten with rejected-only candidates
- None

### Expected gemeenten still with zero candidates
- Valkenswaard
- Veldhoven

## Deduplication Summary
- Unique sources after dedupe: 402
- Deduped candidates removed from final outputs: 11
- Skipped candidates during analysis: 0

## Top 15 Gemeenten Still Weak
- Land van Cuijk: weak_score=22, valid=9, suspect=2, missing=2, rejected=3
- Altena: weak_score=21, valid=12, suspect=4, missing=3, rejected=1
- Breda: weak_score=20, valid=13, suspect=3, missing=2, rejected=2
- Eindhoven: weak_score=18, valid=13, suspect=3, missing=4, rejected=0
- 's-Hertogenbosch: weak_score=17, valid=13, suspect=4, missing=3, rejected=0
- Drimmelen: weak_score=14, valid=7, suspect=2, missing=2, rejected=1
- Heusden: weak_score=13, valid=12, suspect=2, missing=3, rejected=0
- Moerdijk: weak_score=12, valid=5, suspect=1, missing=2, rejected=1
- Oosterhout: weak_score=11, valid=8, suspect=2, missing=1, rejected=1
- Boxtel: weak_score=10, valid=2, suspect=1, missing=0, rejected=2
- Nuenen, Gerwen en Nederwetten: weak_score=9, valid=5, suspect=3, missing=1, rejected=0
- Reusel-De Mierden: weak_score=9, valid=1, suspect=1, missing=1, rejected=1
- Tilburg: weak_score=9, valid=16, suspect=3, missing=1, rejected=0
- Bergeijk: weak_score=8, valid=1, suspect=2, missing=0, rejected=1
- Bergen op Zoom: weak_score=8, valid=4, suspect=2, missing=0, rejected=1

## Top Recommended Query Targets
- Valkenswaard: priority=150, discovered=0, total=0, valid=0
- Veldhoven: priority=150, discovered=0, total=0, valid=0
- Baarle-Nassau: priority=69, discovered=1, total=1, valid=1
- Boekel: priority=69, discovered=1, total=1, valid=1
- Loon op Zand: priority=69, discovered=1, total=1, valid=1
- Rucphen: priority=69, discovered=1, total=1, valid=1
- Steenbergen: priority=69, discovered=1, total=1, valid=1
- Gilze en Rijen: priority=47, discovered=2, total=3, valid=1
- Alphen-Chaam: priority=38, discovered=2, total=2, valid=2
- Bladel: priority=38, discovered=2, total=2, valid=2
- Cranendonck: priority=38, discovered=2, total=2, valid=2
- Sint-Michielsgestel: priority=38, discovered=2, total=2, valid=2
- Zundert: priority=38, discovered=2, total=2, valid=2
- Dongen: priority=27, discovered=3, total=3, valid=1
- Son en Breugel: priority=27, discovered=3, total=3, valid=1

## Next Recommended Actions
- Investigate expected gemeenten with zero discovered sources after Overpass: Valkenswaard, Veldhoven.
- Review offices with missing aanbod_url and validate suggested common paths on official websites.
- Manually verify suspect aanbod_url pages that look commercial or ambiguous.
- Prioritize weak gemeenten first: Land van Cuijk, Altena, Breda, Eindhoven, 's-Hertogenbosch.
