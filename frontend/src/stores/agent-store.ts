import { create } from 'zustand';

import type { Agent, AgentType } from '@/types/agents';

interface AgentState {
  selectedAgent: Agent | null;
  runningAgents: Set<string>;
  agentLogs: Map<string, string[]>;

  // Actions
  selectAgent: (agent: Agent | null) => void;
  setAgentRunning: (agentId: string, running: boolean) => void;
  addLog: (agentId: string, log: string) => void;
  clearLogs: (agentId: string) => void;
}

export const useAgentStore = create<AgentState>((set) => ({
  selectedAgent: null,
  runningAgents: new Set(),
  agentLogs: new Map(),

  selectAgent: (agent) => set({ selectedAgent: agent }),

  setAgentRunning: (agentId, running) =>
    set((state) => {
      const newRunning = new Set(state.runningAgents);
      if (running) {
        newRunning.add(agentId);
      } else {
        newRunning.delete(agentId);
      }
      return { runningAgents: newRunning };
    }),

  addLog: (agentId, log) =>
    set((state) => {
      const newLogs = new Map(state.agentLogs);
      const existing = newLogs.get(agentId) || [];
      newLogs.set(agentId, [...existing, log]);
      return { agentLogs: newLogs };
    }),

  clearLogs: (agentId) =>
    set((state) => {
      const newLogs = new Map(state.agentLogs);
      newLogs.delete(agentId);
      return { agentLogs: newLogs };
    }),
}));

// Selector helpers
export const selectRunningAgentTypes = (state: AgentState): AgentType[] => {
  return Array.from(state.runningAgents) as AgentType[];
};
