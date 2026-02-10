// ANSI color helpers
export const bold = (s: string) => `\x1b[1m${s}\x1b[0m`;
export const dim = (s: string) => `\x1b[2m${s}\x1b[0m`;
export const red = (s: string) => `\x1b[31m${s}\x1b[0m`;
export const green = (s: string) => `\x1b[32m${s}\x1b[0m`;
export const yellow = (s: string) => `\x1b[33m${s}\x1b[0m`;
export const blue = (s: string) => `\x1b[34m${s}\x1b[0m`;
export const cyan = (s: string) => `\x1b[36m${s}\x1b[0m`;

export function printHeader(title: string) {
  const line = '═'.repeat(title.length + 6);
  console.log(`\n${bold(cyan(`╔${line}╗`))}`);
  console.log(`${bold(cyan(`║   ${title}   ║`))}`);
  console.log(`${bold(cyan(`╚${line}╝`))}\n`);
}

export function printSuccess(msg: string) {
  console.log(`${green('✓')} ${msg}`);
}

export function printError(msg: string) {
  console.error(`${red('✗')} ${msg}`);
}

export function printWarning(msg: string) {
  console.log(`${yellow('!')} ${msg}`);
}

export function printInfo(msg: string) {
  console.log(`${blue('i')} ${msg}`);
}

export function printTable(headers: string[], rows: string[][]) {
  const colWidths = headers.map((h, i) =>
    Math.max(h.length, ...rows.map((r) => (r[i] ?? '').length)),
  );

  const separator = colWidths.map((w) => '─'.repeat(w + 2)).join('┼');
  const formatRow = (row: string[]) =>
    row.map((cell, i) => ` ${(cell ?? '').padEnd(colWidths[i])} `).join('│');

  console.log(dim(`┌${separator.replaceAll('┼', '┬')}┐`));
  console.log(`│${bold(formatRow(headers))}│`);
  console.log(dim(`├${separator}┤`));
  for (const row of rows) {
    console.log(`│${formatRow(row)}│`);
  }
  console.log(dim(`└${separator.replaceAll('┼', '┴')}┘`));
}

export function printJSON(data: unknown) {
  console.log(JSON.stringify(data, null, 2));
}

export function printStep(step: number, total: number, msg: string) {
  console.log(`\n${bold(cyan(`[${step}/${total}]`))} ${msg}`);
}

export function printDivider() {
  console.log(dim('─'.repeat(60)));
}

export function spinner(msg: string) {
  const frames = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'];
  let i = 0;
  const interval = setInterval(() => {
    process.stdout.write(`\r${cyan(frames[i++ % frames.length])} ${msg}`);
  }, 80);
  return {
    stop(finalMsg?: string) {
      clearInterval(interval);
      process.stdout.write(`\r${' '.repeat(msg.length + 4)}\r`);
      if (finalMsg) printSuccess(finalMsg);
    },
  };
}
