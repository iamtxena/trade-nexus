import { createServiceRoleClient } from '@/lib/supabase/server';
import { auth } from '@clerk/nextjs/server';
import { type NextRequest, NextResponse } from 'next/server';

import type { AgentRun } from '@/types/agents';

type AgentRunRow = {
  id: string;
  user_id: string;
  agent_type: string;
  input: unknown;
  output: unknown;
  status: string;
  created_at: string;
  completed_at: string | null;
};

function toAgentRun(row: AgentRunRow): AgentRun {
  return {
    id: row.id,
    userId: row.user_id,
    agentType: row.agent_type as AgentRun['agentType'],
    input: (row.input ?? {}) as Record<string, unknown>,
    output: row.output as Record<string, unknown> | undefined,
    status: row.status as AgentRun['status'],
    createdAt: row.created_at,
    completedAt: row.completed_at ?? undefined,
  };
}

export async function GET(request: NextRequest) {
  try {
    const { userId } = await auth();
    if (!userId) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const { searchParams } = new URL(request.url);
    const agentType = searchParams.get('type');

    const supabase = await createServiceRoleClient();
    let query = supabase
      .from('agent_runs')
      .select('*')
      .eq('user_id', userId)
      .order('created_at', { ascending: false })
      .limit(50);

    if (agentType) {
      query = query.eq('agent_type', agentType);
    }

    const { data, error } = await query;

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 });
    }

    return NextResponse.json((data as AgentRunRow[]).map(toAgentRun));
  } catch (error) {
    console.error('Agent runs GET error:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 },
    );
  }
}
