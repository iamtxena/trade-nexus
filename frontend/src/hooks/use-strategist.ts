import { useMutation } from '@tanstack/react-query';

import type { StrategistOptions } from '@/lib/ai/strategist';

async function runStrategistApi(input: StrategistOptions): Promise<string> {
  const response = await fetch('/api/strategist', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Request failed' }));
    throw new Error(error.error ?? `HTTP ${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) throw new Error('No response stream');

  const decoder = new TextDecoder();
  let text = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    text += decoder.decode(value, { stream: true });
  }

  return text;
}

export function useStrategist() {
  return useMutation({
    mutationKey: ['strategist'],
    mutationFn: runStrategistApi,
  });
}
