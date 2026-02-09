import { NextResponse } from 'next/server';
import { auth } from '@clerk/nextjs/server';

import type { Agent, AgentType } from '@/types/agents';

const AGENTS: Agent[] = [
  {
    id: 'agent-predictor',
    type: 'predictor' as AgentType,
    name: 'Price Predictor',
    status: 'idle',
  },
  {
    id: 'agent-anomaly',
    type: 'anomaly' as AgentType,
    name: 'Anomaly Detector',
    status: 'idle',
  },
  {
    id: 'agent-optimizer',
    type: 'optimizer' as AgentType,
    name: 'Portfolio Optimizer',
    status: 'idle',
  },
  {
    id: 'agent-strategy',
    type: 'strategy' as AgentType,
    name: 'Strategy Generator',
    status: 'idle',
  },
  {
    id: 'agent-decision',
    type: 'decision' as AgentType,
    name: 'Decision Maker',
    status: 'idle',
  },
];

export async function GET() {
  try {
    const { userId } = await auth();
    if (!userId) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    return NextResponse.json(AGENTS);
  } catch (error) {
    console.error('Agents GET error:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 },
    );
  }
}
