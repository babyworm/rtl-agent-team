<!-- RTL-AGENT-TEAM:START -->
# RTL Agent Team - 플러그인 지침

## 스킬 호출 규칙

RTL/HDL/FPGA/ASIC 관련 작업이 감지되면 이 플러그인의 전문 스킬을 사용한다.

| 패턴 감지 | 호출할 스킬 |
|-----------|------------|
| "RTL 설계", "verilog", "FPGA", "ASIC", "칩 설계", "rtl-autopilot" | `/rtl-agent-team:rtl-autopilot` |
| "lint", "린트" (RTL 컨텍스트) | `/rtl-agent-team:lint-check` |
| "시뮬레이션", "검증", "testbench", "cocotb" | `/rtl-agent-team:func-verify` |
| "합성", "synthesis", "yosys" | `/rtl-agent-team:synth-check` |
| "formal", "SVA", "assertion" | `/rtl-agent-team:sva-check` |
| "아키텍처 설계" (RTL 컨텍스트) | `/rtl-agent-team:arch-design` |
| "CDC", "clock domain" | `/rtl-agent-team:cdc-verify` |
| "AXI", "APB", "AHB", "프로토콜" (RTL 컨텍스트) | `/rtl-agent-team:protocol-verify` |
| "커버리지", "coverage" | `/rtl-agent-team:coverage-analyze` |
| "setup", "초기화", "프로젝트 시작", "init" | `/rtl-agent-team:rtl-setup` |

## 절대 규칙

1. 사양서 없이 RTL 코딩 시작 금지 (spec-analyst 먼저)
2. Reference Model 없이 Testbench 작성 금지
3. RTL 코딩 없이 합성 실행 금지
4. Lint 통과 없이 Formal 검증 실행 금지

## IMPORTANT — 상위 스펙 준수 원칙 (Hierarchical Spec Compliance)

> **이 원칙은 모든 Phase, 모든 에이전트, 모든 리뷰에 적용되는 최상위 규칙이다.**
>
> **하위 단계는 상위 단계의 스펙을 절대 위반할 수 없다.**
>
> ```
> 요구사항(Spec) → Architecture → μArch → RTL → Verification
>     ↑ 각 단계는 왼쪽 단계의 결정을 반드시 준수한다
> ```
>
> 1. **Architecture는 Spec의 요구 기능을 모두 구현해야 한다.**
>    - 아키텍처 편의를 위해 요구 기능을 삭제하거나 축소하는 것은 금지
>    - 기능 변경이 필요하면 Spec 단계로 되돌아가 사용자 승인을 받아야 한다
>
> 2. **μArch는 Architecture의 블록 경계와 인터페이스를 준수해야 한다.**
>    - 타이밍/설계 편의를 위해 블록 경계를 임의로 변경하는 것은 금지
>    - 블록 분할 변경이 필요하면 Architecture 단계로 되돌아가야 한다
>
> 3. **RTL은 μArch의 설계를 충실히 구현해야 한다.**
>    - 구현 편의를 위해 기능을 생략하거나 인터페이스를 변경하는 것은 금지
>
> 4. **Verification은 원래 Spec의 요구사항 기준으로 검증한다.**
>    - 테스트가 RTL에 맞춰져서는 안 된다 — Spec에 맞춰야 한다
>
> **설계 우선순위 (RTL 품질 판단 기준):**
>
> | 우선순위 | 항목 | 설명 |
> |---------|------|------|
> | 1 (최고) | **기능 정확성** | Spec의 모든 요구 기능이 정확히 동작하는가? |
> | 2 | **인터페이스 준수** | 포트, 프로토콜, 타이밍 인터페이스가 Architecture와 일치하는가? |
> | 3 | **타이밍/성능** | throughput, latency, 클럭 주파수 목표를 달성하는가? |
> | 4 | **면적/전력** | 리소스 사용이 합리적인가? |
>
> **Phase Gate 리뷰 시 반드시 확인할 사항:**
> - 상위 스펙 대비 기능 누락 여부 (Feature Coverage Checklist)
> - 상위 스펙 대비 인터페이스 변경 여부
> - 변경이 있다면: 정당한 사유 + 사용자 승인 여부

## 5-Phase 설계 파이프라인

```
Phase 1: Research    → 자연어 스펙 분석, 도메인 지식 적용
Phase 2: Arch/Ref    → 블록 아키텍처 + Reference Model 개발
Phase 3: μArch/TLM   → 마이크로아키텍처 + BFM 개발
Phase 4: RTL         → 합성 가능한 SystemVerilog 구현
Phase 5: Verify      → SV 유닛(1차) → cocotb Regression(2차) → 합성
```

## 위임 규칙

RTL 작업은 반드시 전문 에이전트에 위임한다. `.sv`, `.v`, `.vhd` 파일을 다루거나 EDA 도구를 사용하는 작업에 적용된다.

| 작업 유형 | 위임 대상 에이전트 | 모델 |
|----------|-----------------|------|
| 사양서 분석 | `rtl-agent-team:spec-analyst` | Opus |
| 아키텍처 설계 | `rtl-agent-team:arch-designer` | Opus |
| 아키텍처 리뷰 | `rtl-agent-team:rtl-architect` | Opus |
| μArch 설계 | `rtl-agent-team:uarch-designer` | Opus |
| RTL 코딩 | `rtl-agent-team:rtl-coder` | Sonnet |
| RTL 리뷰 | `rtl-agent-team:rtl-critic` | Opus |
| 기능 검증 | `rtl-agent-team:func-verifier` | Sonnet |
| 성능 검증 | `rtl-agent-team:perf-verifier` | Sonnet |
| 테스트벤치 작성 | `rtl-agent-team:testbench-dev` | Opus |
| 합성 | `rtl-agent-team:synthesis-reporter` | Sonnet |
| EDA 도구 실행 | `rtl-agent-team:eda-runner` | Sonnet |
| 린트 검사 | `rtl-agent-team:lint-checker` | Opus |
| 파형 분석 | `rtl-agent-team:waveform-analyzer` | Opus |
| 설계 계획 | `rtl-agent-team:rtl-planner` | Opus |
| 코드베이스 탐색 | `rtl-agent-team:rtl-explorer` | Sonnet |

## 코딩 컨벤션 (필수)

**기본: lowRISC SystemVerilog Coding Style Guide를 따른다.**
(참고: https://github.com/lowRISC/style-guides/blob/master/VerilogCodingStyle.md)

> **IMPORTANT — 아래 항목은 lowRISC 가이드를 override한다. 반드시 이 규칙을 우선 적용할 것.**
>
> 1. **포트 방향 prefix**: 입력 `i_`, 출력 `o_`, 양방향 `io_`
>    - lowRISC는 suffix (`_i`, `_o`)를 사용하지만, 이 프로젝트는 **prefix**를 사용한다.
>    - 예: `i_data`, `o_valid`, `io_sda` (NOT `data_i`, `valid_o`)
>
> 2. **클럭 명명**: `{domain}_clk` 형식
>    - lowRISC는 `clk_i`를 사용하지만, 이 프로젝트는 `{domain}_clk` 형식이다.
>    - 예: `sys_clk`, `pixel_clk`, `axi_clk` (NOT `clk_i`, `clk`)
>    - 단일 클럭 도메인이면 `sys_clk` 사용
>
> 3. **리셋 명명**: `{domain}_rst_n` 형식 (active-low 기본)
>    - 예: `sys_rst_n`, `pixel_rst_n` (NOT `rst_ni`)

### 파일명 규칙
- 모듈 파일: `module_name.sv`
- 패키지 파일: `module_name_pkg.sv`
- 인터페이스 파일: `module_name_if.sv`
- Testbench 파일: `tb_module_name.sv`

### 명명 규칙
- 모듈: `snake_case` (예: `axi_lite_slave`)
- 파라미터: `UPPER_SNAKE_CASE` (예: `DATA_WIDTH`)
- 로컬 파라미터: `UPPER_SNAKE_CASE` (예: `ADDR_BITS`)
- 타입: `snake_case_t` suffix (예: `state_t`, `bus_req_t`)
- enum 값: `UPPER_SNAKE_CASE` (예: `IDLE`, `WAIT_RESP`)
- 인스턴스: `u_` prefix (예: `u_fifo`, `u_arbiter`)
- generate 블록: `gen_` prefix (예: `gen_pipeline_stage`)

### SystemVerilog 코딩 규칙 (lowRISC 기반)
- `logic` 사용 (`reg`/`wire` 사용 금지)
- `always_ff` for sequential logic (non-blocking `<=`)
- `always_comb` for combinational logic (blocking `=`)
- `always_latch` 명시적 래치가 필요한 경우만 (일반적으로 사용 금지)
- No latches — every `case` must have `default`
- No `initial` blocks in synthesizable code
- One module per file, filename matches module name
- `typedef enum` / `typedef struct packed` 적극 사용
- 패키지(`_pkg.sv`)로 공유 타입 정의
- 포트 선언은 `input logic` / `output logic` 형식 (ANSI style)
- 매직 넘버 금지 — `parameter` 또는 `localparam`으로 정의

## EDA 도구 사용

`eda-runner` 에이전트가 Bash를 통해 EDA CLI 도구를 직접 실행한다:
- 시뮬레이션: `verilator`, `iverilog` (Icarus Verilog)
- 합성: `yosys`
- Formal 검증: `sby` (SymbiYosys)
- Lint: `verilator --lint-only`, `slang`
- cocotb 테스트: `make SIM=icarus TOPLEVEL=<mod> MODULE=<test>`
- SystemC: `g++ -lsystemc` (로컬 빌드)

도구 미설치 시 `eda-runner`가 설치 안내를 제공한다.
`/rtl-agent-team:rtl-setup` 스킬로 환경 점검 및 프로젝트 초기화가 가능하다.

## 상태 파일

설계 흐름 상태는 `.rtl-agent-team/state/` 하위에 저장한다:
- `.rtl-agent-team/state/rtl-design-state.json` — 설계 단계 추적
- `.rtl-agent-team/state/rtl-verification-state.json` — 검증 상태
- `.rtl-agent-team/state/rtl-lint-state.json` — 린트 상태
- `.rtl-agent-team/state/rtl-autopilot-state.json` — 파이프라인 진행 상태 (재개용)
- `.rtl-agent-team/rtl/{module}/phase-{n}-complete.json` — Phase 완료 게이트

<!-- RTL-AGENT-TEAM:END -->
