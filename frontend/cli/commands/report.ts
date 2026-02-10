import { generateText } from 'ai';
import { xai } from '@ai-sdk/xai';
import { parseArgs } from 'util';

import {
  printHeader, printError, printSuccess, printTable, printDivider,
  dim, bold, cyan, green, red, yellow, spinner,
} from '../lib/output';
import { validateConfig } from '../lib/config';
import { getLiveEngineClient } from '../lib/live-engine';

export async function reportCommand(args: string[]) {
  const subcommand = args[0];

  if (!subcommand || subcommand === '--help' || subcommand === '-h') {
    printHelp();
    return;
  }

  const handlers: Record<string, (a: string[]) => Promise<void>> = {
    daily: dailyReport,
    strategy: strategyReport,
  };

  const handler = handlers[subcommand];
  if (!handler) {
    printError(`Unknown subcommand: ${subcommand}`);
    printHelp();
    process.exit(1);
  }

  await handler(args.slice(1));
}

function printHelp() {
  printHeader('Report Commands');
  console.log(`${bold('Usage:')}  nexus report <subcommand> [options]\n`);
  console.log(`${bold('Subcommands:')}`);
  console.log(`  ${cyan('daily')}      Generate daily trading summary`);
  console.log(`  ${cyan('strategy')}   Detailed report for one strategy\n`);
  console.log(`${bold('Examples:')}`);
  console.log(`  ${dim('nexus report daily')}`);
  console.log(`  ${dim('nexus report strategy --id <live-engine-strategy-id>')}\n`);
}

async function dailyReport(_args: string[]) {
  validateConfig(['LIVE_ENGINE_SERVICE_KEY', 'XAI_API_KEY']);
  const engine = getLiveEngineClient();

  printHeader(`Daily Report - ${new Date().toLocaleDateString()}`);

  const spin = spinner('Gathering data from all systems...');

  // Gather data
  let portfolios: Awaited<ReturnType<typeof engine.listPortfolios>> = [];
  let strategies: Awaited<ReturnType<typeof engine.listStrategies>> = [];

  try {
    portfolios = await engine.listPortfolios();
  } catch {
    // live-engine may be down
  }

  try {
    strategies = await engine.listStrategies();
  } catch {
    // live-engine may be down
  }

  spin.stop('Data gathered');

  // Summary stats
  const activeStrategies = strategies.filter((s) => s.status === 'running').length;
  const stoppedStrategies = strategies.filter((s) => s.status === 'stopped').length;

  console.log(`\n${bold('Overview:')}`);
  console.log(`  ${cyan('Portfolios:')}          ${portfolios.length}`);
  console.log(`  ${cyan('Strategies:')}          ${strategies.length} total`);
  console.log(`  ${cyan('Active strategies:')}   ${green(String(activeStrategies))}`);
  console.log(`  ${cyan('Stopped strategies:')} ${stoppedStrategies > 0 ? red(String(stoppedStrategies)) : dim('0')}`);

  // Portfolio details
  if (portfolios.length > 0) {
    console.log(`\n${bold('Portfolios:')}`);
    let totalValue = 0;
    const portfolioRows: string[][] = [];

    for (const p of portfolios) {
      try {
        const detail = await engine.getPortfolio(p.id);
        totalValue += detail.totalValue;
        const pnlStr = detail.pnl >= 0
          ? green(`+$${detail.pnl.toFixed(2)} (${detail.pnlPercent.toFixed(2)}%)`)
          : red(`-$${Math.abs(detail.pnl).toFixed(2)} (${detail.pnlPercent.toFixed(2)}%)`);
        portfolioRows.push([
          p.name?.slice(0, 20) ?? p.id.slice(0, 8),
          `$${detail.totalValue.toLocaleString()}`,
          pnlStr,
          String(detail.positions.length),
        ]);
      } catch {
        portfolioRows.push([p.name?.slice(0, 20) ?? p.id.slice(0, 8), `$${p.balance}`, dim('N/A'), '-']);
      }
    }

    printTable(['Portfolio', 'Value', 'P&L', 'Positions'], portfolioRows);
    console.log(`\n  ${bold('Total Portfolio Value:')} $${totalValue.toLocaleString()}`);
  }

  // Strategy status
  if (strategies.length > 0) {
    console.log(`\n${bold('Strategies:')}`);
    printTable(
      ['Name', 'Status', 'Asset', 'Interval'],
      strategies.map((s) => [
        s.name.slice(0, 25),
        s.status === 'running' ? green(s.status) : s.status === 'stopped' ? red(s.status) : s.status,
        s.asset ?? '-',
        s.interval ?? '-',
      ]),
    );
  }

  // AI Summary
  if (portfolios.length > 0 || strategies.length > 0) {
    const aiSpin = spinner('Generating AI summary...');
    try {
      const { text } = await generateText({
        model: xai('grok-4-1-fast-non-reasoning'),
        system: 'You are a trading operations analyst. Provide a brief daily summary of trading operations.',
        prompt: `Summarize today's trading status:
- ${portfolios.length} portfolios, ${strategies.length} strategies (${activeStrategies} active, ${stoppedStrategies} stopped)
- Date: ${new Date().toISOString().split('T')[0]}
Keep it to 3-5 sentences focusing on actionable insights.`,
      });
      aiSpin.stop('');
      console.log(`\n${bold('AI Summary:')}\n  ${text}\n`);
    } catch {
      aiSpin.stop('');
    }
  }

  printDivider();
  console.log(dim(`Report generated at ${new Date().toLocaleString()}\n`));
}

async function strategyReport(args: string[]) {
  const { values } = parseArgs({
    args,
    options: { id: { type: 'string' } },
    allowPositionals: false,
  });

  if (!values.id) {
    printError('--id is required (live-engine strategy ID)');
    process.exit(1);
  }

  validateConfig(['LIVE_ENGINE_SERVICE_KEY']);
  const engine = getLiveEngineClient();

  const spin = spinner('Fetching strategy details...');
  const strategy = await engine.getStrategy(values.id);
  spin.stop('Done');

  printHeader(`Strategy Report: ${strategy.name}`);
  console.log(`  ${bold('ID:')}       ${strategy.id}`);
  console.log(`  ${bold('Status:')}   ${strategy.status === 'running' ? green(strategy.status) : red(strategy.status)}`);
  console.log(`  ${bold('Asset:')}    ${strategy.asset}`);
  console.log(`  ${bold('Interval:')} ${strategy.interval}`);

  // Recent logs
  if (strategy.logs?.length) {
    console.log(`\n${bold('Recent Logs:')}`);
    for (const log of strategy.logs.slice(0, 20)) {
      const levelColor = log.level === 'error' ? red : log.level === 'warn' ? yellow : dim;
      const time = new Date(log.created_at).toLocaleTimeString();
      console.log(`  ${dim(time)} ${levelColor(`[${log.level}]`)} ${log.message}`);
    }
  }

  console.log();
}
