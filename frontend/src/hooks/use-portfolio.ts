import { useQuery } from '@tanstack/react-query';

export interface PortfolioSummary {
  totalValue: number;
  availableBalance: number;
  unrealizedPnl: number;
  unrealizedPnlPercent: number;
  holdings: Holding[];
}

export interface Holding {
  symbol: string;
  quantity: number;
  avgPrice: number;
  currentPrice: number;
  value: number;
  pnl: number;
  pnlPercent: number;
}

async function fetchPortfolio(): Promise<PortfolioSummary> {
  const response = await fetch('/api/portfolio');
  if (!response.ok) throw new Error('Failed to fetch portfolio');
  return response.json();
}

async function fetchHolding(symbol: string): Promise<Holding> {
  const response = await fetch(`/api/portfolio/${symbol}`);
  if (!response.ok) throw new Error('Failed to fetch holding');
  return response.json();
}

export function usePortfolio() {
  return useQuery({
    queryKey: ['portfolio'],
    queryFn: fetchPortfolio,
    refetchInterval: 30000, // Refresh every 30 seconds
  });
}

export function useHolding(symbol: string) {
  return useQuery({
    queryKey: ['portfolio', symbol],
    queryFn: () => fetchHolding(symbol),
    enabled: !!symbol,
    refetchInterval: 30000,
  });
}
