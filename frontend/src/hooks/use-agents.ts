import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

import type { Agent, AgentRun } from '@/types/agents';

async function fetchAgents(): Promise<Agent[]> {
  const response = await fetch('/api/agents');
  if (!response.ok) throw new Error('Failed to fetch agents');
  return response.json();
}

async function fetchAgentRuns(agentType?: string): Promise<AgentRun[]> {
  const url = agentType ? `/api/agents/runs?type=${agentType}` : '/api/agents/runs';
  const response = await fetch(url);
  if (!response.ok) throw new Error('Failed to fetch agent runs');
  return response.json();
}

async function runAgent(agentType: string, input: Record<string, unknown>): Promise<AgentRun> {
  const response = await fetch('/api/agents/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ agentType, input }),
  });
  if (!response.ok) throw new Error('Failed to run agent');
  return response.json();
}

export function useAgents() {
  return useQuery({
    queryKey: ['agents'],
    queryFn: fetchAgents,
  });
}

export function useAgentRuns(agentType?: string) {
  return useQuery({
    queryKey: ['agent-runs', agentType],
    queryFn: () => fetchAgentRuns(agentType),
  });
}

export function useRunAgent() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ agentType, input }: { agentType: string; input: Record<string, unknown> }) =>
      runAgent(agentType, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agent-runs'] });
      queryClient.invalidateQueries({ queryKey: ['agents'] });
    },
  });
}
