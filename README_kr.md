> **English version**: [README.md](./README.md)

# RTL Agent Team

> A Claude Code plugin for automated RTL design and verification.
> 94 specialized AI agents + 92 skills automate the 6-Phase pipeline:
> Research → Architecture → μArch → RTL → Verify → Design Note.

RTL 설계 및 검증 자동화를 위한 Claude Code 플러그인.

94개 전문 AI 에이전트 + 92개 스킬 + 13개 레퍼런스 문서를 통해 6-Phase 설계 파이프라인(Research → Architecture → μArch → RTL → Verify → Design Note)을 자동화합니다.

![](./rat_logo.jpg)

## Marketplace

이 repository는 **RTL Agent Marketplace**로, 하드웨어 설계 관련 플러그인들을 제공합니다.

| 플러그인 | 설명 | 버전 |
|---------|------|------|
| **rtl-agent-team** | 94-agent RTL 설계 파이프라인 (Research → Architecture → μArch → RTL → Verify → Design Note) | 0.8.6 |
| **systemverilog-lsp** | SystemVerilog/Verilog LSP (slang-server 기반 — diagnostics, hover, go-to-definition 등) | 1.1.1 |

Marketplace에 추가 플러그인(도메인 지식 패키지, MCP 서버, 전문 스킬 등)이 지속적으로 추가될 예정입니다.

## Quick Start

```bash
# 1. Marketplace 등록
/plugin marketplace add babyworm/rtl-agent-team

# 2. 플러그인 설치
/plugin install rtl-agent-team
/plugin install systemverilog-lsp   # (선택) SV LSP

# 3. 환경 점검
/rtl-agent-team:rat-setup

# 4. 전체 자동화 (또는 "H.264 TQ 서브시스템 설계해줘")
/rtl-agent-team:rat-auto-design
```

`systemverilog-lsp`가 설치되어 있지만 `slang-server`가 없으면, 서브플러그인이 `SessionStart`에서 이를 점검하고 `local`(`~/.local/bin`, 권장), `global`, `skip` 중 하나를 고르도록 안내합니다.

## 설치

### Claude Code 대화창에서 설치 (권장)

```
/plugin marketplace add babyworm/rtl-agent-team
/plugin install rtl-agent-team
```

설치 확인: `/plugin`

### CLI에서 설치

```bash
claude plugin marketplace add babyworm/rtl-agent-team
claude plugin install rtl-agent-team
```

### 개발용 로컬 심볼릭 링크

플러그인 소스를 직접 수정하며 개발할 때:

```bash
git clone https://github.com/babyworm/rtl-agent-team.git
ln -s "$(pwd)/rtl-agent-team" ~/.claude/plugins/local/rtl-agent-team
```

## 사용법

### 라우팅 계약

- 사용자 요청은 **Action Skill 우선**으로 라우팅합니다 (예: `/rtl-agent-team:rat-auto-design`, `/rtl-agent-team:rtl-p5-verify`).
- Orchestrator Agent는 사용자 직접 호출 대상이 아니며, Action Skill이 `Task(...)`로 내부 스폰합니다.
- Policy Skill은 Orchestrator의 `skills: [*-policy]`를 통해 로드됩니다.
- `rtl-orchestrate`는 내부 라우팅 참조 스킬(`user-invocable: false`)이며 사용자 slash-command가 아닙니다.

### 전체 자동화

```
/rtl-agent-team:rat-auto-design
```

6-Phase 파이프라인 전체를 자동 실행합니다. 또는 자연어로 "H.264 TQ 서브시스템 설계해줘"라고 요청할 수 있습니다.

### Autopilot 에스컬레이션 래더

`rat-auto-design`의 gate 재시도는 gate별 `N` 기준으로 동작합니다:
- `1..N`: 기본 전략
- `N+1..2N`: fallback 전략 (실패 범위 분해 + 에이전트 조합 전환)
- `2N+1`: last-chance 대안 전략 1회 자동 실행
- last-chance 실패 후: 즉시 사용자 가이드 요청

fallback/last-chance 지시는 상태(`orchestration_control.dynamic_prompt_text`)에 기록되고 Stop hook에서 주입됩니다.

### 파이프라인 분할 실행

```
/rtl-agent-team:rat-dse              # Phase 1→2: 심층 알고리즘 + 아키텍처 탐색 (DSE)
/rtl-agent-team:codec-rd-eval        # BD-PSNR/BD-rate 평가 (알고리즘 비교)
/rtl-agent-team:codec-conformance-eval  # 디코더 conformance 평가 (JVET/JCTVC/3rd party)
/rtl-agent-team:rat-p1p3-spec-uarch    # Phase 1→3: Spec → μArch 설계 문서 완성
/rtl-agent-team:rat-p4p5-impl-verify  # Phase 4→5: μArch → RTL 구현 + 검증
```

설계와 구현 사이에 인간 리뷰를 위해 파이프라인을 분할합니다:
- `rat-dse`: 심층 Design Space Exploration — 여러 알고리즘과 아키텍처 후보를 정량적 trade-off로 비교합니다. 기존 functional C model을 architectural reference model로 변환할 수도 있습니다. Phase 2에서 리뷰를 위해 멈춥니다.
- `rat-p1p3-spec-uarch`: 표준 Phase 1→3 — μArch까지 설계 문서를 완성합니다. RTL 구현 전 리뷰를 위해 멈춥니다.
- `rat-p4p5-impl-verify`: Phase 4→5 — 승인된 μArch 문서로부터 RTL 구현 및 전체 검증을 수행합니다.

### 중단된 파이프라인 재개

`rat-auto-design` 실행 중 중단되면 진행 상태가 자동 저장됩니다. 동일 명령을 다시 실행하면 완료된 Phase를 건너뛰고 마지막 미완료 단계부터 재개합니다.

### 프로젝트 초기화

```
/rtl-agent-team:rat-setup
```

프로젝트 디렉토리 구조 생성, EDA 도구 설치 확인, 그리고 **EDA wrapper 스크립트 자동 배포**(`run_sim.sh`, `run_lint.sh`, `run_syn.sh`, `run_cdc.sh`)를 수행합니다. Hook-driven bootstrap으로 기존 스크립트는 절대 덮어쓰지 않습니다 (non-destructive 정책).

### 개별 스킬

```
/rtl-agent-team:rtl-lint-check        # RTL lint 검사
/rtl-agent-team:rtl-p5s-func-verify       # cocotb 기능 검증
/rtl-agent-team:rtl-synth-check       # Yosys 합성
/rtl-agent-team:rtl-p5s-sva-check         # SVA formal 검증
/rtl-agent-team:p2-arch-design    # 아키텍처 설계
/rtl-agent-team:domain-consult    # 도메인 전문가 상담
```

전체 92개 스킬 목록은 `skills/` 디렉토리를 참조하세요.

## 프로젝트 산출물 구조

각 Phase의 설계 산출물(`docs/`)은 다음 Phase의 입력이 되는 파이프라인을 형성합니다.
상위 스펙 준수 여부 verdict(`reviews/`)는 별도로 관리됩니다.

```
docs/phase-1-research/ ──→ docs/phase-2-architecture/ ──→ docs/phase-3-uarch/
        ──→ docs/phase-4-rtl/ ──→ docs/phase-5-verify/ ──→ reviews/phase-6-review/
        ──→ docs/phase-7-exploration/ (선택적, 자유 탐색)
```

| 디렉토리 | 역할 | 비고 |
|----------|------|------|
| `docs/phase-N-*/` | Phase별 설계 문서 (가이드 파이프라인) | Phase N → Phase N+1 입력 |
| `reviews/phase-N-*/` | 상위 스펙 준수 verdict (PASS/FAIL) | 데이터 없이 판정만 |
| `rtl/` | RTL SystemVerilog 소스코드 | Phase 4 코드 산출물 |
| `sim/`, `sim/formal/` | 테스트벤치 | Phase 4-5 코드 산출물 |
| `refc/` | C 골든 레퍼런스 모델 (DPI-C 호환) | Phase 2 코드 산출물 |
| `docs/decisions/` | Architecture Decision Records (ADR) | Phase 2-3 설계 결정 근거 |
| `docs/lessons-learned.md` | 피드백 루프에서 축적된 교훈 | Phase 전체에 걸쳐 누적 |

## 플러그인 구조

```
rtl-agent-team/
├── .claude-plugin/
│   ├── plugin.json             # 플러그인 매니페스트 (auto-discovery)
│   └── marketplace.json        # 마켓플레이스 정의
├── CLAUDE.md                   # 6-Phase 파이프라인 규칙
├── agents/                     # 94개 에이전트 (설계/검증/리뷰/EDA/도메인/오케스트레이터)
├── scripts/
│   └── run_sim.sh              # 시뮬레이터 공통 compile+run wrapper (replay 지원)
├── skills/                     # 92개 스킬 (SKILL.md + templates/ + examples/)
│   ├── rtl-orchestrate/        # 내부 라우팅 SSOT + SessionStart hook export 소스
│   ├── rat-setup/
│   │   ├── scripts/
│   │   │   └── install_project_templates.sh  # Hook-driven 템플릿 자동 설치
│   │   └── templates/          # run_lint.sh, run_syn.sh, run_cdc.sh + 기타 템플릿
│   ├── rtl-p5s-func-verify/
│   │   ├── scripts/            # run_regression.sh, merge_coverage.sh
│   │       └── run_regression.sh  # Multi-seed 회귀 테스트 (local-first)
│   ├── systemverilog/          # RTL 코딩 컨벤션 (lowRISC + 오버라이드)
│   ├── systemverilog-assertion/ # SVA 코딩 컨벤션 (bind, SymbiYosys)
│   ├── uvm/                    # UVM 코딩 컨벤션 (factory, TLM, coverage)
│   ├── systemc/                # SystemC/TLM-2.0 (AT non-blocking, AMBA-PV)
│   └── {skill}/references/     # 13개 레퍼런스 문서 (스킬별 분산)
│       ├── coding-style-guide.md   # SV 명명 규칙 상세 (systemverilog/)
│       ├── axi-protocol-rules.md   # AXI4 채널별 SVA 템플릿 (rtl-p5s-protocol-verify/)
│       ├── sva-patterns.md         # SVA 시간 연산자 + 패턴 라이브러리 (rtl-p5s-sva-check/)
│       ├── cocotb-ecosystem.md     # cocotb API, cocotb-bus, coverage (rtl-p5s-func-verify/)
│       └── ...                     # + 9개 (CDC, UVM, Yosys, SDC 등)
├── hooks/                      # 이벤트 기반 품질 게이트 (14개 hook 스크립트 / 17개 등록)
│   ├── rtl-skill-activation.sh # PreToolUse:Skill — setup 체크 + 템플릿 bootstrap
│   └── ...                     # + 13개 (라우팅 주입, 검증 게이트, cascade 등)
├── docker/                     # EDA 도구 Docker 이미지
│   └── Dockerfile              # 오픈소스 EDA 전체 번들
└── domain-packages/            # 도메인 지식 패키지
    ├── video-codec/            # H.264/H.265 지식, 적합성 데이터
    └── video-processing/       # 색공간 변환, 노이즈 제거, HDR/ISP (3 agents)
```

### 라우팅 동기화 (기여자)

라우팅/위임 문서를 수정한 뒤 아래를 실행하세요:

```bash
sh scripts/sync_orchestrator_inject.sh
python -m pytest -q tests/unit/test_agent_skill_structure.py tests/unit/test_hooks.py tests/unit/test_plugin_runtime_contract.py
```

## 에이전트 팀

### 에이전트 구성 (94개, 전체 Opus)

| 카테고리 | 에이전트 수 | 주요 에이전트 |
|---------|-----------|-------------|
| 설계 | 8 | spec-analyst, arch-designer, rtl-architect, uarch-designer, rtl-coder, rtl-critic, rtl-planner, rtl-explorer |
| 검증 | 7 | testbench-dev, func-verifier, perf-verifier, sva-extractor, protocol-checker, coverage-analyst, waveform-analyzer |
| 전문 리뷰 | 14 | codex-cross-reviewer, cdc-reviewer, protocol-reviewer, formal-reviewer, power-analyzer, synthesis-reviewer, uvm-reviewer, cocotb-reviewer, ref-model-reviewer, requirement-tracer, regression-analyzer, equivalence-checker, integration-verifier, security-reviewer |
| Phase 6 설계 노트 | 4 | code-quality-reviewer, design-quality-reviewer, design-note-writer, improvement-analyst |
| EDA/합성 | 8 | eda-runner, synthesis-reporter, lint-checker, constraint-writer, timing-advisor, cdc-checker, clock-architect, dft-designer |
| 인프라 | 3 | ipxact-generator, bfm-dev, ref-model-dev |
| 도메인 전문가 | 13 | domain-expert, vcodec-chief-standard-expert, vcodec-syntax-entropy-expert, vcodec-intra-pred-expert, vcodec-me-expert, vcodec-mc-expert, vcodec-transform-quant-expert, vcodec-filter-recon-expert, vcodec-architecture-expert, video-processing-expert, vproc-color-format-expert, vproc-denoise-expert, vproc-image-processing-expert |
| 오케스트레이터 | 32 | autopilot-orchestrator, p1-research-orchestrator, p2-arch-orchestrator, p3-uarch-orchestrator, p4-implement-orchestrator, p5-verify-orchestrator, p6-review-orchestrator 외 25개 (팀/서브페이즈 변형) |

모델 사용 원칙:
- 추론이 많이 필요한 설계/검증/디버깅은 `opus` 사용
- `sonnet`은 문서 생성 또는 도구 결과 요약/포맷팅 용도로만 사용

### 6-Phase 파이프라인 (+Phase 7 선택적 탐색)

| Phase | 이름 | 주요 에이전트 | docs/ 산출물 | reviews/ verdict |
|-------|------|-------------|-------------|-----------------|
| 1 | Research | spec-analyst | requirements.json, io_definition.json, domain-analysis.md | research-review.md |
| 2 | Architecture + Ref Model | arch-designer, ref-model-dev | architecture.md | architecture-review.md |
| 3 | μArch + BFM | uarch-designer, bfm-dev | {module}.md (모듈별) | uarch-review.md |
| 4 | RTL + Unit Test | rtl-coder, lint-checker | module-descriptions.md, unit-test-design.md, Stream B 산출물 | design-review.md |
| 5 | Verify | func-verifier, sva-extractor | unit-test-report.md, lint-report.md 등 | final-compliance.md, e2e-traceability.md |
| 6 | Design Note | code-quality-reviewer, design-note-writer | - | code-review.md, design-review.md, design-note.md, improvements.md |
| 7 | Exploration (선택) | improvement-analyst | exploration-notes.md | exploration-review.md |

> **추가 파이프라인 산출물:** 각 Phase(1-5) 완료 시 `phase-N-summary.md`가 생성되어 하위 Phase의 컨텍스트 압축에 사용됩니다. Phase 4 Stream B는 RTL 코딩과 병렬로 SVA/CDC/TB 스켈레톤을 생성합니다. Phase 2-3은 주요 설계 결정을 `docs/decisions/`에 ADR로 기록합니다.

### 코딩 컨벤션 스킬

| 스킬 | 적용 대상 | 주요 내용 |
|------|----------|----------|
| `systemverilog` | `.sv`, `.svh`, `.v`, `.vh` | lowRISC + 프로젝트 오버라이드, Power, FPGA, Pipelining |
| `systemverilog-assertion` | SVA, bind 파일 | assume/assert/cover, SymbiYosys, bind 패턴 |
| `uvm` | UVM testbench | factory, TLM 포트, coverage, phase callback |
| `systemc` | `.cpp`, `.h` (SystemC) | TLM-2.0 AT non-blocking, AMBA-PV (AXI/AHB/APB), Memory Manager, PEQ |

### 문서 3계층 구조 (점진적 공개)

| 계층 | 위치 | 역할 |
|------|------|------|
| 핵심 규칙 | `skills/*/SKILL.md` → `<Steps>` | 에이전트가 항상 읽는 필수 규칙 |
| 상황별 가이드 | `skills/*/SKILL.md` → `<Advanced>` | 특정 최적화/상황에서만 참조 |
| 상세 레퍼런스 | `skills/*/references/*.md` | 명령 레퍼런스, 패턴 라이브러리, 프로토콜 상세 |

## EDA 도구

`eda-runner` 에이전트가 Bash를 통해 로컬 EDA CLI 도구를 직접 실행합니다.

| 도구 | 용도 | 필수 여부 |
|------|------|----------|
| verilator | 시뮬레이션 + Lint | 필수 |
| verible | 스타일 Lint + 포매팅 | 필수 |
| yosys | 합성 | 필수 |
| cocotb (Python) | 기능 검증 | 필수 |
| iverilog | 대안 시뮬레이터 | 선택 |
| slang | IEEE 1800 시맨틱 Lint | 선택 |
| sby (SymbiYosys) | Formal 검증 | 선택 |
| gtkwave | 파형 뷰어 | 선택 |
| vcs / xrun / questa | 상용 시뮬레이터 | 선택 |
| spyglass | 상용 lint + CDC | 선택 |
| dc_shell (Design Compiler) | 상용 합성 | 선택 |
| vc_cdc / questa_cdc | 상용 CDC 분석 | 선택 |

`/rtl-agent-team:rat-setup`으로 도구 설치 상태를 확인할 수 있습니다.

### EDA Wrapper 스크립트

모든 EDA 작업은 재현 가능한 wrapper 스크립트를 사용하며, 매 실행마다 타임스탬프 + `_latest.sh` replay 스크립트를 자동 생성합니다.

| 스크립트 | 위치 | 지원 도구 |
|---------|------|----------|
| `run_sim.sh` | `scripts/` | iverilog, verilator, vcs, xrun (xcelium), questa |
| `run_lint.sh` | `lint/scripts/` | verilator, verible, slang, spyglass |
| `run_syn.sh` | `syn/scripts/` | yosys, dc_shell (Design Compiler) |
| `run_cdc.sh` | `sim/cdc/` | structural (heuristic), spyglass, vc_cdc, questa_cdc |
| `run_regression.sh` | `sim/regression/` | Multi-seed cocotb 회귀 테스트 (local-first, AWS opt-in) |

스크립트는 `rat-setup` hook bootstrap으로 자동 설치됩니다. 각 실행은 `{outdir}/replay/` 아래에 replay 스크립트를 생성하며, `bash replay/run_*_latest.sh`로 동일 EDA 명령을 재실행할 수 있습니다.

Regression runner는 기본 `--mode local`에 `max(1, nproc-2)` 병렬로 동작합니다. AWS Batch는 명시적 opt-in이 필요합니다 (`RTL_ALLOW_AWS=1` + `RTL_AWS_BATCH_RUNNER`).

### Docker EDA 이미지 (권장)

EDA 도구 설치가 번거롭다면, 모든 도구가 포함된 Docker 이미지를 빌드할 수 있습니다:

```bash
# 이미지 빌드 (최초 1회)
docker build -t rtl-eda-tools docker/

# 프로젝트 마운트하여 실행
docker run -it --rm -v $(pwd):/workspace -w /workspace rtl-eda-tools

# 버전 지정 빌드
docker build -t rtl-eda-tools \
  --build-arg VERILATOR_VERSION=5.024 \
  --build-arg SLANG_VERSION=v6.0 \
  --build-arg SYSTEMC_VERSION=3.0.2 \
  docker/
```

포함 도구: Verilator, Verible, Yosys, Icarus Verilog, slang, SystemC/TLM-2.0, SymbiYosys (+ boolector, z3), GTKWave, cocotb, cocotb-bus, cocotbext-axi, gcc/g++.

Claude Code에서도 빌드 가능: "EDA 도커 이미지 만들어줘" 또는 `/rtl-agent-team:rat-setup` 실행 후 Docker 옵션 선택.

## Marketplace 구조

이 repository는 단일 플러그인이 아닌 **marketplace**로 동작합니다.

```
rtl-agent-team/                          # Marketplace root
├── .claude-plugin/
│   ├── plugin.json                      # rtl-agent-team 플러그인 매니페스트
│   └── marketplace.json                 # Marketplace 정의 (플러그인 목록)
├── agents/                              # rtl-agent-team 에이전트 (94개)
├── skills/                              # rtl-agent-team 스킬 (92개, 13개 레퍼런스 문서 포함)
├── plugins/
│   └── systemverilog-lsp/               # SV LSP 플러그인 (독립)
└── domain-packages/                     # 도메인 지식 패키지
    ├── video-codec/                     # H.264/H.265 코덱 지식
    └── video-processing/                # 색공간, 노이즈 제거, HDR/ISP
```

Marketplace에 새 플러그인을 추가하려면 `marketplace.json`의 `plugins` 배열에 항목을 추가합니다:
- 같은 repo 내: `"source": "./plugins/new-plugin"`
- 외부 repo: `"source": {"source": "github", "repo": "owner/repo"}`

## 개발

이 플러그인은 순수 선언형(`.md` + `.json` 파일만)으로 빌드 과정이 필요 없습니다.

```bash
git clone https://github.com/babyworm/rtl-agent-team.git
ln -s "$(pwd)/rtl-agent-team" ~/.claude/plugins/local/rtl-agent-team
```

## 라이선스

MIT
