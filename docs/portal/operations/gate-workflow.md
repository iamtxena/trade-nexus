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

1. Parent epics are updated on every PR state transition (`STARTED`, `IN_REVIEW`, `MERGED`, `BLOCKED`).
2. Child issues are closed only when linked PR is merged and required gates are green.
3. Gate5 deployment/reliability tracking references `/docs/portal/operations/gate5-deployment-profile.md`.
