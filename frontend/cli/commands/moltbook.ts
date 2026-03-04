import { spawn } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { join } from 'node:path';
import { parseArgs } from 'node:util';

import { validateConfig } from '../lib/config';
import {
  bold,
  cyan,
  dim,
  green,
  printError,
  printHeader,
  printSuccess,
  printWarning,
  spinner,
  wantsHelp,
} from '../lib/output';

const WORKSPACE_DIR = process.env.WORKSPACE_PATH || join(homedir(), 'lona', 'workspace');
const MOLTBOOK_CREDENTIALS =
  process.env.MOLTBOOK_CREDENTIALS || join(WORKSPACE_DIR, 'moltbook-credentials.json');

const STRATEGY_KEYWORDS = ['ema', 'rsi', 'macd', 'strategy', 'backtest', 'trading', 'indicator'];

type MoltbookCredentials = {
  api_key?: string;
};

type MoltbookPost = {
  id: string;
  title: string;
  content: string;
  author: {
    name: string;
  };
};

function asTrimmedString(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

function parseMoltbookPost(value: unknown): MoltbookPost | null {
  if (!value || typeof value !== 'object') return null;
  const record = value as Record<string, unknown>;

  const id = asTrimmedString(record.id);
  const title = asTrimmedString(record.title);
  const content = asTrimmedString(record.content);

  const authorValue = record.author;
  if (!authorValue || typeof authorValue !== 'object') return null;
  const authorRecord = authorValue as Record<string, unknown>;
  const authorName = asTrimmedString(authorRecord.name);

  if (!id || !title || !content || !authorName) return null;

  return {
    id,
    title,
    content,
    author: { name: authorName },
  };
}

function includesStrategyKeyword(post: MoltbookPost): boolean {
  const text = `${post.title} ${post.content}`.toLowerCase();
  return STRATEGY_KEYWORDS.some((keyword) => text.includes(keyword));
}

function sanitizeStrategySegment(value: string): string {
  return value
    .replace(/[^a-zA-Z0-9]/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_+|_+$/g, '');
}

type StrategyCreateSpawnResult = {
  stdout: NodeJS.ReadableStream | null;
  stderr: NodeJS.ReadableStream | null;
  on(event: 'error', listener: (error: Error) => void): StrategyCreateSpawnResult;
  on(
    event: 'close',
    listener: (code: number | null, signal: NodeJS.Signals | null) => void,
  ): StrategyCreateSpawnResult;
};

type StrategyCreateSpawn = (
  command: string,
  args: string[],
  options: {
    cwd: string;
    stdio: 'pipe';
    timeout: number;
  },
) => StrategyCreateSpawnResult;

function stripAnsi(value: string): string {
  let sanitized = '';
  let i = 0;

  while (i < value.length) {
    if (value[i] !== '\u001b') {
      sanitized += value[i];
      i += 1;
      continue;
    }

    i += 1;
    if (value[i] !== '[') {
      continue;
    }

    i += 1;
    while (i < value.length) {
      const code = value.charCodeAt(i);
      if (code >= 0x40 && code <= 0x7e) {
        i += 1;
        break;
      }
      i += 1;
    }
  }

  return sanitized;
}

function toTextChunk(chunk: unknown): string {
  if (typeof chunk === 'string') return chunk;
  if (chunk instanceof Uint8Array) return Buffer.from(chunk).toString('utf-8');
  return String(chunk);
}

export function extractStrategyIdFromOutput(commandOutput: string): string | null {
  const output = stripAnsi(commandOutput);
  const strategyIdMatch = output.match(/\bID:\s*([a-f0-9-]+)/i);
  return strategyIdMatch ? strategyIdMatch[1] : null;
}

export async function runStrategyCreateCommand(
  strategyDesc: string,
  strategyName: string,
  options?: {
    cwd?: string;
    spawnCommand?: StrategyCreateSpawn;
  },
): Promise<string> {
  const cwd = options?.cwd ?? '.';
  const spawnCommand = options?.spawnCommand ?? spawn;

  return await new Promise((resolve, reject) => {
    let child: StrategyCreateSpawnResult;
    try {
      child = spawnCommand(
        'bun',
        [
          'run',
          'nexus',
          'strategy',
          'create',
          '--description',
          strategyDesc,
          '--name',
          strategyName,
        ],
        {
          cwd,
          stdio: 'pipe',
          timeout: 310000,
        },
      );
    } catch (error) {
      reject(error);
      return;
    }

    let commandOutput = '';
    child.stdout?.on('data', (chunk) => {
      commandOutput += toTextChunk(chunk);
    });
    child.stderr?.on('data', (chunk) => {
      commandOutput += toTextChunk(chunk);
    });

    child.on('error', reject);
    child.on('close', (code, signal) => {
      if (code === 0) {
        resolve(commandOutput);
        return;
      }

      const signalPart = signal ? ` (signal ${signal})` : '';
      const fallback = `Command failed with exit code ${code ?? 'unknown'}${signalPart}`;
      reject(new Error(commandOutput || fallback));
    });
  });
}

export async function moltbookCommand(args: string[]) {
  const subcommand = args[0];

  if (!subcommand || subcommand === '--help' || subcommand === '-h') {
    printHelp();
    return;
  }

  const handlers: Record<string, (a: string[]) => Promise<void>> = {
    replicate: replicateStrategy,
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
  printHeader('Moltbook Commands');
  console.log(`${bold('Usage:')}  nexus moltbook <subcommand> [options]\n`);
  console.log(`${bold('Subcommands:')}`);
  console.log(`  ${cyan('replicate')}  Replicate a Moltbook strategy on Lona`);
  console.log();
  console.log(`${bold('Examples:')}`);
  console.log('  nexus moltbook replicate --post-id abc123');
  console.log('  nexus moltbook replicate --author claw-n --strategy-name EMA33');
}

async function replicateStrategy(args: string[]) {
  if (wantsHelp(args)) {
    console.log(`${bold('Usage:')} nexus moltbook replicate [options]\n`);
    console.log(`${bold('Options:')}`);
    console.log(`  ${dim('--post-id')}        Moltbook post ID to replicate`);
    console.log(`  ${dim('--author')}         Filter by author name`);
    console.log(`  ${dim('--strategy-name')}  Filter by strategy name\n`);
    console.log(`${bold('Examples:')}`);
    console.log('  nexus moltbook replicate --post-id 57bc7211-20a0-4c86-8b23-89288bc72f84');
    console.log('  nexus moltbook replicate --author claw-n');
    return;
  }
  const { values } = parseArgs({
    args,
    options: {
      'post-id': { type: 'string' },
      author: { type: 'string' },
      'strategy-name': { type: 'string' },
    },
    allowPositionals: false,
    strict: true,
  });

  validateConfig(['LONA_AGENT_TOKEN']);

  printHeader('Moltbook Strategy Replication');

  // Load Moltbook credentials
  if (!existsSync(MOLTBOOK_CREDENTIALS)) {
    printError(`Moltbook credentials not found: ${MOLTBOOK_CREDENTIALS}`);
    process.exit(1);
  }

  const credentials = JSON.parse(
    readFileSync(MOLTBOOK_CREDENTIALS, 'utf-8'),
  ) as MoltbookCredentials;
  const apiKey = credentials.api_key;

  if (!apiKey) {
    printError('API key not found in credentials file');
    process.exit(1);
  }

  let postId = values['post-id'];
  const authorFilter = values.author?.trim().toLowerCase();
  const strategyNameFilter = values['strategy-name']?.trim().toLowerCase();

  // If no post-id, search for strategies
  if (!postId) {
    const searchSpinner = spinner('Searching for strategies on Moltbook...');

    try {
      const response = await fetch(
        'https://www.moltbook.com/api/v1/posts?submolt=trading&sort=hot&limit=10',
        {
          headers: { Authorization: `Bearer ${apiKey}` },
        },
      );

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = (await response.json()) as { posts?: unknown };
      const parsedPosts = Array.isArray(data.posts)
        ? data.posts
            .map((candidate) => parseMoltbookPost(candidate))
            .filter((candidate): candidate is MoltbookPost => candidate !== null)
        : [];

      const strategyPosts = parsedPosts.filter((post) => {
        if (!includesStrategyKeyword(post)) return false;
        if (authorFilter && !post.author.name.toLowerCase().includes(authorFilter)) return false;
        if (
          strategyNameFilter &&
          !`${post.title} ${post.content}`.toLowerCase().includes(strategyNameFilter)
        ) {
          return false;
        }
        return true;
      });

      searchSpinner.stop(`Found ${strategyPosts.length} strategy posts`);

      if (strategyPosts.length === 0) {
        printWarning('No strategy posts found');
        return;
      }

      // Show options
      console.log(`\n${bold('Available strategies:')}`);
      strategyPosts.forEach((post, i) => {
        console.log(`  ${cyan(`${i + 1}.`)} ${post.title} by ${post.author.name}`);
      });

      // For now, take the first one
      postId = strategyPosts[0].id;
      console.log(`\n${dim('Using:')} ${strategyPosts[0].title}\n`);
    } catch (error) {
      searchSpinner.stop();
      printError(
        `Failed to fetch posts: ${error instanceof Error ? error.message : 'Unknown error'}`,
      );
      process.exit(1);
    }
  }

  // Fetch post details
  const fetchSpinner = spinner('Fetching strategy details...');

  let post: MoltbookPost;
  try {
    const response = await fetch(`https://www.moltbook.com/api/v1/posts/${postId}`, {
      headers: { Authorization: `Bearer ${apiKey}` },
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = (await response.json()) as { post?: unknown };
    const parsedPost = parseMoltbookPost(data.post);
    if (!parsedPost) {
      throw new Error('Moltbook API returned an invalid post payload');
    }
    post = parsedPost;
    fetchSpinner.stop('Strategy details fetched');
  } catch (error) {
    fetchSpinner.stop();
    printError(`Failed to fetch post: ${error instanceof Error ? error.message : 'Unknown error'}`);
    process.exit(1);
  }

  if (authorFilter && !post.author.name.toLowerCase().includes(authorFilter)) {
    printWarning(
      `Fetched post author "${post.author.name}" does not match --author filter "${values.author}"`,
    );
    return;
  }

  if (
    strategyNameFilter &&
    !`${post.title} ${post.content}`.toLowerCase().includes(strategyNameFilter)
  ) {
    printWarning(
      `Fetched post "${post.title}" does not match --strategy-name filter "${values['strategy-name']}"`,
    );
    return;
  }

  console.log(`\n${bold('Strategy:')} ${post.title}`);
  console.log(`${bold('Author:')} ${post.author.name}`);
  console.log(`${dim('Content preview:')} ${post.content.substring(0, 200)}...\n`);

  // Extract strategy description
  // In a real implementation, use LLM to extract structured rules
  const strategyDesc =
    `Replicated from ${post.author.name}'s post: ${post.title}. ` +
    `Original content: ${post.content.substring(0, 500)}`;

  // Create strategy on Lona
  const createSpinner = spinner('Creating strategy on Lona (this takes ~5 min)...');

  try {
    const strategyName = `${sanitizeStrategySegment(post.author.name)}_${sanitizeStrategySegment(post.title).substring(0, 30)}`;
    const commandOutput = await runStrategyCreateCommand(strategyDesc, strategyName, {
      cwd: process.env.TRADE_NEXUS_PATH || '.',
    });

    // Extract strategy ID
    const strategyId = extractStrategyIdFromOutput(commandOutput);

    if (!strategyId) {
      throw new Error('Could not extract strategy ID from output');
    }

    createSpinner.stop(`Strategy created: ${green(strategyId)}`);

    // Download data and backtest
    console.log(`\n${dim('Next steps:')}`);
    console.log(
      `  1. Download market data: ${cyan('nexus data download --symbol BTCUSDT --interval 4h')}`,
    );
    console.log(
      `  2. Run backtest: ${cyan(`nexus strategy backtest --strategy-id ${strategyId} --symbol-id <data-id> --start YYYY-MM-DD --end YYYY-MM-DD`)}`,
    );
    console.log('  3. Post results to Moltbook');

    // Save to file for later
    const replicationData = {
      postId,
      strategyId,
      author: post.author.name,
      title: post.title,
      createdAt: new Date().toISOString(),
    };
    const outputPath = join(WORKSPACE_DIR, `replication_${postId}.json`);
    mkdirSync(WORKSPACE_DIR, { recursive: true });

    writeFileSync(outputPath, JSON.stringify(replicationData, null, 2));

    printSuccess(`\nReplication data saved to ${outputPath}`);
  } catch (error) {
    createSpinner.stop();
    printError(
      `Strategy creation failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
    );
    process.exit(1);
  }
}
