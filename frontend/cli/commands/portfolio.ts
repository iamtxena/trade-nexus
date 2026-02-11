import { parseArgs } from 'node:util';

import { validateConfig } from '../lib/config';
import { getLiveEngineClient } from '../lib/live-engine';
import {
  bold,
  cyan,
  dim,
  green,
  printError,
  printHeader,
  printTable,
  red,
  spinner,
} from '../lib/output';

export async function portfolioCommand(args: string[]) {
  const subcommand = args[0];

  if (!subcommand || subcommand === '--help' || subcommand === '-h') {
    printHelp();
    return;
  }

  const handlers: Record<string, (a: string[]) => Promise<void>> = {
    list: listPortfolios,
    show: showPortfolio,
    trade: executeTrade,
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
  printHeader('Portfolio Commands');
  console.log(`${bold('Usage:')}  nexus portfolio <subcommand> [options]\n`);
  console.log(`${bold('Subcommands:')}`);
  console.log(`  ${cyan('list')}    List all paper portfolios`);
  console.log(`  ${cyan('show')}    Show portfolio details + positions`);
  console.log(`  ${cyan('trade')}   Execute a paper trade\n`);
  console.log(`${bold('Examples:')}`);
  console.log(`  ${dim('nexus portfolio list')}`);
  console.log(`  ${dim('nexus portfolio show --id <portfolioId>')}`);
  console.log(
    `  ${dim('nexus portfolio trade --portfolio-id <id> --symbol BTCUSDT --side buy --quantity 0.1')}\n`,
  );
}

async function listPortfolios(_args: string[]) {
  validateConfig(['LIVE_ENGINE_SERVICE_KEY']);
  const engine = getLiveEngineClient();

  const spin = spinner('Fetching portfolios...');
  const portfolios = await engine.listPortfolios();
  spin.stop(`Found ${portfolios.length} portfolios`);

  if (portfolios.length === 0) {
    console.log(dim('\n  No portfolios. Create one via: nexus deploy --strategy-id <id>\n'));
    return;
  }

  printTable(
    ['ID', 'Name', 'Balance', 'Created'],
    portfolios.map((p) => [
      p.id,
      p.name?.slice(0, 25) ?? '-',
      `$${p.balance?.toLocaleString() ?? '0'}`,
      p.created_at ? new Date(p.created_at).toLocaleDateString() : '-',
    ]),
  );
  console.log();
}

async function showPortfolio(args: string[]) {
  const { values } = parseArgs({
    args,
    options: { id: { type: 'string' } },
    allowPositionals: false,
  });

  if (!values.id) {
    printError('--id is required');
    process.exit(1);
  }

  validateConfig(['LIVE_ENGINE_SERVICE_KEY']);
  const engine = getLiveEngineClient();

  const spin = spinner('Fetching portfolio...');
  const data = await engine.getPortfolio(values.id);
  spin.stop('Done');

  printHeader(`Portfolio: ${data.portfolio.name ?? values.id}`);
  console.log(`  ${bold('ID:')}          ${data.portfolio.id}`);
  console.log(`  ${bold('Cash:')}        $${data.portfolio.balance.toLocaleString()}`);
  console.log(`  ${bold('Total Value:')} $${data.totalValue.toLocaleString()}`);

  const pnlColor = data.pnl >= 0 ? green : red;
  console.log(
    `  ${bold('P&L:')}         ${pnlColor(`$${data.pnl.toFixed(2)} (${data.pnlPercent.toFixed(2)}%)`)}`,
  );

  if (data.positions.length > 0) {
    console.log(`\n${bold('Positions:')}`);
    printTable(
      ['Symbol', 'Qty', 'Avg Price', 'Current', 'Unrealized P&L'],
      data.positions.map((p) => {
        const pnlStr =
          p.unrealizedPnl >= 0
            ? green(`+$${p.unrealizedPnl.toFixed(2)}`)
            : red(`-$${Math.abs(p.unrealizedPnl).toFixed(2)}`);
        return [
          p.asset,
          p.amount.toString(),
          `$${p.avgPrice.toFixed(2)}`,
          `$${p.currentPrice.toFixed(2)}`,
          pnlStr,
        ];
      }),
    );
  } else {
    console.log(`\n  ${dim('No open positions')}`);
  }
  console.log();
}

async function executeTrade(args: string[]) {
  const { values } = parseArgs({
    args,
    options: {
      'portfolio-id': { type: 'string' },
      symbol: { type: 'string' },
      side: { type: 'string' },
      quantity: { type: 'string' },
      type: { type: 'string', default: 'market' },
      price: { type: 'string' },
    },
    allowPositionals: false,
  });

  if (!values['portfolio-id'] || !values.symbol || !values.side || !values.quantity) {
    printError(
      'Required: --portfolio-id <id> --symbol <BTCUSDT> --side <buy|sell> --quantity <amount>',
    );
    process.exit(1);
  }

  validateConfig(['LIVE_ENGINE_SERVICE_KEY']);
  const engine = getLiveEngineClient();

  const side = values.side as 'buy' | 'sell';
  const type = (values.type ?? 'market') as 'market' | 'limit';

  printHeader('Execute Trade');
  console.log(`  ${cyan('Portfolio:')} ${values['portfolio-id']}`);
  console.log(`  ${cyan('Symbol:')}    ${values.symbol}`);
  console.log(`  ${cyan('Side:')}      ${side === 'buy' ? green(side) : red(side)}`);
  console.log(`  ${cyan('Quantity:')}  ${values.quantity}`);
  console.log(`  ${cyan('Type:')}      ${type}`);
  if (values.price) console.log(`  ${cyan('Price:')}     $${values.price}`);
  console.log();

  const spin = spinner('Executing trade...');
  try {
    const result = await engine.executeTrade(
      values['portfolio-id'],
      values.symbol, // passed as `asset` to live-engine
      side,
      Number(values.quantity), // passed as `amount` to live-engine
      type,
      values.price ? Number(values.price) : undefined,
    );

    spin.stop('Trade executed!');
    console.log(`\n  ${bold('New Balance:')} $${result.newBalance.toLocaleString()}\n`);
  } catch (error) {
    spin.stop();
    printError(error instanceof Error ? error.message : String(error));
    process.exit(1);
  }
}
