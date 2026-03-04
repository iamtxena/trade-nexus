'use client';

import {
  CheckCircle2,
  Clock3,
  Laptop,
  Loader2,
  RefreshCw,
  ShieldCheck,
  Trash2,
} from 'lucide-react';
import { Suspense, type FormEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import {
  buildValidationCliPendingApprovalRows,
  type ValidationCliPendingDeviceRequest,
  formatValidationCliTimestamp,
  mapValidationCliSessionListResponse,
  normalizeValidationCliUserCode,
  readPendingCliDeviceRequests,
  removePendingCliDeviceRequest,
  resolveValidationCliUserCodeImport,
  upsertPendingCliDeviceRequest,
} from '@/lib/validation/cli-access-state';
import type {
  ValidationCliDeviceApprovalResponse,
  ValidationCliSession,
  ValidationCliSessionRevokeResponse,
} from '@/lib/validation/types';
import { useAuth } from '@clerk/nextjs';
import { useSearchParams } from 'next/navigation';

function extractErrorMessage(payload: unknown, fallback: string): string {
  if (!payload || typeof payload !== 'object') {
    return fallback;
  }
  const responsePayload = payload as {
    error?: string | { message?: string };
  };
  const errorValue = responsePayload.error;
  if (typeof errorValue === 'string' && errorValue.trim()) {
    return errorValue;
  }
  if (errorValue && typeof errorValue === 'object' && typeof errorValue.message === 'string') {
    return errorValue.message;
  }
  return fallback;
}

function CliAccessPageContent() {
  const { userId } = useAuth();
  const searchParams = useSearchParams();
  const pendingOwnerScope = userId ?? 'anonymous';

  const [manualUserCode, setManualUserCode] = useState('');
  const [pendingRequests, setPendingRequests] = useState<ValidationCliPendingDeviceRequest[]>([]);
  const [sessions, setSessions] = useState<ValidationCliSession[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [noticeMessage, setNoticeMessage] = useState<string | null>(null);
  const [isLoadingSessions, setIsLoadingSessions] = useState(false);
  const [isBulkRevoking, setIsBulkRevoking] = useState(false);
  const [approvingUserCode, setApprovingUserCode] = useState<string | null>(null);
  const [revokingSessionId, setRevokingSessionId] = useState<string | null>(null);

  const importedUserCodeKeyRef = useRef<string | null>(null);

  const activeSessionCount = sessions.length;
  const pendingApprovalCount = pendingRequests.length;

  const loadSessions = useCallback(async () => {
    setIsLoadingSessions(true);
    setErrorMessage(null);
    try {
      const response = await fetch('/api/validation/cli-access/sessions');
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        setErrorMessage(
          extractErrorMessage(payload, `Failed to load CLI sessions (${response.status})`),
        );
        setSessions([]);
        return;
      }
      setSessions(mapValidationCliSessionListResponse(payload));
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Failed to load CLI sessions.');
      setSessions([]);
    } finally {
      setIsLoadingSessions(false);
    }
  }, []);

  useEffect(() => {
    setPendingRequests(readPendingCliDeviceRequests(pendingOwnerScope));
  }, [pendingOwnerScope]);

  useEffect(() => {
    void loadSessions();
  }, [loadSessions]);

  useEffect(() => {
    const importResolution = resolveValidationCliUserCodeImport({
      ownerScope: pendingOwnerScope,
      urlUserCode: searchParams.get('user_code'),
      previousImportedKey: importedUserCodeKeyRef.current,
    });
    importedUserCodeKeyRef.current = importResolution.nextImportedKey;
    if (!importResolution.shouldQueue || !importResolution.normalizedUserCode) {
      return;
    }
    setPendingRequests(
      upsertPendingCliDeviceRequest(pendingOwnerScope, importResolution.normalizedUserCode),
    );
    setNoticeMessage(
      `Added pending request ${importResolution.normalizedUserCode} from verification link.`,
    );
    setErrorMessage(null);
  }, [pendingOwnerScope, searchParams]);

  const pendingApprovalRows = useMemo(
    () => buildValidationCliPendingApprovalRows(pendingRequests),
    [pendingRequests],
  );

  async function handleApprovePendingRequest(userCode: string) {
    setApprovingUserCode(userCode);
    setErrorMessage(null);
    setNoticeMessage(null);
    try {
      const response = await fetch('/api/validation/cli-access/device/approve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ userCode }),
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        setErrorMessage(extractErrorMessage(payload, `Approve failed (${response.status})`));
        return;
      }

      const approved = payload as ValidationCliDeviceApprovalResponse;
      setPendingRequests(removePendingCliDeviceRequest(pendingOwnerScope, userCode));
      await loadSessions();
      setNoticeMessage(
        `Approved ${approved.userCode}. Session expires ${formatValidationCliTimestamp(approved.expiresAt)}.`,
      );
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Failed to approve device request.');
    } finally {
      setApprovingUserCode(null);
    }
  }

  async function handleRevokeSession(sessionId: string) {
    setRevokingSessionId(sessionId);
    setErrorMessage(null);
    setNoticeMessage(null);
    try {
      const response = await fetch(`/api/validation/cli-access/sessions/${sessionId}/revoke`, {
        method: 'POST',
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        setErrorMessage(extractErrorMessage(payload, `Revoke failed (${response.status})`));
        return;
      }
      const revoked = payload as ValidationCliSessionRevokeResponse;
      setSessions((previous) => previous.filter((item) => item.id !== revoked.session.id));
      setNoticeMessage(`Revoked session ${revoked.session.id}.`);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Failed to revoke session.');
    } finally {
      setRevokingSessionId(null);
    }
  }

  async function handleBulkRevoke() {
    if (sessions.length === 0) {
      return;
    }
    const confirmed = window.confirm(
      `Revoke all ${sessions.length} active CLI sessions for this account? This cannot be undone.`,
    );
    if (!confirmed) {
      return;
    }

    setIsBulkRevoking(true);
    setErrorMessage(null);
    setNoticeMessage(null);

    const sessionsToRevoke = [...sessions];
    try {
      const revokeResults = await Promise.allSettled(
        sessionsToRevoke.map(async (session) => {
          const response = await fetch(`/api/validation/cli-access/sessions/${session.id}/revoke`, {
            method: 'POST',
          });
          const payload = await response.json().catch(() => null);
          if (!response.ok) {
            throw new Error(extractErrorMessage(payload, `Revoke failed (${response.status})`));
          }
        }),
      );

      const failedSessions = revokeResults.flatMap((result, index) => {
        if (result.status === 'fulfilled') {
          return [];
        }
        const sessionId = sessionsToRevoke[index]?.id ?? `session-${index + 1}`;
        const reason =
          result.reason instanceof Error && result.reason.message.length > 0
            ? ` (${result.reason.message})`
            : '';
        return [`${sessionId}${reason}`];
      });

      await loadSessions();
      if (failedSessions.length > 0) {
        setErrorMessage(
          `Failed to revoke ${failedSessions.length} session(s): ${failedSessions.join(', ')}.`,
        );
      } else {
        setNoticeMessage('Revoked all active CLI sessions.');
      }
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Failed to revoke sessions.');
    } finally {
      setIsBulkRevoking(false);
    }
  }

  function handleAddPendingRequest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrorMessage(null);
    setNoticeMessage(null);

    const normalized = normalizeValidationCliUserCode(manualUserCode);
    if (!normalized) {
      setErrorMessage('Invalid user code format. Expected 8 characters (example: ABCD-2345).');
      return;
    }

    setPendingRequests(upsertPendingCliDeviceRequest(pendingOwnerScope, normalized));
    setManualUserCode('');
    setNoticeMessage(`Added pending request ${normalized}.`);
  }

  function handleDismissPendingRequest(userCode: string) {
    setPendingRequests(removePendingCliDeviceRequest(pendingOwnerScope, userCode));
    setNoticeMessage(`Dismissed pending request ${userCode}.`);
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-lg bg-primary/15">
            <Laptop className="size-5 text-primary" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">CLI Access</h1>
            <p className="text-sm text-muted-foreground">
              Approve device-flow requests and manage active CLI sessions without exposing tokens.
            </p>
          </div>
        </div>
      </div>

      {errorMessage ? (
        <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {errorMessage}
        </div>
      ) : null}

      {noticeMessage ? (
        <div className="rounded-md border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-700 dark:text-emerald-400">
          {noticeMessage}
        </div>
      ) : null}

      <div className="grid gap-4 md:grid-cols-2">
        <Card className="py-4">
          <CardHeader>
            <CardTitle>Pending Approvals</CardTitle>
            <CardDescription>
              Requests waiting for approval from the signed-in user identity.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold">{pendingApprovalCount}</p>
          </CardContent>
        </Card>
        <Card className="py-4">
          <CardHeader>
            <CardTitle>Active Sessions</CardTitle>
            <CardDescription>CLI sessions currently active for this account.</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold">{activeSessionCount}</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Card className="py-4">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ShieldCheck className="size-4" />
              Device Authorization Requests
            </CardTitle>
            <CardDescription>
              Add user codes from `verification_uri_complete` links, then approve selected requests.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <form className="flex flex-col gap-2 sm:flex-row" onSubmit={handleAddPendingRequest}>
              <Input
                value={manualUserCode}
                onChange={(event) => setManualUserCode(event.target.value)}
                placeholder="ABCD-2345"
                className="font-mono"
              />
              <Button type="submit" variant="secondary">
                Queue Request
              </Button>
            </form>

            {pendingApprovalRows.length === 0 ? (
              <div className="rounded-md border border-dashed border-border px-4 py-6 text-sm text-muted-foreground">
                No pending approval requests queued.
              </div>
            ) : (
              <div className="space-y-2">
                {pendingApprovalRows.map((request) => (
                  <div
                    key={request.userCode}
                    className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border/70 bg-muted/20 px-3 py-2"
                  >
                    <div>
                      <p className="font-mono text-sm">{request.userCode}</p>
                      <p className="text-xs text-muted-foreground">
                        Queued {formatValidationCliTimestamp(request.requestedAt)}
                      </p>
                    </div>
                    <div className="flex gap-2">
                      {request.showApproveAction ? (
                        <Button
                          type="button"
                          size="sm"
                          onClick={() => {
                            void handleApprovePendingRequest(request.userCode);
                          }}
                          disabled={approvingUserCode === request.userCode}
                        >
                          {approvingUserCode === request.userCode ? (
                            <>
                              <Loader2 className="size-4 animate-spin" />
                              Approving...
                            </>
                          ) : (
                            <>
                              <CheckCircle2 className="size-4" />
                              Approve
                            </>
                          )}
                        </Button>
                      ) : null}
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => handleDismissPendingRequest(request.userCode)}
                        disabled={approvingUserCode === request.userCode}
                      >
                        Dismiss
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="py-4">
          <CardHeader className="flex flex-row items-start justify-between gap-3">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Clock3 className="size-4" />
                Active CLI Sessions
              </CardTitle>
              <CardDescription>
                Tenant/user scoped sessions with per-session revoke controls.
              </CardDescription>
            </div>
            <div className="flex gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => {
                  void loadSessions();
                }}
                disabled={isLoadingSessions}
              >
                {isLoadingSessions ? (
                  <>
                    <Loader2 className="size-4 animate-spin" />
                    Refreshing...
                  </>
                ) : (
                  <>
                    <RefreshCw className="size-4" />
                    Refresh
                  </>
                )}
              </Button>
              <Button
                type="button"
                variant="destructive"
                size="sm"
                onClick={() => {
                  void handleBulkRevoke();
                }}
                disabled={isBulkRevoking || sessions.length === 0}
              >
                {isBulkRevoking ? (
                  <>
                    <Loader2 className="size-4 animate-spin" />
                    Revoking...
                  </>
                ) : (
                  <>
                    <Trash2 className="size-4" />
                    Revoke All
                  </>
                )}
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {isLoadingSessions && sessions.length === 0 ? (
              <div className="rounded-md border border-dashed border-border px-4 py-6 text-sm text-muted-foreground">
                Loading active sessions...
              </div>
            ) : sessions.length === 0 ? (
              <div className="rounded-md border border-dashed border-border px-4 py-6 text-sm text-muted-foreground">
                No active CLI sessions.
              </div>
            ) : (
              <div className="space-y-2">
                {sessions.map((session) => (
                  <div
                    key={session.id}
                    className="rounded-md border border-border/70 bg-muted/20 px-3 py-3"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div className="space-y-1">
                        <p className="font-mono text-sm">{session.id}</p>
                        <p className="text-xs text-muted-foreground">
                          Created {formatValidationCliTimestamp(session.createdAt)} • Expires{' '}
                          {formatValidationCliTimestamp(session.expiresAt)}
                          {session.lastUsedAt
                            ? ` • Last used ${formatValidationCliTimestamp(session.lastUsedAt)}`
                            : ' • Last used never'}
                        </p>
                        <div className="flex flex-wrap gap-1">
                          {session.scopes.map((scope) => (
                            <Badge key={scope} variant="outline">
                              {scope}
                            </Badge>
                          ))}
                        </div>
                      </div>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          void handleRevokeSession(session.id);
                        }}
                        disabled={revokingSessionId === session.id || isBulkRevoking}
                      >
                        {revokingSessionId === session.id ? (
                          <>
                            <Loader2 className="size-4 animate-spin" />
                            Revoking...
                          </>
                        ) : (
                          'Revoke'
                        )}
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default function CliAccessPage() {
  return (
    <Suspense
      fallback={
        <div className="rounded-md border border-border bg-card p-4 text-sm text-muted-foreground">
          Loading CLI Access...
        </div>
      }
    >
      <CliAccessPageContent />
    </Suspense>
  );
}
