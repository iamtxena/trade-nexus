import { describe, expect, test } from 'bun:test';

import { resolveTraderReviewLaneState } from '../review-lane-state';

describe('resolveTraderReviewLaneState', () => {
  test('maps not_requested mode to requestable state', () => {
    const state = resolveTraderReviewLaneState({
      required: false,
      status: 'not_requested',
      comments: [],
    });

    expect(state.mode).toBe('not_requested');
    expect(state.label).toBe('Not Requested');
    expect(state.tone).toBe('neutral');
    expect(state.canSubmitTraderVerdict).toBe(false);
    expect(state.canRequestTraderMode).toBe(true);
  });

  test('maps requested mode to trader-verdict-ready state', () => {
    const state = resolveTraderReviewLaneState({
      required: true,
      status: 'requested',
      comments: [],
    });

    expect(state.mode).toBe('requested');
    expect(state.label).toBe('Requested');
    expect(state.tone).toBe('pending');
    expect(state.canSubmitTraderVerdict).toBe(true);
    expect(state.canRequestTraderMode).toBe(false);
  });

  test('maps approved mode to locked approved state', () => {
    const state = resolveTraderReviewLaneState({
      required: true,
      status: 'approved',
      comments: ['Accepted'],
    });

    expect(state.mode).toBe('approved');
    expect(state.label).toBe('Approved');
    expect(state.tone).toBe('success');
    expect(state.canSubmitTraderVerdict).toBe(false);
    expect(state.canRequestTraderMode).toBe(false);
  });

  test('maps rejected mode to locked rejected state', () => {
    const state = resolveTraderReviewLaneState({
      required: true,
      status: 'rejected',
      comments: ['Insufficient evidence.'],
    });

    expect(state.mode).toBe('rejected');
    expect(state.label).toBe('Rejected');
    expect(state.tone).toBe('danger');
    expect(state.canSubmitTraderVerdict).toBe(false);
    expect(state.canRequestTraderMode).toBe(false);
  });
});
