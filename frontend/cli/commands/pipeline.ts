import { parseArgs } from 'node:util';
import { xai } from '@ai-sdk/xai';
import { generateText } from 'ai';

import { getLonaClient } from '../../src/lib/lona/client';
import type { LonaReport } from '../../src/lib/lona/types';
import { validateConfig } from '../lib/config';
import { getLiveEngineClient } from '../lib/live-engine';
import {
  bold,
  cyan,
  dim,
  green,
  printDivider,
  printError,
  printHeader,
  printStep,
  printSuccess,
  printTable,
  red,
  spinner,
  yellow,
} from '../lib/output';

const RESEARCH_PROMPT = `You are an elite quantitative market analyst. Analyze market conditions and generate strategy ideas.

For each asset class, assess market regime, key trends, and specific trade setups.

Output as JSON:
{
  "market_analysis": "comprehensive analysis",
  "strategy_ideas": [
    { "name": "Strategy Name", "asset_class": "crypto|stocks|forex", "type": "trend|mean_reversion|volatility|arbitrage", "description": "detailed Backtrader strategy with entry/exit rules, indicators, and timeframe", "symbol": "BTCUSDT", "rationale": "why" }
  ]
}`;

interface StrategyIdea {
  name: string;
  asset_class: string;
  type: string;
  description: string;
  symbol?: string;
  rationale: string;
}

interface PipelineResult {
  strategyId: string;
  name: string;
  reportId?: string;
  score: number;
  metrics?: Record<string, number>;
  deployedId?: string;
  portfolioId?: string;
}

export async function pipelineCommand(args: string[]) {
  const { values } = parseArgs({
    args,
    options: {
      assets: { type: 'string', default: 'crypto' },
      capital: { type: 'string', default: '50000' },
      top: { type: 'string', default: '3' },
      help: { type: 'boolean', default: false },
      'skip-deploy': { type: 'boolean', default: false },
    },
    allowPositionals: false,
  });

  if (values.help) {
    printHeader('Pipeline Command');
    console.log(`${bold('Usage:')}  nexus pipeline [options]\n`);
    console.log(`${bold('Options:')}`);
    console.log('  --assets       Comma-separated asset classes (default: crypto)');
    console.log('  --capital      Total capital (default: 50000)');
    console.log('  --top          Number of top strategies to deploy (default: 3)');
    console.log('  --skip-deploy  Skip deployment to live-engine');
    console.log('  --help         Show this help\n');
    return;
  }

  const requiredVars = ['XAI_API_KEY', 'LONA_AGENT_TOKEN'];
  if (!values['skip-deploy']) {
    requiredVars.push('LIVE_ENGINE_SERVICE_KEY');
  }
  validateConfig(requiredVars);

  const assetClasses = (values.assets ?? 'crypto').split(',').map((s) => s.trim());
  const capital = Number(values.capital);
  const topN = Number(values.top);
  const pipelineStart = Date.now();

  printHeader('Full Automated Pipeline');
  console.log(`  ${cyan('Assets:')}  ${assetClasses.join(', ')}`);
  console.log(`  ${cyan('Capital:')} $${capital.toLocaleString()}`);
  console.log(`  ${cyan('Top N:')}   ${topN}`);
  console.log(
    `  ${cyan('Deploy:')}  ${values['skip-deploy'] ? yellow('skipped') : green('enabled')}\n`,
  );

  const lona = getLonaClient();
  const results: PipelineResult[] = [];

  // ── Step 1: Research ───────────────────────────────────
  printStep(1, 7, 'Researching markets with Grok...');
  let ideas: StrategyIdea[] = [];

  try {
    const { text } = await generateText({
      model: xai('grok-4-1-fast-non-reasoning'),
      system: RESEARCH_PROMPT,
      prompt: `Analyze current market conditions for: ${assetClasses.join(', ')}.
Capital: $${capital.toLocaleString()}.
Date: ${new Date().toISOString().split('T')[0]}.
Generate 3-5 diverse, codeable Backtrader strategy ideas. For each, include the specific symbol to trade (e.g., BTCUSDT for crypto).`,
    });

    const jsonMatch = text.match(/\{[\s\S]*\}/);
    if (jsonMatch) {
      const parsed = JSON.parse(jsonMatch[0]);
      ideas = parsed.strategy_ideas ?? [];
    }

    if (ideas.length === 0) {
      printError('No strategy ideas generated. Try different assets.');
      process.exit(1);
    }

    printSuccess(`Generated ${ideas.length} strategy ideas`);
    for (const idea of ideas) {
      console.log(`    ${dim(`- ${idea.name} [${idea.asset_class}/${idea.type}]`)}`);
    }
  } catch (error) {
    printError(`Research failed: ${error instanceof Error ? error.message : error}`);
    process.exit(1);
  }

  // ── Step 2: Create strategies ──────────────────────────
  printStep(2, 7, 'Creating strategies on Lona...');
  const createdStrategies: Array<{ id: string; name: string; idea: StrategyIdea }> = [];

  for (const idea of ideas) {
    const spin = spinner(`Creating: ${idea.name}...`);
    try {
      const result = await lona.createStrategyFromDescription(idea.description, idea.name, 'xai');
      createdStrategies.push({ id: result.strategyId, name: result.name, idea });
      spin.stop(`Created: ${result.name} (${result.strategyId})`);
    } catch (error) {
      spin.stop();
      console.log(
        `    ${red('!')} Failed to create ${idea.name}: ${error instanceof Error ? error.message : error}`,
      );
    }
  }

  if (createdStrategies.length === 0) {
    printError('No strategies created successfully.');
    process.exit(1);
  }

  printSuccess(`${createdStrategies.length}/${ideas.length} strategies created`);

  // ── Step 3: Download market data ───────────────────────
  printStep(3, 7, 'Downloading market data...');
  const dataMap = new Map<string, string>(); // symbol → dataId

  const endDate = new Date().toISOString().split('T')[0];
  const startDate = new Date(Date.now() - 180 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];

  // Deduplicate symbols
  const symbols = [...new Set(createdStrategies.map((s) => s.idea.symbol ?? 'BTCUSDT'))];

  for (const symbol of symbols) {
    const spin = spinner(`Downloading ${symbol}...`);
    try {
      // Auto-delete existing symbol to prevent name conflicts on re-runs
      const expectedName = `${symbol}_1h_${startDate.replace(/-/g, '')}_${endDate.replace(/-/g, '')}`;
      const existing = await lona.findSymbolByName(expectedName);
      if (existing) {
        await lona.deleteSymbol(existing.id);
      }
      const result = await lona.downloadMarketData(symbol, '1h', startDate, endDate);
      dataMap.set(symbol, result.id);
      spin.stop(`${symbol}: ${result.id}`);
    } catch (error) {
      spin.stop();
      console.log(
        `    ${red('!')} Failed ${symbol}: ${error instanceof Error ? error.message : error}`,
      );
    }
  }

  if (dataMap.size === 0) {
    printError('No market data downloaded. Check Binance connectivity.');
    process.exit(1);
  }

  printSuccess(`Downloaded data for ${dataMap.size} symbols`);

  // ── Step 4: Backtest ───────────────────────────────────
  printStep(4, 7, 'Backtesting strategies...');

  for (const strategy of createdStrategies) {
    const symbol = strategy.idea.symbol ?? 'BTCUSDT';
    const dataId = dataMap.get(symbol);

    if (!dataId) {
      console.log(`    ${yellow('!')} Skipping ${strategy.name}: no data for ${symbol}`);
      results.push({ strategyId: strategy.id, name: strategy.name, score: 0 });
      continue;
    }

    const spin = spinner(`Backtesting: ${strategy.name}...`);
    try {
      const { report_id } = await lona.runBacktest({
        strategy_id: strategy.id,
        data_ids: [dataId],
        start_date: startDate,
        end_date: endDate,
        simulation_parameters: {
          initial_cash: capital,
          commission_schema: { commission: 0.001, leverage: 1 },
          buy_on_close: true,
        },
      });

      const report: LonaReport = await lona.waitForReport(report_id);
      const stats = (report.total_stats ?? {}) as Record<string, number>;

      results.push({
        strategyId: strategy.id,
        name: strategy.name,
        reportId: report.id,
        score: 0,
        metrics: stats,
      });

      spin.stop(
        `${strategy.name}: Sharpe ${(stats.sharpe_ratio ?? 0).toFixed(2)}, Return ${(stats.total_return ?? 0).toFixed(2)}%`,
      );
    } catch (error) {
      spin.stop();
      console.log(
        `    ${red('!')} Backtest failed for ${strategy.name}: ${error instanceof Error ? error.message : error}`,
      );
      results.push({ strategyId: strategy.id, name: strategy.name, score: 0 });
    }
  }

  // ── Step 5: Score and rank ─────────────────────────────
  printStep(5, 7, 'Scoring and ranking strategies...');

  for (const r of results) {
    if (!r.metrics) continue;
    const sharpe = r.metrics.sharpe_ratio ?? 0;
    const maxDd = r.metrics.max_drawdown ?? 0;
    const winRate = r.metrics.win_rate ?? 0;
    const totalReturn = r.metrics.total_return ?? 0;

    const sharpeScore = Math.min(Math.max(sharpe / 3.0, 0), 1);
    const drawdownScore = Math.min(Math.max(1 - Math.abs(maxDd) / 50, 0), 1);
    const winScore = Math.min(Math.max(winRate > 1 ? winRate / 100 : winRate, 0), 1);
    const returnScore = Math.min(Math.max(totalReturn / 100, 0), 1);

    r.score =
      Math.round(
        (0.4 * sharpeScore + 0.25 * drawdownScore + 0.2 * winScore + 0.15 * returnScore) * 10000,
      ) / 10000;
  }

  results.sort((a, b) => b.score - a.score);

  printTable(
    ['Rank', 'Strategy', 'Score', 'Sharpe', 'Return', 'Max DD', 'Win Rate'],
    results.map((r, i) => [
      `#${i + 1}`,
      r.name.slice(0, 25),
      r.score.toFixed(4),
      (r.metrics?.sharpe_ratio ?? 0).toFixed(2),
      `${(r.metrics?.total_return ?? 0).toFixed(2)}%`,
      `${(r.metrics?.max_drawdown ?? 0).toFixed(2)}%`,
      `${((r.metrics?.win_rate ?? 0) > 1 ? (r.metrics?.win_rate ?? 0) : (r.metrics?.win_rate ?? 0) * 100).toFixed(1)}%`,
    ]),
  );

  // ── Step 6: Deploy top strategies ──────────────────────
  const topStrategies = results.filter((r) => r.score > 0.3).slice(0, topN);

  if (values['skip-deploy'] || topStrategies.length === 0) {
    if (topStrategies.length === 0) {
      printStep(6, 7, dim('No strategies scored above 0.3 threshold, skipping deployment'));
    } else {
      printStep(6, 7, dim('Deployment skipped (--skip-deploy)'));
    }
  } else {
    printStep(6, 7, `Deploying top ${topStrategies.length} strategies to paper trading...`);
    const engine = getLiveEngineClient();

    for (const strategy of topStrategies) {
      const spin = spinner(`Deploying: ${strategy.name}...`);
      try {
        // Get code
        const pythonCode = await lona.getStrategyCode(strategy.strategyId);

        // Convert
        const conversion = await engine.convertCode(pythonCode, {
          context: strategy.name,
          validate: true,
        });

        // Create portfolio
        const capitalPerStrategy = Math.floor(capital / topStrategies.length);
        const { portfolio } = await engine.createPortfolio(
          `${strategy.name} - Paper`,
          capitalPerStrategy,
        );

        // Deploy
        const deployed = await engine.createStrategy({
          name: strategy.name,
          python_code: pythonCode,
          typescript_code: conversion.conversion.typescript,
          description: `Pipeline-deployed from Lona ${strategy.strategyId}`,
          dependencies: conversion.conversion.dependencies,
          asset: 'btcusdt',
          interval: '1m',
          portfolio_id: portfolio.id,
        });

        await engine.updateStrategy(deployed.id, { status: 'running' });

        strategy.deployedId = deployed.id;
        strategy.portfolioId = portfolio.id;

        spin.stop(`Deployed: ${strategy.name} → Portfolio ${portfolio.id}`);
      } catch (error) {
        spin.stop();
        console.log(
          `    ${red('!')} Deploy failed for ${strategy.name}: ${error instanceof Error ? error.message : error}`,
        );
      }
    }
  }

  // ── Step 7: Summary ────────────────────────────────────
  printStep(7, 7, 'Pipeline complete!');
  const elapsed = ((Date.now() - pipelineStart) / 1000).toFixed(1);

  console.log(`\n${bold(green('═══ Pipeline Summary ═══'))}\n`);

  const deployed = results.filter((r) => r.deployedId);
  console.log(`  ${cyan('Strategies created:')}  ${createdStrategies.length}`);
  console.log(`  ${cyan('Backtested:')}          ${results.filter((r) => r.metrics).length}`);
  console.log(`  ${cyan('Above threshold:')}     ${topStrategies.length}`);
  console.log(`  ${cyan('Deployed:')}            ${deployed.length}`);

  if (deployed.length > 0) {
    console.log(`\n${bold('Deployed Strategies:')}`);
    printTable(
      ['Strategy', 'Score', 'Portfolio ID', 'Strategy ID'],
      deployed.map((r) => [
        r.name.slice(0, 20),
        r.score.toFixed(4),
        r.portfolioId ?? '-',
        r.deployedId ?? '-',
      ]),
    );

    console.log(`\n${bold('Next steps:')}`);
    console.log(`  ${dim('nexus portfolio list')}     View all portfolios`);
    console.log(`  ${dim('nexus deploy list')}        View deployed strategies`);
    console.log(`  ${dim('nexus report daily')}       Generate daily report`);
    console.log(`  ${dim(`nexus news --assets ${assetClasses.join(',')}`)} Check market news`);
  }

  printDivider();
  console.log(dim(`Pipeline completed in ${elapsed}s\n`));
}
