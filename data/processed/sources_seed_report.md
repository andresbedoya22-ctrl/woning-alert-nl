# Sources Seed Report

## Resumen
- Registros de entrada: 417
- Registros de salida: 413
- Duplicados eliminados: 4
- Cantidad con website: 395
- Cantidad con koopaanbod_url: 323
- koopaanbod_url valid: 295
- koopaanbod_url suspect: 28
- koopaanbod_url missing: 90
- Cantidad needs_review: 118

## Top 20 root_domain repetidos
- `staete.nl`: 7
- `kinmakelaars.nl`: 7
- `amb-makelaars.nl`: 5
- `idealemakelaar.nl`: 4
- `hendriks.nl`: 4
- `vansantvoort.nl`: 4
- `krabben.nl`: 4
- `erafocus.nl`: 3
- `biemansmade.nl`: 3
- `bogaersmakelaardij.nl`: 3
- `verbrugge.com`: 3
- `eraoosterhout.nl`: 3
- `biemansmakelaardij.nl`: 3
- `vdplas.nl`: 3
- `noudkopsmakelaardij.nl`: 3
- `mrmakelaardij.nl`: 3
- `klijsen.nl`: 3
- `vbtmakelaars.nl`: 3
- `woonplezier.nl`: 3
- `carredewit.nl`: 3

## Top 20 suspect koopaanbod_url
| office_name | koopaanbod_url | reason |
| --- | --- | --- |
| Nouwen Makelaardij o.g. b.v. | https://nouwen.nl/gratis-verkoopadvies | suspect koopaanbod_url: contains excluded token 'gratis-verkoopadvies' |
| Brabant Makelaardij | https://www.brabantmakelaardij.nl/huis-verkopen-bergen-op-zoom | suspect koopaanbod_url: missing listing signal |
| DE VIERWINDEN MAKELAARDIJ B.V. | https://www.devierwindenmakelaardij.nl/property/holleweg-187-bergen-op-zoom-612 | suspect koopaanbod_url: missing listing signal |
| Van den Berk & Kerkhof Makelaars en Taxateurs | https://www.berkkerkhof.nl/actueel/ontdek-het-nieuwbouwproject | suspect koopaanbod_url: missing listing signal |
| Bink & Partners | https://binkenpartners.nl/huis-verkopen-breda | suspect koopaanbod_url: missing listing signal |
| Van den Bosch Makelaars | https://www.vandenboschmakelaars.com/diensten/verkoopmakelaar | suspect koopaanbod_url: contains excluded token 'diensten' |
| Biemans Made, Makelaardij o.z. en Hypotheken | http://www.biemansmade.nl/nl/diensten/verkoop | suspect koopaanbod_url: contains excluded token 'diensten' |
| ERA Makelaardij Amerstreek | http://www.eramakelaardijamerstreek.nl/raamsdonksveer/era-makelaardij-amerstreek/verkoopmakelaar-raamsdonksveer | suspect koopaanbod_url: contains excluded token 'verkoopmakelaar' |
| Lemon Suites | https://www.lemonsuites.nl/woning-huren | suspect koopaanbod_url: missing listing signal |
| Biemans Made, Makelaardij o.z. en Hypotheken | http://www.biemansmade.nl/nl/diensten/verkoop | suspect koopaanbod_url: contains excluded token 'diensten' |
| ERA Makelaardij Amerstreek | http://www.eramakelaardijamerstreek.nl/raamsdonksveer/era-makelaardij-amerstreek/verkoopmakelaar-raamsdonksveer | suspect koopaanbod_url: contains excluded token 'verkoopmakelaar' |
| Van Tuijl makelaardij | https://vantuijl-makelaardij.nl/woning-kopen | suspect koopaanbod_url: missing listing signal |
| Makelaardij Twan Poels | https://www.twanpoels.nl/nieuwbouw | suspect koopaanbod_url: missing listing signal |
| Woonschuijt Makelaars | http://www.woonschuijt.nl/wonen/diensten/huis-verkopen | suspect koopaanbod_url: contains excluded token 'diensten' |
| Van Tuijl makelaardij | https://vantuijl-makelaardij.nl/woning-kopen | suspect koopaanbod_url: missing listing signal |
| Gijs Claassen Vastgoed advies | https://www.gijsclaassen.nl | suspect koopaanbod_url: missing listing signal |
| Quinten Vastgoed | https://www.funda.nl/makelaarsmatch | suspect koopaanbod_url: missing listing signal |
| Gijs Claassen Vastgoed advies | https://www.gijsclaassen.nl | suspect koopaanbod_url: missing listing signal |
| Biemans Made, Makelaardij o.z. en Hypotheken | http://www.biemansmade.nl/nl/diensten/verkoop | suspect koopaanbod_url: contains excluded token 'diensten' |
| De Landerije Maas en Waal | https://www.landerije.nl/diensten/stille-verkoop | suspect koopaanbod_url: contains excluded token 'diensten' |

## Primeras 20 filas limpias
| office_name | website | domain | root_domain | koopaanbod_url | koopaanbod_url_quality | plaats | provincie | source_type | discovery_source | confidence | needs_review | review_reason | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Makelaars- en Adviesburo Broeders | http://www.broedersmakelaardij.nl | broedersmakelaardij.nl | broedersmakelaardij.nl | http://www.broedersmakelaardij.nl/aanbod/woningaanbod/gilze/koop/huis-10225430-Nerhovensestraat-17 | valid | Alphen Chaam | Noord-Brabant | makelaar_site | nvm_harvester_2026_06_12 | 0.85 | false |  | prijzen=4, koop=5, huur=0 |
| Van Hoven & Oomen | https://www.vhno.nl | vhno.nl | vhno.nl |  | missing | Alphen Chaam | Noord-Brabant | makelaar_site | nvm_harvester_2026_06_12 | 0.65 | true | missing koopaanbod_url | home did not load; missing koopaanbod_url |
| Baas Makelaardij B.V. | http://www.baasmakelaardij.nl | baasmakelaardij.nl | baasmakelaardij.nl | http://www.baasmakelaardij.nl/aanbod/woningaanbod/dordrecht/koop/huis-10137064-Dubbeldamseweg-Noord-17 | valid | Altena | Noord-Brabant | makelaar_site | nvm_harvester_2026_06_12 | 0.85 | false |  | prijzen=4, koop=4, huur=0 |
| Hofstede Bedrijfshuisvesting B.V. | https://www.hofstedebedrijfshuisvesting.nl | hofstedebedrijfshuisvesting.nl | hofstedebedrijfshuisvesting.nl |  | missing | Altena | Noord-Brabant | makelaar_site | nvm_harvester_2026_06_12 | 0.65 | true | missing koopaanbod_url | home did not load; missing koopaanbod_url |
| Hofstede Land van Heusden | https://www.hofstedelandvanheusden.nl | hofstedelandvanheusden.nl | hofstedelandvanheusden.nl |  | missing | Altena | Noord-Brabant | makelaar_site | nvm_harvester_2026_06_12 | 0.65 | true | missing koopaanbod_url | home did not load; missing koopaanbod_url |
| Hofstede Makelaardij Werkendam | http://www.hofstedemakelaardij.nl | hofstedemakelaardij.nl | hofstedemakelaardij.nl |  | missing | Altena | Noord-Brabant | makelaar_site | nvm_harvester_2026_06_12 | 0.65 | true | missing koopaanbod_url | home did not load; missing koopaanbod_url |
| Hoogveste B.V. | http://www.hoogveste.nl | hoogveste.nl | hoogveste.nl | http://www.hoogveste.nl/aanbod/woningaanbod/nieuwe-niedorp/koop/huis-10300026-Vijverweg-1673 | valid | Altena | Noord-Brabant | makelaar_site | nvm_harvester_2026_06_12 | 0.85 | false |  | prijzen=9, koop=4, huur=0 |
| Kolpa OZP makelaars | http://www.kolpa-ozp.nl | kolpa-ozp.nl | kolpa-ozp.nl |  | missing | Altena | Noord-Brabant | makelaar_site | nvm_harvester_2026_06_12 | 0.65 | true | missing koopaanbod_url | sin candidatos de koop; missing koopaanbod_url |
| Lamper & van Vliet Woningmakelaars | http://www.lvmakelaars.nl | lvmakelaars.nl | lvmakelaars.nl | https://www.lvmakelaars.nl/wonen | valid | Altena | Noord-Brabant | makelaar_site | nvm_harvester_2026_06_12 | 0.85 | false |  | prijzen=12, koop=2, huur=0 |
| Merwelanden Vastgoed Associatie BV | http://www.merwelanden-makelaardij.nl | merwelanden-makelaardij.nl | merwelanden-makelaardij.nl |  | missing | Altena | Noord-Brabant | makelaar_site | nvm_harvester_2026_06_12 | 0.65 | true | missing koopaanbod_url | sin candidatos de koop; missing koopaanbod_url |
| Mol & Roubos Makelaardij | http://www.molroubosmakelaardij.nl | molroubosmakelaardij.nl | molroubosmakelaardij.nl | https://molroubosmakelaardij.nl/aanbod | valid | Altena | Noord-Brabant | makelaar_site | nvm_harvester_2026_06_12 | 0.85 | false |  | prijzen=27, koop=1, huur=0 |
| Nouwen Makelaardij o.g. b.v. | http://www.nouwen.nl | nouwen.nl | nouwen.nl | https://nouwen.nl/gratis-verkoopadvies | suspect | Altena | Noord-Brabant | makelaar_site | nvm_harvester_2026_06_12 | 0.65 | true | suspect koopaanbod_url: contains excluded token 'gratis-verkoopadvies' | mejor candidato sin verificar (score=1.58); suspect koopaanbod_url: contains excluded token 'gratis-verkoopadvies' |
| NVW Vastgoed B.V. |  |  |  |  | missing | Altena | Noord-Brabant | makelaar_site | nvm_harvester_2026_06_12 | 0.40 | true | missing website; missing koopaanbod_url; missing domain; missing root_domain | missing website; missing koopaanbod_url; missing domain; missing root_domain |
| Oomen Makelaardij & Taxaties | http://www.oomenmakelaardij.nl | oomenmakelaardij.nl | oomenmakelaardij.nl | https://www.oomenmakelaardij.nl/wonen | valid | Altena | Noord-Brabant | makelaar_site | nvm_harvester_2026_06_12 | 0.85 | false |  | prijzen=146, koop=3, huur=0 |
| Paans Makelaars in onroerende goederen | http://www.paansmakelaars.nl | paansmakelaars.nl | paansmakelaars.nl | https://www.paansmakelaars.nl/aanbod/koopwoningen | valid | Altena | Noord-Brabant | makelaar_site | nvm_harvester_2026_06_12 | 0.85 | false |  | prijzen=24, koop=2, huur=0 |
| Taxanja Taxaties | https://www.taxanja.nl | taxanja.nl | taxanja.nl |  | missing | Altena | Noord-Brabant | makelaar_site | nvm_harvester_2026_06_12 | 0.65 | true | missing koopaanbod_url | sin candidatos de koop; missing koopaanbod_url |
| Van Geffen Makelaardij | http://www.vangeffen.nl | vangeffen.nl | vangeffen.nl | https://www.vangeffen.nl/aanbod/koopwoningen | valid | Altena | Noord-Brabant | makelaar_site | nvm_harvester_2026_06_12 | 0.85 | false |  | prijzen=5, koop=1, huur=0 |
| ViaJoop Makelaardij | http://www.viajoop.nl | viajoop.nl | viajoop.nl | http://www.viajoop.nl/woningen?type=koop | valid | Altena | Noord-Brabant | makelaar_site | nvm_harvester_2026_06_12 | 0.85 | false |  | prijzen=142, koop=3, huur=1 |
| Vos Woningmakelaardij | https://www.voswoningmakelaardij.nl | voswoningmakelaardij.nl | voswoningmakelaardij.nl | https://www.voswoningmakelaardij.nl/aanbod | valid | Altena | Noord-Brabant | makelaar_site | nvm_harvester_2026_06_12 | 0.85 | false |  | prijzen=12, koop=1, huur=0 |
| Waltmann & Co. Papendrecht b.v. | http://www.waltmann.com | waltmann.com | waltmann.com | https://www.waltmann.com/aanbod/koopwoningen | valid | Altena | Noord-Brabant | makelaar_site | nvm_harvester_2026_06_12 | 0.85 | false |  | prijzen=20, koop=2, huur=0 |

## Advertencias
- Columnas no mapeadas: `adres`, `provincie`, `bronnen`, `koopaanbod_confidence`, `koopaanbod_metodo`, `platform_hint`, `requires_js`
- Hay registros marcados para manual review.
