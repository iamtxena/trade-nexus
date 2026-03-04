# Issue #382 - CLI Access Flow Evidence

Date: 2026-03-04  
Branch: `codex/web-cli-access-382`

## Flow Steps

1. Open unauthenticated sign-in route with preserved redirect:
   - `http://localhost:3011/sign-in?redirect_url=%2Fcli-access%3Fuser_code%3DNB8W-5YXP`
2. Verify redirect payload contains `user_code`:
   - Sign-up link includes `redirect_url=http://localhost:3011/cli-access?user_code=NB8W-5YXP`
3. Open CLI access route directly with query:
   - `http://localhost:3011/cli-access?user_code=NB8W-5YXP`
4. Verify queued approval appears automatically:
   - Banner: `Added pending request NB8W-5YXP from verification link.`
   - Pending approvals count: `1`
   - Pending row shown for `NB8W-5YXP`
   - `Approve` button visible without manual entry

## Screenshots

- Sign-in redirect with preserved `user_code`:
  - `./issue-382-signin-redirect.png`
- CLI access auto-queue and approve action visible:
  - `./issue-382-autoqueue.png`

## Automated Validation

Command:

- `cd frontend && bun run test && bun run typecheck`

Observed result:

- `bun test src cli`: `169 pass`, `0 fail`
- `tsc --noEmit`: success

## Regression Tests Added

- `frontend/src/lib/auth/__tests__/sign-in-redirect.test.ts`
  - redirect preservation for `/cli-access?user_code=...`
- `frontend/src/lib/validation/__tests__/cli-access-state.test.ts`
  - owner-scope transition requeue (`anonymous` -> signed-in)
  - same-scope dedupe (no duplicate import)
  - auto-queued row surfaces approve action
