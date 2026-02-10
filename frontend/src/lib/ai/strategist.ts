import * as ai from 'ai';
import { tool, zodSchema, stepCountIs } from 'ai';
import { xai } from '@ai-sdk/xai';
import { wrapAISDK } from 'langsmith/experimental/vercel';
import { z } from 'zod';

import { getLonaClient } from '@/lib/lona/client';
import type { LonaBacktestRequest, LonaReport } from '@/lib/lona/types';

const { generateText, streamText } = wrapAISDK(ai);
const model = xai('grok-4-1-fast-non-reasoning');

const STRATEGIST_SYSTEM_PROMPT = `You are the Trade Nexus Strategist Brain — an elite quantitative portfolio strategist.

Your mission: research markets, generate trading strategies, backtest them via Lona, score the results, and produce a capital allocation plan.

## Pipeline
1. **Research**: Call research_markets to analyze market conditions for requested asset classes.
2. **Create strategies**: For each promising idea, call create_strategy to generate Backtrader code via Lona AI.
3. **Get market data**: Call list_symbols to check available data. If needed, call download_market_data for missing symbols.
4. **Backtest**: Call run_backtest for each strategy with the relevant data IDs. This returns metrics.
5. **Score**: Call score_strategies with the backtest metrics to rank them.
6. **Allocate**: Call decide_allocation with the ranked strategies and risk constraints.

## Rules
- Always research before creating strategies.
- Create 3-5 diverse strategies spanning different asset classes and types.
- Use provider "xai" when creating strategies for best results.
- When backtesting, use realistic date ranges (at least 6 months of data).
- Only allocate to strategies with a composite score above 0.3.
- Keep at least 10% in cash reserve.
- Never exceed the max position size per strategy.

After completing the full pipeline, summarize: which strategies were created, their backtest scores, and the final allocation plan.`;

const MARKET_RESEARCH_PROMPT = `You are an elite quantitative market analyst. Analyze market conditions and generate strategy ideas.

For each asset class, assess:
1. Market regime (trending/range-bound/transitioning) and volatility regime
2. Key trends, macro drivers, and dominant narratives
3. Specific trade setups for systematic strategies (name indicators, timeframes, pairs)
4. Risk factors that could invalidate the thesis

Suggest strategies codeable as Backtrader strategies with clear rules:
- Trend-following (MA crossovers, breakouts, momentum)
- Mean-reversion (RSI extremes, Bollinger bounces)
- Volatility strategies (regime switching)
- Statistical arbitrage

Output as JSON:
{
  "market_analysis": "comprehensive analysis",
  "strategy_ideas": [
    { "name": "Strategy Name", "asset_class": "crypto|stocks|forex", "type": "trend|mean_reversion|volatility|arbitrage", "description": "strategy logic", "rationale": "why it fits current conditions" }
  ]
}`;

const researchMarketsSchema = z.object({
  assetClasses: z
    .array(z.string())
    .describe('Asset classes to analyze, e.g. ["crypto", "stocks", "forex"]'),
  capital: z.number().describe('Total capital available'),
  maxPositionPct: z
    .number()
    .default(5)
    .describe('Max position size as % of portfolio'),
  maxDrawdownPct: z
    .number()
    .default(15)
    .describe('Max portfolio drawdown tolerance %'),
});

const createStrategySchema = z.object({
  description: z
    .string()
    .min(10)
    .describe('Detailed strategy description with entry/exit rules, indicators, timeframe'),
  name: z.string().optional().describe('Optional strategy name'),
  provider: z
    .string()
    .default('xai')
    .describe('AI provider for code generation (xai recommended)'),
});

const listSymbolsSchema = z.object({
  isGlobal: z
    .boolean()
    .default(false)
    .describe('Only show globally available (pre-loaded) symbols'),
  limit: z.number().default(20).describe('Max symbols to return'),
});

const downloadMarketDataSchema = z.object({
  symbol: z.string().describe('Trading symbol, e.g. BTCUSDT'),
  interval: z
    .string()
    .default('1h')
    .describe('Candle interval: 1m, 5m, 15m, 30m, 1h, 4h, 1d'),
  startDate: z.string().describe('Start date YYYY-MM-DD'),
  endDate: z.string().describe('End date YYYY-MM-DD'),
});

const runBacktestSchema = z.object({
  strategyId: z.string().describe('Lona strategy ID'),
  dataIds: z.array(z.string()).describe('Symbol/data IDs for the backtest'),
  startDate: z.string().describe('Backtest start date YYYY-MM-DD'),
  endDate: z.string().describe('Backtest end date YYYY-MM-DD'),
  initialCash: z.number().default(100000).describe('Starting capital'),
});

const scoreStrategiesSchema = z.object({
  strategies: z.array(
    z.object({
      name: z.string(),
      strategyId: z.string().nullable(),
      reportId: z.string().nullable(),
      metrics: z
        .object({
          sharpe_ratio: z.number().default(0),
          max_drawdown: z.number().default(0),
          win_rate: z.number().default(0),
          total_return: z.number().default(0),
        })
        .nullable(),
    }),
  ),
});

const decideAllocationSchema = z.object({
  rankedStrategies: z.array(
    z.object({
      name: z.string(),
      strategyId: z.string().nullable(),
      score: z.number(),
      assetClass: z.string().optional(),
      metrics: z.record(z.string(), z.unknown()).nullable(),
    }),
  ),
  capital: z.number().describe('Total capital to allocate'),
  maxPositionPct: z.number().default(5).describe('Max % per strategy'),
  maxDrawdownPct: z.number().default(15).describe('Max portfolio drawdown %'),
  marketAnalysis: z.string().optional().describe('Market context summary'),
});

const getMlPredictionSchema = z.object({
  symbol: z.string().describe('Trading symbol'),
  predictionType: z
    .string()
    .default('price')
    .describe('Type: price, anomaly, volatility'),
  timeframe: z.string().default('1d').describe('Prediction timeframe'),
});

const strategistTools = {
  research_markets: tool({
    description:
      'Analyze current market conditions for given asset classes. Returns market regime, key trends, strategy ideas.',
    inputSchema: zodSchema(researchMarketsSchema),
    execute: async (input: z.infer<typeof researchMarketsSchema>) => {
      const { text } = await generateText({
        model,
        system: MARKET_RESEARCH_PROMPT,
        prompt: `Analyze current market conditions for: ${input.assetClasses.join(', ')}.
Capital: $${input.capital.toLocaleString()}.
Risk: max ${input.maxPositionPct}% per position, max ${input.maxDrawdownPct}% drawdown.
Generate 3-5 diverse strategy ideas.`,
      });
      return text;
    },
  }),

  create_strategy: tool({
    description:
      'Create a Backtrader strategy from a natural language description via Lona AI code generation.',
    inputSchema: zodSchema(createStrategySchema),
    execute: async (input: z.infer<typeof createStrategySchema>) => {
      const client = getLonaClient();
      const result = await client.createStrategyFromDescription(
        input.description,
        input.name,
        input.provider,
      );
      return {
        strategyId: result.strategyId,
        name: result.name,
        explanation: result.explanation,
        codePreview: result.code.slice(0, 500) + (result.code.length > 500 ? '...' : ''),
      };
    },
  }),

  list_symbols: tool({
    description:
      'List available market data symbols on Lona. Use isGlobal=true for pre-loaded US equities/forex.',
    inputSchema: zodSchema(listSymbolsSchema),
    execute: async (input: z.infer<typeof listSymbolsSchema>) => {
      const client = getLonaClient();
      const symbols = await client.listSymbols(input.isGlobal, input.limit);
      return symbols.map((s) => ({
        id: s.id,
        name: s.name,
        exchange: s.type_metadata?.exchange ?? 'N/A',
        assetClass: s.type_metadata?.asset_class ?? 'N/A',
        frequencies: s.frequencies,
        isGlobal: s.is_global,
      }));
    },
  }),

  download_market_data: tool({
    description:
      'Download market data from Binance and upload to Lona. Returns the symbol ID for backtesting.',
    inputSchema: zodSchema(downloadMarketDataSchema),
    execute: async (input: z.infer<typeof downloadMarketDataSchema>) => {
      const client = getLonaClient();
      const result = await client.downloadMarketData(
        input.symbol,
        input.interval,
        input.startDate,
        input.endDate,
      );
      return {
        symbolId: result.id,
        name: result.name,
        description: result.description,
      };
    },
  }),

  run_backtest: tool({
    description:
      'Run a backtest for a strategy on Lona. Polls until complete and returns performance metrics.',
    inputSchema: zodSchema(runBacktestSchema),
    execute: async (input: z.infer<typeof runBacktestSchema>) => {
      const client = getLonaClient();
      const request: LonaBacktestRequest = {
        strategy_id: input.strategyId,
        data_ids: input.dataIds,
        start_date: input.startDate,
        end_date: input.endDate,
        simulation_parameters: {
          initial_cash: input.initialCash,
          commission_schema: { commission: 0.001, leverage: 1 },
          buy_on_close: true,
        },
      };

      const { report_id } = await client.runBacktest(request);
      const report: LonaReport = await client.waitForReport(report_id);

      return {
        reportId: report.id,
        status: report.status,
        metrics: report.total_stats,
        error: report.error,
      };
    },
  }),

  score_strategies: tool({
    description: `Score and rank strategies based on backtest metrics.
Composite score (0-1): 40% Sharpe + 25% max drawdown (inverted) + 20% win rate + 15% total return.`,
    inputSchema: zodSchema(scoreStrategiesSchema),
    execute: async (input: z.infer<typeof scoreStrategiesSchema>) => {
      return input.strategies
        .map((s) => {
          if (!s.metrics) return { ...s, score: 0 };

          const sharpeScore = Math.min(Math.max(s.metrics.sharpe_ratio / 3.0, 0), 1);
          const drawdownScore = Math.min(Math.max(1 - Math.abs(s.metrics.max_drawdown) / 50, 0), 1);
          const winScore = Math.min(
            Math.max(s.metrics.win_rate > 1 ? s.metrics.win_rate / 100 : s.metrics.win_rate, 0),
            1,
          );
          const returnScore = Math.min(Math.max(s.metrics.total_return / 100, 0), 1);

          const score =
            0.4 * sharpeScore +
            0.25 * drawdownScore +
            0.2 * winScore +
            0.15 * returnScore;

          return { ...s, score: Math.round(score * 10000) / 10000 };
        })
        .sort((a, b) => b.score - a.score);
    },
  }),

  decide_allocation: tool({
    description:
      'Decide portfolio capital allocation across ranked strategies respecting risk constraints.',
    inputSchema: zodSchema(decideAllocationSchema),
    execute: async (input: z.infer<typeof decideAllocationSchema>) => {
      const strategySummary = input.rankedStrategies
        .map(
          (s, i) =>
            `${i + 1}. Score: ${s.score.toFixed(4)} | ${s.name}${s.metrics ? ` | Metrics: ${JSON.stringify(s.metrics)}` : ''}`,
        )
        .join('\n');

      const { text } = await generateText({
        model,
        system: `You are a senior portfolio manager. Allocate capital across strategies.
Hard constraints: max ${input.maxPositionPct}% per position, max ${input.maxDrawdownPct}% drawdown, total capital $${input.capital.toLocaleString()}.
Only allocate to strategies with score > 0.3. Keep 10%+ in cash.
Output JSON: { allocations: [{ strategy_name, capital_pct, capital_amount, rationale }], cash_reserve_pct, risk_assessment }`,
        prompt: `Ranked strategies:\n${strategySummary}\n\nMarket context:\n${input.marketAnalysis?.slice(0, 500) ?? 'N/A'}`,
      });

      try {
        const jsonMatch = text.match(/\{[\s\S]*\}/);
        if (jsonMatch) return JSON.parse(jsonMatch[0]);
      } catch {
        // fallback
      }
      return { raw_response: text };
    },
  }),

  get_ml_prediction: tool({
    description:
      'Get ML predictions (LSTM, anomaly detection) from the Python backend. Optional enrichment step.',
    inputSchema: zodSchema(getMlPredictionSchema),
    execute: async (input: z.infer<typeof getMlPredictionSchema>) => {
      const mlBackendUrl = process.env.ML_BACKEND_URL ?? 'http://localhost:8000';
      try {
        const url = new URL('/api/predict', mlBackendUrl);
        const response = await fetch(url.toString(), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            symbol: input.symbol,
            prediction_type: input.predictionType,
            timeframe: input.timeframe,
          }),
        });

        if (!response.ok) {
          return {
            available: false,
            error: `ML backend returned ${response.status}`,
          };
        }

        return { available: true, ...(await response.json()) };
      } catch {
        return { available: false, error: 'ML backend unavailable' };
      }
    },
  }),
};

export interface StrategistOptions {
  assetClasses?: string[];
  capital?: number;
  maxPositionPct?: number;
  maxDrawdownPct?: number;
}

export interface StrategistResult {
  text: string;
  steps: Array<{
    toolCalls: Array<{ toolName: string; args: unknown }>;
    toolResults: Array<{ toolName: string; result: unknown }>;
    text: string;
  }>;
  usage: { totalTokens: number };
}

function buildPrompt(options: StrategistOptions) {
  const {
    assetClasses = ['crypto', 'stocks', 'forex'],
    capital = 100_000,
    maxPositionPct = 5,
    maxDrawdownPct = 15,
  } = options;

  return `Run the full strategist pipeline.

Asset classes: ${assetClasses.join(', ')}
Capital: $${capital.toLocaleString()}
Risk constraints: max ${maxPositionPct}% per position, max ${maxDrawdownPct}% drawdown.

Start by researching markets, then create strategies, download data if needed, backtest, score, and allocate capital. Produce a complete portfolio plan.`;
}

const sharedConfig = {
  model,
  system: STRATEGIST_SYSTEM_PROMPT,
  tools: strategistTools,
  stopWhen: stepCountIs(20),
} as const;

export async function runStrategist(
  options: StrategistOptions = {},
): Promise<StrategistResult> {
  const result = await generateText({
    ...sharedConfig,
    prompt: buildPrompt(options),
  });

  return {
    text: result.text,
    steps: result.steps.map((step) => ({
      toolCalls: step.toolCalls.map((tc) => ({
        toolName: tc.toolName,
        args: tc.input,
      })),
      toolResults: step.toolResults.map((tr) => ({
        toolName: tr.toolName,
        result: tr.output,
      })),
      text: step.text,
    })),
    usage: { totalTokens: result.totalUsage.totalTokens ?? 0 },
  };
}

export function streamStrategist(options: StrategistOptions = {}) {
  return streamText({
    ...sharedConfig,
    prompt: buildPrompt(options),
  });
}
