# CLI Auth Incident Response

**Owner**: CloudOps Team
**Created**: 2026-03-02
**Related**: Migration 009 (`cli_device_authorizations`, `cli_sessions`)

## Scenario 1: Token Compromise

A CLI access token has been leaked or is suspected compromised.

### Immediate Actions

1. **Revoke the session** via API:
   ```bash
   curl -X POST "${BACKEND_URL}/v2/validation-cli-auth/sessions/${SESSION_ID}/revoke" \
     -H "Authorization: Bearer ${ADMIN_JWT}"
   ```

2. **Revoke via SQL** (if API is unavailable):
   ```sql
   UPDATE cli_sessions
   SET revoked_at = now()
   WHERE session_id = '<compromised-session-id>';
   ```

3. **Audit usage**: Check `last_used_at` to determine if the token was used:
   ```sql
   SELECT session_id, user_id, tenant_id, created_at, last_used_at, revoked_at
   FROM cli_sessions
   WHERE session_id = '<compromised-session-id>';
   ```

4. **Notify the affected user** to re-authenticate via the device flow.

## Scenario 2: Mass Session Revocation

Revoke all sessions for a specific tenant or user (e.g., employee offboarding).

### By User

```sql
UPDATE cli_sessions
SET revoked_at = now()
WHERE user_id = '<user-id>'
  AND revoked_at IS NULL;
```

### By Tenant

```sql
UPDATE cli_sessions
SET revoked_at = now()
WHERE tenant_id = '<tenant-id>'
  AND revoked_at IS NULL;
```

### All Sessions (nuclear option)

```sql
UPDATE cli_sessions
SET revoked_at = now()
WHERE revoked_at IS NULL;
```

After mass revocation, monitor for:
- Spike in `/v2/validation-cli-auth/device/start` requests (users re-authenticating)
- Error rates on CLI-authenticated endpoints

## Scenario 3: Device Code Abuse

Anomalous creation rates of device authorizations (brute-force or DoS).

### Detection

```sql
-- Check creation rate over last hour
SELECT
  date_trunc('minute', created_at) AS minute,
  count(*) AS requests
FROM cli_device_authorizations
WHERE created_at > now() - interval '1 hour'
GROUP BY minute
ORDER BY minute DESC;

-- Check for expired/unconsumed flood
SELECT status, count(*)
FROM cli_device_authorizations
WHERE created_at > now() - interval '1 hour'
GROUP BY status;
```

### Mitigation

1. **Lower device code TTL** to reduce window of abuse:
   ```bash
   az containerapp update \
     --name trade-nexus-backend \
     --resource-group trade-nexus \
     --set-env-vars CLI_AUTH_DEVICE_CODE_TTL_SECONDS=300
   ```

2. **Increase polling interval** to slow down brute-force:
   ```bash
   az containerapp update \
     --name trade-nexus-backend \
     --resource-group trade-nexus \
     --set-env-vars CLI_AUTH_POLL_INTERVAL_SECONDS=10
   ```

3. **Clean up expired records**:
   ```sql
   DELETE FROM cli_device_authorizations
   WHERE status = 'expired'
     OR (status = 'pending' AND expires_at < now());
   ```

## Scenario 4: TTL Emergency Change

Need to immediately change token lifetimes (e.g., shorten access token TTL during active incident).

```bash
# Shorten access token TTL to 15 minutes
az containerapp update \
  --name trade-nexus-backend \
  --resource-group trade-nexus \
  --set-env-vars CLI_AUTH_ACCESS_TOKEN_TTL_SECONDS=900

# Verify the update
az containerapp show \
  --name trade-nexus-backend \
  --resource-group trade-nexus \
  --query "properties.template.containers[0].env[?name=='CLI_AUTH_ACCESS_TOKEN_TTL_SECONDS']"
```

Note: Changing TTL only affects new tokens. Existing tokens retain their original `expires_at`. To invalidate existing tokens, use mass revocation (Scenario 2).

## Scenario 5: Rollback to In-Memory

If the Supabase persistence layer causes issues, the platform code can fall back to in-memory state.

### Steps

1. **Apply rollback migration**:
   ```bash
   psql "$PROD_DB_URL" -f supabase/migrations/009_cli_auth_sessions_rollback.sql
   ```

2. **Verify tables are dropped**:
   ```sql
   SELECT count(*) FROM information_schema.tables
   WHERE table_schema = 'public'
     AND table_name IN ('cli_device_authorizations', 'cli_sessions');
   -- Expected: 0
   ```

3. **Restart backend** (platform code auto-detects missing tables and uses in-memory):
   ```bash
   az containerapp revision restart \
     --name trade-nexus-backend \
     --resource-group trade-nexus \
     --revision <active-revision>
   ```

### Consequences of rollback to in-memory
- All active CLI sessions are lost (users must re-authenticate)
- Session state does not survive container restarts
- No audit trail for CLI access

## Escalation Path

| Severity | Response Time | Escalation |
|----------|--------------|------------|
| Token leak (single user) | 15 min | Revoke + notify user |
| Mass compromise | 5 min | Mass revocation + incident channel |
| Abuse/DoS | 30 min | TTL adjustment + rate monitoring |
| Data layer failure | 15 min | Rollback to in-memory + investigate |
