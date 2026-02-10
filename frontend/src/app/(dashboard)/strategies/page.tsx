'use client';

import { useEffect, useState } from 'react';
import { LineChart, Plus } from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

interface Strategy {
  id: string;
  name: string;
  code: string;
  backtestResults: Record<string, unknown> | null;
  isActive: boolean;
  createdAt: string;
}

export default function StrategiesPage() {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/strategies')
      .then((res) => (res.ok ? res.json() : []))
      .then(setStrategies)
      .catch(() => setStrategies([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Strategies</h2>
        <p className="text-muted-foreground">
          View, manage, and monitor your trading strategies
        </p>
      </div>

      {loading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Card key={i} className="animate-pulse">
              <CardHeader className="space-y-2">
                <div className="h-4 w-3/4 rounded bg-muted" />
                <div className="h-3 w-1/2 rounded bg-muted" />
              </CardHeader>
            </Card>
          ))}
        </div>
      ) : strategies.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center justify-center py-12 text-center">
            <div className="mb-4 rounded-full bg-muted p-3">
              <Plus className="size-6 text-muted-foreground" />
            </div>
            <h3 className="text-lg font-semibold">No strategies yet</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              Use the Strategist Brain to create and backtest strategies
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {strategies.map((strategy) => (
            <Card key={strategy.id}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">{strategy.name}</CardTitle>
                  <Badge variant={strategy.isActive ? 'default' : 'secondary'}>
                    {strategy.isActive ? 'Active' : 'Inactive'}
                  </Badge>
                </div>
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <LineChart className="size-3" />
                  <span>
                    Created {new Date(strategy.createdAt).toLocaleDateString()}
                  </span>
                </div>
              </CardHeader>
              {strategy.backtestResults && (
                <CardContent>
                  <p className="text-xs text-muted-foreground">
                    Backtest results available
                  </p>
                </CardContent>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
