#!/usr/bin/env node
/**
 * Verification Gate Hook (Stop)
 * Blocks session termination if RTL verification is incomplete.
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
  message?: string;
  sessionId?: string;
  cwd?: string;
  toolName?: string;
}

interface VerificationChecks {
  lint_clean: boolean;
  sim_pass: boolean;
  formal_pass: boolean;
  synth_pass: boolean;
}

export interface VerificationState {
  verification_required: boolean;
  checks: VerificationChecks;
  module?: string;
}

interface HookOutput {
  continue: boolean;
  hookSpecificOutput?: {
    additionalContext?: string;
  };
}

const CHECK_LABELS: Record<keyof VerificationChecks, string> = {
  lint_clean:  'Lint clean (no errors/warnings)',
  sim_pass:    'Simulation pass (all testbenches)',
  formal_pass: 'Formal verification pass (SVA properties)',
  synth_pass:  'Synthesis pass (no timing/area violations)',
};

function loadVerificationState(cwd: string): VerificationState | null {
  try {
    const statePath = resolve(cwd, '.rtl-agent-team/state/rtl-verification-state.json');
    const raw = readFileSync(statePath, 'utf8');
    return JSON.parse(raw) as VerificationState;
  } catch {
    return null;
  }
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
  const state = loadVerificationState(cwd);

  // No state file → not in RTL verification flow, allow stop
  if (state === null || !state.verification_required) {
    process.stdout.write(JSON.stringify({ continue: true }));
    return;
  }

  const checks = state.checks;
  const failedChecks = (Object.keys(checks) as Array<keyof VerificationChecks>).filter(
    (key) => !checks[key],
  );

  if (failedChecks.length === 0) {
    // All checks passed — allow stop
    process.stdout.write(JSON.stringify({ continue: true }));
    return;
  }

  const moduleName = state.module ? ` for module "${state.module}"` : '';
  const failedList = failedChecks.map((k) => `  - [ ] ${CHECK_LABELS[k]}`).join('\n');
  const passedChecks = (Object.keys(checks) as Array<keyof VerificationChecks>).filter(
    (key) => checks[key],
  );
  const passedList = passedChecks.length > 0
    ? passedChecks.map((k) => `  - [x] ${CHECK_LABELS[k]}`).join('\n')
    : '  (none)';

  const additionalContext = [
    `Verification incomplete${moduleName}. Do NOT stop until all checks pass.`,
    '',
    'Remaining checks:',
    failedList,
    '',
    'Completed checks:',
    passedList,
    '',
    'Run the appropriate verification skills:',
    '  - lint_clean:  /rtl-agent-team:lint-check',
    '  - sim_pass:    /rtl-agent-team:func-verify',
    '  - formal_pass: /rtl-agent-team:sva-check',
    '  - synth_pass:  /rtl-agent-team:synth-check',
  ].join('\n');

  const output: HookOutput = {
    continue: false,
    hookSpecificOutput: { additionalContext },
  };
  process.stdout.write(JSON.stringify(output));
}

main().catch(() => {
  process.stdout.write(JSON.stringify({ continue: true }));
});
