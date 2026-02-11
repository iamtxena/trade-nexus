import { parseArgs } from 'node:util';

import { getLonaClient } from '../../src/lib/lona/client';
import { validateConfig } from '../lib/config';
import { getLiveEngineClient } from '../lib/live-engine';
import {
  bold,
  cyan,
  dim,
  green,
  printError,
  printHeader,
  printStep,
  printSuccess,
  printTable,
  red,
  spinner,
  yellow,
} from '../lib/output';

export async function deployCommand(args: string[]) {
  const subcommand = args[0];

  if (subcommand === '--help' || subcommand === '-h') {
    printHelp();
    return;
  }

  if (subcommand === 'list') return deployList(args.slice(1));
  if (subcommand === 'stop') return deployStop(args.slice(1));
  if (subcommand === 'logs') return deployLogs(args.slice(1));

  // Default: deploy a strategy
  return deployStrategy(args);
}

function printHelp() {
  printHeader('Deploy Commands');
  console.log(`${bold('Usage:')}  nexus deploy [subcommand] [options]\n`);
  console.log(`${bold('Subcommands:')}`);
  console.log(`  ${cyan('(default)')}  Deploy a Lona strategy to paper trading`);
  console.log(`  ${cyan('list')}       List deployed strategies`);
  console.log(`  ${cyan('stop')}       Stop a running strategy`);
  console.log(`  ${cyan('logs')}       View strategy execution logs\n`);
  console.log(`${bold('Examples:')}`);
  console.log(`  ${dim('nexus deploy --strategy-id <lona-id> --capital 10000')}`);
  console.log(`  ${dim('nexus deploy list')}`);
  console.log(`  ${dim('nexus deploy stop --id <live-engine-id>')}`);
  console.log(`  ${dim('nexus deploy logs --id <live-engine-id>')}\n`);
}

async function deployStrategy(args: string[]) {
  const { values } = parseArgs({
    args,
    options: {
      'strategy-id': { type: 'string' },
      capital: { type: 'string', default: '10000' },
      asset: { type: 'string', default: 'btcusdt' },
      interval: { type: 'string', default: '1m' },
    },
    allowPositionals: false,
  });

  if (!values['strategy-id']) {
    printError('--strategy-id is required (Lona strategy ID)');
    process.exit(1);
  }

  validateConfig(['LONA_AGENT_TOKEN', 'LIVE_ENGINE_SERVICE_KEY']);
  const lona = getLonaClient();
  const engine = getLiveEngineClient();
  const strategyId = values['strategy-id'];
  const capital = Number(values.capital);

  printHeader('Deploy to Paper Trading');

  // Step 1: Get strategy from Lona
  printStep(1, 5, 'Fetching strategy from Lona...');
  const strategy = await lona.getStrategy(strategyId);
  printSuccess(`Strategy: ${strategy.name}`);

  // Step 2: Get strategy code
  printStep(2, 5, 'Fetching strategy code...');
  const pythonCode = await lona.getStrategyCode(strategyId);
  printSuccess(`Code: ${pythonCode.length} chars`);

  // Step 3: Convert Python to TypeScript
  printStep(3, 5, 'Converting Python to TypeScript via live-engine...');
  const spin = spinner('Converting code...');
  try {
    const conversion = await engine.convertCode(pythonCode, {
      context: strategy.name,
      validate: true,
    });
    spin.stop('Code converted!');

    if (conversion.validation && !conversion.validation.isValid) {
      console.log(`  ${yellow('!')} Validation issues:`);
      for (const issue of conversion.validation.issues) {
        console.log(`    - ${issue}`);
      }
    }

    // Step 4: Create paper portfolio
    printStep(4, 5, `Creating paper portfolio ($${capital.toLocaleString()})...`);
    const portfolioName = `${strategy.name} - Paper`;
    const { portfolio } = await engine.createPortfolio(portfolioName, capital);
    printSuccess(`Portfolio: ${portfolio.id}`);

    // Step 5: Create and start strategy on live-engine
    printStep(5, 5, 'Creating strategy on live-engine...');
    const deployed = await engine.createStrategy({
      name: strategy.name,
      python_code: pythonCode,
      typescript_code: conversion.conversion.typescript,
      description: `Deployed from Lona strategy ${strategyId}`,
      explanation: conversion.explanation,
      dependencies: conversion.conversion.dependencies,
      conversion_notes: conversion.conversion.notes,
      asset: values.asset,
      interval: values.interval,
      portfolio_id: portfolio.id,
    });
    printSuccess(`Strategy deployed: ${deployed.id}`);

    // Start the strategy
    await engine.updateStrategy(deployed.id, { status: 'running' });

    console.log(`\n${bold(green('Deployment Complete!'))}\n`);
    console.log(`  ${bold('Strategy ID:')}  ${cyan(deployed.id)}`);
    console.log(`  ${bold('Portfolio ID:')} ${cyan(portfolio.id)}`);
    console.log(`  ${bold('Status:')}       ${green('running')}`);
    console.log(`  ${bold('Asset:')}        ${values.asset}`);
    console.log(`  ${bold('Interval:')}     ${values.interval}`);
    console.log(`  ${bold('Capital:')}      $${capital.toLocaleString()}`);
    console.log(`\n  ${dim(`View portfolio: nexus portfolio show --id ${portfolio.id}`)}`);
    console.log(`  ${dim(`View logs:      nexus deploy logs --id ${deployed.id}`)}\n`);
  } catch (error) {
    spin.stop();
    printError(error instanceof Error ? error.message : String(error));
    process.exit(1);
  }
}

async function deployList(_args: string[]) {
  validateConfig(['LIVE_ENGINE_SERVICE_KEY']);
  const engine = getLiveEngineClient();

  const spin = spinner('Fetching deployed strategies...');
  const strategies = await engine.listStrategies();
  spin.stop(`Found ${strategies.length} strategies`);

  if (strategies.length === 0) {
    console.log(
      dim('\n  No deployed strategies. Deploy one with: nexus deploy --strategy-id <id>\n'),
    );
    return;
  }

  printTable(
    ['ID', 'Name', 'Status', 'Asset', 'Interval', 'Updated'],
    strategies.map((s) => [
      s.id,
      s.name.slice(0, 25),
      s.status === 'running' ? green(s.status) : s.status === 'stopped' ? red(s.status) : s.status,
      s.asset ?? '-',
      s.interval ?? '-',
      s.updated_at ? new Date(s.updated_at).toLocaleDateString() : '-',
    ]),
  );
  console.log();
}

async function deployStop(args: string[]) {
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

  const spin = spinner('Stopping strategy...');
  await engine.updateStrategy(values.id, { status: 'stopped' });
  spin.stop(`Strategy ${values.id} stopped`);
}

async function deployLogs(args: string[]) {
  const { values } = parseArgs({
    args,
    options: {
      id: { type: 'string' },
      limit: { type: 'string', default: '50' },
    },
    allowPositionals: false,
  });

  if (!values.id) {
    printError('--id is required');
    process.exit(1);
  }

  validateConfig(['LIVE_ENGINE_SERVICE_KEY']);
  const engine = getLiveEngineClient();

  const spin = spinner('Fetching logs...');
  const { logs, total } = await engine.getStrategyLogs(values.id, Number(values.limit));
  spin.stop(`${logs.length} logs (${total} total)`);

  if (logs.length === 0) {
    console.log(dim('\n  No logs yet.\n'));
    return;
  }

  for (const log of logs) {
    const levelColor = log.level === 'error' ? red : log.level === 'warn' ? yellow : dim;
    const time = new Date(log.created_at).toLocaleTimeString();
    console.log(`  ${dim(time)} ${levelColor(`[${log.level}]`)} ${log.message}`);
  }
  console.log();
}
