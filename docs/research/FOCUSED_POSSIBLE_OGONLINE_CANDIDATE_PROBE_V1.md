# Focused Possible OGonline Candidate Probe v1

## Objective

Run a narrow controlled follow-up probe against the best remaining possible OGonline candidates to either find a deterministic OGonline/XHR endpoint or downgrade the candidates when the evidence is not compatible.

This was a discovery/probe phase only. It was not a second OGonline makelaar validation run.

## Inputs

- Previous report: `docs/research/OGONLINE_CANDIDATE_RECLASSIFICATION_DISCOVERY_V1.md`
- Allowed candidates from that report:
  - `kernmakelaars.nl__tilburg`
  - `lemmens.nl__tilburg`
  - `architectuurmakelaar.nl__tilburg`
  - `hendriks.nl__tilburg`
- Listing URLs reused from the previous report only.
- Existing robots gate: `scraper/src/domek_wonen/compliance/robots_gate.py`
- Existing OGonline parser/source-config path:
  - `scraper/src/domek_wonen/pilots/ogonline_xhr_live_fetch.py`
  - `scraper/src/domek_wonen/pilots/ogonline_xhr_paginated_runner.py`
  - `scraper/src/domek_wonen/parsers/source_config.py`
  - `scraper/src/domek_wonen/parsers/ogonline_xhr_family.py`
  - `scraper/src/domek_wonen/parsers/runner.py`

## Scope and constraints

- No broad crawl.
- No Google.
- No browser, Playwright, Selenium, proxies, or stealth behavior.
- No Funda or Pararius.
- No matching, email, n8n, dashboard, or eligibility changes.
- No `data/raw` changes.
- No raw HTML or JSON persisted.
- Responses were held in memory only.
- `robots_gate.can_fetch(domain, path)` was checked before every page, script, endpoint, or detail fetch.
- Maximum five fetches per candidate domain.
- Only compact marker snippets were retained in this report.
- No parser per makelaar was created.

## Domains probed

- `kernmakelaars.nl`
- `lemmens.nl`
- `architectuurmakelaar.nl`
- `hendriks.nl`

## Fetch budget used

| domain | fetches | fetch labels |
| --- | ---: | --- |
| `kernmakelaars.nl` | 4 | listing, homepage, script_1, detail |
| `lemmens.nl` | 5 | listing, homepage, script_1, script_2, api_candidate |
| `architectuurmakelaar.nl` | 2 | listing, homepage |
| `hendriks.nl` | 5 | listing, homepage, script_1, script_2, api_candidate |

## Results by candidate

| source_id | domain | fetches | robots | markers | api_candidate | parser_probe | classification | next_step |
| --- | --- | ---: | --- | --- | --- | --- | --- | --- |
| `kernmakelaars.nl__tilburg` | `kernmakelaars.nl` | 4 | allow for all fetched URLs | `window.__` only in same-domain app script | none | not run | `possible_but_no_api` | Keep as possible non-OGonline candidate only; no second validation. |
| `lemmens.nl__tilburg` | `lemmens.nl` | 5 | allow for all fetched URLs | generic `/api/`; generic `docs` text from page copy | false-positive same-domain URL wrapping Google Maps path; returned `http_404` | not run | `not_ogonline` | Do not use as OGonline/XHR candidate. |
| `architectuurmakelaar.nl__tilburg` | `architectuurmakelaar.nl` | 2 | allow for listing and homepage | none | none | not run | `not_ogonline` | No OGonline/XHR follow-up recommended. |
| `hendriks.nl__tilburg` | `hendriks.nl` | 5 | allow for all fetched URLs | generic `/api/` in scripts | `https://hendriks.nl/api/offices`, JSON, not listing inventory and no OGonline docs markers | not run | `not_ogonline` | Treat as custom API/manual source, not OGonline/XHR. |

## Compact marker snippets

`kernmakelaars.nl`:

- `window.__`: `ar k=function(){function e(){this._store=d(O,window.__REDUX_DEVTOOLS_EXTENSION__&&window.__REDUX_DE`

`lemmens.nl`:

- `docs`: `en overige bijlagen</h3> <ul class="other-docs-list"> <li> <a class="`
- `/api/`: `c defer src="https://maps.googleapis.com/maps/api/js?key=AIzaSyCmvyPAOQqwCdeF3XI6V0Mgwgv2SxFwRH`

`architectuurmakelaar.nl`:

- No requested markers found.

`hendriks.nl`:

- `/api/`: `s:f=3,url:d="https://maps.googleapis.com/maps/api/js",version:g}){if(this.callbacks=[],this.don`

## Parser probe result if any

No parser probe was executed.

Reason:

- No candidate exposed a deterministic OGonline/XHR listing endpoint.
- No candidate exposed an API payload with `docs`, `totalDocs`, `totalPages`, or `hasNextPage`.
- The only fetched JSON endpoint was `https://hendriks.nl/api/offices`, which is an offices endpoint, not a listing inventory endpoint, and therefore is not compatible with `ParserSourceConfig` plus `OGonlineXHRParserFamily`.

## Final decision

No candidate is ready for `Second OGonline Makelaar Validation v1`.

The previous best handoff, `kernmakelaars.nl__tilburg`, remains the least-bad possible candidate only because it is reachable and policy-allowed, but this focused probe found no OGonline marker, no `api.ogonline`, no `ogonline.nl`, no `docs` payload marker, and no deterministic API endpoint.

## Recommendation

Do not start second OGonline validation yet.

Recommended next step:

Run a separate non-OGonline source-family discovery for `hendriks.nl`, because it exposes a same-domain JSON API surface, but keep it outside the OGonline/XHR path unless a listing endpoint with compatible inventory payload evidence is found.
