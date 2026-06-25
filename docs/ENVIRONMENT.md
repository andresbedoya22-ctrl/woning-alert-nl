# Environment

## Setup

Create a local `.env` from `.env.example` and keep it out of git.

```powershell
Copy-Item .env.example .env
```

Then edit `.env` locally and fill only the values you actually need.

## Variables

- `WNA_ENV`
  Local runtime profile. Default: `local`.
- `WNA_USER_AGENT`
  Default user agent string for bounded fetches.
- `WNA_CONTACT_EMAIL`
  Optional contact email for polite identification.
- `WNA_REQUEST_TIMEOUT_SECONDS`
  Request timeout. Default: `20`.
- `WNA_MAX_REQUESTS_PER_RUN`
  Global request budget. Default: `100`.
- `WNA_MAX_REQUESTS_PER_DOMAIN`
  Per-domain request budget. Default: `10`.
- `WNA_MIN_REQUEST_INTERVAL_SECONDS`
  Minimum interval between requests. Default: `2`.
- `WNA_RESPECT_ROBOTS_TX`
  Respect robots policy. Default: `true`.
- `WNA_ENABLE_PLAYWRIGHT`
  Default: `false`.
- `LLM_PROVIDER`
  Target provider. Default: `openai`.
- `OPENAI_API_KEY`
  Local secret only. Never commit it.
- `LLM_MODEL`
  Optional model override.
- `ENABLE_LLM_EXTRACTION`
  Default: `false`.
- `MAX_LLM_CALLS_PER_RUN`
  Default: `0`.
- `MAX_LLM_TOKENS_PER_RUN`
  Default: `0`.
- `WNA_STORAGE_BACKEND`
  Default: `sqlite`.
- `WNA_SQLITE_PATH`
  Local SQLite path. Default: `data/local/woningalert.sqlite`.

## Safe defaults

LLM is off by default because V4 does not call OpenAI before the coarse match. `MAX_LLM_CALLS_PER_RUN=0` stays at zero by default to prevent accidental spend and to keep local runs deterministic until the extraction stage is explicitly enabled.

Playwright is disabled by default because it is not the MVP path for JS-heavy sources. It remains available only as legacy or tooling support where older code or diagnostics still import it.

## Policies

- OpenAI policy:
  Use OpenAI only after the coarse match.
- Playwright policy:
  Disabled by default and not the MVP path.
- Secrets policy:
  Never commit `.env`. Never print API keys. Keep `OPENAI_API_KEY` only in a local `.env`.

## Commands

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Run tests:

```powershell
py -3.12 -m pytest
```
