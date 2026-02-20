import { strategyCommand } from './strategy';

export async function backtestCommand(args: string[]) {
  await strategyCommand(['backtest', ...args]);
}
