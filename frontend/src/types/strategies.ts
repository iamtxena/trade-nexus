import type { PortfolioState, Prediction } from './agents';

export interface Strategy {
  id: string;
  userId: string;
  name: string;
  code: string;
  backtestResults?: BacktestResults;
  isActive: boolean;
  createdAt: string;
}

export interface StrategyContext {
  symbol: string;
  currentPrice: number;
  priceChange24h: number;
  predictions: Prediction[];
  portfolio: PortfolioState;
  newsSentiment: number;
}

export interface StrategyOutput {
  name: string;
  entryConditions: string;
  exitConditions: string;
  riskParameters: {
    stopLoss: number;
    positionSize: number;
    takeProfitLevels?: number[];
  };
  confidence: number;
  rawOutput: string;
}

export interface BacktestResults {
  startDate: string;
  endDate: string;
  initialCapital: number;
  finalCapital: number;
  totalReturn: number;
  sharpeRatio: number;
  maxDrawdown: number;
  winRate: number;
  totalTrades: number;
  profitableTrades: number;
  avgTradeReturn: number;
  trades: BacktestTrade[];
}

export interface BacktestTrade {
  entryDate: string;
  exitDate: string;
  symbol: string;
  side: 'long' | 'short';
  entryPrice: number;
  exitPrice: number;
  quantity: number;
  pnl: number;
  returnPercent: number;
}

export interface StrategySignal {
  strategyId: string;
  symbol: string;
  action: 'buy' | 'sell' | 'hold';
  strength: number;
  timestamp: string;
  reason: string;
}
