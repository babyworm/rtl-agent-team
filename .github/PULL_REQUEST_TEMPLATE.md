## Summary

Brief description of the changes.

## Type of Change

- [ ] Bug fix
- [ ] New feature (agent, skill, domain package, etc.)
- [ ] Documentation update
- [ ] Refactoring (no functional change)
- [ ] Other: 

## Checklist

- [ ] Agent/skill count updated in README.md, README_kr.md, CLAUDE.md, marketplace.json (if added/removed)
- [ ] Routing sync done: `sh scripts/sync_orchestrator_inject.sh` (if routing changed)
- [ ] Tests pass: `python3 -m pytest tests/unit/ -x -q`
- [ ] Shell scripts pass: `shellcheck -s sh hooks/*.sh hooks/lib/*.sh` (if hooks modified)
- [ ] No stale version references: `grep -r 'OLD_VER' package.json .claude-plugin/ README.md`

## Related Issues

Closes #
