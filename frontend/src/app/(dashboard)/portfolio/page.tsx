'use client';

import { DollarSign, PieChart, TrendingUp, Wallet } from 'lucide-react';
import { useEffect, useState } from 'react';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

interface Portfolio {
  balance: number;
  holdings: Record<string, { quantity: number; avgPrice: number }>;
  totalValue: number;
}

export default function PortfolioPage() {
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/portfolio')
      .then((res) => (res.ok ? res.json() : null))
      .then(setPortfolio)
      .catch(() => setPortfolio(null))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Portfolio</h2>
          <p className="text-muted-foreground">Loading...</p>
        </div>
      </div>
    );
  }

  const holdingEntries = portfolio ? Object.entries(portfolio.holdings) : [];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Portfolio</h2>
        <p className="text-muted-foreground">Track your portfolio performance and holdings</p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Total Value</CardTitle>
            <DollarSign className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">${(portfolio?.totalValue ?? 0).toLocaleString()}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Available Balance
            </CardTitle>
            <Wallet className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">${(portfolio?.balance ?? 0).toLocaleString()}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Positions</CardTitle>
            <PieChart className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{holdingEntries.length}</p>
          </CardContent>
        </Card>
      </div>

      {holdingEntries.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center justify-center py-12 text-center">
            <div className="mb-4 rounded-full bg-muted p-3">
              <TrendingUp className="size-6 text-muted-foreground" />
            </div>
            <h3 className="text-lg font-semibold">No positions</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              Run the strategist to generate and allocate strategies
            </p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Holdings</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {holdingEntries.map(([symbol, pos]) => (
                <div
                  key={symbol}
                  className="flex items-center justify-between rounded-lg border p-3"
                >
                  <div>
                    <p className="font-medium">{symbol}</p>
                    <p className="text-xs text-muted-foreground">Avg: ${pos.avgPrice.toFixed(2)}</p>
                  </div>
                  <p className="font-mono text-sm">{pos.quantity}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
