#!/usr/bin/env node
/**
 * RTL Keyword Detector Hook (UserPromptSubmit)
 * Detects RTL magic keywords in user prompts and injects skill activation directives.
 */

async function readStdin(): Promise<string> {
  return new Promise((resolve) => {
    let data = '';
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', (chunk) => { data += chunk; });
    process.stdin.on('end', () => resolve(data));
  });
}

interface HookInput {
  message?: string;
  sessionId?: string;
  cwd?: string;
  toolName?: string;
}

interface HookOutput {
  continue: boolean;
  hookSpecificOutput?: {
    additionalContext?: string;
  };
}

export type RTLKeyword = {
  pattern: RegExp;
  skill: string;
  label: string;
};

export const RTL_KEYWORDS: RTLKeyword[] = [
  { pattern: /\brtl-autopilot\b/i,     skill: 'rtl-agent-team:rtl-autopilot',     label: 'RTL-AUTOPILOT' },
  { pattern: /\brtl-verify\b/i,        skill: 'rtl-agent-team:func-verify',        label: 'RTL-VERIFY' },
  { pattern: /\brtl-synth\b/i,         skill: 'rtl-agent-team:synth-check',        label: 'RTL-SYNTH' },
  { pattern: /\brtl-formal\b/i,        skill: 'rtl-agent-team:sva-check',          label: 'RTL-FORMAL' },
  { pattern: /\brtl-lint\b/i,          skill: 'rtl-agent-team:lint-check',         label: 'RTL-LINT' },
  { pattern: /\bspec-analyze\b/i,      skill: 'rtl-agent-team:research-analyze',   label: 'SPEC-ANALYZE' },
  { pattern: /\bref-model\b/i,         skill: 'rtl-agent-team:ref-model',          label: 'REF-MODEL' },
  { pattern: /\bresearch-analyze\b/i,  skill: 'rtl-agent-team:research-analyze',   label: 'RESEARCH-ANALYZE' },
  { pattern: /\barch-design\b/i,       skill: 'rtl-agent-team:arch-design',        label: 'ARCH-DESIGN' },
  { pattern: /\buarch-design\b/i,      skill: 'rtl-agent-team:uarch-design',       label: 'UARCH-DESIGN' },
  { pattern: /\bbfm-develop\b/i,       skill: 'rtl-agent-team:bfm-develop',        label: 'BFM-DEVELOP' },
  { pattern: /\brtl-code\b/i,          skill: 'rtl-agent-team:rtl-code',           label: 'RTL-CODE' },
] as const satisfies RTLKeyword[];

function stripCodeBlocks(text: string): string {
  // Remove fenced code blocks (``` ... ```) to avoid false positives
  return text.replace(/```[\s\S]*?```/g, '').replace(/`[^`]*`/g, '');
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

  const message = input.message ?? '';
  const stripped = stripCodeBlocks(message);

  const matched: Array<{ skill: string; label: string }> = [];
  for (const entry of RTL_KEYWORDS) {
    if (entry.pattern.test(stripped)) {
      matched.push({ skill: entry.skill, label: entry.label });
    }
  }

  if (matched.length === 0) {
    const output: HookOutput = { continue: true };
    process.stdout.write(JSON.stringify(output));
    return;
  }

  const lines: string[] = [];
  for (const m of matched) {
    lines.push(`[MAGIC KEYWORD: RTL] Detected keyword "${m.label}". Invoke skill \`/${m.skill}\` immediately.`);
  }
  const additionalContext = lines.join('\n');

  const output: HookOutput = {
    continue: true,
    hookSpecificOutput: { additionalContext },
  };
  process.stdout.write(JSON.stringify(output));
}

main().catch(() => {
  process.stdout.write(JSON.stringify({ continue: true }));
});
