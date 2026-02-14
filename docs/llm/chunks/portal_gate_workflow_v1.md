# Gate Workflow

Source: `docs/portal/operations/gate-workflow.md`
Topic: `operations`
Stable ID: `portal_gate_workflow_v1`

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
