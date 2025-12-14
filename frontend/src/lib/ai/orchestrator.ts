import { generateText } from 'ai';
import { xai } from '@ai-sdk/xai';
import { wrapAISDKModel } from 'langsmith/wrappers/vercel';

import type { AgentContext, AgentResult, OrchestratorTask } from '@/types/agents';

const model = wrapAISDKModel(xai('grok-2-latest'));

export async function orchestrate(tasks: OrchestratorTask[]): Promise<AgentResult[]> {
  const results: AgentResult[] = [];

  for (const task of tasks) {
    const result = await executeTask(task);
    results.push(result);

    // If a task fails, decide whether to continue or abort
    if (!result.success && task.critical) {
      break;
    }
  }

  return results;
}

async function executeTask(task: OrchestratorTask): Promise<AgentResult> {
  const startTime = Date.now();

  try {
    const response = await generateText({
      model,
      system: `You are the Trade Nexus orchestrator. Your role is to coordinate
               trading agents and make decisions based on their outputs.
               Current task: ${task.type}`,
      prompt: JSON.stringify(task.context),
    });

    return {
      taskId: task.id,
      type: task.type,
      success: true,
      output: response.text,
      duration: Date.now() - startTime,
    };
  } catch (error) {
    return {
      taskId: task.id,
      type: task.type,
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error',
      duration: Date.now() - startTime,
    };
  }
}

export async function analyzeContext(context: AgentContext): Promise<string> {
  const response = await generateText({
    model,
    system: `Analyze the following trading context and provide actionable insights.
             Focus on: market conditions, risk factors, and opportunities.`,
    prompt: JSON.stringify(context),
  });

  return response.text;
}
