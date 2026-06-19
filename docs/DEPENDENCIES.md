# Dependencies

| Dependency | Use | Phase | Type |
| --- | --- | --- | --- |
| `pytest` | Test runner and fixtures | 0+ | dev |
| `httpx` | Bounded HTTP fetch and diagnostics | 1+ | runtime |
| `selectolax` | HTML parsing and future card harvest | 1+ | runtime |
| `pydantic` | Future models and validation contracts | 3+ | runtime |
| `python-dotenv` | Local `.env` loading | 0.4+ | runtime |
| `tenacity` | Controlled retries and retry policies | 1+ | runtime |
| `openai` | LLM extraction after coarse match | 6+ | runtime |
| `playwright` | Legacy browser tooling and older diagnostics | legacy / fallback | legacy/tooling |

## Notes

- `pytest`
  Required for repo validation and phase gates.
- `httpx`
  Supports bounded HTTP work already present in the repo.
- `selectolax`
  Added for future HTML parsing and card harvest work.
- `pydantic`
  Added for future settings, schemas, and validation layers.
- `python-dotenv`
  Allows safe local loading of `.env` without requiring a real `.env` file.
- `tenacity`
  Reserved for explicit, controlled retry logic rather than ad hoc loops.
- `openai`
  Reserved for extraction after the coarse match. No runtime path should call it before that stage.
- `playwright`
  Kept because legacy code and tests still import it, especially `listing_page_crawler.py`, `aanbod_auditor.py`, and related diagnostics. It is not the MVP path for JS sources.
