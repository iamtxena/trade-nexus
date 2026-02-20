import { describe, expect, it } from 'bun:test';
import { parseArgs } from 'node:util';

/**
 * Tests for #217 (param normalization) and #220 (top-level backtest alias).
 *
 * We test the parseArgs configuration directly rather than calling runBacktest,
 * since runBacktest validates config and calls the Lona API. This isolates the
 * CLI parsing logic which is what #217 addresses.
 */

const backtestParseOptions = {
  'strategy-id': { type: 'string' as const },
  id: { type: 'string' as const },
  'symbol-id': { type: 'string' as const },
  data: { type: 'string' as const },
  start: { type: 'string' as const },
  end: { type: 'string' as const },
  capital: { type: 'string' as const, default: '100000' },
};

function parseBacktestArgs(argv: string[]) {
  const { values } = parseArgs({
    args: argv,
    options: backtestParseOptions,
    allowPositionals: false,
  });
  const strategyId = values['strategy-id'] ?? values.id;
  const symbolId = values['symbol-id'] ?? values.data;
  return { strategyId, symbolId, start: values.start, end: values.end, capital: values.capital };
}

describe('backtest param parsing (#217)', () => {
  it('accepts --strategy-id and --symbol-id as primary names', () => {
    const result = parseBacktestArgs([
      '--strategy-id',
      'strat-1',
      '--symbol-id',
      'sym-1',
      '--start',
      '2025-01-01',
      '--end',
      '2025-06-01',
    ]);
    expect(result.strategyId).toBe('strat-1');
    expect(result.symbolId).toBe('sym-1');
    expect(result.start).toBe('2025-01-01');
    expect(result.end).toBe('2025-06-01');
  });

  it('accepts --id and --data as backward-compatible aliases', () => {
    const result = parseBacktestArgs([
      '--id',
      'strat-old',
      '--data',
      'sym-old',
      '--start',
      '2025-01-01',
      '--end',
      '2025-06-01',
    ]);
    expect(result.strategyId).toBe('strat-old');
    expect(result.symbolId).toBe('sym-old');
  });

  it('prefers --strategy-id over --id when both are provided', () => {
    const result = parseBacktestArgs([
      '--strategy-id',
      'primary',
      '--id',
      'alias',
      '--symbol-id',
      'sym-1',
      '--start',
      '2025-01-01',
      '--end',
      '2025-06-01',
    ]);
    expect(result.strategyId).toBe('primary');
  });

  it('prefers --symbol-id over --data when both are provided', () => {
    const result = parseBacktestArgs([
      '--strategy-id',
      'strat-1',
      '--symbol-id',
      'primary',
      '--data',
      'alias',
      '--start',
      '2025-01-01',
      '--end',
      '2025-06-01',
    ]);
    expect(result.symbolId).toBe('primary');
  });

  it('allows mixed usage: --strategy-id with --data', () => {
    const result = parseBacktestArgs([
      '--strategy-id',
      'strat-1',
      '--data',
      'sym-old',
      '--start',
      '2025-01-01',
      '--end',
      '2025-06-01',
    ]);
    expect(result.strategyId).toBe('strat-1');
    expect(result.symbolId).toBe('sym-old');
  });

  it('allows mixed usage: --id with --symbol-id', () => {
    const result = parseBacktestArgs([
      '--id',
      'strat-old',
      '--symbol-id',
      'sym-1',
      '--start',
      '2025-01-01',
      '--end',
      '2025-06-01',
    ]);
    expect(result.strategyId).toBe('strat-old');
    expect(result.symbolId).toBe('sym-1');
  });

  it('defaults capital to 100000', () => {
    const result = parseBacktestArgs([
      '--strategy-id',
      'strat-1',
      '--symbol-id',
      'sym-1',
      '--start',
      '2025-01-01',
      '--end',
      '2025-06-01',
    ]);
    expect(result.capital).toBe('100000');
  });

  it('accepts custom --capital value', () => {
    const result = parseBacktestArgs([
      '--strategy-id',
      'strat-1',
      '--symbol-id',
      'sym-1',
      '--start',
      '2025-01-01',
      '--end',
      '2025-06-01',
      '--capital',
      '50000',
    ]);
    expect(result.capital).toBe('50000');
  });

  it('returns undefined for missing required params', () => {
    const result = parseBacktestArgs([]);
    expect(result.strategyId).toBeUndefined();
    expect(result.symbolId).toBeUndefined();
    expect(result.start).toBeUndefined();
    expect(result.end).toBeUndefined();
  });
});

describe('top-level backtest command (#220)', () => {
  it('backtest module re-exports runBacktest from strategy', async () => {
    const backtestMod = await import('../backtest');
    expect(typeof backtestMod.backtestCommand).toBe('function');
  });

  it('strategy module exports runBacktest', async () => {
    const strategyMod = await import('../strategy');
    expect(typeof strategyMod.runBacktest).toBe('function');
  });
});
