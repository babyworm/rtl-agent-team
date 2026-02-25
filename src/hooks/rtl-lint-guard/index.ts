#!/usr/bin/env node
/**
 * RTL Lint Guard Hook (PreToolUse: Write|Edit)
 * Reminds agent to run lint after modifying .sv or .v files.
 * Tracks lint state in .rtl-agent-team/state/rtl-lint-state.json.
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

interface LintResult {
  errors: number;
  warnings: number;
  timestamp: string;
}

export interface LintState {
  files_needing_lint: string[];
  last_lint_results: Record<string, LintResult>;
}

interface HookOutput {
  continue: boolean;
  hookSpecificOutput?: {
    additionalContext?: string;
  };
}

const RTL_FILE_PATTERN = /\.(sv|v)(\s|$|"|')/i;

function loadLintState(cwd: string): LintState | null {
  try {
    const statePath = resolve(cwd, '.rtl-agent-team/state/rtl-lint-state.json');
    const raw = readFileSync(statePath, 'utf8');
    return JSON.parse(raw) as LintState;
  } catch {
    return null;
  }
}

function extractFilePath(message: string): string | null {
  // Try to extract file path from tool input (Write/Edit tool input contains file_path)
  // Heuristic: look for .sv or .v file references in the message
  const match = message.match(/["']?([^\s"']+\.(?:sv|v))["']?/i);
  return match ? match[1] : null;
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
  const toolInput = input.tool_input ?? {};
  // Extract file path from tool_input (Write/Edit provide file_path directly)
  const filePath = toolInput.file_path ?? extractFilePath(toolInput.command ?? '');

  // Only act on RTL file modifications
  if (!filePath || !RTL_FILE_PATTERN.test(filePath)) {
    process.stdout.write(JSON.stringify({ continue: true }));
    return;
  }
  const lintState = loadLintState(cwd);

  const contextLines: string[] = [
    'REMINDER: You are about to modify an RTL file (.sv/.v).',
    'After making changes, run lint to ensure no new violations are introduced.',
    'Use: rtl-agent-team:lint-check or invoke the EDA sim MCP tool `run_lint`.',
  ];

  if (filePath) {
    contextLines.push(`File: ${filePath}`);

    if (lintState) {
      const needsLint = lintState.files_needing_lint.includes(filePath);
      const lastResult = lintState.last_lint_results[filePath];

      if (needsLint) {
        contextLines.push(`Status: This file is already flagged as needing lint.`);
      } else if (lastResult) {
        const { errors, warnings, timestamp } = lastResult;
        contextLines.push(
          `Last lint result (${timestamp}): ${errors} error(s), ${warnings} warning(s).`,
        );
        if (errors > 0) {
          contextLines.push(`WARNING: File had ${errors} lint error(s) before this edit. Fix them too.`);
        }
      } else {
        contextLines.push(`Status: No previous lint results recorded for this file.`);
      }
    }
  }

  if (lintState && lintState.files_needing_lint.length > 0) {
    contextLines.push(
      `Other files needing lint: ${lintState.files_needing_lint.join(', ')}`,
    );
  }

  const output: HookOutput = {
    continue: true,
    hookSpecificOutput: { additionalContext: contextLines.join('\n') },
  };
  process.stdout.write(JSON.stringify(output));
}

main().catch(() => {
  process.stdout.write(JSON.stringify({ continue: true }));
});
