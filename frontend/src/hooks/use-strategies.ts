import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

import type { Strategy } from '@/types/strategies';

async function fetchStrategies(): Promise<Strategy[]> {
  const response = await fetch('/api/strategies');
  if (!response.ok) throw new Error('Failed to fetch strategies');
  return response.json();
}

async function fetchStrategy(id: string): Promise<Strategy> {
  const response = await fetch(`/api/strategies/${id}`);
  if (!response.ok) throw new Error('Failed to fetch strategy');
  return response.json();
}

async function createStrategy(data: Partial<Strategy>): Promise<Strategy> {
  const response = await fetch('/api/strategies', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!response.ok) throw new Error('Failed to create strategy');
  return response.json();
}

async function updateStrategy(id: string, data: Partial<Strategy>): Promise<Strategy> {
  const response = await fetch(`/api/strategies/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!response.ok) throw new Error('Failed to update strategy');
  return response.json();
}

async function deleteStrategy(id: string): Promise<void> {
  const response = await fetch(`/api/strategies/${id}`, { method: 'DELETE' });
  if (!response.ok) throw new Error('Failed to delete strategy');
}

export function useStrategies() {
  return useQuery({
    queryKey: ['strategies'],
    queryFn: fetchStrategies,
  });
}

export function useStrategy(id: string) {
  return useQuery({
    queryKey: ['strategies', id],
    queryFn: () => fetchStrategy(id),
    enabled: !!id,
  });
}

export function useCreateStrategy() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createStrategy,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['strategies'] });
    },
  });
}

export function useUpdateStrategy() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<Strategy> }) => updateStrategy(id, data),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['strategies'] });
      queryClient.invalidateQueries({ queryKey: ['strategies', data.id] });
    },
  });
}

export function useDeleteStrategy() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: deleteStrategy,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['strategies'] });
    },
  });
}
