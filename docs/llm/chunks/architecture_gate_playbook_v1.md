# Gate and Team Execution Playbook

Source: `docs/architecture/GATE_TEAM_EXECUTION_PLAYBOOK.md`
Topic: `operations`
Stable ID: `architecture_gate_playbook_v1`

# Gate and Team Execution Playbook

## Purpose

Provide one operating method for all teams and agents to execute architecture work by parent epic and gate, with predictable status reporting.

## Canonical Inputs

1. `/Users/txena/sandbox/16.enjoy/trading/trade-nexus/docs/architecture/TARGET_ARCHITECTURE_V2.md`
2. `/Users/txena/sandbox/16.enjoy/trading/trade-nexus/docs/architecture/DELIVERY_PLAN_AND_TEAM_TOPOLOGY.md`
3. `/Users/txena/sandbox/16.enjoy/trading/trade-nexus/docs/architecture/specs/platform-api.openapi.yaml`
4. Parent epics `#76` to `#81` in GitHub.

## Gate Definitions

### Gate G0 (Program Setup)

- repo decisions and bootstrap,
- governance and branch protections,
- ownership ADRs.

### Gate G1 (Contract Freeze)

- OpenAPI freeze and generated artifacts,
- contract CI gates.

### Gate G2 (Thin Vertical Slice)

- minimal end-to-end path across contract, platform, adapters, and client.

### Gate G3 (Scale + Hardening)

- data scale, worker reliability, resilience policies, reconciliation.

### Gate G4 (Ops Maturity)

- SLOs, alerting, runbooks, failure recovery drills.

## Team-to-Parent Ownership

1. Parent A (`#76`): Team A + Architect.
2. Parent B (`#77`): Team B (+ Team C/D dependencies).
3. Parent C (`#78`): Data/Knowledge Team + Team C.
4. Parent D (`#79`): Team D (+ Team F dependencies).
5. Parent E (`#80`): Team E (+ Team F dependencies).
6. Parent F (`#81`): Team F + Architect.

## Standard Working Rules

1. No ticket starts without a parent and gate assignment.
2. All implementation tickets must reference contract version/tag.
3. Each PR links exactly one active ticket as primary.
4. Status updates are posted at:
   - branch start,
   - PR open,
   - merge,
   - blocker discovered.
5. Parent epic gets a closeout summary at the end of every gate.

## Status Update Template (Issue Comment)

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

## Gate Closeout Template (Parent Comment)

```md
Gate G<0-4> closeout summary:
- Completed children: #x #y #z
- Deferred children: #a #b (reason)
- Contract version used: <tag/commit>
- Risks remaining: <short list>
- Gate decision: PASS | CONDITIONAL_PASS | FAIL
- Next gate owner(s): <team/DRI list>
```

## Data and Lona-Specific Working Rules

1. Lona internals are treated as fixed.
2. Data team can change storage/processing architecture freely behind Platform API.
3. Publish to Lona must happen through connector workflow with audit trail.
4. Backtest orchestration must resolve dataset refs internally.
5. CLI/OpenClaw must never bypass Platform API for data/backtest operations.

## Definition of Done by Gate

### G2 Done

1. dataset lifecycle contract merged,
2. minimal upload -> validate -> publish -> backtest path works,
3. one end-to-end test green.

### G3 Done

1. large dataset path validated,
2. transform and quality-report jobs operational,
3. retry/idempotency and observability baseline in place.

### G4 Done

1. SLO/alerts enabled,
2. operational runbook tested,
3. reconciliation and incident drill documented.
