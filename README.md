# RTL Agent Team

RTL 설계 및 검증 자동화를 위한 Claude Code 플러그인.

27개 전문 AI 에이전트 + 32개 스킬을 통해 5-Phase 설계 파이프라인(Research → Architecture → μArch → RTL → Verify)을 자동화합니다.

## 설치

### Claude Code에서 설치 (권장)

Claude Code 대화창에서 다음 명령을 순서대로 실행합니다:

```
/plugin marketplace add babyworm/rtl-agent-team
```

```
/plugin install rtl-agent-team@rtl-agent-marketplace
```

설치 확인:

```
/plugin
```

### 대안: CLI에서 설치

```bash
claude plugin marketplace add https://github.com/babyworm/rtl-agent-team.git
claude plugin install rtl-agent-team@rtl-agent-marketplace
```

### 대안: 프로젝트 로컬 설치

특정 프로젝트에서만 사용하려면:

```bash
mkdir -p my-chip-project/.claude/plugins/
ln -s /path/to/rtl-agent-team my-chip-project/.claude/plugins/rtl-agent-team
```

### 대안: 개발용 로컬 심볼릭 링크

```bash
cd /path/to/rtl-agent-team
npm install && npm run build
ln -s "$(pwd)" ~/.claude/plugins/local/rtl-agent-team
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

전체 32개 스킬 목록은 `skills/` 디렉토리를 참조하세요.

## 구조

```
rtl-agent-team/
├── .claude-plugin/
│   ├── plugin.json             # 플러그인 매니페스트
│   └── marketplace.json        # 마켓플레이스 정의
├── CLAUDE.md                   # 5-Phase 파이프라인 규칙
├── hooks/hooks.json            # Hook 이벤트 와이어링
├── agents/                     # 24 core + 3 domain = 27 에이전트
│   └── domain/video-codec/     # 도메인 전문가 (H.264/H.265)
├── skills/                     # 32개 스킬 (SKILL.md)
│   ├── systemverilog/          # RTL 코딩 컨벤션
│   ├── systemverilog-assertion/ # SVA 코딩 컨벤션
│   ├── uvm/                    # UVM 코딩 컨벤션
│   └── systemc/                # SystemC/TLM 코딩 컨벤션
├── docker/                     # EDA 도구 Docker 이미지
│   └── Dockerfile              # 오픈소스 EDA 전체 번들
├── src/hooks/                  # 4개 Hook (TypeScript)
├── bridge/                     # Hook CJS 번들 (빌드 산출물)
└── domain-packages/            # 도메인 지식 패키지
    └── video-codec/            # H.264/H.265 지식, 적합성 데이터
```

## 에이전트 팀

### 모델 라우팅

| 모델 | 에이전트 수 | 역할 |
|------|-----------|------|
| Opus | 18 + 3 domain | 코딩, 분석, 리뷰, 도메인 전문 |
| Sonnet | 6 | 탐색, 실행, 리포팅 |

### 5-Phase 파이프라인

| Phase | 이름 | 주요 에이전트 |
|-------|------|-------------|
| 1 | Research | spec-analyst |
| 2 | Architecture + Ref Model | arch-designer, ref-model-dev |
| 3 | μArch + BFM | uarch-designer, bfm-dev |
| 4 | RTL Coding | rtl-coder, lint-checker |
| 5 | Verification | func-verifier, sva-extractor, synthesis-reporter |

### 코딩 컨벤션 스킬

| 스킬 | 적용 대상 | 주요 내용 |
|------|----------|----------|
| `systemverilog` | `.sv`, `.svh`, `.v`, `.vh` | lowRISC + 프로젝트 오버라이드, Power, FPGA, Pipelining |
| `systemverilog-assertion` | SVA, bind 파일 | assume/assert/cover, SymbiYosys, bind 패턴 |
| `uvm` | UVM testbench | factory, TLM 포트, coverage, phase callback |
| `systemc` | `.cpp`, `.h` (SystemC) | TLM-2.0, BFM, Ref Model, cocotb 연동 |

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

```bash
npm install
npm run build       # tsc + esbuild (hooks)
npm run dev         # tsc --watch
npm test            # vitest
```

## 라이선스

MIT
