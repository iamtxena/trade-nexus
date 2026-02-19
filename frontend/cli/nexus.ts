#!/usr/bin/env bun
import { getLonaClient } from '../src/lib/lona/client';
import {
  LIVE_ENGINE_URL,
  LONA_GATEWAY_URL,
  getLiveEngineConfig,
  getLonaConfig,
} from './lib/config';
import { getLiveEngineClient } from './lib/live-engine';
import {
  bold,
  cyan,
  dim,
  green,
  printError,
  printHeader,
  printInfo,
  printWarning,
  red,
  spinner,
  yellow,
} from './lib/output';

// Command registry
const COMMANDS: Record<
  string,
  { description: string; handler: (args: string[]) => Promise<void> }
> = {
  status: {
    description: 'Health check all systems (Lona Gateway + live-engine)',
    handler: statusCommand,
  },
  register: {
    description: 'Register with Lona Gateway and get API token',
    handler: registerCommand,
  },
  research: {
    description: 'AI market research and strategy ideas',
    handler: lazyLoad('research'),
  },
  strategy: {
    description: 'Strategy management (list, create, backtest, score)',
    handler: lazyLoad('strategy'),
  },
  data: {
    description: 'Market data management (list symbols, download)',
    handler: lazyLoad('data'),
  },
  deploy: {
    description: 'Deploy strategies to paper trading on live-engine',
    handler: lazyLoad('deploy'),
  },
  portfolio: {
    description: 'Portfolio management (list, show, trade)',
    handler: lazyLoad('portfolio'),
  },
  news: {
    description: 'AI news and sentiment analysis',
    handler: lazyLoad('news'),
  },
  report: {
    description: 'Generate daily or strategy reports',
    handler: lazyLoad('report'),
  },
  adjust: {
    description: 'AI-driven portfolio adjustment suggestions',
    handler: lazyLoad('adjust'),
  },
  pipeline: {
    description: 'Run full automated pipeline (research → deploy)',
    handler: lazyLoad('pipeline'),
  },
  validation: {
    description: 'Validation lifecycle (create, list, get, review, render, replay)',
    handler: lazyLoad('validation'),
  },
};

function lazyLoad(command: string): (args: string[]) => Promise<void> {
  return async (args: string[]) => {
    const mod = await import(`./commands/${command}`);
    const handlerName = `${command}Command`;
    if (typeof mod[handlerName] !== 'function') {
      printError(`Command module '${command}' does not export '${handlerName}'`);
      process.exit(1);
    }
    await mod[handlerName](args);
  };
}

function printHelp() {
  printHeader('Trade Nexus CLI');
  console.log(`${bold('Usage:')}  nexus <command> [options]\n`);
  console.log(`${bold('Commands:')}`);

  const maxLen = Math.max(...Object.keys(COMMANDS).map((k) => k.length));
  for (const [name, cmd] of Object.entries(COMMANDS)) {
    console.log(`  ${cyan(name.padEnd(maxLen + 2))} ${cmd.description}`);
  }

  console.log(`\n${bold('Examples:')}`);
  console.log(`  ${dim('nexus status')}                              Check system health`);
  console.log(`  ${dim('nexus register')}                            Register with Lona`);
  console.log(`  ${dim('nexus research --assets crypto,stocks')}     Research markets`);
  console.log(`  ${dim('nexus strategy list')}                       List strategies`);
  console.log(`  ${dim('nexus strategy create --description "..."')} Create strategy`);
  console.log(`  ${dim('nexus data list --global')}                  List global symbols`);
  console.log(`  ${dim('nexus deploy --strategy-id <id>')}           Deploy to paper trading`);
  console.log(`  ${dim('nexus portfolio list')}                      List portfolios`);
  console.log(`  ${dim('nexus news --assets crypto')}                Sentiment analysis`);
  console.log(`  ${dim('nexus report daily')}                        Daily summary`);
  console.log(`  ${dim('nexus validation create --input file.json')} Validation lifecycle`);
  console.log(`  ${dim('nexus pipeline --assets crypto')}            Full automated pipeline`);
  console.log();
}

async function statusCommand(_args: string[]) {
  printHeader('System Status');

  // Check Lona Gateway
  const lonaConfig = getLonaConfig();
  process.stdout.write(`  Lona Gateway (${dim(LONA_GATEWAY_URL)}) ... `);
  try {
    const response = await fetch(LONA_GATEWAY_URL, {
      method: 'GET',
      signal: AbortSignal.timeout(5000),
    });
    if (response.ok || response.status < 500) {
      console.log(green('UP'));
    } else {
      console.log(red(`DOWN (${response.status})`));
    }
  } catch {
    console.log(red('DOWN (unreachable)'));
  }

  // Check live-engine
  const leConfig = getLiveEngineConfig();
  process.stdout.write(`  live-engine  (${dim(LIVE_ENGINE_URL)}) ... `);
  const leClient = getLiveEngineClient();
  const leUp = await leClient.ping();
  console.log(leUp ? green('UP') : red('DOWN'));

  // Auth status
  console.log(`\n${bold('Auth:')}`);
  console.log(`  Lona token:        ${lonaConfig.token ? green('configured') : yellow('missing')}`);
  console.log(
    `  Lona reg secret:   ${lonaConfig.registrationSecret ? green('configured') : yellow('missing')}`,
  );
  console.log(
    `  live-engine key:   ${leConfig.serviceKey ? green('configured') : yellow('missing')}`,
  );
  console.log(
    `  XAI API key:       ${process.env.XAI_API_KEY ? green('configured') : yellow('missing')}`,
  );
  console.log();
}

async function registerCommand(_args: string[]) {
  printHeader('Lona Gateway Registration');

  const lonaConfig = getLonaConfig();
  const client = getLonaClient();

  try {
    let result: import('../src/lib/lona/types').LonaRegistrationResponse;
    if (lonaConfig.registrationSecret) {
      // Secret-based registration (existing flow)
      const spin = spinner('Registering with Lona Gateway...');
      try {
        result = await client.register();
        spin.stop('Registered successfully!');
      } catch (error) {
        spin.stop();
        throw error;
      }
    } else {
      // Invite code fallback (zero-config)
      printInfo('No registration secret found, using invite code flow...');
      const inviteSpin = spinner('Requesting invite code...');
      let invite_code: string;
      try {
        const inviteResult = await client.requestInvite();
        invite_code = inviteResult.invite_code;
        inviteSpin.stop(`Got invite code: ${dim(invite_code)}`);
      } catch (error) {
        inviteSpin.stop();
        throw error;
      }

      const regSpin = spinner('Registering with invite code...');
      try {
        result = await client.registerWithInviteCode(invite_code);
        regSpin.stop('Registered successfully!');
      } catch (error) {
        regSpin.stop();
        throw error;
      }
    }

    console.log(`\n  ${bold('Token:')}       ${dim(`${result.token.slice(0, 20)}...`)}`);
    console.log(`  ${bold('Partner ID:')} ${result.partner_id}`);
    console.log(`  ${bold('Expires:')}    ${result.expires_at}`);
    console.log(`\n${bold('Next step:')} Add this to your ${cyan('.env.local')}:`);
    console.log(`  ${dim(`LONA_AGENT_TOKEN=${result.token}`)}\n`);
  } catch (error) {
    printError(error instanceof Error ? error.message : String(error));
    process.exit(1);
  }
}

// Main
const args = Bun.argv.slice(2);
const command = args[0];

if (!command || command === '--help' || command === '-h') {
  printHelp();
  process.exit(0);
}

if (command === '--version' || command === '-v') {
  console.log('nexus v0.1.0');
  process.exit(0);
}

const cmd = COMMANDS[command];
if (!cmd) {
  printError(`Unknown command: ${command}`);
  printWarning(`Run ${cyan('nexus --help')} to see available commands`);
  process.exit(1);
}

try {
  await cmd.handler(args.slice(1));
} catch (error) {
  printError(error instanceof Error ? error.message : String(error));
  process.exit(1);
}
