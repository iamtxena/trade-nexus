---
title: CLI Auth Operator Runbook
summary: Incident and operations runbook for CLI auth revocation, token TTL policy, and audit tracing.
owners:
  - Gate1 Docs Team
updated: 2026-03-02
---

# CLI Auth Operator Runbook

This runbook covers credential incidents and governance for CLI authentication paths used by `trading-cli`.

## Revoke Compromised CLI Sessions

### 1. Classify the compromised credential

1. Human session token (JWT bearer).
2. Runtime bot key (`tnx.bot.<botId>.<keyId>.<secret>`).

### 2. Revoke compromised runtime bot key

If `botId` and `keyId` are known:

```bash
trading-cli key revoke \
  --bot-id <bot-id> \
  --key-id <key-id> \
  --reason "compromised credential" \
  --request-id req-cli-auth-revoke-001
```

If only `botId` is known and any active key may be compromised, rotate immediately:

```bash
trading-cli key rotate \
  --bot-id <bot-id> \
  --reason "emergency rotation" \
  --request-id req-cli-auth-rotate-001
```

Then:
1. Update downstream secret stores with the new key.
2. Restart affected automation workers.
3. Verify old key now fails with `BOT_API_KEY_REVOKED`.

### 3. Revoke compromised human session token

1. Revoke the session/token in the identity provider (Clerk/JWT issuer).
2. Force re-authentication for affected users.
3. Validate old token is rejected (`AUTH_UNAUTHORIZED`).

### 4. Post-incident validation

```bash
trading-cli bot list --request-id req-cli-auth-postcheck-001
trading-cli health get
```

## Token TTL Policy

| Credential / token type | Enforcement source | Current behavior | Operator policy |
| --- | --- | --- | --- |
| Human bearer JWT | JWT issuer + Platform API claim validation | `exp` is required and validated; 15-second leeway is allowed for clock skew. | Keep short-lived access tokens (recommended: 15-60 minutes) and force refresh on sensitive environments. |
| Runtime bot key | Platform API validation identity service | No built-in expiration; key remains valid until rotated/revoked. | Rotate at least every 30 days and immediately on any compromise signal. |
| Bot invite code | Validation identity service | Invite code TTL defaults to 3600 seconds. | Keep at 1 hour or less; regenerate on expiry. |
| Lona gateway token | Backend env (`LONA_TOKEN_TTL_DAYS`) | Default is `30` days. | Keep minimum viable TTL for integrations and rotate on ownership changes. |

## Audit and Event Tracing Fields

### Request-level correlation

Use request IDs on all incident actions:

```bash
trading-cli key revoke --bot-id <bot-id> --key-id <key-id> --request-id req-cli-auth-audit-001
```

`trading-cli` surfaces `requestId` in responses and error envelopes for correlation.

### Validation identity audit event schema

| Field | Description |
| --- | --- |
| `id` | Audit event record ID. |
| `event_type` | `register`, `rotate`, `revoke`, `share`, or `accept`. |
| `request_id` | Correlation ID from request header/CLI flag. |
| `tenant_id` | Tenant scope for event. |
| `owner_user_id` | Owner user identity scope. |
| `actor_type` | `user` or `bot`. |
| `actor_id` | Acting user ID or bot ID. |
| `metadata` | Event-specific fields (see below). |
| `created_at` | UTC event timestamp. |

### Metadata keys by event type

| Event type | Metadata keys |
| --- | --- |
| `register` | `botId`, `keyId`, `method` |
| `rotate` | `botId`, `rotatedKeyIds`, `issuedKeyId` |
| `revoke` (bot key) | `botId`, `revokedKeyIds` |
| `share` | `runId`, `inviteId`, `inviteeEmail`, `permission` |
| `accept` | `runId`, `inviteId`, `acceptedEmail`, `permission` |

### Structured request log fields

Platform API structured logs include:
- `requestId`
- `tenantId`
- `userId`
- `component`
- `operation`
- optional `resourceType`, `resourceId`, `statusCode`

Use these fields to stitch CLI request IDs to backend events during incident review.

## OPEN/MERGED Evidence Comment Templates

### OPEN

```text
Status: OPEN
- Parent: <parent-link>
- Child: <child-link>
- Incident/Task: CLI auth rollout
- Evidence: requestId=<request-id>, command=<command>, result=<result>
```

### MERGED

```text
Status: MERGED
- Parent: <parent-link>
- Child: <child-link>
- PR: <merged-pr-link>
- Evidence: requestId=<request-id>, command=<command>, result=<result>
```
