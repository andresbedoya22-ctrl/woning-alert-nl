# n8n Orchestration Skill

Use this skill when designing automation around WoningAlert NL.

## Required reading

- `AGENTS.md`
- `docs/00_AGENT_OS_AND_ROADMAP.md`
- `docs/02_CODEX_WORKFLOWS.md`

## Goal

Use n8n as an orchestrator for backend jobs, not as the scraping engine.

## Correct architecture

```text
n8n schedule
  -> backend daily inventory job
  -> backend diff report
  -> backend matching job
  -> AI summary or email draft
  -> advisor notification
```

## Recommended nodes

- Schedule Trigger;
- HTTP Request;
- If/Switch;
- Merge;
- Send Email or Gmail;
- Slack/Teams notification if configured;
- Error Trigger;
- AI Agent only for summaries, triage, and drafting.

## Rules

- Do not put scraper logic in n8n workflows.
- Do not use AI Agent nodes for bulk extraction.
- Store credentials in n8n credentials, not in repo.
- Keep workflows idempotent.
- Use error workflows for failures.
- Use backend APIs or scripts for deterministic work.

## Output

Produce:

- workflow purpose;
- trigger;
- backend endpoint or command;
- inputs;
- outputs;
- error path;
- retry policy;
- notification behavior;
- what AI may and may not do.
