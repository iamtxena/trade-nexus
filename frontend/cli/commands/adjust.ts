import { parseArgs } from 'node:util';
import { xai } from '@ai-sdk/xai';
import { generateText } from 'ai';

import { validateConfig } from '../lib/config';
import { getLiveEngineClient } from '../lib/live-engine';
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

const ADJUSTMENT_PROMPT = `You are a senior portfolio manager reviewing live trading operations. Analyze portfolio performance, current positions, and market conditions to suggest adjustments.

For each recommendation, provide:
1. Action (stop, start, rebalance, increase, decrease)
2. Target (strategy name or portfolio)
3. Rationale (data-driven reasoning)
4. Priority (high/medium/low)

Output as JSON:
{
  "portfolio_assessment": "brief overall assessment",
  "recommendations": [
    { "action": "stop|start|rebalance|increase|decrease", "target": "strategy or portfolio name", "rationale": "why", "priority": "high|medium|low" }
  ],
  "risk_assessment": "current portfolio risk level and concerns",
  "next_review": "when to review again"
}`;

export async function adjustCommand(args: string[]) {
  const { values } = parseArgs({
    args,
    options: {
      'portfolio-id': { type: 'string' },
      help: { type: 'boolean', default: false },
    },
    allowPositionals: false,
  });

  if (values.help) {
    printHeader('Adjust Command');
    console.log(`${bold('Usage:')}  nexus adjust [options]\n`);
    console.log(`${bold('Options:')}`);
    console.log('  --portfolio-id   Portfolio to analyze (optional, analyzes all if omitted)');
    console.log('  --help           Show this help\n');
    return;
  }

  validateConfig(['LIVE_ENGINE_SERVICE_KEY', 'XAI_API_KEY']);
  const engine = getLiveEngineClient();

  printHeader('AI Portfolio Adjustment');

  const spin = spinner('Gathering portfolio and strategy data...');

  // Gather data
  let portfolioData = '';
  let strategiesData = '';

  try {
    if (values['portfolio-id']) {
      const detail = await engine.getPortfolio(values['portfolio-id']);
      portfolioData = JSON.stringify(detail, null, 2);
    } else {
      const portfolios = await engine.listPortfolios();
      const details = [];
      for (const p of portfolios.slice(0, 5)) {
        try {
          details.push(await engine.getPortfolio(p.id));
        } catch {
          details.push({
            portfolio: p,
            positions: [],
            totalValue: p.balance,
            pnl: 0,
            pnlPercent: 0,
          });
        }
      }
      portfolioData = JSON.stringify(details, null, 2);
    }
  } catch (error) {
    spin.stop();
    printError(`Failed to fetch portfolio: ${error instanceof Error ? error.message : error}`);
    process.exit(1);
  }

  try {
    const strategies = await engine.listStrategies();
    strategiesData = JSON.stringify(strategies, null, 2);
  } catch {
    strategiesData = '[]';
  }

  spin.stop('Data gathered');

  const aiSpin = spinner('AI analyzing portfolio and generating recommendations...');
  const startTime = Date.now();

  try {
    const { text, usage } = await generateText({
      model: xai('grok-4-1-fast-non-reasoning'),
      system: ADJUSTMENT_PROMPT,
      prompt: `Review these trading portfolios and strategies. Suggest adjustments.

Date: ${new Date().toISOString().split('T')[0]}

Portfolios:
${portfolioData.slice(0, 3000)}

Deployed Strategies:
${strategiesData.slice(0, 2000)}

Provide specific, actionable recommendations.`,
    });

    const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
    aiSpin.stop('Analysis complete!');

    const jsonMatch = text.match(/\{[\s\S]*\}/);
    if (jsonMatch) {
      try {
        const data = JSON.parse(jsonMatch[0]);

        if (data.portfolio_assessment) {
          console.log(`\n${bold('Assessment:')}\n  ${data.portfolio_assessment}`);
        }

        if (data.recommendations?.length) {
          console.log(`\n${bold('Recommendations:')}\n`);
          for (const [i, rec] of data.recommendations.entries()) {
            const priorityColor =
              rec.priority === 'high' ? red : rec.priority === 'medium' ? yellow : dim;
            const actionColor = rec.action === 'stop' ? red : rec.action === 'start' ? green : cyan;

            console.log(
              `  ${bold(`${i + 1}.`)} ${actionColor(rec.action.toUpperCase())} ${rec.target} ${priorityColor(`[${rec.priority}]`)}`,
            );
            console.log(`     ${dim(rec.rationale)}\n`);
          }
        } else {
          console.log(`\n  ${green('No adjustments recommended at this time.')}`);
        }

        if (data.risk_assessment) {
          console.log(`${bold('Risk Assessment:')}\n  ${data.risk_assessment}`);
        }

        if (data.next_review) {
          console.log(`\n  ${dim(`Next review: ${data.next_review}`)}`);
        }
      } catch {
        console.log(`\n${text}`);
      }
    } else {
      console.log(`\n${text}`);
    }

    console.log(
      `\n${dim(`Completed in ${elapsed}s | ${usage?.totalTokens?.toLocaleString() ?? '?'} tokens`)}`,
    );
    console.log(`${yellow('!')} These are suggestions only. Review before taking action.\n`);
  } catch (error) {
    aiSpin.stop();
    printError(error instanceof Error ? error.message : String(error));
    process.exit(1);
  }
}
