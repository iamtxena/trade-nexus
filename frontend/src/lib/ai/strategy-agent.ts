import { generateText } from 'ai';
import { xai } from '@ai-sdk/xai';
import { wrapAISDKModel } from 'langsmith/wrappers/vercel';

import type { StrategyContext, StrategyOutput } from '@/types/strategies';

const model = wrapAISDKModel(xai('grok-2-latest'));

export async function generateStrategy(context: StrategyContext): Promise<StrategyOutput> {
  const response = await generateText({
    model,
    system: `You are a trading strategy agent. Generate or modify trading strategies
             based on market conditions, ML predictions, and portfolio state.

             Output format:
             - Strategy name
             - Entry conditions (when to buy)
             - Exit conditions (when to sell)
             - Risk parameters (stop loss, position size)
             - Confidence score (0-100)`,
    prompt: buildStrategyPrompt(context),
  });

  return parseStrategyOutput(response.text);
}

export async function modifyStrategy(
  existingStrategy: string,
  context: StrategyContext
): Promise<StrategyOutput> {
  const response = await generateText({
    model,
    system: `You are a trading strategy agent. Modify the existing strategy
             based on new market conditions and ML predictions.
             Keep changes minimal unless significant improvement is expected.

             Existing strategy:
             ${existingStrategy}`,
    prompt: buildStrategyPrompt(context),
  });

  return parseStrategyOutput(response.text);
}

function buildStrategyPrompt(context: StrategyContext): string {
  return `
Market Data:
- Symbol: ${context.symbol}
- Current Price: ${context.currentPrice}
- 24h Change: ${context.priceChange24h}%

ML Predictions:
${context.predictions.map((p) => `- ${p.type}: ${p.value} (confidence: ${p.confidence}%)`).join('\n')}

Portfolio State:
- Current Holdings: ${JSON.stringify(context.portfolio.holdings)}
- Available Balance: ${context.portfolio.availableBalance}
- Total Value: ${context.portfolio.totalValue}

News Sentiment: ${context.newsSentiment}

Generate an optimal trading strategy for these conditions.
  `.trim();
}

function parseStrategyOutput(text: string): StrategyOutput {
  // Parse the LLM output into structured format
  // This is a simplified parser - in production, use more robust parsing
  return {
    name: extractField(text, 'Strategy name') || 'Generated Strategy',
    entryConditions: extractField(text, 'Entry conditions') || '',
    exitConditions: extractField(text, 'Exit conditions') || '',
    riskParameters: {
      stopLoss: parseFloat(extractField(text, 'Stop loss') || '5'),
      positionSize: parseFloat(extractField(text, 'Position size') || '10'),
    },
    confidence: parseInt(extractField(text, 'Confidence') || '50', 10),
    rawOutput: text,
  };
}

function extractField(text: string, field: string): string | null {
  const regex = new RegExp(`${field}[:\\s]+([^\\n]+)`, 'i');
  const match = text.match(regex);
  return match ? match[1].trim() : null;
}
