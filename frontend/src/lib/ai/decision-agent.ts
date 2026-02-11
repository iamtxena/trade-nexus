import { xai } from '@ai-sdk/xai';
import * as ai from 'ai';
import { wrapAISDK } from 'langsmith/experimental/vercel';

import type { DecisionContext, TradeDecision } from '@/types/agents';

const { generateText } = wrapAISDK(ai);
const model = xai('grok-4-1-fast-non-reasoning');

export async function makeDecision(context: DecisionContext): Promise<TradeDecision> {
  const response = await generateText({
    model,
    system: `You are a trading decision agent. Based on strategy signals,
             ML predictions, and current market conditions, decide whether to:
             - BUY: Open or add to a position
             - SELL: Close or reduce a position
             - HOLD: Maintain current position

             Output JSON format:
             {
               "action": "BUY" | "SELL" | "HOLD",
               "symbol": "string",
               "quantity": number,
               "price": number,
               "confidence": number (0-100),
               "reasoning": "string"
             }`,
    prompt: buildDecisionPrompt(context),
  });

  return parseDecisionOutput(response.text);
}

function buildDecisionPrompt(context: DecisionContext): string {
  return `
Strategy Signal: ${context.strategySignal}

ML Predictions:
${context.predictions.map((p) => `- ${p.type}: ${p.value} (confidence: ${p.confidence}%)`).join('\n')}

Current Position:
- Symbol: ${context.symbol}
- Holdings: ${context.currentPosition.quantity} @ ${context.currentPosition.avgPrice}
- P&L: ${context.currentPosition.unrealizedPnl}

Market Conditions:
- Current Price: ${context.currentPrice}
- Volume: ${context.volume24h}
- Volatility: ${context.volatility}

Risk Limits:
- Max Position Size: ${context.riskLimits.maxPositionSize}
- Max Drawdown: ${context.riskLimits.maxDrawdown}%

Make a trading decision based on these inputs.
  `.trim();
}

function parseDecisionOutput(text: string): TradeDecision {
  try {
    // Try to extract JSON from the response
    const jsonMatch = text.match(/\{[\s\S]*\}/);
    if (jsonMatch) {
      const parsed = JSON.parse(jsonMatch[0]);
      return {
        action: parsed.action || 'HOLD',
        symbol: parsed.symbol || '',
        quantity: parsed.quantity || 0,
        price: parsed.price || 0,
        confidence: parsed.confidence || 50,
        reasoning: parsed.reasoning || text,
        timestamp: new Date().toISOString(),
      };
    }
  } catch {
    // If JSON parsing fails, extract manually
  }

  // Fallback: determine action from text
  const action = text.toLowerCase().includes('buy')
    ? 'BUY'
    : text.toLowerCase().includes('sell')
      ? 'SELL'
      : 'HOLD';

  return {
    action,
    symbol: '',
    quantity: 0,
    price: 0,
    confidence: 50,
    reasoning: text,
    timestamp: new Date().toISOString(),
  };
}
