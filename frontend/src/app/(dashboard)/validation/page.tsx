'use client';

import {
  CircleAlert,
  FileCode2,
  FileJson,
  FileText,
  Loader2,
  ShieldCheck,
  Sparkles,
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import { resolveTraderReviewLaneState } from '@/lib/validation/review-lane-state';
import {
  resolveRunIdForListToDetailTransition,
  sortValidationRunsByUpdatedAtDesc,
} from '@/lib/validation/review-run-list-state';
import {
  type CreateValidationRunRequestPayload,
  type ErrorPayload,
  type ValidationArtifactResponse,
  type ValidationDecision,
  type ValidationProfile,
  type ValidationRenderFormat,
  type ValidationRenderResponse,
  type ValidationReviewerType,
  type ValidationRunListResponse,
  type ValidationRunResponse,
  type ValidationRunReviewRequestPayload,
  type ValidationRunSummary,
  isValidationRunArtifact,
} from '@/lib/validation/types';

interface ValidationCreateFormState {
  strategyId: string;
  providerRefId: string;
  prompt: string;
  requestedIndicators: string;
  datasetIds: string;
  backtestReportRef: string;
  profile: ValidationProfile;
  requestTraderReview: boolean;
}

interface ValidationReviewFormState {
  reviewerType: ValidationReviewerType;
  decision: ValidationDecision;
  summary: string;
  comments: string;
}

const DEFAULT_CREATE_FORM_STATE: ValidationCreateFormState = {
  strategyId: '',
  providerRefId: '',
  prompt: '',
  requestedIndicators: '',
  datasetIds: '',
  backtestReportRef: '',
  profile: 'STANDARD',
  requestTraderReview: false,
};

const DEFAULT_REVIEW_FORM_STATE: ValidationReviewFormState = {
  reviewerType: 'trader',
  decision: 'pass',
  summary: '',
  comments: '',
};

function parseListInput(value: string): string[] {
  return value
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
}

function toPrettyJson(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

function extractErrorMessage(payload: unknown, fallback: string): string {
  if (!payload || typeof payload !== 'object') {
    return fallback;
  }
  const responsePayload = payload as ErrorPayload & { error?: string };
  if (typeof responsePayload.error === 'string' && responsePayload.error.trim()) {
    return responsePayload.error;
  }
  const nestedMessage = responsePayload.error?.message;
  if (nestedMessage?.trim()) {
    return nestedMessage;
  }
  return fallback;
}

function toneToBadgeVariant(tone: ReturnType<typeof resolveTraderReviewLaneState>['tone']) {
  switch (tone) {
    case 'pending':
      return 'secondary';
    case 'success':
      return 'default';
    case 'danger':
      return 'destructive';
    default:
      return 'outline';
  }
}

function decisionToBadgeVariant(decision: ValidationRunSummary['finalDecision']) {
  switch (decision) {
    case 'pass':
      return 'default';
    case 'fail':
      return 'destructive';
    default:
      return 'secondary';
  }
}

export default function ValidationPage() {
  const [runLookupId, setRunLookupId] = useState('');
  const [runList, setRunList] = useState<ValidationRunSummary[]>([]);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [runResponse, setRunResponse] = useState<ValidationRunResponse | null>(null);
  const [artifactResponse, setArtifactResponse] = useState<ValidationArtifactResponse | null>(null);
  const [renderJobs, setRenderJobs] = useState<
    Partial<Record<ValidationRenderFormat, ValidationRenderResponse['render']>>
  >({});
  const [createForm, setCreateForm] =
    useState<ValidationCreateFormState>(DEFAULT_CREATE_FORM_STATE);
  const [reviewForm, setReviewForm] =
    useState<ValidationReviewFormState>(DEFAULT_REVIEW_FORM_STATE);
  const [isLoadingList, setIsLoadingList] = useState(false);
  const [isLoadingRun, setIsLoadingRun] = useState(false);
  const [isCreatingRun, setIsCreatingRun] = useState(false);
  const [isSubmittingReview, setIsSubmittingReview] = useState(false);
  const [requestingRender, setRequestingRender] = useState<Record<ValidationRenderFormat, boolean>>(
    {
      html: false,
      pdf: false,
    },
  );
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [noticeMessage, setNoticeMessage] = useState<string | null>(null);

  const runArtifact = useMemo(() => {
    if (!artifactResponse) {
      return null;
    }
    return isValidationRunArtifact(artifactResponse.artifact) ? artifactResponse.artifact : null;
  }, [artifactResponse]);

  const traderLaneState = useMemo(() => {
    if (!runArtifact) {
      return null;
    }
    return resolveTraderReviewLaneState(runArtifact.traderReview);
  }, [runArtifact]);

  const traderCommentEntries = useMemo(() => {
    if (!runArtifact) {
      return [];
    }
    const occurrences = new Map<string, number>();
    return runArtifact.traderReview.comments.map((comment) => {
      const count = (occurrences.get(comment) ?? 0) + 1;
      occurrences.set(comment, count);
      return {
        key: `${comment}-${count}`,
        comment,
      };
    });
  }, [runArtifact]);

  const loadRunList = useCallback(
    async (options?: {
      clearNotice?: boolean;
      selectRunId?: string | null;
      suppressErrors?: boolean;
    }): Promise<void> => {
      const clearNotice = options?.clearNotice ?? true;
      setIsLoadingList(true);
      setErrorMessage(null);
      if (clearNotice) {
        setNoticeMessage(null);
      }
      try {
        const response = await fetch('/api/validation/runs');
        const responsePayload = await response.json().catch(() => null);
        if (!response.ok) {
          if (!options?.suppressErrors) {
            setErrorMessage(
              extractErrorMessage(responsePayload, `Run list request failed (${response.status})`),
            );
          }
          return;
        }

        const runsPayload = responsePayload as ValidationRunListResponse;
        const runs = sortValidationRunsByUpdatedAtDesc(runsPayload.runs ?? []);
        setRunList(runs);
        if (options?.selectRunId && !runs.some((run) => run.id === options.selectRunId)) {
          setActiveRunId(null);
          setRunResponse(null);
          setArtifactResponse(null);
          setRenderJobs({});
        }
      } catch (error) {
        if (!options?.suppressErrors) {
          setErrorMessage(
            error instanceof Error ? error.message : 'Failed to load validation runs.',
          );
        }
      } finally {
        setIsLoadingList(false);
      }
    },
    [],
  );

  async function loadRunById(
    runId: string,
    options?: {
      clearNotice?: boolean;
      successNotice?: string;
    },
  ): Promise<void> {
    const clearNotice = options?.clearNotice ?? true;
    const successNotice = options?.successNotice ?? `Loaded validation run ${runId}.`;
    setIsLoadingRun(true);
    setErrorMessage(null);
    if (clearNotice) {
      setNoticeMessage(null);
    }
    try {
      const [runRes, artifactRes] = await Promise.all([
        fetch(`/api/validation/runs/${runId}`),
        fetch(`/api/validation/runs/${runId}/artifact`),
      ]);
      const [runPayload, artifactPayload] = await Promise.all([
        runRes.json().catch(() => null),
        artifactRes.json().catch(() => null),
      ]);

      if (!runRes.ok) {
        setErrorMessage(extractErrorMessage(runPayload, `Run lookup failed (${runRes.status})`));
        return;
      }
      if (!artifactRes.ok) {
        setErrorMessage(
          extractErrorMessage(artifactPayload, `Artifact lookup failed (${artifactRes.status})`),
        );
        return;
      }

      setRunResponse(runPayload as ValidationRunResponse);
      setArtifactResponse(artifactPayload as ValidationArtifactResponse);
      setActiveRunId(runId);
      setRunLookupId(runId);
      setRenderJobs({});
      setNoticeMessage(successNotice);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Failed to load validation run.');
    } finally {
      setIsLoadingRun(false);
    }
  }

  useEffect(() => {
    void loadRunList({ clearNotice: false, suppressErrors: true });
  }, [loadRunList]);

  async function handleLoadRun(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = runLookupId.trim();
    if (!normalized) {
      setErrorMessage('Run ID is required.');
      return;
    }
    await loadRunById(normalized);
  }

  async function handleOpenRunFromList(runId: string) {
    const targetRunId = resolveRunIdForListToDetailTransition(runList, runId, activeRunId);
    if (!targetRunId) {
      setErrorMessage('Selected run is no longer available in the list.');
      return;
    }
    await loadRunById(targetRunId);
  }

  async function handleCreateRun(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsCreatingRun(true);
    setErrorMessage(null);
    setNoticeMessage(null);

    const requestedIndicators = parseListInput(createForm.requestedIndicators);
    const datasetIds = parseListInput(createForm.datasetIds);
    if (requestedIndicators.length === 0) {
      setErrorMessage('At least one requested indicator is required.');
      setIsCreatingRun(false);
      return;
    }
    if (datasetIds.length === 0) {
      setErrorMessage('At least one dataset ID is required.');
      setIsCreatingRun(false);
      return;
    }

    const payload: CreateValidationRunRequestPayload = {
      strategyId: createForm.strategyId.trim(),
      providerRefId: createForm.providerRefId.trim() || undefined,
      prompt: createForm.prompt.trim() || undefined,
      requestedIndicators,
      datasetIds,
      backtestReportRef: createForm.backtestReportRef.trim(),
      policy: {
        profile: createForm.profile,
        blockMergeOnFail: true,
        blockReleaseOnFail: true,
        blockMergeOnAgentFail: true,
        blockReleaseOnAgentFail: false,
        requireTraderReview: createForm.requestTraderReview,
        hardFailOnMissingIndicators: true,
        failClosedOnEvidenceUnavailable: true,
      },
    };

    if (!payload.strategyId || !payload.backtestReportRef) {
      setErrorMessage('strategyId and backtestReportRef are required.');
      setIsCreatingRun(false);
      return;
    }

    try {
      const response = await fetch('/api/validation/runs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const responsePayload = await response.json().catch(() => null);
      if (!response.ok) {
        setErrorMessage(
          extractErrorMessage(responsePayload, `Create run failed (${response.status})`),
        );
        return;
      }

      const createdRun = (responsePayload as ValidationRunResponse).run.id;
      const createNotice = createForm.requestTraderReview
        ? `Run ${createdRun} created in trader-request mode.`
        : `Run ${createdRun} created.`;
      setNoticeMessage(createNotice);
      await loadRunById(createdRun, {
        clearNotice: false,
        successNotice: createNotice,
      });
      void loadRunList({
        clearNotice: false,
        selectRunId: createdRun,
        suppressErrors: true,
      });
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Failed to create validation run.');
    } finally {
      setIsCreatingRun(false);
    }
  }

  async function handleSubmitReview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeRunId || !runArtifact || !traderLaneState) {
      setErrorMessage('Load a validation run before submitting a review.');
      return;
    }

    if (reviewForm.reviewerType === 'trader' && !traderLaneState.canSubmitTraderVerdict) {
      setErrorMessage(
        traderLaneState.canRequestTraderMode
          ? 'Trader review mode is not requested for this run. Enable trader mode when creating the run.'
          : `Trader verdict cannot be submitted while status is ${traderLaneState.mode}.`,
      );
      return;
    }

    setIsSubmittingReview(true);
    setErrorMessage(null);
    setNoticeMessage(null);
    try {
      const payload: ValidationRunReviewRequestPayload = {
        reviewerType: reviewForm.reviewerType,
        decision: reviewForm.decision,
        summary: reviewForm.summary.trim() || undefined,
        comments: parseListInput(reviewForm.comments),
        findings: [],
      };

      const response = await fetch(`/api/validation/runs/${activeRunId}/review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const responsePayload = await response.json().catch(() => null);
      if (!response.ok) {
        setErrorMessage(
          extractErrorMessage(responsePayload, `Review submission failed (${response.status})`),
        );
        return;
      }

      const reviewNotice = `Review accepted for ${activeRunId}.`;
      setNoticeMessage(reviewNotice);
      await loadRunById(activeRunId, {
        clearNotice: false,
        successNotice: reviewNotice,
      });
      void loadRunList({
        clearNotice: false,
        selectRunId: activeRunId,
        suppressErrors: true,
      });
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Failed to submit review.');
    } finally {
      setIsSubmittingReview(false);
    }
  }

  async function handleRequestRender(format: ValidationRenderFormat) {
    if (!activeRunId) {
      setErrorMessage('Load a validation run before requesting a render artifact.');
      return;
    }
    setRequestingRender((previous) => ({ ...previous, [format]: true }));
    setErrorMessage(null);
    setNoticeMessage(null);
    try {
      const response = await fetch(`/api/validation/runs/${activeRunId}/render`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ format }),
      });
      const responsePayload = await response.json().catch(() => null);
      if (!response.ok) {
        setErrorMessage(
          extractErrorMessage(responsePayload, `Render request failed (${response.status})`),
        );
        return;
      }

      const renderResponse = responsePayload as ValidationRenderResponse;
      setRenderJobs((previous) => ({
        ...previous,
        [format]: renderResponse.render,
      }));
      setNoticeMessage(`Render request accepted for ${format.toUpperCase()}.`);
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : 'Failed to request render artifact.',
      );
    } finally {
      setRequestingRender((previous) => ({ ...previous, [format]: false }));
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-lg bg-primary/15">
            <ShieldCheck className="size-5 text-primary" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Validation Review Lane</h1>
            <p className="text-sm text-muted-foreground">
              JSON-first artifact review with optional trader approval and on-demand render
              requests.
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
        <div className="flex items-center gap-2 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-700 dark:text-emerald-400">
          <Sparkles className="size-4" />
          <span>{noticeMessage}</span>
        </div>
      ) : null}

      <Card className="py-4">
        <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <CardTitle>Validation Run List</CardTitle>
            <CardDescription>Open a run from list to detail review flow.</CardDescription>
          </div>
          <Button
            type="button"
            variant="outline"
            disabled={isLoadingList}
            onClick={() => {
              void loadRunList();
            }}
          >
            {isLoadingList ? (
              <>
                <Loader2 className="size-4 animate-spin" />
                Refreshing…
              </>
            ) : (
              'Refresh Runs'
            )}
          </Button>
        </CardHeader>
        <CardContent>
          {isLoadingList && runList.length === 0 ? (
            <div className="rounded-md border border-dashed border-border px-4 py-6 text-sm text-muted-foreground">
              Loading validation runs…
            </div>
          ) : runList.length === 0 ? (
            <div className="rounded-md border border-dashed border-border px-4 py-6 text-sm text-muted-foreground">
              No validation runs found for this tenant/user context yet.
            </div>
          ) : (
            <div className="space-y-2">
              {runList.map((run) => (
                <div
                  key={run.id}
                  className={`flex flex-col gap-3 rounded-md border p-3 sm:flex-row sm:items-center sm:justify-between ${
                    activeRunId === run.id ? 'border-primary/40 bg-primary/5' : 'border-border'
                  }`}
                >
                  <div className="space-y-1">
                    <p className="font-mono text-xs text-foreground">{run.id}</p>
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="outline">{run.status}</Badge>
                      <Badge variant={decisionToBadgeVariant(run.finalDecision)}>
                        {run.finalDecision}
                      </Badge>
                      <span className="text-xs text-muted-foreground">
                        Updated {new Date(run.updatedAt).toLocaleString()}
                      </span>
                    </div>
                  </div>
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={isLoadingRun}
                    onClick={() => {
                      void handleOpenRunFromList(run.id);
                    }}
                  >
                    {isLoadingRun ? (
                      <>
                        <Loader2 className="size-4 animate-spin" />
                        Loading…
                      </>
                    ) : (
                      'Open Run'
                    )}
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card className="py-4">
          <CardHeader>
            <CardTitle>Load Existing Run</CardTitle>
            <CardDescription>Fetch status and artifact by run ID.</CardDescription>
          </CardHeader>
          <CardContent>
            <form className="space-y-3" onSubmit={handleLoadRun}>
              <div className="space-y-2">
                <Label htmlFor="run-id">Run ID</Label>
                <Input
                  id="run-id"
                  placeholder="valrun-20260217-0001"
                  value={runLookupId}
                  onChange={(event) => setRunLookupId(event.target.value)}
                />
              </div>
              <Button type="submit" disabled={isLoadingRun} className="w-full">
                {isLoadingRun ? (
                  <>
                    <Loader2 className="size-4 animate-spin" />
                    Loading…
                  </>
                ) : (
                  'Load Validation Run'
                )}
              </Button>
            </form>
          </CardContent>
        </Card>

        <Card className="py-4">
          <CardHeader>
            <CardTitle>Create Review Candidate</CardTitle>
            <CardDescription>
              Start a validation run and optionally request trader review mode up front.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form className="grid gap-3 md:grid-cols-2" onSubmit={handleCreateRun}>
              <div className="space-y-2">
                <Label htmlFor="strategy-id">Strategy ID</Label>
                <Input
                  id="strategy-id"
                  value={createForm.strategyId}
                  onChange={(event) =>
                    setCreateForm((previous) => ({ ...previous, strategyId: event.target.value }))
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="provider-ref-id">Provider Ref ID</Label>
                <Input
                  id="provider-ref-id"
                  value={createForm.providerRefId}
                  onChange={(event) =>
                    setCreateForm((previous) => ({
                      ...previous,
                      providerRefId: event.target.value,
                    }))
                  }
                />
              </div>
              <div className="space-y-2 md:col-span-2">
                <Label htmlFor="prompt">Prompt</Label>
                <Textarea
                  id="prompt"
                  value={createForm.prompt}
                  onChange={(event) =>
                    setCreateForm((previous) => ({ ...previous, prompt: event.target.value }))
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="requested-indicators">Requested Indicators</Label>
                <Input
                  id="requested-indicators"
                  value={createForm.requestedIndicators}
                  onChange={(event) =>
                    setCreateForm((previous) => ({
                      ...previous,
                      requestedIndicators: event.target.value,
                    }))
                  }
                  placeholder="zigzag, ema"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="dataset-ids">Dataset IDs</Label>
                <Input
                  id="dataset-ids"
                  value={createForm.datasetIds}
                  onChange={(event) =>
                    setCreateForm((previous) => ({ ...previous, datasetIds: event.target.value }))
                  }
                  placeholder="dataset-btc-1h-2025"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="backtest-ref">Backtest Report Ref</Label>
                <Input
                  id="backtest-ref"
                  value={createForm.backtestReportRef}
                  onChange={(event) =>
                    setCreateForm((previous) => ({
                      ...previous,
                      backtestReportRef: event.target.value,
                    }))
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="profile">Profile</Label>
                <Select
                  value={createForm.profile}
                  onValueChange={(value: ValidationProfile) =>
                    setCreateForm((previous) => ({ ...previous, profile: value }))
                  }
                >
                  <SelectTrigger id="profile" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="FAST">FAST</SelectItem>
                    <SelectItem value="STANDARD">STANDARD</SelectItem>
                    <SelectItem value="EXPERT">EXPERT</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <label className="md:col-span-2 flex items-center gap-2 rounded-md border border-border px-3 py-2 text-sm">
                <input
                  type="checkbox"
                  checked={createForm.requestTraderReview}
                  onChange={(event) =>
                    setCreateForm((previous) => ({
                      ...previous,
                      requestTraderReview: event.target.checked,
                    }))
                  }
                />
                <span>Request trader review mode (`requested`) for this run</span>
              </label>
              <div className="md:col-span-2">
                <Button type="submit" className="w-full" disabled={isCreatingRun}>
                  {isCreatingRun ? (
                    <>
                      <Loader2 className="size-4 animate-spin" />
                      Creating…
                    </>
                  ) : (
                    'Create Validation Run'
                  )}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>

      {runResponse && runArtifact && traderLaneState ? (
        <Card className="py-4">
          <CardHeader>
            <CardTitle>Active Run Overview</CardTitle>
            <CardDescription>{runResponse.run.id}</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 md:grid-cols-2 lg:grid-cols-5">
            <div className="rounded-md border border-border p-3">
              <p className="text-xs text-muted-foreground">Run Status</p>
              <p className="mt-1 text-sm font-medium capitalize">{runResponse.run.status}</p>
            </div>
            <div className="rounded-md border border-border p-3">
              <p className="text-xs text-muted-foreground">Final Decision</p>
              <p className="mt-1 text-sm font-medium">{runResponse.run.finalDecision}</p>
            </div>
            <div className="rounded-md border border-border p-3">
              <p className="text-xs text-muted-foreground">Profile</p>
              <p className="mt-1 text-sm font-medium">{runResponse.run.profile}</p>
            </div>
            <div className="rounded-md border border-border p-3">
              <p className="text-xs text-muted-foreground">Trader Mode</p>
              <div className="mt-1">
                <Badge variant={toneToBadgeVariant(traderLaneState.tone)}>
                  {traderLaneState.label}
                </Badge>
              </div>
            </div>
            <div className="rounded-md border border-border p-3">
              <p className="text-xs text-muted-foreground">Trader Required</p>
              <p className="mt-1 text-sm font-medium">
                {runArtifact.traderReview.required ? 'Yes' : 'No'}
              </p>
            </div>
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <Card className="py-4">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileJson className="size-4 text-primary" />
              JSON-First Artifact Viewer
            </CardTitle>
            <CardDescription>
              Canonical JSON is primary. HTML/PDF remain optional request-only outputs.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {!runResponse || !artifactResponse ? (
              <div className="rounded-md border border-dashed border-border px-4 py-6 text-sm text-muted-foreground">
                Load or create a run to inspect artifact JSON.
              </div>
            ) : (
              <Tabs defaultValue="artifact">
                <TabsList variant="line">
                  <TabsTrigger value="artifact" className="gap-1.5">
                    <FileJson className="size-3.5" />
                    Artifact JSON
                  </TabsTrigger>
                  <TabsTrigger value="run" className="gap-1.5">
                    <FileCode2 className="size-3.5" />
                    Run JSON
                  </TabsTrigger>
                </TabsList>
                <TabsContent value="artifact">
                  <pre className="max-h-[520px] overflow-auto rounded-md border border-border bg-muted/40 p-3 text-xs leading-relaxed">
                    {toPrettyJson(artifactResponse.artifact)}
                  </pre>
                </TabsContent>
                <TabsContent value="run">
                  <pre className="max-h-[520px] overflow-auto rounded-md border border-border bg-muted/40 p-3 text-xs leading-relaxed">
                    {toPrettyJson(runResponse.run)}
                  </pre>
                </TabsContent>
              </Tabs>
            )}
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card className="py-4">
            <CardHeader>
              <CardTitle>Review Verdict</CardTitle>
              <CardDescription>Submit comments and a decision for the active run.</CardDescription>
            </CardHeader>
            <CardContent>
              <form className="space-y-3" onSubmit={handleSubmitReview}>
                <div className="space-y-2">
                  <Label htmlFor="reviewer-type">Reviewer Type</Label>
                  <Select
                    value={reviewForm.reviewerType}
                    onValueChange={(value: ValidationReviewerType) =>
                      setReviewForm((previous) => ({ ...previous, reviewerType: value }))
                    }
                  >
                    <SelectTrigger id="reviewer-type" className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="trader">trader</SelectItem>
                      <SelectItem value="agent">agent</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="decision">Decision</Label>
                  <Select
                    value={reviewForm.decision}
                    onValueChange={(value: ValidationDecision) =>
                      setReviewForm((previous) => ({ ...previous, decision: value }))
                    }
                  >
                    <SelectTrigger id="decision" className="w-full">
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
                  <Label htmlFor="summary">Summary</Label>
                  <Textarea
                    id="summary"
                    placeholder="Optional summary"
                    value={reviewForm.summary}
                    onChange={(event) =>
                      setReviewForm((previous) => ({ ...previous, summary: event.target.value }))
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="comments">Comments (comma or newline separated)</Label>
                  <Textarea
                    id="comments"
                    placeholder="Needs guardrails before rollout."
                    value={reviewForm.comments}
                    onChange={(event) =>
                      setReviewForm((previous) => ({ ...previous, comments: event.target.value }))
                    }
                  />
                </div>

                {traderLaneState?.canRequestTraderMode ? (
                  <div className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-300">
                    Trader mode is currently `not_requested`. Use the create form toggle to request
                    trader mode for a new run.
                  </div>
                ) : null}

                {traderCommentEntries.length ? (
                  <div className="space-y-1 rounded-md border border-border bg-muted/40 px-3 py-2 text-xs">
                    <p className="font-medium text-foreground">Current trader comments</p>
                    {traderCommentEntries.map((entry) => (
                      <p key={entry.key} className="text-muted-foreground">
                        - {entry.comment}
                      </p>
                    ))}
                  </div>
                ) : null}

                <Button type="submit" className="w-full" disabled={isSubmittingReview}>
                  {isSubmittingReview ? (
                    <>
                      <Loader2 className="size-4 animate-spin" />
                      Submitting…
                    </>
                  ) : (
                    'Submit Review'
                  )}
                </Button>
              </form>
            </CardContent>
          </Card>

          <Card className="py-4">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText className="size-4 text-primary" />
                Optional Render Artifacts
              </CardTitle>
              <CardDescription>Request HTML/PDF artifacts only when needed.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid grid-cols-2 gap-2">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => handleRequestRender('html')}
                  disabled={requestingRender.html}
                >
                  {requestingRender.html ? (
                    <>
                      <Loader2 className="size-4 animate-spin" />
                      HTML…
                    </>
                  ) : (
                    'Request HTML'
                  )}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => handleRequestRender('pdf')}
                  disabled={requestingRender.pdf}
                >
                  {requestingRender.pdf ? (
                    <>
                      <Loader2 className="size-4 animate-spin" />
                      PDF…
                    </>
                  ) : (
                    'Request PDF'
                  )}
                </Button>
              </div>

              {(['html', 'pdf'] as const).map((format) => {
                const render = renderJobs[format];
                if (!render) {
                  return null;
                }
                return (
                  <div key={format} className="rounded-md border border-border p-3 text-xs">
                    <p className="font-medium uppercase">{format}</p>
                    <p className="text-muted-foreground">Status: {render.status}</p>
                    {render.artifactRef ? (
                      <p className="break-all text-muted-foreground">
                        artifactRef: {render.artifactRef}
                      </p>
                    ) : null}
                  </div>
                );
              })}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
