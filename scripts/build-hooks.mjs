#!/usr/bin/env node
/**
 * Build hook scripts from TypeScript sources to CJS bundles.
 * Each hook is bundled independently for Claude Code runtime.
 */
import { build } from 'esbuild';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const rootDir = resolve(__dirname, '..');

const hookEntries = [
  { entry: 'src/hooks/rtl-keyword-detector/index.ts', output: 'bridge/rtl-keyword-detector.cjs' },
  { entry: 'src/hooks/design-stage-control/index.ts', output: 'bridge/design-stage-control.cjs' },
  { entry: 'src/hooks/rtl-lint-guard/index.ts', output: 'bridge/rtl-lint-guard.cjs' },
  { entry: 'src/hooks/verification-gate/index.ts', output: 'bridge/verification-gate.cjs' },
];

async function buildAll() {
  console.log('Building hook bundles...');

  for (const hook of hookEntries) {
    try {
      await build({
        entryPoints: [resolve(rootDir, hook.entry)],
        outfile: resolve(rootDir, hook.output),
        bundle: true,
        platform: 'node',
        target: 'node20',
        format: 'cjs',
        external: ['child_process', 'fs', 'path', 'os', 'crypto', 'util', 'stream', 'events'],
        minify: false,
        sourcemap: true,
      });
      console.log(`  ✓ ${hook.output}`);
    } catch (err) {
      console.error(`  ✗ ${hook.output}: ${err.message}`);
      process.exit(1);
    }
  }

  console.log('Hook bundles built successfully.');
}

buildAll();
