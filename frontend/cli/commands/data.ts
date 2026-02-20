import { writeFileSync } from 'node:fs';
import { parseArgs } from 'node:util';

import { LonaClientError, getLonaClient } from '../../src/lib/lona/client';
import type { OhlcDataPoint } from '../../src/lib/lona/types';
import { validateConfig } from '../lib/config';
import {
  bold,
  cyan,
  dim,
  printError,
  printHeader,
  printSuccess,
  printTable,
  spinner,
} from '../lib/output';

export async function dataCommand(args: string[]) {
  const subcommand = args[0];

  if (!subcommand || subcommand === '--help' || subcommand === '-h') {
    printHelp();
    return;
  }

  const handlers: Record<string, (a: string[]) => Promise<void>> = {
    list: listSymbols,
    download: downloadData,
    export: exportSymbolData,
    delete: deleteSymbol,
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
  console.log(`  ${cyan('download')}   Download market data from Binance to Lona`);
  console.log(`  ${cyan('export')}     Export symbol OHLC data as JSON or CSV`);
  console.log(`  ${cyan('delete')}     Delete a symbol by ID\n`);
  console.log(`${bold('Examples:')}`);
  console.log(
    `  ${dim('nexus data list --global')}                                    List pre-loaded symbols`,
  );
  console.log(
    `  ${dim('nexus data download --symbol BTCUSDT --interval 1h --start 2025-01-01 --end 2025-06-01')}`,
  );
  console.log(
    `  ${dim('nexus data download --symbol BTCUSDT --interval 1h --start 2025-01-01 --end 2025-06-01 --force')}`,
  );
  console.log(`  ${dim('nexus data export --id <symbol-id> --format json')}`);
  console.log(`  ${dim('nexus data export --id <symbol-id> --format csv --output /tmp/data.csv')}`);
  console.log(`  ${dim('nexus data delete --id <symbol-id>')}\n`);
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
      s.id,
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
      force: { type: 'boolean', default: false },
    },
    allowPositionals: false,
  });

  if (!values.symbol || !values.start || !values.end) {
    printError('Required: --symbol <BTCUSDT> --start YYYY-MM-DD --end YYYY-MM-DD');
    process.exit(1);
  }

  validateConfig(['LONA_AGENT_TOKEN']);
  const client = getLonaClient();
  const interval = values.interval ?? '1h';

  printHeader('Download Market Data');
  console.log(`  ${cyan('Symbol:')}   ${values.symbol}`);
  console.log(`  ${cyan('Interval:')} ${interval}`);
  console.log(`  ${cyan('Period:')}   ${values.start} to ${values.end}`);
  if (values.force) console.log(`  ${cyan('Force:')}    enabled`);
  console.log();

  // If --force, delete existing symbol with same name
  if (values.force) {
    const expectedName = `${values.symbol}_${interval}_${values.start.replace(/-/g, '')}_${values.end.replace(/-/g, '')}`;
    const existing = await client.findSymbolByName(expectedName);
    if (existing) {
      const delSpin = spinner(`Deleting existing symbol ${expectedName}...`);
      try {
        await client.deleteSymbol(existing.id);
        delSpin.stop(`Deleted ${expectedName}`);
      } catch (error) {
        delSpin.stop();
        printError(
          `Failed to delete existing symbol: ${error instanceof Error ? error.message : String(error)}`,
        );
        process.exit(1);
      }
    }
  }

  const spin = spinner('Downloading from Binance and uploading to Lona...');
  try {
    const result = await client.downloadMarketData(
      values.symbol,
      interval,
      values.start,
      values.end,
    );

    spin.stop('Download complete!');
    console.log(`\n  ${bold('Symbol ID:')} ${cyan(result.id)}`);
    console.log(`  ${bold('Name:')}      ${result.name}`);
    if (result.description) {
      console.log(`  ${bold('Info:')}      ${dim(result.description)}`);
    }
    console.log(
      `\n  ${dim(`Use this ID for backtesting: nexus strategy backtest --data ${result.id}`)}\n`,
    );
  } catch (error) {
    spin.stop();
    if (error instanceof LonaClientError) {
      const msg = error.message;
      const isBinanceError =
        msg.includes('Binance') || msg.includes('klines') || msg.includes('candle');
      if (error.statusCode === 404 && isBinanceError) {
        printError(
          `Symbol not found on Binance. Ensure '${values.symbol}' is a valid Binance symbol, verify the date range, or try a shorter period.`,
        );
      } else if (error.statusCode === 404) {
        printError(msg);
      } else if (error.statusCode === 400 || msg.includes('not found on Binance')) {
        printError(msg);
        console.log(
          dim(
            '  Tip: Check the symbol name (e.g. BTCUSDT, ETHUSDT) and ensure the interval is valid (1m, 5m, 1h, 1d).',
          ),
        );
      } else {
        printError(msg);
      }
    } else {
      printError(error instanceof Error ? error.message : String(error));
    }
    process.exit(1);
  }
}

async function exportSymbolData(args: string[]) {
  const { values } = parseArgs({
    args,
    options: {
      id: { type: 'string' },
      format: { type: 'string', default: 'json' },
      output: { type: 'string' },
    },
    allowPositionals: false,
  });

  if (!values.id) {
    printError('--id is required (symbol ID from "nexus data list")');
    process.exit(1);
  }

  const format = values.format ?? 'json';
  if (format !== 'json' && format !== 'csv') {
    printError('--format must be "json" or "csv"');
    process.exit(1);
  }

  validateConfig(['LONA_AGENT_TOKEN']);
  const client = getLonaClient();

  const spin = spinner(`Fetching OHLC data for symbol ${values.id}...`);
  try {
    const data = await client.getSymbolData(values.id);
    spin.stop(`Fetched ${data.length} data points`);

    const content = format === 'csv' ? ohlcToCsv(data) : JSON.stringify(data, null, 2);

    if (values.output) {
      writeFileSync(values.output, content, 'utf-8');
      printSuccess(
        `Data written to ${values.output} (${data.length} rows, ${format.toUpperCase()})`,
      );
    } else {
      console.log(content);
    }
  } catch (error) {
    spin.stop();
    if (error instanceof LonaClientError && error.statusCode === 404) {
      printError(error.message);
    } else {
      printError(error instanceof Error ? error.message : String(error));
    }
    process.exit(1);
  }
}

function ohlcToCsv(data: OhlcDataPoint[]): string {
  const rows = ['timestamp,open,high,low,close,volume'];
  for (const d of data) {
    rows.push(`${d.timestamp},${d.open},${d.high},${d.low},${d.close},${d.volume}`);
  }
  return rows.join('\n');
}

async function deleteSymbol(args: string[]) {
  const { values } = parseArgs({
    args,
    options: {
      id: { type: 'string' },
    },
    allowPositionals: false,
  });

  if (!values.id) {
    printError('--id is required (symbol ID from "nexus data list")');
    process.exit(1);
  }

  validateConfig(['LONA_AGENT_TOKEN']);
  const client = getLonaClient();

  const spin = spinner(`Deleting symbol ${values.id}...`);
  try {
    await client.deleteSymbol(values.id);
    spin.stop(`Symbol ${values.id} deleted`);
  } catch (error) {
    spin.stop();
    printError(error instanceof Error ? error.message : String(error));
    process.exit(1);
  }
}
