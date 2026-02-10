import { generateText } from 'ai';
import { xai } from '@ai-sdk/xai';
import { parseArgs } from 'util';

import { printHeader, printError, printSuccess, dim, bold, cyan, spinner } from '../lib/output';
import { validateConfig } from '../lib/config';

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

export async function researchCommand(args: string[]) {
  const { values } = parseArgs({
    args,
    options: {
      assets: { type: 'string', default: 'crypto,stocks,forex' },
      capital: { type: 'string', default: '100000' },
      help: { type: 'boolean', default: false },
    },
    allowPositionals: false,
  });

  if (values.help) {
    printHeader('Research Command');
    console.log(`${bold('Usage:')}  nexus research [options]\n`);
    console.log(`${bold('Options:')}`);
    console.log(`  --assets    Comma-separated asset classes (default: crypto,stocks,forex)`);
    console.log(`  --capital   Total capital (default: 100000)`);
    console.log(`  --help      Show this help\n`);
    return;
  }

  validateConfig(['XAI_API_KEY']);

  const assetClasses = (values.assets ?? 'crypto,stocks,forex').split(',').map((s) => s.trim());
  const capital = Number(values.capital);

  printHeader('Market Research');
  console.log(`  ${cyan('Assets:')}  ${assetClasses.join(', ')}`);
  console.log(`  ${cyan('Capital:')} $${capital.toLocaleString()}\n`);

  const spin = spinner('Analyzing markets with Grok...');
  const startTime = Date.now();

  try {
    const { text, usage } = await generateText({
      model: xai('grok-4-1-fast-non-reasoning'),
      system: MARKET_RESEARCH_PROMPT,
      prompt: `Analyze current market conditions for: ${assetClasses.join(', ')}.
Capital: $${capital.toLocaleString()}.
Today's date: ${new Date().toISOString().split('T')[0]}.
Generate 3-5 diverse strategy ideas.`,
    });

    const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
    spin.stop('Research complete!');

    // Try to parse and format JSON
    const jsonMatch = text.match(/\{[\s\S]*\}/);
    if (jsonMatch) {
      try {
        const data = JSON.parse(jsonMatch[0]);
        if (data.market_analysis) {
          console.log(`\n${bold('Market Analysis:')}\n${data.market_analysis}\n`);
        }
        if (data.strategy_ideas?.length) {
          console.log(`${bold('Strategy Ideas:')}\n`);
          for (const [i, idea] of data.strategy_ideas.entries()) {
            console.log(`  ${cyan(`${i + 1}.`)} ${bold(idea.name)} ${dim(`[${idea.asset_class}/${idea.type}]`)}`);
            console.log(`     ${idea.description}`);
            console.log(`     ${dim(`Rationale: ${idea.rationale}`)}\n`);
          }
        }
      } catch {
        console.log(`\n${text}`);
      }
    } else {
      console.log(`\n${text}`);
    }

    console.log(dim(`Completed in ${elapsed}s | ${usage?.totalTokens?.toLocaleString() ?? '?'} tokens`));
  } catch (error) {
    spin.stop();
    printError(error instanceof Error ? error.message : String(error));
    process.exit(1);
  }
}
