---
title: Gate Workflow
summary: Gate execution workflow, required issue updates, and status semantics for delivery teams.
owners:
  - Gate1 Docs Team
updated: 2026-02-20
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

## Merge Gate Sequencing

1. `review-governance` must pass before merge.
2. All review threads must be resolved before merge.
3. For Platform API/runtime contract changes, both `cursor` and `greptile-apps` reviews must be present before merge.
4. If a comment is intentionally not applied, post rationale on the thread and resolve it.

## Governance Workflow Behavior

`contracts-governance`, `docs-governance`, and `llm-package-governance` run on every `pull_request` event.

On `push` to `main`, each workflow keeps path filters for scoped enforcement.

## Drift Guard

Docs governance runs `python3 scripts/docs/check_stale_references.py` via `npm --prefix docs/portal-site run check:stale`.

That check validates workflow trigger/step claims in portal and governance docs so workflow changes fail CI until documentation is updated.
