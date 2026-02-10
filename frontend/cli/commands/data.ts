import { parseArgs } from 'util';

import {
  printHeader, printError, printSuccess, printTable,
  dim, bold, cyan, spinner,
} from '../lib/output';
import { validateConfig } from '../lib/config';
import { getLonaClient } from '../../src/lib/lona/client';

export async function dataCommand(args: string[]) {
  const subcommand = args[0];

  if (!subcommand || subcommand === '--help' || subcommand === '-h') {
    printHelp();
    return;
  }

  const handlers: Record<string, (a: string[]) => Promise<void>> = {
    list: listSymbols,
    download: downloadData,
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
  printHeader('Data Commands');
  console.log(`${bold('Usage:')}  nexus data <subcommand> [options]\n`);
  console.log(`${bold('Subcommands:')}`);
  console.log(`  ${cyan('list')}       List available market data symbols`);
  console.log(`  ${cyan('download')}   Download market data from Binance to Lona\n`);
  console.log(`${bold('Examples:')}`);
  console.log(`  ${dim('nexus data list --global')}                                    List pre-loaded symbols`);
  console.log(`  ${dim('nexus data download --symbol BTCUSDT --interval 1h --start 2025-01-01 --end 2025-06-01')}\n`);
}

async function listSymbols(args: string[]) {
  const { values } = parseArgs({
    args,
    options: {
      global: { type: 'boolean', default: false },
      limit: { type: 'string', default: '50' },
    },
    allowPositionals: false,
  });

  validateConfig(['LONA_AGENT_TOKEN']);
  const client = getLonaClient();

  const isGlobal = values.global ?? false;
  const spin = spinner(`Fetching ${isGlobal ? 'global ' : ''}symbols...`);
  const symbols = await client.listSymbols(isGlobal, Number(values.limit));
  spin.stop(`Found ${symbols.length} symbols`);

  if (symbols.length === 0) {
    console.log(dim('\n  No symbols found.\n'));
    return;
  }

  printTable(
    ['ID', 'Name', 'Exchange', 'Asset Class', 'Frequencies', 'Date Range'],
    symbols.map((s) => [
      s.id.slice(0, 8) + '...',
      s.name?.slice(0, 20) ?? '-',
      s.type_metadata?.exchange ?? '-',
      s.type_metadata?.asset_class ?? '-',
      (s.frequencies ?? []).join(', ') || '-',
      s.data_range
        ? `${s.data_range.start_timestamp?.slice(0, 10) ?? '?'} to ${s.data_range.end_timestamp?.slice(0, 10) ?? '?'}`
        : '-',
    ]),
  );
  console.log();
}

async function downloadData(args: string[]) {
  const { values } = parseArgs({
    args,
    options: {
      symbol: { type: 'string' },
      interval: { type: 'string', default: '1h' },
      start: { type: 'string' },
      end: { type: 'string' },
    },
    allowPositionals: false,
  });

  if (!values.symbol || !values.start || !values.end) {
    printError('Required: --symbol <BTCUSDT> --start YYYY-MM-DD --end YYYY-MM-DD');
    process.exit(1);
  }

  validateConfig(['LONA_AGENT_TOKEN']);
  const client = getLonaClient();

  printHeader('Download Market Data');
  console.log(`  ${cyan('Symbol:')}   ${values.symbol}`);
  console.log(`  ${cyan('Interval:')} ${values.interval}`);
  console.log(`  ${cyan('Period:')}   ${values.start} to ${values.end}\n`);

  const spin = spinner('Downloading from Binance and uploading to Lona...');
  try {
    const result = await client.downloadMarketData(
      values.symbol,
      values.interval ?? '1h',
      values.start,
      values.end,
    );

    spin.stop('Download complete!');
    console.log(`\n  ${bold('Symbol ID:')} ${cyan(result.id)}`);
    console.log(`  ${bold('Name:')}      ${result.name}`);
    if (result.description) {
      console.log(`  ${bold('Info:')}      ${dim(result.description)}`);
    }
    console.log(`\n  ${dim('Use this ID for backtesting: nexus strategy backtest --data ' + result.id)}\n`);
  } catch (error) {
    spin.stop();
    printError(error instanceof Error ? error.message : String(error));
    process.exit(1);
  }
}
