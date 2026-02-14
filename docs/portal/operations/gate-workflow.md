---
title: Gate Workflow
summary: Gate execution workflow, required issue updates, and status semantics for delivery teams.
owners:
  - Gate1 Docs Team
updated: 2026-02-14
---

# Gate Workflow

Use the gate operating model defined in `/docs/architecture/GATE_TEAM_EXECUTION_PLAYBOOK.md`.

## Required Status Values

- `STARTED`
- `IN_REVIEW`
- `MERGED`
- `BLOCKED`

## Required Issue Comment Template

```md
Gate update:
- Parent: #<id>
- Gate: G<0-4>
- Child: #<id>
- Repo/Branch: <repo>:<branch>
- PR: <url or pending>
- Status: STARTED | IN_REVIEW | MERGED | BLOCKED
- Blocker: <none or short reason>
- Next: <single concrete next action>
```

## Parent Tracking

- Parent `#106` is not closed by Docs Team.
- Child issues are closed when their PR is merged and CI is green.
- After `#108` merge, handoff to Review Team on `#109`.

## Contributor Checklist

1. Post `STARTED` comment before implementation.
2. Open exactly one PR per active child issue.
3. Include docs changes, index/navigation updates, and validation evidence in PR body.
4. Post `IN_REVIEW` and `MERGED` comments using the gate template.
5. Update parent issue with gate progress and next child handoff.

## Traceability

Use [Gate0 and Gate1 Traceability](gate0-gate1-traceability.md) to map docs claims to merged issue/PR evidence.
