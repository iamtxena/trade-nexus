import { getLonaConfig, initializeLonaCredentials } from './config';

export const PLATFORM_API_URL = 'http://localhost:8000';

type RequestOptions = {
  requestId?: string;
  idempotencyKey?: string;
};

export type ValidationProfile = 'FAST' | 'STANDARD' | 'EXPERT';
export type ValidationDecision = 'pass' | 'conditional_pass' | 'fail';
export type ValidationRenderFormat = 'html' | 'pdf';

export type ValidationPolicyProfile = {
  profile: ValidationProfile;
  blockMergeOnFail: boolean;
  blockReleaseOnFail: boolean;
  blockMergeOnAgentFail: boolean;
  blockReleaseOnAgentFail: boolean;
  requireTraderReview: boolean;
  hardFailOnMissingIndicators: boolean;
  failClosedOnEvidenceUnavailable: boolean;
};

export type CreateValidationRunRequest = {
  strategyId: string;
  providerRefId?: string;
  prompt?: string;
  requestedIndicators: string[];
  datasetIds: string[];
  backtestReportRef: string;
  policy: ValidationPolicyProfile;
};

export type CreateValidationRunReviewRequest = {
  reviewerType: 'agent' | 'trader';
  decision: ValidationDecision;
  summary?: string;
  findings?: Array<{
    id: string;
    priority: number;
    confidence: number;
    summary: string;
    evidenceRefs: string[];
  }>;
  comments?: string[];
};

export type CreateValidationRenderRequest = {
  format: ValidationRenderFormat;
};

export type CreateValidationRegressionReplayRequest = {
  baselineId: string;
  candidateRunId: string;
  policyOverrides?: Record<string, unknown>;
};

export type ValidationRunResponse = {
  requestId: string;
  run: {
    id: string;
    status: string;
    profile: ValidationProfile;
    schemaVersion: string;
    finalDecision: string;
    createdAt: string;
    updatedAt: string;
  };
};

export type ValidationArtifactResponse = {
  requestId: string;
  artifactType: string;
  artifact: Record<string, unknown>;
};

export type ValidationRunReviewResponse = {
  requestId: string;
  runId: string;
  reviewAccepted: boolean;
};

export type ValidationRenderResponse = {
  requestId: string;
  render: {
    runId: string;
    format: ValidationRenderFormat;
    status: string;
    artifactRef: string | null;
  };
};

export type ValidationRegressionReplayResponse = {
  requestId: string;
  replay: {
    id: string;
    baselineId: string;
    candidateRunId: string;
    status: string;
    decision: string;
    summary: string;
  };
};

type ErrorEnvelope = {
  error?: {
    code?: string;
    message?: string;
    details?: unknown;
  };
  requestId?: string;
};

function trimTrailingSlash(url: string): string {
  return url.replace(/\/+$/, '');
}

function resolvePlatformApiUrl(): string {
  return process.env.ML_BACKEND_URL ?? PLATFORM_API_URL;
}

function createRequestId(prefix = 'req-cli-validation'): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;
}

function tryParseJson(text: string): unknown {
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

export class PlatformApiError extends Error {
  statusCode: number;
  code?: string;
  requestId?: string;
  details?: unknown;

  constructor(params: {
    message: string;
    statusCode: number;
    code?: string;
    requestId?: string;
    details?: unknown;
  }) {
    super(params.message);
    this.name = 'PlatformApiError';
    this.statusCode = params.statusCode;
    this.code = params.code;
    this.requestId = params.requestId;
    this.details = params.details;
  }
}

export class PlatformApiClient {
  private readonly baseUrl: string;
  private readonly apiKey: string;
  private readonly tenantId: string;
  private readonly userId: string;
  private readonly fetchImpl: typeof fetch;

  constructor(config?: {
    baseUrl?: string;
    apiKey?: string;
    tenantId?: string;
    userId?: string;
    fetchImpl?: typeof fetch;
  }) {
    initializeLonaCredentials();
    const lonaConfig = getLonaConfig();
    this.baseUrl = trimTrailingSlash(config?.baseUrl ?? resolvePlatformApiUrl());
    this.apiKey = config?.apiKey ?? lonaConfig.token;
    this.tenantId = config?.tenantId ?? process.env.PLATFORM_TENANT_ID ?? 'tenant-local';
    this.userId = config?.userId ?? lonaConfig.agentId;
    this.fetchImpl = config?.fetchImpl ?? fetch;
  }

  private async request<T>(
    method: 'GET' | 'POST',
    path: string,
    options: RequestOptions & { body?: unknown } = {},
  ): Promise<T> {
    const requestId = options.requestId ?? createRequestId();
    const headers: Record<string, string> = {
      Accept: 'application/json',
      'X-Request-Id': requestId,
      'X-Tenant-Id': this.tenantId,
      'X-User-Id': this.userId,
    };

    if (this.apiKey) {
      headers['X-API-Key'] = this.apiKey;
    }

    if (options.idempotencyKey) {
      headers['Idempotency-Key'] = options.idempotencyKey;
    }

    if (options.body !== undefined) {
      headers['Content-Type'] = 'application/json';
    }

    let response: Response;
    try {
      response = await this.fetchImpl(`${this.baseUrl}${path}`, {
        method,
        headers,
        body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
      });
    } catch (error) {
      throw new PlatformApiError({
        message: `Platform API request failed: ${error instanceof Error ? error.message : String(error)}`,
        statusCode: 0,
      });
    }

    const text = await response.text();
    const parsed = text ? tryParseJson(text) : undefined;

    if (!response.ok) {
      const envelope = (parsed ?? {}) as ErrorEnvelope;
      const code = envelope.error?.code;
      const message = envelope.error?.message ?? `Platform API error ${response.status}`;
      throw new PlatformApiError({
        message: `Platform API error ${response.status}${code ? ` (${code})` : ''}: ${message}`,
        statusCode: response.status,
        code,
        requestId: envelope.requestId,
        details: envelope.error?.details,
      });
    }

    return parsed as T;
  }

  async createValidationRun(
    request: CreateValidationRunRequest,
    options: RequestOptions = {},
  ): Promise<ValidationRunResponse> {
    return this.request<ValidationRunResponse>('POST', '/v2/validation-runs', {
      ...options,
      body: request,
    });
  }

  async getValidationRun(
    runId: string,
    options: RequestOptions = {},
  ): Promise<ValidationRunResponse> {
    return this.request<ValidationRunResponse>(
      'GET',
      `/v2/validation-runs/${encodeURIComponent(runId)}`,
      options,
    );
  }

  async getValidationRunArtifact(
    runId: string,
    options: RequestOptions = {},
  ): Promise<ValidationArtifactResponse> {
    return this.request<ValidationArtifactResponse>(
      'GET',
      `/v2/validation-runs/${encodeURIComponent(runId)}/artifact`,
      options,
    );
  }

  async submitValidationRunReview(
    runId: string,
    request: CreateValidationRunReviewRequest,
    options: RequestOptions = {},
  ): Promise<ValidationRunReviewResponse> {
    return this.request<ValidationRunReviewResponse>(
      'POST',
      `/v2/validation-runs/${encodeURIComponent(runId)}/review`,
      {
        ...options,
        body: request,
      },
    );
  }

  async createValidationRender(
    runId: string,
    request: CreateValidationRenderRequest,
    options: RequestOptions = {},
  ): Promise<ValidationRenderResponse> {
    return this.request<ValidationRenderResponse>(
      'POST',
      `/v2/validation-runs/${encodeURIComponent(runId)}/render`,
      {
        ...options,
        body: request,
      },
    );
  }

  async replayValidationRegression(
    request: CreateValidationRegressionReplayRequest,
    options: RequestOptions = {},
  ): Promise<ValidationRegressionReplayResponse> {
    return this.request<ValidationRegressionReplayResponse>(
      'POST',
      '/v2/validation-regressions/replay',
      {
        ...options,
        body: request,
      },
    );
  }
}

export function getPlatformApiClient(config?: {
  baseUrl?: string;
  apiKey?: string;
  tenantId?: string;
  userId?: string;
  fetchImpl?: typeof fetch;
}) {
  return new PlatformApiClient(config);
}
