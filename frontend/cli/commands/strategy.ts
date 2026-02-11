import { parseArgs } from 'node:util';

import { getLonaClient } from '../../src/lib/lona/client';
import { validateConfig } from '../lib/config';
import { bold, cyan, dim, printError, printHeader, printTable, spinner } from '../lib/output';

export async function strategyCommand(args: string[]) {
  const subcommand = args[0];

  if (!subcommand || subcommand === '--help' || subcommand === '-h') {
    printHelp();
    return;
  }

  const handlers: Record<string, (a: string[]) => Promise<void>> = {
    list: listStrategies,
    create: createStrategy,
    get: getStrategy,
    code: getStrategyCode,
    backtest: runBacktest,
    score: scoreStrategies,
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
  printHeader('Strategy Commands');
  console.log(`${bold('Usage:')}  nexus strategy <subcommand> [options]\n`);
  console.log(`${bold('Subcommands:')}`);
  console.log(`  ${cyan('list')}       List all strategies on Lona`);
  console.log(`  ${cyan('create')}     Create a strategy from description`);
  console.log(`  ${cyan('get')}        Get strategy details`);
  console.log(`  ${cyan('code')}       Get strategy Python code`);
  console.log(`  ${cyan('backtest')}   Run a backtest`);
  console.log(`  ${cyan('score')}      Score strategies from backtest results\n`);
}

async function listStrategies(_args: string[]) {
  validateConfig(['LONA_AGENT_TOKEN']);
  const client = getLonaClient();

  const spin = spinner('Fetching strategies...');
  const strategies = await client.listStrategies();
  spin.stop(`Found ${strategies.length} strategies`);

  if (strategies.length === 0) {
    console.log(dim('\n  No strategies found. Create one with: nexus strategy create\n'));
    return;
  }

  printTable(
    ['ID', 'Name', 'Version', 'Language', 'Created'],
    strategies.map((s) => [
      s.id,
      s.name.slice(0, 30),
      s.version ?? '-',
      s.language ?? 'python',
      s.created_at ? new Date(s.created_at).toLocaleDateString() : '-',
    ]),
  );
}

async function createStrategy(args: string[]) {
  const { values } = parseArgs({
    args,
    options: {
      description: { type: 'string' },
      name: { type: 'string' },
      provider: { type: 'string', default: 'xai' },
    },
    allowPositionals: false,
  });

  if (!values.description) {
    printError('--description is required');
    console.log(
      dim('  Example: nexus strategy create --description "RSI mean reversion on BTCUSDT 1h"'),
    );
    process.exit(1);
  }

  validateConfig(['LONA_AGENT_TOKEN']);
  const client = getLonaClient();

  printHeader('Create Strategy');
  console.log(`  ${cyan('Description:')} ${values.description}`);
  if (values.name) console.log(`  ${cyan('Name:')}        ${values.name}`);
  console.log(`  ${cyan('Provider:')}    ${values.provider}\n`);

  const spin = spinner('Generating strategy via Lona AI...');
  try {
    const result = await client.createStrategyFromDescription(
      values.description,
      values.name,
      values.provider,
    );
    spin.stop('Strategy created!');

    console.log(`\n  ${bold('Strategy ID:')} ${cyan(result.strategyId)}`);
    console.log(`  ${bold('Name:')}        ${result.name}`);
    console.log(`  ${bold('Explanation:')}\n${dim(result.explanation.slice(0, 500))}`);
    console.log(
      `\n  ${dim(`Code: ${result.code.length} chars (use 'nexus strategy code --id ${result.strategyId}' to view)`)}\n`,
    );
  } catch (error) {
    spin.stop();
    printError(error instanceof Error ? error.message : String(error));
    process.exit(1);
  }
}

async function getStrategy(args: string[]) {
  const { values } = parseArgs({
    args,
    options: { id: { type: 'string' } },
    allowPositionals: false,
  });

  if (!values.id) {
    printError('--id is required');
    process.exit(1);
  }

  validateConfig(['LONA_AGENT_TOKEN']);
  const client = getLonaClient();

  const spin = spinner('Fetching strategy...');
  const strategy = await client.getStrategy(values.id);
  spin.stop('Done');

  printHeader(`Strategy: ${strategy.name}`);
  console.log(`  ${bold('ID:')}       ${strategy.id}`);
  console.log(`  ${bold('Name:')}     ${strategy.name}`);
  console.log(`  ${bold('Version:')}  ${strategy.version ?? '-'}`);
  console.log(`  ${bold('Language:')} ${strategy.language ?? 'python'}`);
  console.log(`  ${bold('Created:')}  ${strategy.created_at}`);
  console.log(`  ${bold('Updated:')}  ${strategy.updated_at}\n`);
}

async function getStrategyCode(args: string[]) {
  const { values } = parseArgs({
    args,
    options: { id: { type: 'string' } },
    allowPositionals: false,
  });

  if (!values.id) {
    printError('--id is required');
    process.exit(1);
  }

  validateConfig(['LONA_AGENT_TOKEN']);
  const client = getLonaClient();

  const spin = spinner('Fetching code...');
  const code = await client.getStrategyCode(values.id);
  spin.stop('Done');

  console.log(`\n${code}\n`);
}

async function runBacktest(args: string[]) {
  const { values } = parseArgs({
    args,
    options: {
      id: { type: 'string' },
      data: { type: 'string' },
      start: { type: 'string' },
      end: { type: 'string' },
      capital: { type: 'string', default: '100000' },
    },
    allowPositionals: false,
  });

  if (!values.id || !values.data || !values.start || !values.end) {
    printError('Required: --id <strategyId> --data <dataId> --start YYYY-MM-DD --end YYYY-MM-DD');
    process.exit(1);
  }

  validateConfig(['LONA_AGENT_TOKEN']);
  const client = getLonaClient();

  printHeader('Backtest');
  console.log(`  ${cyan('Strategy:')} ${values.id}`);
  console.log(`  ${cyan('Data:')}     ${values.data}`);
  console.log(`  ${cyan('Period:')}   ${values.start} to ${values.end}`);
  console.log(`  ${cyan('Capital:')}  $${Number(values.capital).toLocaleString()}\n`);

  const spin = spinner('Running backtest...');
  try {
    const { report_id } = await client.runBacktest({
      strategy_id: values.id,
      data_ids: values.data.split(','),
      start_date: values.start,
      end_date: values.end,
      simulation_parameters: {
        initial_cash: Number(values.capital),
        commission_schema: { commission: 0.001, leverage: 1 },
        buy_on_close: true,
      },
    });

    spin.stop(`Backtest started (report: ${report_id})`);

    const pollSpin = spinner('Waiting for results...');
    const report = await client.waitForReport(report_id);
    pollSpin.stop('Backtest complete!');

    if (report.total_stats) {
      const stats = report.total_stats as Record<string, number>;
      console.log(`\n${bold('Results:')}`);
      printTable(
        ['Metric', 'Value'],
        Object.entries(stats).map(([k, v]) => [
          k,
          typeof v === 'number' ? v.toFixed(4) : String(v),
        ]),
      );
    }

    console.log(`\n  ${dim(`Report ID: ${report.id}`)}\n`);
  } catch (error) {
    spin.stop();
    printError(error instanceof Error ? error.message : String(error));
    process.exit(1);
  }
}

async function scoreStrategies(args: string[]) {
  const { values } = parseArgs({
    args,
    options: {
      ids: { type: 'string' },
    },
    allowPositionals: false,
  });

  if (!values.ids) {
    printError('--ids is required (comma-separated report IDs)');
    process.exit(1);
  }

  validateConfig(['LONA_AGENT_TOKEN']);
  const client = getLonaClient();
  const reportIds = values.ids.split(',').map((s) => s.trim());

  printHeader('Score Strategies');

  const spin = spinner(`Fetching ${reportIds.length} reports...`);
  const results: Array<{
    reportId: string;
    name: string;
    score: number;
    metrics: Record<string, number>;
  }> = [];

  for (const reportId of reportIds) {
    try {
      const report = await client.getReport(reportId);
      const stats = (report.total_stats ?? {}) as Record<string, number>;

      const sharpe = stats.sharpe_ratio ?? 0;
      const maxDd = stats.max_drawdown ?? 0;
      const winRate = stats.win_rate ?? 0;
      const totalReturn = stats.total_return ?? 0;

      const sharpeScore = Math.min(Math.max(sharpe / 3.0, 0), 1);
      const drawdownScore = Math.min(Math.max(1 - Math.abs(maxDd) / 50, 0), 1);
      const winScore = Math.min(Math.max(winRate > 1 ? winRate / 100 : winRate, 0), 1);
      const returnScore = Math.min(Math.max(totalReturn / 100, 0), 1);

      const score = 0.4 * sharpeScore + 0.25 * drawdownScore + 0.2 * winScore + 0.15 * returnScore;

      results.push({
        reportId,
        name: report.strategy_id ?? reportId.slice(0, 8),
        score: Math.round(score * 10000) / 10000,
        metrics: { sharpe, maxDd, winRate, totalReturn },
      });
    } catch (error) {
      results.push({
        reportId,
        name: 'ERROR',
        score: 0,
        metrics: { sharpe: 0, maxDd: 0, winRate: 0, totalReturn: 0 },
      });
    }
  }

  spin.stop('Scoring complete!');

  results.sort((a, b) => b.score - a.score);

  printTable(
    ['Rank', 'Report', 'Score', 'Sharpe', 'Max DD', 'Win Rate', 'Return'],
    results.map((r, i) => [
      `#${i + 1}`,
      r.reportId,
      r.score.toFixed(4),
      r.metrics.sharpe.toFixed(2),
      `${r.metrics.maxDd.toFixed(2)}%`,
      `${(r.metrics.winRate > 1 ? r.metrics.winRate : r.metrics.winRate * 100).toFixed(1)}%`,
      `${r.metrics.totalReturn.toFixed(2)}%`,
    ]),
  );
  console.log();
}
