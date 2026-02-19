import { readFileSync } from 'node:fs';
import { type ParseArgsConfig, parseArgs } from 'node:util';

import { printError, printHeader, printJSON } from '../lib/output';
import {
  type CreateValidationRegressionReplayRequest,
  type CreateValidationRunRequest,
  type CreateValidationRunReviewRequest,
  PlatformApiError,
  type ValidationDecision,
  type ValidationPolicyProfile,
  type ValidationProfile,
  type ValidationRenderFormat,
  getPlatformApiClient,
} from '../lib/platform-api';
import {
  readValidationHistory,
  recordValidationReplay,
  recordValidationRun,
} from '../lib/validation-history';

type ParsedValues<T extends ParseArgsConfig['options']> = ReturnType<typeof parseArgs<T>>['values'];

const VALID_PROFILES: ValidationProfile[] = ['FAST', 'STANDARD', 'EXPERT'];
const VALID_RENDER_FORMATS: ValidationRenderFormat[] = ['html', 'pdf'];
const VALID_REVIEWERS: Array<CreateValidationRunReviewRequest['reviewerType']> = [
  'agent',
  'trader',
];
const VALID_DECISIONS: ValidationDecision[] = ['pass', 'conditional_pass', 'fail'];

export async function validationCommand(args: string[]) {
  const subcommand = args[0];

  if (!subcommand || subcommand === '--help' || subcommand === '-h') {
    printHelp();
    return;
  }

  const handlers: Record<string, (subArgs: string[]) => Promise<void>> = {
    create: createValidationRun,
    list: listValidationHistory,
    get: getValidationRun,
    review: reviewValidationRun,
    render: renderValidationRun,
    replay: replayValidationRegression,
  };

  const handler = handlers[subcommand];
  if (!handler) {
    exitWithError(`Unknown subcommand: ${subcommand}`);
  }

  await handler(args.slice(1));
}

function printHelp() {
  printHeader('Validation Commands');
  console.log('Usage:  nexus validation <subcommand> [options]\n');
  console.log('Subcommands:');
  console.log('  create    Start validation run (JSON-first payload)');
  console.log('  list      List locally tracked validation runs/replays');
  console.log('  get       Get validation run status or artifact');
  console.log('  review    Submit validation review decision');
  console.log('  render    Trigger optional html/pdf render artifact');
  console.log('  replay    Replay regression against a baseline\n');
  console.log('Examples:');
  console.log(
    '  nexus validation create --input ./contracts/fixtures/create-validation-run.request.json',
  );
  console.log(
    '  nexus validation create --strategy-id strat-001 --requested-indicators zigzag,ema --dataset-ids dataset-a --backtest-report-ref blob://validation/backtest.json --render html,pdf',
  );
  console.log('  nexus validation list --kind all --limit 20');
  console.log('  nexus validation get --id valrun-0001');
  console.log('  nexus validation get --id valrun-0001 --artifact');
  console.log('  nexus validation review --run-id valrun-0001 --reviewer trader --decision pass');
  console.log('  nexus validation render --run-id valrun-0001 --format html');
  console.log(
    '  nexus validation replay --baseline-id valbase-001 --candidate-run-id valrun-0002\n',
  );
}

function exitWithError(message: string): never {
  printError(message);
  process.exit(1);
}

function parseArgsOrExit<T extends ParseArgsConfig['options']>(config: {
  args: string[];
  options: T;
}): ParsedValues<T> {
  try {
    const parsed = parseArgs({
      args: config.args,
      options: config.options,
      allowPositionals: false,
      strict: true,
    });
    return parsed.values;
  } catch (error) {
    exitWithError(error instanceof Error ? error.message : String(error));
  }
}

function readJsonFile<T>(path: string, label: string): T {
  try {
    return JSON.parse(readFileSync(path, 'utf-8')) as T;
  } catch (error) {
    exitWithError(
      `Unable to parse ${label} at ${path}: ${error instanceof Error ? error.message : String(error)}`,
    );
  }
}

function parseCsv(value?: string): string[] {
  if (!value) return [];
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

function parseProfile(value?: string): ValidationProfile {
  const normalized = value?.trim().toUpperCase();
  if (!normalized) return 'STANDARD';
  if (VALID_PROFILES.includes(normalized as ValidationProfile)) {
    return normalized as ValidationProfile;
  }
  exitWithError(`Unsupported --profile value: ${value}`);
}

function defaultPolicy(profile: ValidationProfile): ValidationPolicyProfile {
  return {
    profile,
    blockMergeOnFail: true,
    blockReleaseOnFail: true,
    blockMergeOnAgentFail: true,
    blockReleaseOnAgentFail: false,
    requireTraderReview: false,
    hardFailOnMissingIndicators: true,
    failClosedOnEvidenceUnavailable: true,
  };
}

function parseRenderFormats(value?: string): ValidationRenderFormat[] {
  const formats = parseCsv(value).map((item) => item.toLowerCase());
  if (formats.length === 0) return [];
  const invalid = formats.find(
    (item) => !VALID_RENDER_FORMATS.includes(item as ValidationRenderFormat),
  );
  if (invalid) exitWithError(`Unsupported render format: ${invalid}`);
  return [...new Set(formats)] as ValidationRenderFormat[];
}

function parseDecision(value?: string): ValidationDecision {
  const decision = value?.trim().toLowerCase();
  if (decision && VALID_DECISIONS.includes(decision as ValidationDecision)) {
    return decision as ValidationDecision;
  }
  exitWithError(`Unsupported decision: ${value}`);
}

function parseReviewerType(value?: string): CreateValidationRunReviewRequest['reviewerType'] {
  const reviewer = value?.trim().toLowerCase();
  if (
    reviewer &&
    VALID_REVIEWERS.includes(reviewer as CreateValidationRunReviewRequest['reviewerType'])
  ) {
    return reviewer as CreateValidationRunReviewRequest['reviewerType'];
  }
  exitWithError(`Unsupported reviewer: ${value}`);
}

function formatCommandError(error: unknown): string {
  if (error instanceof PlatformApiError) {
    const requestSuffix = error.requestId ? ` [requestId=${error.requestId}]` : '';
    return `${error.message}${requestSuffix}`;
  }
  return error instanceof Error ? error.message : String(error);
}

function deriveRequestId(baseRequestId: string | undefined, suffix: string): string | undefined {
  if (!baseRequestId) return undefined;
  return `${baseRequestId}-${suffix}`;
}

function deriveIdempotencyKey(baseKey: string | undefined, suffix: string): string | undefined {
  if (!baseKey) return undefined;
  return `${baseKey}-${suffix}`;
}

async function triggerOptionalRenders(params: {
  runId: string;
  formats: ValidationRenderFormat[];
  requestId?: string;
  idempotencyKey?: string;
}) {
  const client = getPlatformApiClient();
  const responses = [];
  for (const [index, format] of params.formats.entries()) {
    const response = await client.createValidationRender(
      params.runId,
      { format },
      {
        requestId: deriveRequestId(params.requestId, `render-${format}-${index}`),
        idempotencyKey: deriveIdempotencyKey(params.idempotencyKey, `render-${format}-${index}`),
      },
    );
    responses.push(response);
    recordValidationRun({
      runId: response.render.runId,
      requestId: response.requestId,
      status: response.render.status,
    });
  }
  return responses;
}

async function createValidationRun(args: string[]) {
  const values = parseArgsOrExit({
    args,
    options: {
      input: { type: 'string' },
      'strategy-id': { type: 'string' },
      'provider-ref-id': { type: 'string' },
      prompt: { type: 'string' },
      'requested-indicators': { type: 'string' },
      'dataset-ids': { type: 'string' },
      'backtest-report-ref': { type: 'string' },
      profile: { type: 'string', default: 'STANDARD' },
      render: { type: 'string' },
      'request-id': { type: 'string' },
      'idempotency-key': { type: 'string' },
    },
  });

  const payload: CreateValidationRunRequest = values.input
    ? readJsonFile<CreateValidationRunRequest>(values.input, 'validation create payload')
    : buildCreatePayloadFromFlags(values);
  const renderFormats = parseRenderFormats(values.render);
  const client = getPlatformApiClient();

  try {
    const runResponse = await client.createValidationRun(payload, {
      requestId: values['request-id'],
      idempotencyKey: values['idempotency-key'],
    });
    recordValidationRun({
      runId: runResponse.run.id,
      requestId: runResponse.requestId,
      strategyId: payload.strategyId,
      profile: runResponse.run.profile,
      status: runResponse.run.status,
      finalDecision: runResponse.run.finalDecision,
      updatedAt: runResponse.run.updatedAt,
    });

    const renderResponses =
      renderFormats.length > 0
        ? await triggerOptionalRenders({
            runId: runResponse.run.id,
            formats: renderFormats,
            requestId: values['request-id'],
            idempotencyKey: values['idempotency-key'],
          })
        : [];

    if (renderResponses.length === 0) {
      printJSON(runResponse);
      return;
    }

    printJSON({
      run: runResponse,
      renders: renderResponses,
    });
  } catch (error) {
    exitWithError(formatCommandError(error));
  }
}

function buildCreatePayloadFromFlags(
  values: ParsedValues<{
    'strategy-id': { type: 'string' };
    'provider-ref-id': { type: 'string' };
    prompt: { type: 'string' };
    'requested-indicators': { type: 'string' };
    'dataset-ids': { type: 'string' };
    'backtest-report-ref': { type: 'string' };
    profile: { type: 'string'; default: string };
  }>,
): CreateValidationRunRequest {
  if (!values['strategy-id']) {
    exitWithError('--strategy-id is required when --input is not provided');
  }
  if (!values['requested-indicators']) {
    exitWithError('--requested-indicators is required when --input is not provided');
  }
  if (!values['dataset-ids']) {
    exitWithError('--dataset-ids is required when --input is not provided');
  }
  if (!values['backtest-report-ref']) {
    exitWithError('--backtest-report-ref is required when --input is not provided');
  }

  const requestedIndicators = parseCsv(values['requested-indicators']);
  const datasetIds = parseCsv(values['dataset-ids']);
  if (requestedIndicators.length === 0) {
    exitWithError('--requested-indicators must contain at least one value');
  }
  if (datasetIds.length === 0) {
    exitWithError('--dataset-ids must contain at least one value');
  }

  const profile = parseProfile(values.profile);
  return {
    strategyId: values['strategy-id'],
    providerRefId: values['provider-ref-id'],
    prompt: values.prompt,
    requestedIndicators,
    datasetIds,
    backtestReportRef: values['backtest-report-ref'],
    policy: defaultPolicy(profile),
  };
}

async function listValidationHistory(args: string[]) {
  const values = parseArgsOrExit({
    args,
    options: {
      kind: { type: 'string', default: 'all' },
      limit: { type: 'string', default: '20' },
    },
  });

  const kind = values.kind?.toLowerCase();
  if (!kind || !['all', 'runs', 'replays'].includes(kind)) {
    exitWithError(`Unsupported --kind value: ${values.kind}`);
  }

  const limit = Number(values.limit);
  if (!Number.isFinite(limit) || limit <= 0) {
    exitWithError('--limit must be a positive integer');
  }

  const history = readValidationHistory();
  const sortedRuns = [...history.runs].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
  const sortedReplays = [...history.replays].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));

  if (kind === 'runs') {
    printJSON({ source: 'local-history', runs: sortedRuns.slice(0, limit) });
    return;
  }
  if (kind === 'replays') {
    printJSON({ source: 'local-history', replays: sortedReplays.slice(0, limit) });
    return;
  }
  printJSON({
    source: 'local-history',
    runs: sortedRuns.slice(0, limit),
    replays: sortedReplays.slice(0, limit),
  });
}

async function getValidationRun(args: string[]) {
  const values = parseArgsOrExit({
    args,
    options: {
      id: { type: 'string' },
      artifact: { type: 'boolean', default: false },
      'request-id': { type: 'string' },
    },
  });

  if (!values.id) {
    exitWithError('--id is required');
  }

  const client = getPlatformApiClient();

  try {
    if (values.artifact) {
      const artifact = await client.getValidationRunArtifact(values.id, {
        requestId: values['request-id'],
      });
      const runId =
        artifact.artifact && typeof artifact.artifact.runId === 'string'
          ? artifact.artifact.runId
          : values.id;
      recordValidationRun({
        runId,
        requestId: artifact.requestId,
      });
      printJSON(artifact);
      return;
    }

    const run = await client.getValidationRun(values.id, {
      requestId: values['request-id'],
    });
    recordValidationRun({
      runId: run.run.id,
      requestId: run.requestId,
      profile: run.run.profile,
      status: run.run.status,
      finalDecision: run.run.finalDecision,
      updatedAt: run.run.updatedAt,
    });
    printJSON(run);
  } catch (error) {
    exitWithError(formatCommandError(error));
  }
}

async function reviewValidationRun(args: string[]) {
  const values = parseArgsOrExit({
    args,
    options: {
      'run-id': { type: 'string' },
      input: { type: 'string' },
      reviewer: { type: 'string' },
      decision: { type: 'string' },
      summary: { type: 'string' },
      comments: { type: 'string' },
      render: { type: 'string' },
      'request-id': { type: 'string' },
      'idempotency-key': { type: 'string' },
    },
  });

  if (!values['run-id']) {
    exitWithError('--run-id is required');
  }

  const payload: CreateValidationRunReviewRequest = values.input
    ? readJsonFile<CreateValidationRunReviewRequest>(values.input, 'validation review payload')
    : buildReviewPayloadFromFlags(values);
  const renderFormats = parseRenderFormats(values.render);

  const client = getPlatformApiClient();
  try {
    const review = await client.submitValidationRunReview(values['run-id'], payload, {
      requestId: values['request-id'],
      idempotencyKey: values['idempotency-key'],
    });

    recordValidationRun({
      runId: review.runId,
      requestId: review.requestId,
    });

    const renderResponses =
      renderFormats.length > 0
        ? await triggerOptionalRenders({
            runId: review.runId,
            formats: renderFormats,
            requestId: values['request-id'],
            idempotencyKey: values['idempotency-key'],
          })
        : [];

    if (renderResponses.length === 0) {
      printJSON(review);
      return;
    }

    printJSON({
      review,
      renders: renderResponses,
    });
  } catch (error) {
    exitWithError(formatCommandError(error));
  }
}

function buildReviewPayloadFromFlags(
  values: ParsedValues<{
    reviewer: { type: 'string' };
    decision: { type: 'string' };
    summary: { type: 'string' };
    comments: { type: 'string' };
  }>,
): CreateValidationRunReviewRequest {
  if (!values.reviewer) {
    exitWithError('--reviewer is required when --input is not provided');
  }
  if (!values.decision) {
    exitWithError('--decision is required when --input is not provided');
  }

  const comments = parseCsv(values.comments);

  return {
    reviewerType: parseReviewerType(values.reviewer),
    decision: parseDecision(values.decision),
    summary: values.summary,
    comments: comments.length > 0 ? comments : undefined,
  };
}

async function renderValidationRun(args: string[]) {
  const values = parseArgsOrExit({
    args,
    options: {
      'run-id': { type: 'string' },
      format: { type: 'string' },
      'request-id': { type: 'string' },
      'idempotency-key': { type: 'string' },
    },
  });

  if (!values['run-id']) {
    exitWithError('--run-id is required');
  }
  const formats = parseRenderFormats(values.format);
  if (formats.length === 0) {
    exitWithError('--format is required (html, pdf, or html,pdf)');
  }

  const client = getPlatformApiClient();
  try {
    const responses = [];
    for (const [index, format] of formats.entries()) {
      const response = await client.createValidationRender(
        values['run-id'],
        { format },
        {
          requestId: deriveRequestId(values['request-id'], `render-${format}-${index}`),
          idempotencyKey: deriveIdempotencyKey(
            values['idempotency-key'],
            `render-${format}-${index}`,
          ),
        },
      );
      responses.push(response);
      recordValidationRun({
        runId: response.render.runId,
        requestId: response.requestId,
        status: response.render.status,
      });
    }

    if (responses.length === 1) {
      printJSON(responses[0]);
      return;
    }
    printJSON({ renders: responses });
  } catch (error) {
    exitWithError(formatCommandError(error));
  }
}

async function replayValidationRegression(args: string[]) {
  const values = parseArgsOrExit({
    args,
    options: {
      input: { type: 'string' },
      'baseline-id': { type: 'string' },
      'candidate-run-id': { type: 'string' },
      'policy-overrides': { type: 'string' },
      'request-id': { type: 'string' },
      'idempotency-key': { type: 'string' },
    },
  });

  const payload: CreateValidationRegressionReplayRequest = values.input
    ? readJsonFile<CreateValidationRegressionReplayRequest>(
        values.input,
        'validation replay payload',
      )
    : buildReplayPayloadFromFlags(values);

  const client = getPlatformApiClient();
  try {
    const replay = await client.replayValidationRegression(payload, {
      requestId: values['request-id'],
      idempotencyKey: values['idempotency-key'],
    });
    recordValidationReplay({
      replayId: replay.replay.id,
      requestId: replay.requestId,
      baselineId: replay.replay.baselineId,
      candidateRunId: replay.replay.candidateRunId,
      status: replay.replay.status,
      decision: replay.replay.decision,
    });
    printJSON(replay);
  } catch (error) {
    exitWithError(formatCommandError(error));
  }
}

function buildReplayPayloadFromFlags(
  values: ParsedValues<{
    'baseline-id': { type: 'string' };
    'candidate-run-id': { type: 'string' };
    'policy-overrides': { type: 'string' };
  }>,
): CreateValidationRegressionReplayRequest {
  if (!values['baseline-id']) {
    exitWithError('--baseline-id is required when --input is not provided');
  }
  if (!values['candidate-run-id']) {
    exitWithError('--candidate-run-id is required when --input is not provided');
  }

  let policyOverrides: Record<string, unknown> | undefined;
  if (values['policy-overrides']) {
    try {
      const parsed = JSON.parse(values['policy-overrides']);
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
        exitWithError('--policy-overrides must be a JSON object');
      }
      policyOverrides = parsed as Record<string, unknown>;
    } catch (error) {
      exitWithError(
        `Unable to parse --policy-overrides JSON: ${error instanceof Error ? error.message : String(error)}`,
      );
    }
  }

  return {
    baselineId: values['baseline-id'],
    candidateRunId: values['candidate-run-id'],
    policyOverrides,
  };
}
