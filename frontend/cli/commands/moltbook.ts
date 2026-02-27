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
} from '../lib/output';
import { execSync } from 'node:child_process';
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';

const WORKSPACE_DIR = process.env.WORKSPACE_PATH || '/home/txena/lona/workspace';
const MOLTBOOK_CREDENTIALS = process.env.MOLTBOOK_CREDENTIALS || join(WORKSPACE_DIR, 'moltbook-credentials.json');

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
  console.log(`  nexus moltbook replicate --post-id abc123`);
  console.log(`  nexus moltbook replicate --author claw-n --strategy-name EMA33`);
}

async function replicateStrategy(args: string[]) {
  const { values } = parseArgs({
    args,
    options: {
      'post-id': { type: 'string' },
      'author': { type: 'string' },
      'strategy-name': { type: 'string' },
      'optimize': { type: 'boolean', default: false },
      'help': { type: 'boolean', short: 'h' },
    },
  });

  if (values.help) {
    console.log(`${bold('Usage:')} nexus moltbook replicate [options]\n`);
    console.log(`${bold('Options:')}`);
    console.log(`  ${cyan('--post-id')}        Moltbook post ID to replicate`);
    console.log(`  ${cyan('--author')}         Filter by author name`);
    console.log(`  ${cyan('--strategy-name')}  Filter by strategy name`);
    console.log(`  ${cyan('--optimize')}       Run optimization after replication`);
    console.log();
    console.log(`${bold('Examples:')}`);
    console.log(`  nexus moltbook replicate --post-id 57bc7211-20a0-4c86-8b23-89288bc72f84`);
    console.log(`  nexus moltbook replicate --author claw-n`);
    return;
  }

  validateConfig();

  printHeader('Moltbook Strategy Replication');

  // Load Moltbook credentials
  if (!existsSync(MOLTBOOK_CREDENTIALS)) {
    printError(`Moltbook credentials not found: ${MOLTBOOK_CREDENTIALS}`);
    process.exit(1);
  }

  const credentials = JSON.parse(readFileSync(MOLTBOOK_CREDENTIALS, 'utf-8'));
  const apiKey = credentials.api_key;

  if (!apiKey) {
    printError('API key not found in credentials file');
    process.exit(1);
  }

  let postId = values['post-id'];

  // If no post-id, search for strategies
  if (!postId) {
    const searchSpinner = spinner('Searching for strategies on Moltbook...');
    
    try {
      const response = await fetch('https://www.moltbook.com/api/v1/posts?submolt=trading&sort=hot&limit=10', {
        headers: { 'Authorization': `Bearer ${apiKey}` }
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      
      const data = await response.json();
      const posts = data.posts || [];
      
      // Filter for strategy posts
      const strategyPosts = posts.filter((p: any) => {
        const title = p.title?.toLowerCase() || '';
        const content = p.content?.toLowerCase() || '';
        const keywords = ['ema', 'rsi', 'macd', 'strategy', 'backtest', 'trading', 'indicator'];
        return keywords.some(k => title.includes(k) || content.includes(k));
      });
      
      searchSpinner.succeed(`Found ${strategyPosts.length} strategy posts`);
      
      if (strategyPosts.length === 0) {
        printWarning('No strategy posts found');
        return;
      }
      
      // Show options
      console.log(`\n${bold('Available strategies:')}`);
      strategyPosts.forEach((p: any, i: number) => {
        console.log(`  ${cyan(`${i + 1}.`)} ${p.title} by ${p.author.name}`);
      });
      
      // For now, take the first one
      postId = strategyPosts[0].id;
      console.log(`\n${dim('Using:')} ${strategyPosts[0].title}\n`);
      
    } catch (error) {
      searchSpinner.fail('Failed to fetch posts');
      printError(error instanceof Error ? error.message : 'Unknown error');
      process.exit(1);
    }
  }

  // Fetch post details
  const fetchSpinner = spinner('Fetching strategy details...');
  
  let post;
  try {
    const response = await fetch(`https://www.moltbook.com/api/v1/posts/${postId}`, {
      headers: { 'Authorization': `Bearer ${apiKey}` }
    });
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    
    const data = await response.json();
    post = data.post;
    fetchSpinner.succeed('Strategy details fetched');
  } catch (error) {
    fetchSpinner.fail('Failed to fetch post');
    printError(error instanceof Error ? error.message : 'Unknown error');
    process.exit(1);
  }

  console.log(`\n${bold('Strategy:')} ${post.title}`);
  console.log(`${bold('Author:')} ${post.author.name}`);
  console.log(`${dim('Content preview:')} ${post.content.substring(0, 200)}...\n`);

  // Extract strategy description
  // In a real implementation, use LLM to extract structured rules
  const strategyDesc = `Replicated from ${post.author.name}'s post: ${post.title}. ` +
    `Original content: ${post.content.substring(0, 500)}`;

  // Create strategy on Lona
  const createSpinner = spinner('Creating strategy on Lona (this takes ~5 min)...');
  
  try {
    // Call nexus strategy create
    const strategyName = `${post.author.name}_${post.title.replace(/[^a-zA-Z0-9]/g, '_').substring(0, 30)}`;
    
    const cmd = `cd ${process.env.TRADE_NEXUS_PATH || '.'} && timeout 300 bun run nexus strategy create --description ${JSON.stringify(strategyDesc)} --name ${JSON.stringify(strategyName)} 2>&1`;
    
    const result = execSync(cmd, { encoding: 'utf-8', timeout: 310000 });
    
    // Extract strategy ID
    const strategyIdMatch = result.match(/ID: ([a-f0-9-]+)/i);
    const strategyId = strategyIdMatch ? strategyIdMatch[1] : null;
    
    if (!strategyId) {
      throw new Error('Could not extract strategy ID from output');
    }
    
    createSpinner.succeed(`Strategy created: ${green(strategyId)}`);
    
    // Download data and backtest
    console.log(`\n${dim('Next steps:')}`);
    console.log(`  1. Download market data: ${cyan(`nexus data download --symbol BTCUSDT --interval 4h`)}`);
    console.log(`  2. Run backtest: ${cyan(`nexus strategy backtest --id ${strategyId} --data <data-id>`)}`);
    console.log(`  3. Post results to Moltbook`);
    
    // Save to file for later
    const replicationData = {
      postId,
      strategyId,
      author: post.author.name,
      title: post.title,
      createdAt: new Date().toISOString(),
    };
    
    writeFileSync(
      join(WORKSPACE_DIR, `replication_${postId}.json`),
      JSON.stringify(replicationData, null, 2)
    );
    
    printSuccess(`\nReplication data saved to workspace/replication_${postId}.json`);
    
  } catch (error) {
    createSpinner.fail('Strategy creation failed');
    printError(error instanceof Error ? error.message : 'Unknown error');
    process.exit(1);
  }
}
