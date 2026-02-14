# Documentation Information Architecture and Governance

## Purpose

Define one canonical documentation information architecture (IA) for Trade Nexus so all teams publish in a consistent structure and reviewers can apply gate-level quality rules.

## Audience Lanes

| Lane | Primary Questions | Canonical Entry Points |
| --- | --- | --- |
| End user | How do I run common research/backtest/deploy workflows? | `/docs/README.md`, workflow docs under `/docs/portal/cli/` |
| API consumer | How do I integrate with the Platform API and SDK safely? | `/docs/architecture/INTERFACES.md`, `/docs/architecture/specs/platform-api.openapi.yaml`, SDK docs |
| Operator | How do I run/deploy/troubleshoot platform services? | `/docs/architecture/DEPLOYMENT.md`, `/docs/portal/operations/` |
| Internal developer | What boundaries and gates apply to implementation? | `/docs/architecture/TARGET_ARCHITECTURE_V2.md`, `/docs/architecture/GATE_TEAM_EXECUTION_PLAYBOOK.md` |
| LLM/agent | What machine-readable references define contracts, ownership, and workflows? | `/docs/llm/` package artifacts and traceability index |

## Source of Truth by Repository

| Repository | Scope | Canonical Documentation Sources | Owning Parent(s) |
| --- | --- | --- | --- |
| `trade-nexus` | Platform API, architecture, governance, gate program | `/docs/architecture/`, `/docs/portal/`, `/docs/llm/` | `#76`, `#77`, `#78`, `#79`, `#80`, `#81`, `#106` |
| `trading-cli` | External CLI behavior and usage | `trading-cli/README.md`, `trading-cli/docs/` | `#80`, `#106` |
| `trader-data` | Data adapter boundaries and contracts | `trader-data/README.md`, `trader-data/docs/` | `#78`, `#106` |
| `live-engine` | Execution runtime behavior and operating constraints | `live-engine/README.md`, `live-engine/docs/` | `#79`, `#106` |

## Versioning and Ownership Policy

1. Contract-facing documentation is versioned with API contract versions (`v1`, `v2`, etc.) and must reference the canonical OpenAPI file path.
2. Gate delivery documentation is versioned by gate (`G0` to `G4`) and parent epic (`#76` to `#81`, `#106`).
3. Any PR that changes architecture or contract behavior must include docs updates before merge.
4. Breaking contract proposals require:
   - an API contract change issue created from `.github/ISSUE_TEMPLATE/api_contract_change.yml`,
   - an explicit architecture approval comment URL,
   - a documented major-version strategy.
5. Parent owners are accountable for final gate closeout docs; child issue owners are accountable for per-PR accuracy.

## Required Documentation Artifacts Per Feature Ticket

| Artifact | Required For | Location Convention |
| --- | --- | --- |
| Problem/decision statement | Any architecture or contract ticket | Issue body + `/docs/architecture/decisions/` for ADR-worthy decisions |
| Interface/contract reference | Any API-facing feature | `/docs/architecture/INTERFACES.md` and OpenAPI-linked docs |
| User workflow impact | Any CLI or API consumer change | `/docs/portal/cli/` or `/docs/portal/api/` |
| Operational impact | Runtime/deploy/reliability changes | `/docs/portal/operations/` |
| Validation evidence | Every PR | PR body (`What changed`, `Why`, `How validated`) and CI checks |
| Ownership + handoff | Cross-team or gate-completion work | Gate update comments + handoff template below |

## Documentation Taxonomy and Naming Conventions

1. Use stable paths by audience lane:
   - `/docs/portal/platform/`
   - `/docs/portal/api/`
   - `/docs/portal/cli/`
   - `/docs/portal/data-lifecycle/`
   - `/docs/portal/operations/`
   - `/docs/llm/`
2. Prefer lowercase, kebab-case filenames with descriptive nouns.
3. Keep one concept per page; use index pages to aggregate links.
4. Link with repository-relative paths to keep CI link checks deterministic.
5. When moving or renaming docs pages, update all index/navigation pages in the same PR.

## Parent Epic Documentation Deliverable Map

| Parent Epic | Required Documentation Deliverables |
| --- | --- |
| `#76` Contracts and Governance | OpenAPI governance, SDK/mock generation docs, contract CI and templates |
| `#77` Platform Core | Service boundaries, handler behavior docs, API implementation traceability |
| `#78` Data and Knowledge | Data lifecycle contracts, ingestion/publish workflows, ownership boundaries |
| `#79` Execution Integration | Execution adapter contracts, error semantics, operational runbooks |
| `#80` Client Surface | CLI usage guides, examples, release notes, API consumption constraints |
| `#81` Program Governance | Cross-parent delivery tracking, gate closeout summaries, signoff records |

## Gate Handoff Template

Use this template when one team hands work to the next team in a gate sequence:

```md
Gate handoff:
- Parent: #<id>
- Gate: G<0-4>
- From Team: <name>
- To Team: <name>
- Completed scope: <short list>
- Open risks: <short list or none>
- Required follow-ups: <issue links>
- Contract/doc version: <tag/commit>
- Evidence links: <PRs, CI runs, docs pages>
```

## Review Cadence and Gate Criteria

1. Every gate requires a parent closeout comment with explicit PASS/CONDITIONAL_PASS/FAIL.
2. Documentation is reviewed on each PR and again at gate closeout.
3. Gate cannot close if:
   - required audience-lane docs are missing,
   - cross-repo links are broken,
   - ownership or approval references are stale.
4. Quarterly governance review updates taxonomy, ownership map, and template requirements.
