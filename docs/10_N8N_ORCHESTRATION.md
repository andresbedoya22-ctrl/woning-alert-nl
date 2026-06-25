# N8N Orchestration

## Role of n8n

n8n is the orchestrator around the pipeline, not the scraper itself. The runtime extraction logic should stay in repo-owned jobs or services; n8n should schedule, trigger, route failures, and notify stakeholders.

## Core workflow pieces

- schedule trigger for approved inventory jobs;
- backend job execution for source intelligence, parser runs, QA, inventory diffs, and matching;
- error workflow for failed runs or blocked sources;
- advisor notifications when review-ready output exists.

## AI usage boundary

AI may be used later for summary, draft generation, or triage assistance. It should not be used for mass extraction or as a shortcut around parser architecture.

## Design principles

- every n8n workflow should call explicit backend jobs;
- source-policy decisions remain in application code, not in ad hoc workflow branches;
- retries must respect source policy and blocking signals;
- notifications must distinguish blocked-source failures from ordinary zero-result runs.
