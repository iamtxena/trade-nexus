import { NextRequest, NextResponse } from 'next/server';
import { auth } from '@clerk/nextjs/server';
import { createServiceRoleClient } from '@/lib/supabase/server';
import { executeTask } from '@/lib/ai/orchestrator';

import type { Json } from '@/types/database';
import type { AgentRun, AgentType } from '@/types/agents';

const VALID_AGENT_TYPES: AgentType[] = [
  'predictor', 'anomaly', 'optimizer', 'strategy', 'decision', 'strategist',
];

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

export async function POST(request: NextRequest) {
  try {
    const { userId } = await auth();
    if (!userId) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const body = await request.json();

    if (!body.agentType || !VALID_AGENT_TYPES.includes(body.agentType)) {
      return NextResponse.json(
        { error: `agentType must be one of: ${VALID_AGENT_TYPES.join(', ')}` },
        { status: 400 },
      );
    }
    if (!body.input || typeof body.input !== 'object') {
      return NextResponse.json({ error: 'input must be an object' }, { status: 400 });
    }

    const supabase = await createServiceRoleClient();

    // Insert run with status 'running'
    const { data: insertedRow, error: insertError } = await supabase
      .from('agent_runs')
      .insert({
        user_id: userId,
        agent_type: body.agentType as string,
        input: body.input as Json,
        status: 'running',
      })
      .select()
      .single();

    if (insertError) {
      return NextResponse.json({ error: insertError.message }, { status: 500 });
    }

    const row = insertedRow as AgentRunRow;

    // Execute the agent
    const result = await executeTask({
      id: row.id,
      type: body.agentType as AgentType,
      context: body.input,
      critical: false,
      priority: 1,
    });

    // Update the run with results
    const { data: updatedRow, error: updateError } = await supabase
      .from('agent_runs')
      .update({
        output: (result.success ? { result: result.output } : { error: result.error }) as Json,
        status: result.success ? 'completed' : 'failed',
        completed_at: new Date().toISOString(),
      })
      .eq('id', row.id)
      .select()
      .single();

    if (updateError) {
      return NextResponse.json({ error: updateError.message }, { status: 500 });
    }

    return NextResponse.json(toAgentRun(updatedRow as AgentRunRow));
  } catch (error) {
    console.error('Agent run POST error:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 },
    );
  }
}
