# Source Onboarding Playbook

This playbook defines how to move a source from unknown domain to production-ready inventory input.

## 1. Core rule

No source enters production extraction without:

- access decision;
- delivery mode;
- parser family;
- source config or parser implementation;
- QA expectations;
- tests or fixture evidence.

## 2. Onboarding states

| State | Meaning | Can run production extraction? |
|---|---|---|
| `candidate` | Discovered but not reviewed | No |
| `researching` | Under technical/access review | No |
| `allowed` | Access policy permits intended extraction | Yes |
| `limited` | Access allowed with limits | Yes, with limits |
| `permission_required` | Need explicit permission or feed/API | No |
| `legal_review` | Terms/database rights unclear | No |
| `blocked` | CAPTCHA, login, 403, Funda dependency, or explicit block | No |
| `disabled` | Intentionally disabled | No |
| `retired` | No longer useful or active | No |

## 3. Source record v2 fields

Every source should eventually have these fields:

```csv
source_id,source_domain,source_name,source_type,country_scope,province_scope,city_scope,homepage_url,listing_url,access_status,robots_status,terms_status,permission_status,blocking_status,delivery_mode,parser_family,config_path,rate_limit_per_minute,user_agent_policy,last_reviewed_at,reviewed_by,evidence,recommended_action,notes
```

## 4. Onboarding workflow

### Step 1 — Candidate capture

Capture minimal facts:

- domain;
- source name;
- why it matters;
- source type;
- suspected platform;
- known listing URL if available.

### Step 2 — Access pre-check

Check:

- robots file exists and can be parsed;
- target path is allowed for the project user agent;
- terms or public policy do not obviously prohibit intended use;
- no login wall;
- no CAPTCHA;
- no anti-bot/403 block;
- no Funda/blocked portal dependency.

### Step 3 — Minimal fingerprint

Probe only low-volume URLs:

- homepage;
- robots;
- sitemap;
- common listing paths;
- existing listing URL if known.

### Step 4 — Classify delivery mode

Assign delivery mode using evidence, not guesswork.

### Step 5 — Select implementation path

Options:

- existing parser family + config;
- improve existing parser family;
- build new parser family;
- mark manual review;
- seek permission/API;
- block.

### Step 6 — Build fixture and tests

Before production extraction, create tests from synthetic or approved fixture data.

A fixture should prove:

- card/detail URL extraction;
- price parsing;
- status parsing;
- transaction type;
- address/city extraction;
- rejection behavior.

### Step 7 — QA gates

Run source output through:

- transaction type classifier;
- status classifier;
- address quality gate;
- price sanity gate;
- duplicate key builder;
- source access gate;
- confidence/review reason gate.

### Step 8 — Promote carefully

Only promote to production when:

- access is allowed/limited;
- parser output is stable;
- false positives are low;
- QA report is clean;
- missing optional fields are understood;
- source does not endanger the daily run.

## 5. Production run behavior

Production extraction must be resilient:

- one source failure must not fail the full run;
- blocked source does not delete existing inventory;
- timeout source becomes stale, not removed immediately;
- repeated failure creates a review task;
- sudden zero-count creates a quality alert;
- source volume changes must be reported.

## 6. Quality metrics

Track per source:

- candidates found;
- normalized listings;
- clean available koop listings;
- rejected candidates;
- missing address count;
- invalid price count;
- transaction type unknown count;
- duplicate count;
- extraction confidence average;
- parser family;
- runtime;
- failure rate;
- last successful run.

## 7. Promotion thresholds

A source can move from `researching` to `allowed` only if:

- access policy is acceptable;
- no blocking behavior is detected;
- at least one parser route exists;
- QA has clear expectations;
- source-specific limitations are documented.

A source can move from `allowed` to production-active only if:

- tests exist;
- first live run returns plausible output;
- no commercial-only/rental-only pollution appears for koop inventory;
- no known prohibited content is stored.

## 8. Deactivation rules

Deactivate or downgrade a source if:

- robots/terms change;
- CAPTCHA or login appears;
- source returns 403 repeatedly;
- parser produces false positives;
- source becomes commercial-only;
- source depends on a blocked third-party portal;
- source volume drops to zero unexpectedly and cannot be explained.

## 9. Human review queue

Manual queue should be small and prioritized.

Priority score:

```text
source_value_score
+ estimated_listing_volume
+ client_area_relevance
+ parser_reuse_potential
- legal_uncertainty_penalty
- blocker_penalty
```

Review first:

- high-volume sources;
- sources in active client cities;
- sources sharing a parser family with many others;
- sources with clear access policy.

## 10. Done definition

A source is fully onboarded when:

- `source_registry` row is complete;
- access state is production-allowed;
- delivery mode is classified;
- parser family/config exists;
- tests cover the pattern;
- QA gates pass;
- source can fail safely;
- results can feed inventory core.
