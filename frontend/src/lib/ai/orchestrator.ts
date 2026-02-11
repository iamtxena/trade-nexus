import { xai } from '@ai-sdk/xai';
import * as ai from 'ai';
import { wrapAISDK } from 'langsmith/experimental/vercel';

import { makeDecision } from '@/lib/ai/decision-agent';
import { checkAnomaly, getPrediction, optimizePortfolio } from '@/lib/ai/predictor-agent';
import { runStrategist } from '@/lib/ai/strategist';
import { generateStrategy } from '@/lib/ai/strategy-agent';
import type { AgentContext, AgentResult, OrchestratorTask } from '@/types/agents';
import type { DecisionContext } from '@/types/agents';
import type { PredictionRequest } from '@/types/predictions';
import type { StrategyContext } from '@/types/strategies';

const { generateText } = wrapAISDK(ai);
const model = xai('grok-4-1-fast-non-reasoning');

export async function orchestrate(tasks: OrchestratorTask[]): Promise<AgentResult[]> {
  const results: AgentResult[] = [];

  for (const task of tasks) {
    const result = await executeTask(task);
    results.push(result);

    // If a task fails, decide whether to continue or abort
    if (!result.success && task.critical) {
      break;
    }
  }

  return results;
}

export async function executeTask(task: OrchestratorTask): Promise<AgentResult> {
  const startTime = Date.now();

  try {
    const output = await dispatchAgent(task);

    return {
      taskId: task.id,
      type: task.type,
      success: true,
      output: typeof output === 'string' ? output : JSON.stringify(output),
      duration: Date.now() - startTime,
    };
  } catch (error) {
    return {
      taskId: task.id,
      type: task.type,
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error',
      duration: Date.now() - startTime,
    };
  }
}

async function dispatchAgent(task: OrchestratorTask): Promise<unknown> {
  const ctx = task.context;

  switch (task.type) {
    case 'predictor': {
      const request: PredictionRequest = {
        symbol: ctx.symbol,
        predictionType: 'price',
        timeframe: '1d',
      };
      return getPrediction(request);
    }

    case 'anomaly': {
      return checkAnomaly(ctx.symbol, ctx.priceHistory ?? []);
    }

    case 'optimizer': {
      const holdings: Record<string, number> = {};
      if (ctx.portfolio?.holdings) {
        for (const [symbol, pos] of Object.entries(ctx.portfolio.holdings)) {
          holdings[symbol] = pos.quantity;
        }
      }
      const predictions = (ctx.predictions ?? []).map((p) => ({
        id: '',
        userId: '',
        symbol: ctx.symbol,
        predictionType: 'price' as const,
        value: {
          predicted: p.value,
          timeframe: '1d',
        },
        confidence: p.confidence,
        createdAt: p.timestamp,
      }));
      return optimizePortfolio(holdings, predictions);
    }

    case 'strategy': {
      const strategyCtx: StrategyContext = {
        symbol: ctx.symbol,
        currentPrice: ctx.currentPrice,
        priceChange24h: 0,
        predictions: ctx.predictions ?? [],
        portfolio: ctx.portfolio ?? { holdings: {}, availableBalance: 0, totalValue: 0 },
        newsSentiment: ctx.newsSentiment ?? 0,
      };
      return generateStrategy(strategyCtx);
    }

    case 'decision': {
      const decisionCtx: DecisionContext = {
        symbol: ctx.symbol,
        strategySignal: 'neutral',
        predictions: ctx.predictions ?? [],
        currentPosition: {
          quantity: ctx.portfolio?.holdings?.[ctx.symbol]?.quantity ?? 0,
          avgPrice: ctx.portfolio?.holdings?.[ctx.symbol]?.avgPrice ?? 0,
          unrealizedPnl: 0,
        },
        currentPrice: ctx.currentPrice,
        volume24h: ctx.volume ?? 0,
        volatility: 0,
        riskLimits: {
          maxPositionSize: 10000,
          maxDrawdown: 15,
        },
      };
      return makeDecision(decisionCtx);
    }

    case 'strategist': {
      return runStrategist();
    }

    default: {
      const _exhaustive: never = task.type;
      throw new Error(`Unknown agent type: ${_exhaustive}`);
    }
  }
}

export async function analyzeContext(context: AgentContext): Promise<string> {
  const response = await generateText({
    model,
    system: `Analyze the following trading context and provide actionable insights.
             Focus on: market conditions, risk factors, and opportunities.`,
    prompt: JSON.stringify(context),
  });

  return response.text;
}
