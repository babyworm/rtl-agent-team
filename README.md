# RTL Agent Team

RTL 설계 및 검증 자동화를 위한 Claude Code 플러그인.

27개 전문 AI 에이전트 + 28개 스킬을 통해 5-Phase 설계 파이프라인(Research → Architecture → μArch → RTL → Verify)을 자동화합니다.

## 설치

### 방법 1: 로컬 심볼릭 링크 (개발용)

```bash
# 빌드
cd /path/to/rtl-agent-team
npm install
npm run build

# Claude Code 플러그인으로 등록
ln -s "$(pwd)" ~/.claude/plugins/local/rtl-agent-team
```

### 방법 2: GitHub에서 설치

```bash
# 마켓플레이스 등록
claude plugin marketplace add https://github.com/babyworm/rtl-agent-team.git

# 플러그인 설치
claude plugin install rtl-agent-team
```

### 방법 3: 프로젝트 로컬

특정 프로젝트에서만 사용하려면:

```bash
mkdir -p my-chip-project/.claude/plugins/
ln -s /path/to/rtl-agent-team my-chip-project/.claude/plugins/rtl-agent-team
```

### 설치 확인

```bash
claude plugin list
```

## 사용법

### 전체 자동화

```
/rtl-agent-team:rtl-autopilot
```

5-Phase 파이프라인 전체를 자동 실행합니다.

### 프로젝트 초기화

```
/rtl-agent-team:rtl-setup
```

프로젝트 디렉토리 구조 생성 + EDA 도구 설치 확인을 수행합니다.

### 개별 스킬

```
/rtl-agent-team:lint-check        # RTL lint 검사
/rtl-agent-team:func-verify       # cocotb 기능 검증
/rtl-agent-team:synth-check       # Yosys 합성
/rtl-agent-team:sva-check         # SVA formal 검증
/rtl-agent-team:arch-design       # 아키텍처 설계
/rtl-agent-team:domain-consult    # 도메인 전문가 상담
```

전체 28개 스킬 목록은 `skills/` 디렉토리를 참조하세요.

## 구조

```
rtl-agent-team/
├── .claude-plugin/plugin.json   # 플러그인 매니페스트
├── CLAUDE.md                    # 5-Phase 파이프라인 규칙
├── hooks/hooks.json             # Hook 이벤트 와이어링
├── agents/                      # 24 core + 3 domain = 27 에이전트
│   └── domain/video-codec/      # 도메인 전문가 (H.264/H.265)
├── skills/                      # 28개 스킬 (SKILL.md)
├── src/hooks/                   # 4개 Hook (TypeScript)
├── bridge/                      # Hook CJS 번들 (빌드 산출물)
└── domain-packages/             # 도메인 지식 패키지
```

## 에이전트 팀

### 모델 라우팅

| 모델 | 에이전트 수 | 역할 |
|------|-----------|------|
| opus | 14 + 3 domain | 심층 추론, 분석, 리뷰 |
| sonnet | 10 | 구현, 실행, 리포팅 |

### 5-Phase 파이프라인

| Phase | 이름 | 주요 에이전트 |
|-------|------|-------------|
| 1 | Research | spec-analyst |
| 2 | Architecture + Ref Model | arch-designer, ref-model-dev |
| 3 | μArch + BFM | uarch-designer, bfm-dev |
| 4 | RTL Coding | rtl-coder, lint-checker |
| 5 | Verification | func-verifier, sva-extractor, synthesis-reporter |

## EDA 도구

`eda-runner` 에이전트가 Bash를 통해 로컬 EDA CLI 도구를 직접 실행합니다.

| 도구 | 용도 | 필수 여부 |
|------|------|----------|
| verilator | 시뮬레이션 + Lint | 필수 |
| yosys | 합성 | 필수 |
| cocotb (Python) | 기능 검증 | 필수 |
| iverilog | 대안 시뮬레이터 | 선택 |
| sby (SymbiYosys) | Formal 검증 | 선택 |
| slang | 고급 Lint | 선택 |

`/rtl-agent-team:rtl-setup`으로 도구 설치 상태를 확인할 수 있습니다.

## 개발

```bash
npm install
npm run build       # tsc + esbuild (hooks)
npm run dev         # tsc --watch
npm test            # vitest
```

## 라이선스

MIT
