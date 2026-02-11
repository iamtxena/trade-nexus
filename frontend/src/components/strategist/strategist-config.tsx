'use client';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Slider } from '@/components/ui/slider';
import type { StrategistOptions } from '@/lib/ai/strategist';
import { cn } from '@/lib/utils';
import { DollarSign, Play, RotateCcw } from 'lucide-react';
import { useState } from 'react';

const ASSET_CLASSES = [
  { id: 'crypto', label: 'Crypto', color: 'bg-amber-500' },
  { id: 'stocks', label: 'Stocks', color: 'bg-blue-500' },
  { id: 'forex', label: 'Forex', color: 'bg-emerald-500' },
] as const;

interface StrategistConfigProps {
  onRun: (options: StrategistOptions) => void;
  onReset: () => void;
  isRunning: boolean;
}

export function StrategistConfig({ onRun, onReset, isRunning }: StrategistConfigProps) {
  const [selectedAssets, setSelectedAssets] = useState<string[]>(['crypto']);
  const [capital, setCapital] = useState(100_000);
  const [maxPosition, setMaxPosition] = useState(5);
  const [maxDrawdown, setMaxDrawdown] = useState(15);

  function toggleAsset(id: string) {
    setSelectedAssets((prev) => (prev.includes(id) ? prev.filter((a) => a !== id) : [...prev, id]));
  }

  function handleRun() {
    onRun({
      assetClasses: selectedAssets.length > 0 ? selectedAssets : ['crypto'],
      capital,
      maxPositionPct: maxPosition,
      maxDrawdownPct: maxDrawdown,
    });
  }

  return (
    <Card className="border-border/50">
      <CardHeader>
        <CardTitle className="text-base">Pipeline Configuration</CardTitle>
        <CardDescription>Define your universe, capital, and risk parameters</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Asset Classes */}
        <div className="space-y-3">
          <Label className="text-sm font-medium">Asset Classes</Label>
          <div className="flex flex-wrap gap-2">
            {ASSET_CLASSES.map((asset) => {
              const selected = selectedAssets.includes(asset.id);
              return (
                <button
                  key={asset.id}
                  type="button"
                  onClick={() => toggleAsset(asset.id)}
                  disabled={isRunning}
                  className={cn(
                    'inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium transition-all duration-200',
                    selected
                      ? 'border-primary/40 bg-primary/10 text-foreground'
                      : 'border-border/50 bg-secondary/30 text-muted-foreground hover:border-border hover:bg-secondary/60',
                    isRunning && 'opacity-50 cursor-not-allowed',
                  )}
                >
                  <span
                    className={cn(
                      'size-2 rounded-full transition-opacity',
                      asset.color,
                      !selected && 'opacity-30',
                    )}
                  />
                  {asset.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Capital Input */}
        <div className="space-y-2">
          <Label htmlFor="capital" className="text-sm font-medium">
            Starting Capital
          </Label>
          <div className="relative">
            <DollarSign className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              id="capital"
              type="number"
              min={1000}
              step={1000}
              value={capital}
              onChange={(e) => setCapital(Number(e.target.value))}
              disabled={isRunning}
              className="pl-9 tabular-nums"
            />
          </div>
          <p className="text-xs text-muted-foreground">
            {new Intl.NumberFormat('en-US', {
              style: 'currency',
              currency: 'USD',
              maximumFractionDigits: 0,
            }).format(capital)}
          </p>
        </div>

        {/* Max Position Size */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <Label className="text-sm font-medium">Max Position Size</Label>
            <Badge variant="secondary" className="tabular-nums text-xs font-normal">
              {maxPosition}%
            </Badge>
          </div>
          <Slider
            value={[maxPosition]}
            onValueChange={([v]) => setMaxPosition(v)}
            min={1}
            max={25}
            step={1}
            disabled={isRunning}
          />
          <div className="flex justify-between text-[11px] text-muted-foreground">
            <span>Conservative (1%)</span>
            <span>Aggressive (25%)</span>
          </div>
        </div>

        {/* Max Drawdown */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <Label className="text-sm font-medium">Max Drawdown</Label>
            <Badge variant="secondary" className="tabular-nums text-xs font-normal">
              {maxDrawdown}%
            </Badge>
          </div>
          <Slider
            value={[maxDrawdown]}
            onValueChange={([v]) => setMaxDrawdown(v)}
            min={1}
            max={50}
            step={1}
            disabled={isRunning}
          />
          <div className="flex justify-between text-[11px] text-muted-foreground">
            <span>Tight (1%)</span>
            <span>Loose (50%)</span>
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-2 pt-2">
          <Button
            onClick={handleRun}
            disabled={isRunning || selectedAssets.length === 0}
            className="flex-1"
          >
            {isRunning ? (
              <>
                <span className="size-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                Running Pipeline...
              </>
            ) : (
              <>
                <Play className="size-4" />
                Run Pipeline
              </>
            )}
          </Button>
          <Button
            variant="outline"
            size="icon"
            onClick={onReset}
            disabled={isRunning}
            aria-label="Reset"
          >
            <RotateCcw className="size-4" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
