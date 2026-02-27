# RTL Agent Team

> A Claude Code plugin for automated RTL design and verification.
> 50 specialized AI agents + 34 skills automate the 6-Phase pipeline:
> Research → Architecture → μArch → RTL → Verify → Design Note.

RTL 설계 및 검증 자동화를 위한 Claude Code 플러그인.

50개 전문 AI 에이전트 + 34개 스킬 + 11개 레퍼런스 문서를 통해 6-Phase 설계 파이프라인(Research → Architecture → μArch → RTL → Verify → Design Note)을 자동화합니다.

## Quick Start

```bash
# 1. 설치
claude plugin marketplace add https://github.com/babyworm/rtl-agent-team.git
claude plugin install rtl-agent-team@rtl-agent-marketplace

# 2. 환경 점검
/rtl-agent-team:rtl-setup

# 3. 전체 자동화 (또는 "H.264 TQ 서브시스템 설계해줘")
/rtl-agent-team:rtl-autopilot
```

## 설치

### CLI에서 설치 (권장)

```bash
claude plugin marketplace add https://github.com/babyworm/rtl-agent-team.git
claude plugin install rtl-agent-team@rtl-agent-marketplace
```

### 대안: 개발용 로컬 심볼릭 링크

플러그인 소스를 직접 수정하며 개발할 때:

```bash
git clone https://github.com/babyworm/rtl-agent-team.git
ln -s "$(pwd)/rtl-agent-team" ~/.claude/plugins/local/rtl-agent-team
```

### 대안: Claude Code 대화창

```
/plugin marketplace add babyworm/rtl-agent-team
/plugin install rtl-agent-team@rtl-agent-marketplace
```

> GitHub public repo shorthand 방식. 설치 확인: `/plugin`

## 사용법

### 전체 자동화

```
/rtl-agent-team:rtl-autopilot
```

6-Phase 파이프라인 전체를 자동 실행합니다. 또는 자연어로 "H.264 TQ 서브시스템 설계해줘"라고 요청할 수 있습니다.

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

전체 34개 스킬 목록은 `skills/` 디렉토리를 참조하세요.

## 프로젝트 산출물 구조

각 Phase의 설계 산출물(`docs/`)은 다음 Phase의 입력이 되는 파이프라인을 형성합니다.
상위 스펙 준수 여부 verdict(`reviews/`)는 별도로 관리됩니다.

```
docs/phase-1-research/ ──→ docs/phase-2-architecture/ ──→ docs/phase-3-uarch/
        ──→ docs/phase-4-rtl/ ──→ docs/phase-5-verify/ ──→ docs/phase-6-design-note/
        ──→ docs/phase-7-exploration/ (선택적, 자유 탐색)
```

| 디렉토리 | 역할 | 비고 |
|----------|------|------|
| `docs/phase-N-*/` | Phase별 설계 문서 (가이드 파이프라인) | Phase N → Phase N+1 입력 |
| `reviews/phase-N-*/` | 상위 스펙 준수 verdict (PASS/FAIL) | 데이터 없이 판정만 |
| `rtl/src/` | RTL SystemVerilog 소스코드 | Phase 4 코드 산출물 |
| `tb/unit/`, `tb/formal/` | 테스트벤치 | Phase 4-5 코드 산출물 |
| `ref_model/` | C++ 골든 레퍼런스 모델 | Phase 2 코드 산출물 |

## 플러그인 구조

```
rtl-agent-team/
├── .claude-plugin/
│   ├── plugin.json             # 플러그인 매니페스트 (auto-discovery)
│   └── marketplace.json        # 마켓플레이스 정의
├── CLAUDE.md                   # 6-Phase 파이프라인 규칙
├── agents/                     # 50개 에이전트 (설계/검증/리뷰/EDA/도메인)
├── skills/                     # 34개 스킬 (SKILL.md + templates/ + examples/)
│   ├── systemverilog/          # RTL 코딩 컨벤션 (lowRISC + 오버라이드)
│   ├── systemverilog-assertion/ # SVA 코딩 컨벤션 (bind, SymbiYosys)
│   ├── uvm/                    # UVM 코딩 컨벤션 (factory, TLM, coverage)
│   └── systemc/                # SystemC/TLM-2.0 (AT non-blocking, AMBA-PV)
├── references/                 # 11개 상세 레퍼런스 문서
│   ├── coding-style-guide.md   # SV 명명 규칙 상세
│   ├── axi-protocol-rules.md   # AXI4 채널별 SVA 템플릿
│   ├── sva-patterns.md         # SVA 시간 연산자 + 패턴 라이브러리
│   ├── cocotb-ecosystem.md     # cocotb API, cocotb-bus, coverage
│   └── ...                     # + 7개 (CDC, UVM, Yosys, SDC 등)
├── docker/                     # EDA 도구 Docker 이미지
│   └── Dockerfile              # 오픈소스 EDA 전체 번들
└── domain-packages/            # 도메인 지식 패키지
    └── video-codec/            # H.264/H.265 지식, 적합성 데이터
```

## 에이전트 팀

### 에이전트 구성 (50개, 전체 Opus)

| 카테고리 | 에이전트 수 | 주요 에이전트 |
|---------|-----------|-------------|
| 설계 | 8 | spec-analyst, arch-designer, rtl-architect, uarch-designer, rtl-coder, rtl-critic, rtl-planner, rtl-explorer |
| 검증 | 7 | testbench-dev, func-verifier, perf-verifier, sva-extractor, protocol-checker, coverage-analyst, waveform-analyzer |
| 전문 리뷰 | 15 | cdc-reviewer, protocol-reviewer, formal-reviewer, power-analyzer, synthesis-reviewer, uvm-reviewer, cocotb-reviewer, ref-model-reviewer, requirement-tracer, regression-analyzer, equivalence-checker, integration-verifier, dft-designer, clock-architect, security-reviewer |
| EDA/합성 | 6 | eda-runner, synthesis-reporter, lint-checker, constraint-writer, timing-advisor, cdc-checker |
| 인프라 | 3 | ipxact-generator, bfm-dev, ref-model-dev |
| 도메인 전문가 | 7 | vcodec-chief-standard-expert, vcodec-syntax-entropy-expert, vcodec-prediction-expert, vcodec-transform-quant-expert, vcodec-filter-recon-expert, vcodec-architecture-expert, video-processing-expert |

### 6-Phase 파이프라인 (+Phase 7 선택적 탐색)

| Phase | 이름 | 주요 에이전트 | docs/ 산출물 | reviews/ verdict |
|-------|------|-------------|-------------|-----------------|
| 1 | Research | spec-analyst | requirements.json, io_definition.json, domain-analysis.md | research-review.md |
| 2 | Architecture + Ref Model | arch-designer, ref-model-dev | architecture.md | architecture-review.md |
| 3 | μArch + BFM | uarch-designer, bfm-dev | {module}.md (모듈별) | uarch-review.md |
| 4 | RTL + Unit Test | rtl-coder, lint-checker | module-descriptions.md, unit-test-design.md | design-review.md |
| 5 | Verify | func-verifier, sva-extractor | unit-test-report.md, lint-report.md 등 5개 | final-compliance.md |
| 6 | Design Note | code-quality-reviewer, design-note-writer | design-note.md, improvements.md | code-review.md, design-review.md |
| 7 | Exploration (선택) | improvement-analyst | exploration-notes.md | exploration-review.md |

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
| 상세 레퍼런스 | `references/*.md` | 명령 레퍼런스, 패턴 라이브러리, 프로토콜 상세 |

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

`/rtl-agent-team:rtl-setup`으로 도구 설치 상태를 확인할 수 있습니다.

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

Claude Code에서도 빌드 가능: "EDA 도커 이미지 만들어줘" 또는 `/rtl-agent-team:rtl-setup` 실행 후 Docker 옵션 선택.

## 개발

이 플러그인은 순수 선언형(`.md` + `.json` 파일만)으로 빌드 과정이 필요 없습니다.

```bash
git clone https://github.com/babyworm/rtl-agent-team.git
ln -s "$(pwd)/rtl-agent-team" ~/.claude/plugins/local/rtl-agent-team
```

> **참고**: 설계 산출물 이동(`specs/` → `docs/phase-1-research/` 등)은 후속 작업으로 진행됩니다.
> 현재 데모 산출물이 기존 위치에 있을 수 있습니다.

## 라이선스

MIT
