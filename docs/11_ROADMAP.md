# Roadmap

## PR 1: Repo Architecture Reset v1

- Objective: establish the architecture, source-of-truth docs, skills, and target module boundaries.
- Expected files: root `README.md`, `AGENTS.md`, `docs/00-12`, `.agents/skills/`, module READMEs.
- Acceptance criteria: repo has a coherent architecture map without deleting runtime code.
- Out of scope: new scraping logic, crawling, source runs, inventory runtime changes.

## PR 2: Source Intelligence Conversion v1

- Objective: convert existing source data and discovery artifacts into a measurable source-intelligence dataset.
- Expected files: source-intelligence schemas, conversion scripts, reports, tests.
- Acceptance criteria: measurable source records exist with evidence-backed status fields.
- Out of scope: new parser-family runtime.

## PR 3: Access Policy v1

- Objective: formalize allowed, limited, permission-required, legal-review, and blocked behavior.
- Expected files: policy models, compliance checks, decision helpers, tests.
- Acceptance criteria: policy decisions are explicit and reusable across runtime entry points.
- Out of scope: broad parser implementation.

## PR 4: Delivery Mode Fingerprint v2

- Objective: improve evidence-backed technical classification of sources.
- Expected files: fingerprint rules, reports, fixtures, tests.
- Acceptance criteria: delivery modes are assigned with explicit evidence and confidence.
- Out of scope: full inventory pipeline.

## PR 5: Inventory Core v1

- Objective: define normalized listing models, snapshots, diffs, and stale-source rules.
- Expected files: inventory models, diff engine, state handling, tests.
- Acceptance criteria: trusted per-source inventory comparison exists.
- Out of scope: advisor email generation.

## PR 6: Parser Config Runner v1

- Objective: create a config-driven runner that reuses parser families across domains.
- Expected files: parser-family interfaces, config schema, runner wiring, tests.
- Acceptance criteria: new sources can be onboarded via config when a family already exists.
- Out of scope: every future family.

## PR 7: Realworks/OGonline Stabilization

- Objective: stabilize the highest-value parser families already suggested by repo evidence.
- Expected files: family implementations, fixtures, configs, tests.
- Acceptance criteria: approved sources in these families produce normalized listings reliably.
- Out of scope: matching and orchestration.
- Parser Family Readiness Audit v1 decision: start with `Realworks Parser Family Stabilization v1` before broad WordPress/static config-runner expansion, because enriched local evidence shows the largest production-ready parser-family pool there.

## PR 8: Static/WordPress Cards

- Objective: support public HTML-card and WordPress-card patterns through config-first families.
- Expected files: family enhancements, configs, fixtures, tests.
- Acceptance criteria: multiple domains onboard without bespoke parser creation.
- Out of scope: email alerts and dashboarding.

## PR 9: QA + Normalization

- Objective: formalize quality gates and rejection/review flows.
- Expected files: QA rules, normalization helpers, tests, reports.
- Acceptance criteria: clean inventory, rejected inventory, and review queues are explicit.
- Out of scope: advisor drafting.

## PR 10: Matching + Advisor Emails

- Objective: match clean inventory to active clients and prepare advisor-facing outputs.
- Expected files: matching logic, review-pack or email draft helpers, tests.
- Acceptance criteria: approved listings can flow into advisor review.
- Out of scope: n8n production orchestration.

## PR 11: n8n Orchestration

- Objective: orchestrate approved backend jobs and alerts through n8n.
- Expected files: workflow specs, trigger definitions, retry/error handling docs, integration code where needed.
- Acceptance criteria: scheduled runs and notifications have a controlled orchestration path.
- Out of scope: dashboards.

## PR 12: Dashboard

- Objective: expose stable inventory and matching outcomes in a dashboard layer.
- Expected files: dashboard specs or implementation, API adapters, tests as applicable.
- Acceptance criteria: dashboard uses stable inventory and matching outputs rather than raw source captures.
- Out of scope: replacing core backend logic.
