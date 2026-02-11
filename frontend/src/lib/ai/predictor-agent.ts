import type { Prediction, PredictionRequest } from '@/types/predictions';

const ML_BACKEND_URL = process.env.ML_BACKEND_URL || 'http://localhost:8000';

export async function getPrediction(request: PredictionRequest): Promise<Prediction> {
  const response = await fetch(`${ML_BACKEND_URL}/api/predict`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`Prediction failed: ${response.statusText}`);
  }

  return response.json();
}

export async function checkAnomaly(
  symbol: string,
  data: number[],
): Promise<{ isAnomaly: boolean; score: number }> {
  const response = await fetch(`${ML_BACKEND_URL}/api/anomaly`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ symbol, data }),
  });

  if (!response.ok) {
    throw new Error(`Anomaly check failed: ${response.statusText}`);
  }

  return response.json();
}

export async function optimizePortfolio(
  holdings: Record<string, number>,
  predictions: Prediction[],
): Promise<{ allocations: Record<string, number>; expectedReturn: number }> {
  const response = await fetch(`${ML_BACKEND_URL}/api/optimize`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ holdings, predictions }),
  });

  if (!response.ok) {
    throw new Error(`Portfolio optimization failed: ${response.statusText}`);
  }

  return response.json();
}
