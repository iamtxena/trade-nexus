export type AgentType = 'predictor' | 'anomaly' | 'optimizer' | 'strategy' | 'decision';

export type AgentStatus = 'idle' | 'running' | 'completed' | 'failed';

export interface Agent {
  id: string;
  type: AgentType;
  name: string;
  status: AgentStatus;
  lastRun?: string;
  lastResult?: AgentResult;
}

export interface AgentContext {
  symbol: string;
  currentPrice: number;
  priceHistory: number[];
  volume: number;
  predictions: Prediction[];
  portfolio: PortfolioState;
  newsSentiment?: number;
}

export interface Prediction {
  type: string;
  value: number;
  confidence: number;
  timestamp: string;
}

export interface PortfolioState {
  holdings: Record<string, { quantity: number; avgPrice: number }>;
  availableBalance: number;
  totalValue: number;
}

export interface OrchestratorTask {
  id: string;
  type: AgentType;
  context: AgentContext;
  critical: boolean;
  priority: number;
}

export interface AgentResult {
  taskId: string;
  type: AgentType;
  success: boolean;
  output?: string;
  error?: string;
  duration: number;
}

export interface DecisionContext {
  symbol: string;
  strategySignal: string;
  predictions: Prediction[];
  currentPosition: {
    quantity: number;
    avgPrice: number;
    unrealizedPnl: number;
  };
  currentPrice: number;
  volume24h: number;
  volatility: number;
  riskLimits: {
    maxPositionSize: number;
    maxDrawdown: number;
  };
}

export type TradeAction = 'BUY' | 'SELL' | 'HOLD';

export interface TradeDecision {
  action: TradeAction;
  symbol: string;
  quantity: number;
  price: number;
  confidence: number;
  reasoning: string;
  timestamp: string;
}

export interface AgentRun {
  id: string;
  userId: string;
  agentType: AgentType;
  input: Record<string, unknown>;
  output?: Record<string, unknown>;
  status: AgentStatus;
  createdAt: string;
  completedAt?: string;
}
