import { useCallback, useRef, useState } from 'react';

import type { StrategistOptions } from '@/lib/ai/strategist';

export interface UseStrategistReturn {
  run: (options: StrategistOptions) => void;
  streamedText: string;
  isRunning: boolean;
  error: string | null;
  reset: () => void;
}

export function useStrategist(): UseStrategistReturn {
  const [streamedText, setStreamedText] = useState('');
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    setStreamedText('');
    setIsRunning(false);
    setError(null);
  }, []);

  const run = useCallback((options: StrategistOptions) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setStreamedText('');
    setError(null);
    setIsRunning(true);

    (async () => {
      try {
        const response = await fetch('/api/strategist', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(options),
          signal: controller.signal,
        });

        if (!response.ok) {
          const body = await response.json().catch(() => ({ error: 'Request failed' }));
          throw new Error(body.error ?? `HTTP ${response.status}`);
        }

        const reader = response.body?.getReader();
        if (!reader) throw new Error('No response stream');

        const decoder = new TextDecoder();
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value, { stream: true });
          setStreamedText((prev) => prev + chunk);
        }
      } catch (err) {
        if ((err as Error).name !== 'AbortError') {
          setError((err as Error).message);
        }
      } finally {
        setIsRunning(false);
      }
    })();
  }, []);

  return { run, streamedText, isRunning, error, reset };
}
