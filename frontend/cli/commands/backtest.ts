import { runBacktest } from './strategy';

export async function backtestCommand(args: string[]) {
  await runBacktest(args);
}
