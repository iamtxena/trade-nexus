'use client';

import {
  CircleAlert,
  Eye,
  FileJson,
  Loader2,
  MessageSquareText,
  Scale,
  Share2,
} from 'lucide-react';
import { type FormEvent, useCallback, useEffect, useMemo, useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import {
  describeSharedValidationPermission,
  normalizeSharedValidationPermission,
  resolveSharedValidationCapabilities,
} from '@/lib/validation/shared-permissions';
import {
  DEFAULT_SHARED_RUN_LIST_FILTERS,
  type SharedRunListFilters,
  filterRunsSharedWithMe,
  filterSharedRunsForDisplay,
} from '@/lib/validation/shared-run-visibility';
import type {
  CreateSharedValidationCommentPayload,
  CreateSharedValidationDecisionPayload,
  ValidationDecision,
  ValidationReviewComment,
  ValidationReviewDecision,
  ValidationRunArtifact,
  ValidationRunSummary,
  ValidationSharePermission,
  ValidationSharedRunListResponse,
  ValidationSharedRunSummary,
} from '@/lib/validation/types';
import { useAuth } from '@clerk/nextjs';

interface SharedRunDetailState {
  run: ValidationRunSummary;
  artifact: ValidationRunArtifact;
  permission: ValidationSharePermission;
  comments: ValidationReviewComment[];
  decision: ValidationReviewDecision | null;
}

interface ReviewRunSummaryFallback {
  id: string;
  status: ValidationSharedRunSummary['status'];
  profile: ValidationSharedRunSummary['profile'];
  finalDecision: ValidationSharedRunSummary['finalDecision'];
  createdAt: string;
  updatedAt: string;
}

function toPrettyJson(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

function toTimestamp(value: string): number {
  const parsed = Date.parse(value);
  return Number.isNaN(parsed) ? 0 : parsed;
}

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

function normalizeSharedRunList(payload: unknown): ValidationSharedRunSummary[] {
  if (!payload || typeof payload !== 'object') {
    return [];
  }

  const value = payload as {
    items?: ValidationSharedRunSummary[] | ReviewRunSummaryFallback[];
    runs?: ValidationSharedRunSummary[];
  };

  if (Array.isArray(value.runs)) {
    return value.runs
      .map((item) => ({
        ...item,
        permission: normalizeSharedValidationPermission(item.permission),
      }))
      .sort((left, right) => toTimestamp(right.updatedAt) - toTimestamp(left.updatedAt));
  }

  if (!Array.isArray(value.items)) {
    return [];
  }

  const normalized = value.items.map((item) => {
    if ('runId' in item) {
      const sharedRun = item as ValidationSharedRunSummary;
      return {
        ...sharedRun,
        permission: normalizeSharedValidationPermission(sharedRun.permission),
      };
    }
    const fallback = item as ReviewRunSummaryFallback;
    return {
      runId: fallback.id,
      permission: normalizeSharedValidationPermission(undefined),
      status: fallback.status,
      profile: fallback.profile,
      finalDecision: fallback.finalDecision,
      createdAt: fallback.createdAt,
      updatedAt: fallback.updatedAt,
    };
  });

  return normalized.sort(
    (left, right) => toTimestamp(right.updatedAt) - toTimestamp(left.updatedAt),
  );
}

function normalizeSharedRunDetail(
  payload: unknown,
  permissionFromList: ValidationSharePermission,
): SharedRunDetailState | null {
  if (!payload || typeof payload !== 'object') {
    return null;
  }

  const value = payload as {
    run?: ValidationRunSummary;
    artifact?:
      | ValidationRunArtifact
      | {
          run?: ValidationRunSummary;
          artifact?: ValidationRunArtifact;
          comments?: ValidationReviewComment[];
          decision?: ValidationReviewDecision | null;
        };
    permission?: ValidationSharePermission;
    comments?: ValidationReviewComment[];
    decision?: ValidationReviewDecision | null;
  };

  if (value.run && value.artifact && 'runId' in value.artifact) {
    return {
      run: value.run,
      artifact: value.artifact as ValidationRunArtifact,
      permission: normalizeSharedValidationPermission(value.permission ?? permissionFromList),
      comments: value.comments ?? [],
      decision: value.decision ?? null,
    };
  }

  if (value.artifact && typeof value.artifact === 'object' && 'run' in value.artifact) {
    const artifactPayload = value.artifact as {
      run: ValidationRunSummary;
      artifact: ValidationRunArtifact;
      comments?: ValidationReviewComment[];
      decision?: ValidationReviewDecision | null;
    };
    if (artifactPayload.run && artifactPayload.artifact) {
      return {
        run: artifactPayload.run,
        artifact: artifactPayload.artifact,
        permission: normalizeSharedValidationPermission(value.permission ?? permissionFromList),
        comments: artifactPayload.comments ?? [],
        decision: artifactPayload.decision ?? null,
      };
    }
  }

  return null;
}

function permissionBadgeVariant(
  permission: ValidationSharePermission,
): 'default' | 'secondary' | 'outline' {
  if (permission === 'review') {
    return 'default';
  }
  return 'outline';
}

export default function SharedValidationPage() {
  const { userId } = useAuth();
  const [runs, setRuns] = useState<ValidationSharedRunSummary[]>([]);
  const [runFilters, setRunFilters] = useState<SharedRunListFilters>({
    ...DEFAULT_SHARED_RUN_LIST_FILTERS,
  });
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [activeDetail, setActiveDetail] = useState<SharedRunDetailState | null>(null);
  const [commentInput, setCommentInput] = useState('');
  const [decision, setDecision] = useState<ValidationDecision>('pass');
  const [decisionReason, setDecisionReason] = useState('');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [noticeMessage, setNoticeMessage] = useState<string | null>(null);
  const [isLoadingRuns, setIsLoadingRuns] = useState(false);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [isSubmittingComment, setIsSubmittingComment] = useState(false);
  const [isSubmittingDecision, setIsSubmittingDecision] = useState(false);

  const loadRuns = useCallback(async () => {
    setIsLoadingRuns(true);
    setErrorMessage(null);
    try {
      const response = await fetch('/api/shared-validation/runs');
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        setErrorMessage(
          extractErrorMessage(
            payload,
            `Failed to load shared validation runs (${response.status})`,
          ),
        );
        return;
      }
      const normalized = normalizeSharedRunList(payload);
      setRuns(normalized);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Failed to load shared runs.');
    } finally {
      setIsLoadingRuns(false);
    }
  }, []);

  async function loadRunDetail(run: ValidationSharedRunSummary) {
    setIsLoadingDetail(true);
    setErrorMessage(null);
    try {
      const response = await fetch(`/api/shared-validation/runs/${run.runId}`);
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        setErrorMessage(
          extractErrorMessage(payload, `Failed to load run detail (${response.status})`),
        );
        return;
      }
      const detail = normalizeSharedRunDetail(payload, run.permission);
      if (!detail) {
        setErrorMessage('Run detail payload is missing required fields.');
        return;
      }
      setActiveRunId(run.runId);
      setActiveDetail(detail);
      setNoticeMessage(`Loaded shared run ${run.runId}.`);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Failed to load shared run detail.');
    } finally {
      setIsLoadingDetail(false);
    }
  }

  useEffect(() => {
    void loadRuns();
  }, [loadRuns]);

  const runsSharedWithMe = useMemo(
    () => filterRunsSharedWithMe(runs, userId ?? ''),
    [runs, userId],
  );
  const visibleRuns = useMemo(
    () => filterSharedRunsForDisplay(runsSharedWithMe, runFilters),
    [runFilters, runsSharedWithMe],
  );
  const activeCapabilities = useMemo(
    () =>
      resolveSharedValidationCapabilities(
        activeDetail?.permission ?? ('view' satisfies ValidationSharePermission),
      ),
    [activeDetail?.permission],
  );
  const activePermissionDescriptor = useMemo(
    () =>
      describeSharedValidationPermission(
        activeDetail?.permission ?? ('view' satisfies ValidationSharePermission),
      ),
    [activeDetail?.permission],
  );

  async function handleSubmitComment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeRunId || !activeDetail) {
      setErrorMessage('Select a shared run before posting a comment.');
      return;
    }
    if (!activeCapabilities.canComment) {
      setErrorMessage('Current permission level does not allow comments.');
      return;
    }
    const body = commentInput.trim();
    if (!body) {
      setErrorMessage('Comment body is required.');
      return;
    }

    setIsSubmittingComment(true);
    setErrorMessage(null);
    setNoticeMessage(null);
    try {
      const payload: CreateSharedValidationCommentPayload = { body };
      const response = await fetch(`/api/shared-validation/runs/${activeRunId}/comments`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const responsePayload = await response.json().catch(() => null);
      if (!response.ok) {
        setErrorMessage(
          extractErrorMessage(responsePayload, `Comment submission failed (${response.status})`),
        );
        return;
      }

      setCommentInput('');
      setNoticeMessage('Comment submitted to shared validation review lane.');
      await loadRunDetail({
        runId: activeRunId,
        permission: activeDetail.permission,
        status: activeDetail.run.status,
        profile: activeDetail.run.profile,
        finalDecision: activeDetail.run.finalDecision,
        createdAt: activeDetail.run.createdAt,
        updatedAt: activeDetail.run.updatedAt,
      });
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Failed to submit comment.');
    } finally {
      setIsSubmittingComment(false);
    }
  }

  async function handleSubmitDecision(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeRunId || !activeDetail) {
      setErrorMessage('Select a shared run before submitting a decision.');
      return;
    }
    if (!activeCapabilities.canDecide) {
      setErrorMessage('Current permission level does not allow decisions.');
      return;
    }
    if (!decisionReason.trim()) {
      setErrorMessage('Decision reason is required.');
      return;
    }

    setIsSubmittingDecision(true);
    setErrorMessage(null);
    setNoticeMessage(null);
    try {
      const payload: CreateSharedValidationDecisionPayload = {
        decision,
        reason: decisionReason.trim(),
        action: decision === 'fail' ? 'reject' : 'approve',
      };
      const response = await fetch(`/api/shared-validation/runs/${activeRunId}/decisions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const responsePayload = await response.json().catch(() => null);
      if (!response.ok) {
        setErrorMessage(
          extractErrorMessage(responsePayload, `Decision submission failed (${response.status})`),
        );
        return;
      }

      setDecisionReason('');
      setNoticeMessage(`Decision ${decision} submitted.`);
      await loadRunDetail({
        runId: activeRunId,
        permission: activeDetail.permission,
        status: activeDetail.run.status,
        profile: activeDetail.run.profile,
        finalDecision: activeDetail.run.finalDecision,
        createdAt: activeDetail.run.createdAt,
        updatedAt: activeDetail.run.updatedAt,
      });
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Failed to submit decision.');
    } finally {
      setIsSubmittingDecision(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-lg bg-primary/15">
            <Share2 className="size-5 text-primary" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Shared Validation</h1>
            <p className="text-sm text-muted-foreground">
              Dedicated review surface for runs shared with you. Permissions are run-level only.
            </p>
          </div>
        </div>
      </div>

      {errorMessage ? (
        <div className="flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          <CircleAlert className="size-4" />
          <span>{errorMessage}</span>
        </div>
      ) : null}

      {noticeMessage ? (
        <div className="rounded-md border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-700 dark:text-emerald-400">
          {noticeMessage}
        </div>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,360px)_minmax(0,1fr)_minmax(0,380px)]">
        <Card className="py-4">
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Runs Shared With Me</CardTitle>
              <CardDescription>Owner runs only, constrained by invite permissions.</CardDescription>
            </div>
            <Button type="button" variant="outline" disabled={isLoadingRuns} onClick={loadRuns}>
              {isLoadingRuns ? (
                <>
                  <Loader2 className="size-4 animate-spin" />
                  Refreshing…
                </>
              ) : (
                'Refresh'
              )}
            </Button>
          </CardHeader>
          <CardContent>
            <div className="mb-3 grid gap-2 sm:grid-cols-2">
              <Input
                aria-label="Filter shared runs by run ID"
                placeholder="Filter by run ID"
                value={runFilters.query}
                onChange={(event) =>
                  setRunFilters((previous) => ({ ...previous, query: event.target.value }))
                }
              />
              <Select
                value={runFilters.permission}
                onValueChange={(value: ValidationSharePermission | 'all') =>
                  setRunFilters((previous) => ({ ...previous, permission: value }))
                }
              >
                <SelectTrigger aria-label="Filter shared runs by permission" className="w-full">
                  <SelectValue placeholder="Permission" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">all permissions</SelectItem>
                  <SelectItem value="view">view</SelectItem>
                  <SelectItem value="review">review</SelectItem>
                </SelectContent>
              </Select>
              <Select
                value={runFilters.status}
                onValueChange={(value: ValidationSharedRunSummary['status'] | 'all') =>
                  setRunFilters((previous) => ({ ...previous, status: value }))
                }
              >
                <SelectTrigger aria-label="Filter shared runs by status" className="w-full">
                  <SelectValue placeholder="Run status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">all status</SelectItem>
                  <SelectItem value="queued">queued</SelectItem>
                  <SelectItem value="running">running</SelectItem>
                  <SelectItem value="completed">completed</SelectItem>
                  <SelectItem value="failed">failed</SelectItem>
                </SelectContent>
              </Select>
              <Select
                value={runFilters.decision}
                onValueChange={(value: ValidationDecision | 'all') =>
                  setRunFilters((previous) => ({ ...previous, decision: value }))
                }
              >
                <SelectTrigger aria-label="Filter shared runs by final decision" className="w-full">
                  <SelectValue placeholder="Final decision" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">all decisions</SelectItem>
                  <SelectItem value="pass">pass</SelectItem>
                  <SelectItem value="conditional_pass">conditional_pass</SelectItem>
                  <SelectItem value="fail">fail</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {isLoadingRuns && runsSharedWithMe.length === 0 ? (
              <div className="rounded-md border border-dashed border-border px-4 py-6 text-sm text-muted-foreground">
                Loading shared runs…
              </div>
            ) : runsSharedWithMe.length === 0 ? (
              <div className="rounded-md border border-dashed border-border px-4 py-6 text-sm text-muted-foreground">
                No runs are shared with this account yet.
              </div>
            ) : visibleRuns.length === 0 ? (
              <div className="rounded-md border border-dashed border-border px-4 py-6 text-sm text-muted-foreground">
                No shared runs match the current filters.
              </div>
            ) : (
              <div className="space-y-2">
                <p className="text-[11px] text-muted-foreground">
                  Showing {visibleRuns.length} of {runsSharedWithMe.length} runs.
                </p>
                {visibleRuns.map((run) => (
                  <button
                    key={run.runId}
                    type="button"
                    className={`w-full rounded-md border p-3 text-left transition-colors ${
                      activeRunId === run.runId
                        ? 'border-primary/50 bg-primary/5'
                        : 'border-border hover:border-primary/40'
                    }`}
                    onClick={() => {
                      void loadRunDetail(run);
                    }}
                  >
                    <p className="font-mono text-xs">{run.runId}</p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      <Badge variant="outline">{run.status}</Badge>
                      <Badge variant={permissionBadgeVariant(run.permission)}>
                        {run.permission}
                      </Badge>
                      <Badge variant={run.finalDecision === 'fail' ? 'destructive' : 'secondary'}>
                        {run.finalDecision}
                      </Badge>
                    </div>
                    <p className="mt-2 text-xs text-muted-foreground">
                      Updated {new Date(run.updatedAt).toLocaleString()}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {describeSharedValidationPermission(run.permission).summary}
                    </p>
                  </button>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="py-4">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileJson className="size-4 text-primary" />
              Shared Run Artifact
            </CardTitle>
            <CardDescription>
              Canonical JSON remains primary for shared review and decision-making.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {!activeDetail ? (
              <div className="rounded-md border border-dashed border-border px-4 py-6 text-sm text-muted-foreground">
                Select a shared run to inspect details.
              </div>
            ) : (
              <div className="space-y-3">
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <Badge variant="outline">{activeDetail.run.status}</Badge>
                  <Badge variant={permissionBadgeVariant(activeDetail.permission)}>
                    {activeDetail.permission}
                  </Badge>
                  <Badge
                    variant={
                      activeDetail.run.finalDecision === 'fail' ? 'destructive' : 'secondary'
                    }
                  >
                    {activeDetail.run.finalDecision}
                  </Badge>
                  {isLoadingDetail ? (
                    <span className="inline-flex items-center gap-1 text-muted-foreground">
                      <Loader2 className="size-3.5 animate-spin" />
                      Refreshing
                    </span>
                  ) : null}
                </div>
                <div className="rounded-md border border-border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
                  <p className="font-medium text-foreground">{activePermissionDescriptor.label}</p>
                  <p>{activePermissionDescriptor.summary}</p>
                </div>
                <pre className="max-h-[620px] overflow-auto rounded-md border border-border bg-muted/40 p-3 text-xs leading-relaxed">
                  {toPrettyJson(activeDetail.artifact)}
                </pre>
                {activeDetail.comments.length ? (
                  <div className="space-y-2 rounded-md border border-border bg-muted/30 p-3">
                    <p className="text-xs font-medium">Review Comments</p>
                    {activeDetail.comments.map((comment) => (
                      <div
                        key={comment.id}
                        className="rounded border border-border/70 bg-background px-2 py-1.5 text-xs"
                      >
                        <p>{comment.body}</p>
                        <p className="text-muted-foreground">
                          {new Date(comment.createdAt).toLocaleString()}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : null}
              </div>
            )}
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card className="py-4">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <MessageSquareText className="size-4 text-primary" />
                Comment Action
              </CardTitle>
              <CardDescription>
                Available with <code>review</code> permission.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {!activeCapabilities.canComment ? (
                <div className="rounded-md border border-dashed border-border px-3 py-2 text-xs text-muted-foreground">
                  <Eye className="mr-1 inline size-3.5" />
                  View-only access on this run.
                </div>
              ) : (
                <form className="space-y-3" onSubmit={handleSubmitComment}>
                  <div className="space-y-2">
                    <Label htmlFor="shared-comment">Comment</Label>
                    <Textarea
                      id="shared-comment"
                      placeholder="Add review context for the owner."
                      value={commentInput}
                      onChange={(event) => setCommentInput(event.target.value)}
                    />
                  </div>
                  <Button type="submit" className="w-full" disabled={isSubmittingComment}>
                    {isSubmittingComment ? (
                      <>
                        <Loader2 className="size-4 animate-spin" />
                        Submitting…
                      </>
                    ) : (
                      'Submit Comment'
                    )}
                  </Button>
                </form>
              )}
            </CardContent>
          </Card>

          <Card className="py-4">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Scale className="size-4 text-primary" />
                Decide Action
              </CardTitle>
              <CardDescription>
                Available only with <code>review</code> permission.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {!activeCapabilities.canDecide ? (
                <div className="rounded-md border border-dashed border-border px-3 py-2 text-xs text-muted-foreground">
                  Decision controls are disabled for this permission level.
                </div>
              ) : (
                <form className="space-y-3" onSubmit={handleSubmitDecision}>
                  <div className="space-y-2">
                    <Label htmlFor="shared-decision">Decision</Label>
                    <Select
                      value={decision}
                      onValueChange={(value: ValidationDecision) => setDecision(value)}
                    >
                      <SelectTrigger id="shared-decision" className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="pass">pass</SelectItem>
                        <SelectItem value="conditional_pass">conditional_pass</SelectItem>
                        <SelectItem value="fail">fail</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="shared-decision-reason">Reason</Label>
                    <Input
                      id="shared-decision-reason"
                      value={decisionReason}
                      onChange={(event) => setDecisionReason(event.target.value)}
                      placeholder="Decision rationale"
                    />
                  </div>
                  <Button type="submit" className="w-full" disabled={isSubmittingDecision}>
                    {isSubmittingDecision ? (
                      <>
                        <Loader2 className="size-4 animate-spin" />
                        Submitting…
                      </>
                    ) : (
                      'Submit Decision'
                    )}
                  </Button>
                </form>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
