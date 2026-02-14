# Onboarding Paths

Source: `docs/portal/getting-started/onboarding.md`
Topic: `onboarding`
Stable ID: `portal_onboarding_v1`

# Onboarding Paths

## Internal Team Member Onboarding

1. Read architecture baseline documents in `/docs/architecture/`.
2. Review gate workflow requirements in [Gate Workflow](../operations/gate-workflow.md).
3. Set up local docs portal build from `docs/portal-site`.
4. Run docs governance checks before opening PRs.
5. Use issue templates for architecture/contract changes.

## External Integrator Onboarding

1. Start with the Platform API contract at `/docs/architecture/specs/platform-api.openapi.yaml`.
2. Consume SDK artifacts generated from the same OpenAPI source.
3. Use CLI examples from [`trading-cli`](https://github.com/iamtxena/trading-cli).
4. Follow boundary rules: clients use Platform API only.
5. Report integration issues with issue links and reproducible contract examples.

## Cross-Repository Entry Points

- Platform: [`trade-nexus`](https://github.com/iamtxena/trade-nexus)
- CLI: [`trading-cli`](https://github.com/iamtxena/trading-cli)
- Data: [`trader-data`](https://github.com/iamtxena/trader-data)
- Execution: [`live-engine`](https://github.com/iamtxena/live-engine)
