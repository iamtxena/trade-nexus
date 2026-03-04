import { afterEach, beforeEach, describe, expect, mock, spyOn, test } from 'bun:test';

const originalFetch = globalThis.fetch;
const originalExit = process.exit;
const originalEnv = { ...process.env };

describe('subcommand --help / -h flags', () => {
  let consoleLogSpy: ReturnType<typeof spyOn>;
  let consoleErrorSpy: ReturnType<typeof spyOn>;
  let stdoutWriteSpy: ReturnType<typeof spyOn>;

  beforeEach(() => {
    process.env = { ...originalEnv };
    consoleLogSpy = spyOn(console, 'log').mockImplementation(() => {});
    consoleErrorSpy = spyOn(console, 'error').mockImplementation(() => {});
    stdoutWriteSpy = spyOn(process.stdout, 'write').mockImplementation(() => true);
    process.exit = mock((code?: number) => {
      throw new Error(`process.exit(${code})`);
    }) as unknown as typeof process.exit;
    // Prevent any real fetch calls
    globalThis.fetch = mock(() => {
      throw new Error('fetch should not be called in help tests');
    }) as unknown as typeof fetch;
  });

  afterEach(() => {
    consoleLogSpy.mockRestore();
    consoleErrorSpy.mockRestore();
    stdoutWriteSpy.mockRestore();
    globalThis.fetch = originalFetch;
    process.exit = originalExit;
    process.env = { ...originalEnv };
  });

  function getLogOutput(): string {
    return consoleLogSpy.mock.calls.map(([line]: unknown[]) => String(line)).join('\n');
  }

  // ── strategy subcommands ──

  test('strategy list --help prints usage', async () => {
    const { strategyCommand } = await import('../strategy');
    await strategyCommand(['list', '--help']);
    expect(getLogOutput()).toContain('Usage:');
  });

  test('strategy list -h prints usage', async () => {
    const { strategyCommand } = await import('../strategy');
    await strategyCommand(['list', '-h']);
    expect(getLogOutput()).toContain('Usage:');
  });

  test('strategy create --help prints usage and flags', async () => {
    const { strategyCommand } = await import('../strategy');
    await strategyCommand(['create', '--help']);
    const output = getLogOutput();
    expect(output).toContain('Usage:');
    expect(output).toContain('--description');
  });

  test('strategy backtest --help prints usage and flags', async () => {
    const { strategyCommand } = await import('../strategy');
    await strategyCommand(['backtest', '--help']);
    const output = getLogOutput();
    expect(output).toContain('Usage:');
    expect(output).toContain('--strategy-id');
  });

  test('strategy get --help prints usage', async () => {
    const { strategyCommand } = await import('../strategy');
    await strategyCommand(['get', '--help']);
    expect(getLogOutput()).toContain('Usage:');
  });

  test('strategy code --help prints usage', async () => {
    const { strategyCommand } = await import('../strategy');
    await strategyCommand(['code', '--help']);
    expect(getLogOutput()).toContain('Usage:');
  });

  test('strategy score --help prints usage', async () => {
    const { strategyCommand } = await import('../strategy');
    await strategyCommand(['score', '--help']);
    expect(getLogOutput()).toContain('Usage:');
  });

  // ── data subcommands ──

  test('data list --help prints usage', async () => {
    const { dataCommand } = await import('../data');
    await dataCommand(['list', '--help']);
    const output = getLogOutput();
    expect(output).toContain('Usage:');
    expect(output).toContain('--global');
  });

  test('data download -h prints usage', async () => {
    const { dataCommand } = await import('../data');
    await dataCommand(['download', '-h']);
    const output = getLogOutput();
    expect(output).toContain('Usage:');
    expect(output).toContain('--symbol');
  });

  test('data export --help prints usage', async () => {
    const { dataCommand } = await import('../data');
    await dataCommand(['export', '--help']);
    expect(getLogOutput()).toContain('Usage:');
  });

  test('data delete --help prints usage', async () => {
    const { dataCommand } = await import('../data');
    await dataCommand(['delete', '--help']);
    expect(getLogOutput()).toContain('Usage:');
  });

  // ── deploy subcommands ──

  test('deploy --help prints usage', async () => {
    const { deployCommand } = await import('../deploy');
    await deployCommand(['--help']);
    const output = getLogOutput();
    expect(output).toContain('Deploy Commands');
  });

  test('deploy list --help prints usage', async () => {
    const { deployCommand } = await import('../deploy');
    await deployCommand(['list', '--help']);
    expect(getLogOutput()).toContain('Usage:');
  });

  test('deploy stop --help prints usage', async () => {
    const { deployCommand } = await import('../deploy');
    await deployCommand(['stop', '--help']);
    expect(getLogOutput()).toContain('Usage:');
  });

  test('deploy logs --help prints usage and --limit flag', async () => {
    const { deployCommand } = await import('../deploy');
    await deployCommand(['logs', '--help']);
    const output = getLogOutput();
    expect(output).toContain('Usage:');
    expect(output).toContain('--limit');
  });

  // ── portfolio subcommands ──

  test('portfolio list --help prints usage', async () => {
    const { portfolioCommand } = await import('../portfolio');
    await portfolioCommand(['list', '--help']);
    expect(getLogOutput()).toContain('Usage:');
  });

  test('portfolio show -h prints usage', async () => {
    const { portfolioCommand } = await import('../portfolio');
    await portfolioCommand(['show', '-h']);
    expect(getLogOutput()).toContain('Usage:');
  });

  test('portfolio trade --help prints flags', async () => {
    const { portfolioCommand } = await import('../portfolio');
    await portfolioCommand(['trade', '--help']);
    const output = getLogOutput();
    expect(output).toContain('--portfolio-id');
    expect(output).toContain('--symbol');
  });

  // ── report subcommands ──

  test('report get --help prints usage and flags', async () => {
    const { reportCommand } = await import('../report');
    await reportCommand(['get', '--help']);
    const output = getLogOutput();
    expect(output).toContain('Usage:');
    expect(output).toContain('--full');
    expect(output).toContain('--timeline');
  });

  test('report daily -h prints usage', async () => {
    const { reportCommand } = await import('../report');
    await reportCommand(['daily', '-h']);
    expect(getLogOutput()).toContain('Usage:');
  });

  test('report strategy --help prints usage', async () => {
    const { reportCommand } = await import('../report');
    await reportCommand(['strategy', '--help']);
    expect(getLogOutput()).toContain('Usage:');
  });

  // ── single-command files ──

  test('research --help prints usage', async () => {
    const { researchCommand } = await import('../research');
    await researchCommand(['--help']);
    const output = getLogOutput();
    expect(output).toContain('Research Command');
    expect(output).toContain('--assets');
  });

  test('research -h prints usage', async () => {
    const { researchCommand } = await import('../research');
    await researchCommand(['-h']);
    expect(getLogOutput()).toContain('Research Command');
  });

  test('news --help prints usage', async () => {
    const { newsCommand } = await import('../news');
    await newsCommand(['--help']);
    const output = getLogOutput();
    expect(output).toContain('News Command');
    expect(output).toContain('--assets');
  });

  test('adjust --help prints usage', async () => {
    const { adjustCommand } = await import('../adjust');
    await adjustCommand(['--help']);
    const output = getLogOutput();
    expect(output).toContain('Adjust Command');
    expect(output).toContain('--portfolio-id');
  });

  test('pipeline --help prints usage', async () => {
    const { pipelineCommand } = await import('../pipeline');
    await pipelineCommand(['--help']);
    const output = getLogOutput();
    expect(output).toContain('Pipeline Command');
    expect(output).toContain('--skip-deploy');
  });

  test('pipeline -h prints usage', async () => {
    const { pipelineCommand } = await import('../pipeline');
    await pipelineCommand(['-h']);
    expect(getLogOutput()).toContain('Pipeline Command');
  });

  test('moltbook replicate --help prints usage', async () => {
    const { moltbookCommand } = await import('../moltbook');
    await moltbookCommand(['replicate', '--help']);
    const output = getLogOutput();
    expect(output).toContain('Usage:');
    expect(output).toContain('--post-id');
  });
});

describe('strict mode rejects unknown flags', () => {
  let consoleLogSpy: ReturnType<typeof spyOn>;
  let consoleErrorSpy: ReturnType<typeof spyOn>;
  let stdoutWriteSpy: ReturnType<typeof spyOn>;

  beforeEach(() => {
    process.env = { ...originalEnv };
    consoleLogSpy = spyOn(console, 'log').mockImplementation(() => {});
    consoleErrorSpy = spyOn(console, 'error').mockImplementation(() => {});
    stdoutWriteSpy = spyOn(process.stdout, 'write').mockImplementation(() => true);
    process.exit = mock((code?: number) => {
      throw new Error(`process.exit(${code})`);
    }) as unknown as typeof process.exit;
    globalThis.fetch = mock(() => {
      throw new Error('fetch should not be called');
    }) as unknown as typeof fetch;
  });

  afterEach(() => {
    consoleLogSpy.mockRestore();
    consoleErrorSpy.mockRestore();
    stdoutWriteSpy.mockRestore();
    globalThis.fetch = originalFetch;
    process.exit = originalExit;
    process.env = { ...originalEnv };
  });

  test('strategy list rejects --unknown-flag', async () => {
    const { strategyCommand } = await import('../strategy');
    await expect(strategyCommand(['list', '--unknown-flag'])).rejects.toThrow(/Unknown option/);
  });

  test('data list rejects --bogus', async () => {
    const { dataCommand } = await import('../data');
    await expect(dataCommand(['list', '--bogus'])).rejects.toThrow(/Unknown option/);
  });

  test('deploy list rejects --foo', async () => {
    const { deployCommand } = await import('../deploy');
    await expect(deployCommand(['list', '--foo'])).rejects.toThrow(/Unknown option/);
  });

  test('deploy stop rejects --foo', async () => {
    const { deployCommand } = await import('../deploy');
    await expect(deployCommand(['stop', '--foo'])).rejects.toThrow(/Unknown option/);
  });

  test('portfolio list rejects --extra', async () => {
    const { portfolioCommand } = await import('../portfolio');
    await expect(portfolioCommand(['list', '--extra'])).rejects.toThrow(/Unknown option/);
  });

  test('portfolio show rejects --extra', async () => {
    const { portfolioCommand } = await import('../portfolio');
    await expect(portfolioCommand(['show', '--extra'])).rejects.toThrow(/Unknown option/);
  });

  test('report daily rejects --nope', async () => {
    const { reportCommand } = await import('../report');
    await expect(reportCommand(['daily', '--nope'])).rejects.toThrow(/Unknown option/);
  });

  test('report get rejects --nope', async () => {
    const { reportCommand } = await import('../report');
    await expect(reportCommand(['get', '--nope'])).rejects.toThrow(/Unknown option/);
  });

  test('research rejects --invalid', async () => {
    const { researchCommand } = await import('../research');
    await expect(researchCommand(['--invalid'])).rejects.toThrow(/Unknown option/);
  });
});
