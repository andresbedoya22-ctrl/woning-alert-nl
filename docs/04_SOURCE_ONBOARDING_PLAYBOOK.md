# Source Onboarding Playbook

## Canonical onboarding flow

```text
candidate
-> researching
-> access reviewed
-> delivery mode classified
-> parser family chosen
-> config/test fixture created
-> QA gates defined
-> production eligible
```

## Source states

- `candidate`
- `researching`
- `allowed`
- `limited`
- `permission_required`
- `legal_review`
- `blocked`
- `disabled`
- `retired`

## Workflow

1. Register the source with a stable `source_id`, domain, org name, and known URLs.
2. Gather evidence for `aanbod_url`, robots, terms, login, CAPTCHA, `403`, iframe, JSON-LD, and visible cards.
3. Decide access status before parser work.
4. Classify delivery mode from evidence, not from brand assumptions.
5. Choose an existing parser family if possible.
6. Create source config and minimal fixtures before runtime expansion.
7. Define QA gates for transaction type, status, address, and price sanity.
8. Mark production eligibility only when policy, parser path, and QA are all ready.

## Production-eligible requirements

- access status is `allowed` or explicitly `limited` with defined constraints;
- delivery mode is classified with evidence;
- parser family exists or is already approved for implementation;
- source config exists;
- test fixtures exist where applicable;
- QA gates are defined;
- stale-source handling is understood.

## Failure handling

- If policy is unclear, stop at `legal_review` or `permission_required`.
- If delivery mode is unclear, stop at `researching` or `unknown_manual_review`.
- If a source becomes blocked later, disable production use without deleting prior inventory.
