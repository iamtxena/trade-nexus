import { expect, test } from '@playwright/test';

const RUN_ID = 'valrun-20260220-0001';

function buildRunResponse(finalDecision: 'pass' | 'conditional_pass' | 'fail') {
  return {
    requestId: 'req-v-run-001',
    run: {
      id: RUN_ID,
      status: 'completed',
      profile: 'STANDARD',
      schemaVersion: 'validation-run.v1',
      finalDecision,
      createdAt: '2026-02-20T10:00:00Z',
      updatedAt: '2026-02-20T10:30:00Z',
    },
  };
}

function buildArtifactResponse(traderStatus: 'requested' | 'approved') {
  return {
    requestId: 'req-v-artifact-001',
    artifactType: 'validation_run',
    artifact: {
      schemaVersion: 'validation-run.v1',
      runId: RUN_ID,
      createdAt: '2026-02-20T10:20:00Z',
      requestId: 'req-v-artifact-canonical-001',
      tenantId: 'tenant-001',
      userId: 'user-001',
      strategyRef: {
        strategyId: 'strat-001',
        provider: 'lona',
        providerRefId: 'lona-001',
      },
      inputs: {
        prompt: 'Review this candidate strategy.',
        requestedIndicators: ['ema', 'atr'],
        datasetIds: ['dataset-btc-1h-2025'],
        backtestReportRef: 'blob://validation/backtest-report.json',
      },
      outputs: {
        strategyCodeRef: 'blob://validation/strategy.py',
        backtestReportRef: 'blob://validation/backtest-report.json',
        tradesRef: 'blob://validation/trades.json',
        executionLogsRef: 'blob://validation/logs.json',
        chartPayloadRef: 'blob://validation/chart.json',
      },
      deterministicChecks: {
        indicatorFidelity: {
          status: 'pass',
          missingIndicators: [],
        },
        tradeCoherence: {
          status: 'pass',
          violations: [],
        },
        metricConsistency: {
          status: 'pass',
          driftPct: 0.42,
        },
      },
      agentReview: {
        status: 'conditional_pass',
        summary: 'Risk controls should be monitored for first week.',
        findings: [],
      },
      traderReview: {
        required: true,
        status: traderStatus,
        comments:
          traderStatus === 'approved'
            ? ['Needs tighter stop loss.', 'Approved after stop-loss update.']
            : ['Needs tighter stop loss.'],
      },
      policy: {
        profile: 'STANDARD',
        blockMergeOnFail: true,
        blockReleaseOnFail: true,
        blockMergeOnAgentFail: true,
        blockReleaseOnAgentFail: false,
        requireTraderReview: true,
        hardFailOnMissingIndicators: true,
        failClosedOnEvidenceUnavailable: true,
      },
      finalDecision: traderStatus === 'approved' ? 'pass' : 'conditional_pass',
    },
  };
}

test('renders run detail timeline and comments after loading run by ID', async ({ page }) => {
  await page.route(`**/api/validation/runs/${RUN_ID}`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(buildRunResponse('conditional_pass')),
    });
  });
  await page.route(`**/api/validation/runs/${RUN_ID}/artifact`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(buildArtifactResponse('requested')),
    });
  });

  await page.goto('/validation');

  await expect(
    page.getByText(
      'No locally cached runs yet. Create a run or load one by ID to populate this list.',
    ),
  ).toBeVisible();

  await page.getByLabel('Run ID').fill(RUN_ID);
  await page.getByRole('button', { name: 'Load Validation Run' }).click();

  await expect(page.getByText(`Loaded validation run ${RUN_ID}.`)).toBeVisible();
  await expect(page.getByText('Run Detail Timeline')).toBeVisible();
  await expect(page.getByText('Indicator Fidelity Check')).toBeVisible();
  await expect(page.getByText('Current trader comments')).toBeVisible();
  await expect(page.getByText('- Needs tighter stop loss.')).toBeVisible();
});

test('submits review decision action and refreshes run detail', async ({ page }) => {
  let reviewSubmitted = false;

  await page.route(`**/api/validation/runs/${RUN_ID}`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(buildRunResponse(reviewSubmitted ? 'pass' : 'conditional_pass')),
    });
  });
  await page.route(`**/api/validation/runs/${RUN_ID}/artifact`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(buildArtifactResponse(reviewSubmitted ? 'approved' : 'requested')),
    });
  });
  await page.route(`**/api/validation/runs/${RUN_ID}/review`, async (route) => {
    const payload = route.request().postDataJSON() as {
      decision?: string;
      comments?: string[];
      reviewerType?: string;
    };

    expect(payload.reviewerType).toBe('trader');
    expect(payload.decision).toBe('pass');
    expect(payload.comments).toEqual(['Ship with monitored guardrails.']);

    reviewSubmitted = true;
    await route.fulfill({
      status: 202,
      contentType: 'application/json',
      body: JSON.stringify({
        requestId: 'req-v-review-001',
        runId: RUN_ID,
        reviewAccepted: true,
      }),
    });
  });

  await page.goto('/validation');
  await page.getByLabel('Run ID').fill(RUN_ID);
  await page.getByRole('button', { name: 'Load Validation Run' }).click();

  await page.getByRole('button', { name: 'pass', exact: true }).click();
  await page
    .getByLabel('Comments (comma or newline separated)')
    .fill('Ship with monitored guardrails.');
  await page.getByRole('button', { name: 'Submit pass' }).click();

  await expect(page.getByText(`Review accepted for ${RUN_ID}.`)).toBeVisible();
  await expect(page.getByText('Status: approved. Comments: 2.')).toBeVisible();
});

test('shows clear error state when run lookup fails', async ({ page }) => {
  await page.route('**/api/validation/runs/valrun-missing', async (route) => {
    await route.fulfill({
      status: 404,
      contentType: 'application/json',
      body: JSON.stringify({
        error: {
          code: 'VALIDATION_RUN_NOT_FOUND',
          message: 'Validation run valrun-missing was not found.',
        },
        requestId: 'req-v-404',
      }),
    });
  });
  await page.route('**/api/validation/runs/valrun-missing/artifact', async (route) => {
    await route.fulfill({
      status: 404,
      contentType: 'application/json',
      body: JSON.stringify({
        error: {
          code: 'VALIDATION_RUN_NOT_FOUND',
          message: 'Artifact for valrun-missing was not found.',
        },
        requestId: 'req-v-404-artifact',
      }),
    });
  });

  await page.goto('/validation');
  await page.getByLabel('Run ID').fill('valrun-missing');
  await page.getByRole('button', { name: 'Load Validation Run' }).click();

  await expect(page.getByText('Validation run valrun-missing was not found.')).toBeVisible();
  await expect(page.getByText('requestId: req-v-404')).toBeVisible();
});
