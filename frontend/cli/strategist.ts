#!/usr/bin/env bun
import { parseArgs } from 'util';

import { runStrategist } from '../src/lib/ai/strategist';

const bold = (s: string) => `\x1b[1m${s}\x1b[0m`;
const cyan = (s: string) => `\x1b[36m${s}\x1b[0m`;
const green = (s: string) => `\x1b[32m${s}\x1b[0m`;
const red = (s: string) => `\x1b[31m${s}\x1b[0m`;
const dim = (s: string) => `\x1b[2m${s}\x1b[0m`;

const { values } = parseArgs({
  args: Bun.argv.slice(2),
  options: {
    assets: { type: 'string', default: 'crypto,stocks,forex' },
    capital: { type: 'string', default: '100000' },
    'max-position': { type: 'string', default: '5' },
    'max-drawdown': { type: 'string', default: '15' },
    help: { type: 'boolean', default: false },
  },
  allowPositionals: false,
});

if (values.help) {
  console.log(`
${bold('Trade Nexus Strategist Brain')}

${bold('Usage:')}
  bun run cli/strategist.ts [options]

${bold('Options:')}
  --assets         Comma-separated asset classes (default: crypto,stocks,forex)
  --capital        Total capital to allocate (default: 100000)
  --max-position   Max % per position (default: 5)
  --max-drawdown   Max portfolio drawdown % (default: 15)
  --help           Show this help
`);
  process.exit(0);
}

const assetClasses = (values.assets ?? 'crypto,stocks,forex')
  .split(',')
  .map((s) => s.trim());
const capital = Number(values.capital);
const maxPositionPct = Number(values['max-position']);
const maxDrawdownPct = Number(values['max-drawdown']);

console.log(`
${bold(cyan('╔═══════════════════════════════════════════╗'))}
${bold(cyan('║    Trade Nexus Strategist Brain           ║'))}
${bold(cyan('╚═══════════════════════════════════════════╝'))}

${bold('Configuration:')}
  ${cyan('Assets:')}        ${assetClasses.join(', ')}
  ${cyan('Capital:')}       $${capital.toLocaleString()}
  ${cyan('Max Position:')}  ${maxPositionPct}%
  ${cyan('Max Drawdown:')} ${maxDrawdownPct}%
`);

const startTime = Date.now();

try {
  console.log(dim('Starting strategist pipeline...\n'));

  const result = await runStrategist({
    assetClasses,
    capital,
    maxPositionPct,
    maxDrawdownPct,
  });

  const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);

  // Print step summaries
  console.log(bold('\n📊 Pipeline Steps:\n'));
  for (const [i, step] of result.steps.entries()) {
    const toolNames = step.toolCalls.map((tc) => tc.toolName).join(', ');
    if (toolNames) {
      console.log(`  ${cyan(`Step ${i + 1}:`)} ${toolNames}`);
    }
    if (step.text) {
      console.log(`  ${dim(step.text.slice(0, 200))}`);
    }
  }

  // Print final result
  console.log(`\n${bold(green('═══ Final Result ═══'))}\n`);
  console.log(result.text);

  console.log(`\n${dim('─'.repeat(50))}`);
  console.log(
    `${dim(`Completed in ${elapsed}s | ${result.usage.totalTokens.toLocaleString()} tokens`)}`,
  );
} catch (error) {
  const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
  console.error(`\n${red(bold('Error:'))} ${error instanceof Error ? error.message : error}`);
  console.error(dim(`\nFailed after ${elapsed}s`));
  process.exit(1);
}
