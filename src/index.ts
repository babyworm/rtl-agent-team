/**
 * RTL Agent Team Plugin - Entry Point
 *
 * This module exports the plugin's core types and utilities.
 * The actual functionality is provided via:
 * - agents/*.md  — Agent definitions (loaded by Claude Code)
 * - skills/      — Skill definitions (loaded by Claude Code)
 * - hooks/       — Hook wiring (hooks.json → bridge/*.cjs)
 */

export { RTL_KEYWORDS, type RTLKeyword } from './hooks/rtl-keyword-detector/index.js';
export { type DesignState, type DesignPhase } from './hooks/design-stage-control/index.js';
export { type LintState } from './hooks/rtl-lint-guard/index.js';
export { type VerificationState } from './hooks/verification-gate/index.js';
