import { afterEach, describe, expect, spyOn, test } from 'bun:test';
import { EventEmitter } from 'node:events';
import { PassThrough } from 'node:stream';

import { spinner } from '../../lib/output';
import { extractStrategyIdFromOutput, runStrategyCreateCommand } from '../moltbook';

class FakeStrategyCreateProcess extends EventEmitter {
  stdout = new PassThrough();
  stderr = new PassThrough();
}

describe('moltbook strategy creation helpers', () => {
  let stdoutWriteSpy: ReturnType<typeof spyOn> | null = null;
  let consoleLogSpy: ReturnType<typeof spyOn> | null = null;

  afterEach(() => {
    stdoutWriteSpy?.mockRestore();
    consoleLogSpy?.mockRestore();
    stdoutWriteSpy = null;
    consoleLogSpy = null;
  });

  test('extracts strategy ID from ANSI-colored command output (#363)', () => {
    const strategyId = '123e4567-e89b-12d3-a456-426614174000';
    const ansiOutput = [
      '\u001b[32m✓\u001b[0m Strategy created!',
      `\u001b[1mID:\u001b[0m \u001b[36m${strategyId}\u001b[0m`,
    ].join('\n');

    expect(extractStrategyIdFromOutput(ansiOutput)).toBe(strategyId);
  });

  test('keeps spinner output responsive while strategy creation command is running (#362)', async () => {
    stdoutWriteSpy = spyOn(process.stdout, 'write').mockImplementation(() => true);
    consoleLogSpy = spyOn(console, 'log').mockImplementation(() => {});

    const strategyId = '123e4567-e89b-12d3-a456-426614174000';
    const delayedSpawn: NonNullable<
      Parameters<typeof runStrategyCreateCommand>[2]
    >['spawnCommand'] = () => {
      const child = new FakeStrategyCreateProcess();
      setTimeout(() => {
        child.stdout.write(`\u001b[1mID:\u001b[0m \u001b[36m${strategyId}\u001b[0m\n`);
        child.stdout.end();
        child.stderr.end();
        child.emit('close', 0, null);
      }, 220);
      return child;
    };

    const spin = spinner('Creating strategy on Lona (this takes ~5 min)...');
    const commandPromise = runStrategyCreateCommand('desc', 'name', {
      cwd: '.',
      spawnCommand: delayedSpawn,
    });

    await new Promise((resolve) => setTimeout(resolve, 130));

    expect(stdoutWriteSpy.mock.calls.length).toBeGreaterThan(0);

    const output = await commandPromise;
    spin.stop('Strategy created');

    expect(extractStrategyIdFromOutput(output)).toBe(strategyId);
  });
});
