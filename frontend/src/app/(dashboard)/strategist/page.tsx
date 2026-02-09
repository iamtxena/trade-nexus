'use client';

import { Brain } from 'lucide-react';
import { StrategistConfig } from '@/components/strategist/strategist-config';
import { StrategistResults } from '@/components/strategist/strategist-results';
import { useStrategist } from '@/hooks/use-strategist';

export default function StrategistPage() {
  const { run, streamedText, isRunning, error, reset } = useStrategist();

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-lg bg-primary/15">
            <Brain className="size-5 text-primary" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Strategist Brain</h1>
            <p className="text-sm text-muted-foreground">
              AI-powered pipeline: research, generate, backtest, score, and allocate
            </p>
          </div>
        </div>
      </div>

      {/* Two-column layout */}
      <div className="grid gap-6 lg:grid-cols-[380px_1fr]">
        <StrategistConfig onRun={run} onReset={reset} isRunning={isRunning} />
        <StrategistResults
          streamedText={streamedText}
          isRunning={isRunning}
          error={error}
        />
      </div>
    </div>
  );
}
