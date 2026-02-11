import { parseArgs } from 'node:util';
import { xai } from '@ai-sdk/xai';
import { generateText } from 'ai';

import { getLonaClient } from '../../src/lib/lona/client';
import { validateConfig } from '../lib/config';
import {
  bold,
  cyan,
  dim,
  green,
  printError,
  printHeader,
  printSuccess,
  red,
  spinner,
  yellow,
} from '../lib/output';

const NEWS_ANALYSIS_PROMPT = `You are a financial news analyst and sentiment expert. Analyze recent news, events, and market sentiment that could impact trading strategies.

For each asset class or strategy, assess:
1. Overall sentiment (bullish/bearish/neutral) with confidence level
2. Key recent events and their market impact
3. Upcoming catalysts (earnings, fed meetings, protocol upgrades, etc.)
4. Risk events that could cause sharp moves
5. Trading implications and suggested actions

Output as JSON:
{
  "overall_sentiment": "bullish|bearish|neutral",
  "confidence": 0.0-1.0,
  "key_events": [
    { "event": "description", "impact": "positive|negative|neutral", "affected_assets": ["BTC", "ETH"] }
  ],
  "upcoming_catalysts": [
    { "event": "description", "date": "approximate date", "expected_impact": "high|medium|low" }
  ],
  "risk_factors": ["factor 1", "factor 2"],
  "trading_implications": "actionable summary"
}`;

export async function newsCommand(args: string[]) {
  const { values } = parseArgs({
    args,
    options: {
      assets: { type: 'string', default: 'crypto,stocks' },
      'strategy-id': { type: 'string' },
      help: { type: 'boolean', default: false },
    },
    allowPositionals: false,
  });

  if (values.help) {
    printHeader('News Command');
    console.log(`${bold('Usage:')}  nexus news [options]\n`);
    console.log(`${bold('Options:')}`);
    console.log('  --assets        Comma-separated asset classes (default: crypto,stocks)');
    console.log(`  --strategy-id   Analyze news for a specific strategy's assets`);
    console.log('  --help          Show this help\n');
    return;
  }

  validateConfig(['XAI_API_KEY']);

  let assetContext = (values.assets ?? 'crypto,stocks')
    .split(',')
    .map((s) => s.trim())
    .join(', ');
  let strategyContext = '';

  if (values['strategy-id']) {
    validateConfig(['LONA_AGENT_TOKEN']);
    const lona = getLonaClient();
    const strategy = await lona.getStrategy(values['strategy-id']);
    strategyContext = `Strategy: ${strategy.name}`;
    assetContext = strategy.name;
  }

  printHeader('News & Sentiment Analysis');
  console.log(`  ${cyan('Focus:')} ${assetContext}\n`);

  const spin = spinner('Analyzing news and sentiment...');
  const startTime = Date.now();

  try {
    const { text, usage } = await generateText({
      model: xai('grok-4-1-fast-non-reasoning'),
      system: NEWS_ANALYSIS_PROMPT,
      prompt: `Analyze recent news and market sentiment for: ${assetContext}.
${strategyContext ? `Context: ${strategyContext}` : ''}
Today's date: ${new Date().toISOString().split('T')[0]}.
Focus on events from the last 7 days and upcoming catalysts in the next 2 weeks.`,
    });

    const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
    spin.stop('Analysis complete!');

    const jsonMatch = text.match(/\{[\s\S]*\}/);
    if (jsonMatch) {
      try {
        const data = JSON.parse(jsonMatch[0]);

        // Sentiment header
        const sentColor =
          data.overall_sentiment === 'bullish'
            ? green
            : data.overall_sentiment === 'bearish'
              ? red
              : yellow;
        console.log(
          `\n  ${bold('Sentiment:')} ${sentColor(data.overall_sentiment?.toUpperCase() ?? 'N/A')} ${dim(`(${((data.confidence ?? 0) * 100).toFixed(0)}% confidence)`)}`,
        );

        // Key events
        if (data.key_events?.length) {
          console.log(`\n${bold('Key Events:')}`);
          for (const event of data.key_events) {
            const impactIcon =
              event.impact === 'positive'
                ? green('+')
                : event.impact === 'negative'
                  ? red('-')
                  : dim('~');
            console.log(`  ${impactIcon} ${event.event}`);
            if (event.affected_assets?.length) {
              console.log(`    ${dim(`Affects: ${event.affected_assets.join(', ')}`)}`);
            }
          }
        }

        // Upcoming catalysts
        if (data.upcoming_catalysts?.length) {
          console.log(`\n${bold('Upcoming Catalysts:')}`);
          for (const catalyst of data.upcoming_catalysts) {
            const urgency =
              catalyst.expected_impact === 'high'
                ? red('!!')
                : catalyst.expected_impact === 'medium'
                  ? yellow('!')
                  : dim('.');
            console.log(`  ${urgency} ${catalyst.event} ${dim(`(${catalyst.date ?? 'TBD'})`)}`);
          }
        }

        // Risk factors
        if (data.risk_factors?.length) {
          console.log(`\n${bold('Risk Factors:')}`);
          for (const risk of data.risk_factors) {
            console.log(`  ${red('!')} ${risk}`);
          }
        }

        // Trading implications
        if (data.trading_implications) {
          console.log(`\n${bold('Trading Implications:')}\n  ${data.trading_implications}`);
        }
      } catch {
        console.log(`\n${text}`);
      }
    } else {
      console.log(`\n${text}`);
    }

    console.log(
      `\n${dim(`Completed in ${elapsed}s | ${usage?.totalTokens?.toLocaleString() ?? '?'} tokens`)}\n`,
    );
  } catch (error) {
    spin.stop();
    printError(error instanceof Error ? error.message : String(error));
    process.exit(1);
  }
}
