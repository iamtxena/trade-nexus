import type { ValidationTraderReview } from '@/lib/validation/types';

export type TraderReviewTone = 'neutral' | 'pending' | 'success' | 'danger';

export interface TraderReviewLaneState {
  mode: ValidationTraderReview['status'];
  label: string;
  tone: TraderReviewTone;
  canSubmitTraderVerdict: boolean;
  canRequestTraderMode: boolean;
}

export function resolveTraderReviewLaneState(
  review: ValidationTraderReview,
): TraderReviewLaneState {
  switch (review.status) {
    case 'requested':
      return {
        mode: review.status,
        label: 'Requested',
        tone: 'pending',
        canSubmitTraderVerdict: true,
        canRequestTraderMode: false,
      };
    case 'approved':
      return {
        mode: review.status,
        label: 'Approved',
        tone: 'success',
        canSubmitTraderVerdict: false,
        canRequestTraderMode: false,
      };
    case 'rejected':
      return {
        mode: review.status,
        label: 'Rejected',
        tone: 'danger',
        canSubmitTraderVerdict: false,
        canRequestTraderMode: false,
      };
    default:
      return {
        mode: 'not_requested',
        label: 'Not Requested',
        tone: 'neutral',
        canSubmitTraderVerdict: false,
        canRequestTraderMode: !review.required,
      };
  }
}
