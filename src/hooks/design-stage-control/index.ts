#!/usr/bin/env node
/**
 * Design Stage Control Hook (PreToolUse: Bash|Write|Edit)
 * Enforces design stage ordering by reading .rtl-agent-team/state/rtl-design-state.json.
 */

import { readFileSync } from 'fs';
import { resolve } from 'path';

async function readStdin(): Promise<string> {
  return new Promise((res) => {
    let data = '';
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', (c) => { data += c; });
    process.stdin.on('end', () => res(data));
  });
}

interface HookInput {
  tool_name?: string;
  tool_input?: {
    command?: string;
    file_path?: string;
    content?: string;
    new_string?: string;
  };
  session_id?: string;
  cwd?: string;
}

export type DesignPhase = 1 | 2 | 3 | 4 | 5;

export interface DesignState {
  current_phase: number;
  phases_completed: number[];
  active_module?: string;
  last_updated?: string;
}

interface HookOutput {
  continue: boolean;
  hookSpecificOutput?: {
    additionalContext?: string;
  };
}

const PHASE_NAMES: Record<number, string> = {
  1: 'Research',
  2: 'Architecture',
  3: 'Micro-Architecture (μArch)',
  4: 'RTL Coding',
  5: 'Verification',
};

function loadDesignState(cwd: string): DesignState | null {
  try {
    const statePath = resolve(cwd, '.rtl-agent-team/state/rtl-design-state.json');
    const raw = readFileSync(statePath, 'utf8');
    return JSON.parse(raw) as DesignState;
  } catch {
    return null;
  }
}

function detectTargetPhase(toolName: string, message: string): number | null {
  const lowerMsg = message.toLowerCase();

  // Phase 5 (Verify) signals
  if (/\b(sim|simulation|verify|testbench|tb_|_tb\.|cocotb|uvm|formal|sva)\b/.test(lowerMsg)) return 5;
  // Phase 4 (RTL) signals
  if (/\.(sv|v|vhd)\b/.test(lowerMsg) || /\b(module|always_ff|always_comb|endmodule)\b/.test(lowerMsg)) return 4;
  // Phase 3 (uArch) signals
  if (/\b(uarch|microarch|pipeline|datapath|micro.arch)\b/.test(lowerMsg)) return 3;
  // Phase 2 (Architecture) signals
  if (/\b(arch|architecture|block.diagram|interface|protocol)\b/.test(lowerMsg)) return 2;

  return null;
}

async function main(): Promise<void> {
  const raw = await readStdin();

  let input: HookInput = {};
  try {
    input = JSON.parse(raw) as HookInput;
  } catch {
    process.stdout.write(JSON.stringify({ continue: true }));
    return;
  }

  const cwd = input.cwd ?? process.cwd();
  const state = loadDesignState(cwd);

  // No state file → not in RTL flow, allow all operations
  if (state === null) {
    process.stdout.write(JSON.stringify({ continue: true }));
    return;
  }

  const toolName = input.tool_name ?? '';
  const toolInput = input.tool_input ?? {};
  // Combine all tool_input fields for phase detection
  const message = [
    toolInput.command ?? '',
    toolInput.file_path ?? '',
    toolInput.content ?? '',
    toolInput.new_string ?? '',
  ].join(' ');
  const targetPhase = detectTargetPhase(toolName, message);

  if (targetPhase === null) {
    process.stdout.write(JSON.stringify({ continue: true }));
    return;
  }

  const currentPhase = state.current_phase;
  const completed = new Set(state.phases_completed);

  // Check if prerequisite phases are complete
  const missingPhases: number[] = [];
  for (let phase = 1; phase < targetPhase; phase++) {
    if (!completed.has(phase)) {
      missingPhases.push(phase);
    }
  }

  if (missingPhases.length === 0) {
    process.stdout.write(JSON.stringify({ continue: true }));
    return;
  }

  const missingNames = missingPhases.map((p) => `Phase ${p} (${PHASE_NAMES[p] ?? 'Unknown'})`).join(', ');
  const targetName = PHASE_NAMES[targetPhase] ?? `Phase ${targetPhase}`;
  const moduleName = state.active_module ? ` for module "${state.active_module}"` : '';

  const additionalContext = [
    `WARNING: Design stage ordering violation detected${moduleName}.`,
    `Attempting to work on Phase ${targetPhase} (${targetName}) but prerequisite phases are incomplete: ${missingNames}.`,
    `Current phase: ${currentPhase} (${PHASE_NAMES[currentPhase] ?? 'Unknown'}).`,
    `Complete the missing phases before proceeding to ${targetName}.`,
    `Phase order: Research (1) → Architecture (2) → μArch (3) → RTL (4) → Verification (5).`,
  ].join('\n');

  const output: HookOutput = {
    continue: true,
    hookSpecificOutput: { additionalContext },
  };
  process.stdout.write(JSON.stringify(output));
}

main().catch(() => {
  process.stdout.write(JSON.stringify({ continue: true }));
});
