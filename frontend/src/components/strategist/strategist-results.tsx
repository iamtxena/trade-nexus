'use client';

import { useEffect, useRef } from 'react';
import { AlertCircle, Sparkles, Terminal } from 'lucide-react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

interface StrategistResultsProps {
  streamedText: string;
  isRunning: boolean;
  error: string | null;
}

export function StrategistResults({
  streamedText,
  isRunning,
  error,
}: StrategistResultsProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [streamedText]);

  const hasContent = streamedText.length > 0;
  const isComplete = hasContent && !isRunning;

  return (
    <Card className="flex h-full min-h-[500px] flex-col border-border/50">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2 text-base">
              <Terminal className="size-4 text-primary" />
              Pipeline Output
            </CardTitle>
            <CardDescription>
              {isRunning
                ? 'AI agent is executing the pipeline...'
                : isComplete
                  ? 'Pipeline complete'
                  : 'Configure and run the pipeline to see results'}
            </CardDescription>
          </div>
          {isRunning && (
            <div className="flex items-center gap-2">
              <span className="relative flex size-2.5">
                <span className="absolute inline-flex size-full animate-ping rounded-full bg-primary opacity-75" />
                <span className="relative inline-flex size-2.5 rounded-full bg-primary" />
              </span>
              <span className="text-xs text-muted-foreground">Streaming</span>
            </div>
          )}
          {isComplete && (
            <div className="flex items-center gap-2 text-emerald-500">
              <Sparkles className="size-4" />
              <span className="text-xs font-medium">Done</span>
            </div>
          )}
        </div>
      </CardHeader>

      <CardContent className="flex flex-1 flex-col">
        {/* Error State */}
        {error && (
          <div className="flex items-start gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-4">
            <AlertCircle className="mt-0.5 size-4 shrink-0 text-destructive" />
            <div>
              <p className="text-sm font-medium text-destructive">Pipeline Error</p>
              <p className="mt-1 text-sm text-muted-foreground">{error}</p>
            </div>
          </div>
        )}

        {/* Empty State */}
        {!hasContent && !isRunning && !error && (
          <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center">
            <div className="flex size-12 items-center justify-center rounded-xl bg-secondary">
              <Terminal className="size-6 text-muted-foreground" />
            </div>
            <div>
              <p className="text-sm font-medium text-foreground/80">No results yet</p>
              <p className="mt-1 text-xs text-muted-foreground">
                Configure the parameters and hit &quot;Run Pipeline&quot;
              </p>
            </div>
          </div>
        )}

        {/* Loading Skeleton */}
        {isRunning && !hasContent && (
          <div className="space-y-3">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-5/6" />
            <Skeleton className="h-4 w-2/3" />
          </div>
        )}

        {/* Streamed Content */}
        {hasContent && (
          <div
            ref={scrollRef}
            className={cn(
              'flex-1 overflow-y-auto rounded-lg bg-background/50 border border-border/30',
              isRunning && 'border-primary/20'
            )}
          >
            <div className="p-4">
              <pre className="whitespace-pre-wrap break-words font-mono text-[13px] leading-relaxed text-foreground/90">
                {streamedText}
                {isRunning && (
                  <span className="inline-block size-2 animate-pulse rounded-full bg-primary ml-1 align-middle" />
                )}
              </pre>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
