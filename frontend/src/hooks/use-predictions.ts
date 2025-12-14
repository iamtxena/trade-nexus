import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

import type { Prediction, PredictionRequest } from '@/types/predictions';

async function fetchPredictions(symbol?: string): Promise<Prediction[]> {
  const url = symbol ? `/api/predictions?symbol=${symbol}` : '/api/predictions';
  const response = await fetch(url);
  if (!response.ok) throw new Error('Failed to fetch predictions');
  return response.json();
}

async function createPrediction(request: PredictionRequest): Promise<Prediction> {
  const response = await fetch('/api/predictions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!response.ok) throw new Error('Failed to create prediction');
  return response.json();
}

export function usePredictions(symbol?: string) {
  return useQuery({
    queryKey: ['predictions', symbol],
    queryFn: () => fetchPredictions(symbol),
  });
}

export function useCreatePrediction() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createPrediction,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['predictions'] });
      queryClient.invalidateQueries({ queryKey: ['predictions', data.symbol] });
    },
  });
}
