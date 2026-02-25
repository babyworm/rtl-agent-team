<!-- RTL-AGENT-TEAM:START -->
# RTL Agent Team - 플러그인 지침

## 스킬 호출 규칙

RTL/HDL/FPGA/ASIC 관련 작업이 감지되면 이 플러그인의 전문 스킬을 사용한다.

| 패턴 감지 | 호출할 스킬 |
|-----------|------------|
| **--- 전체 파이프라인 ---** | |
| "RTL 설계", "verilog", "FPGA", "ASIC", "칩 설계", "rtl-autopilot" | `/rtl-agent-team:rtl-autopilot` |
| "setup", "초기화", "프로젝트 시작", "init" | `/rtl-agent-team:rtl-setup` |
| **--- Phase 1: Research ---** | |
| "스펙 분석", "요구사항", "논문 조사", "research" | `/rtl-agent-team:research-analyze` |
| "코덱 자문", "H.264", "H.265", "도메인 전문가" | `/rtl-agent-team:domain-consult` |
| **--- Phase 2: Architecture ---** | |
| "아키텍처 설계" (RTL 컨텍스트) | `/rtl-agent-team:arch-design` |
| "아키텍처 리뷰", "설계 리뷰" | `/rtl-agent-team:arch-review` |
| "reference model", "레퍼런스 모델", "C 모델" | `/rtl-agent-team:ref-model` |
| "BFM", "bus functional model", "SystemC 모델" | `/rtl-agent-team:bfm-develop` |
| **--- Phase 3: μArch ---** | |
| "마이크로아키텍처", "μArch", "uarch", "파이프라인 설계" | `/rtl-agent-team:uarch-design` |
| **--- 코딩 컨벤션 (확장자/Phase 자동 적용) ---** | |
| `.sv`, `.svh`, `.v`, `.vh` RTL 코드 생성 | `/rtl-agent-team:systemverilog` |
| `.sva`, SVA bind 파일, formal assertion | `/rtl-agent-team:systemverilog-assertion` |
| UVM testbench, agent, sequence 생성 | `/rtl-agent-team:uvm` |
| `.cpp`, `.h` (SystemC/TLM), Phase 2/3 | `/rtl-agent-team:systemc` |
| **--- Phase 4: RTL ---** | |
| "RTL 코딩", "모듈 구현", "SV 작성" | `/rtl-agent-team:rtl-code` |
| "리팩토링", "RTL 리팩토링", "코드 정리" (RTL 컨텍스트) | `/rtl-agent-team:rtl-refactor` |
| "문서화", "RTL 문서" | `/rtl-agent-team:rtl-document` |
| "IP 인스턴스", "IP 통합", "서브모듈 연결" | `/rtl-agent-team:ip-instantiate` |
| "IP-XACT", "ipxact", "레지스터 맵 생성" | `/rtl-agent-team:ipxact-gen` |
| "lint", "린트" (RTL 컨텍스트) | `/rtl-agent-team:lint-check` |
| "합성", "synthesis", "yosys", "SDC" | `/rtl-agent-team:synth-check` |
| **--- Phase 5: Verify ---** | |
| "시뮬레이션", "기능 검증", "testbench", "cocotb" | `/rtl-agent-team:func-verify` |
| "SV 유닛 테스트", "단위 테스트" (RTL 컨텍스트) | `/rtl-agent-team:sv-unit-test` |
| "UVM", "UVM 검증", "시퀀스", "에이전트" (UVM 컨텍스트) | `/rtl-agent-team:uvm-verify` |
| "성능 검증", "throughput", "latency 측정" | `/rtl-agent-team:perf-verify` |
| "formal", "SVA", "assertion" | `/rtl-agent-team:sva-check` |
| "CDC", "clock domain" | `/rtl-agent-team:cdc-verify` |
| "AXI", "APB", "AHB", "프로토콜" (RTL 컨텍스트) | `/rtl-agent-team:protocol-verify` |
| "커버리지", "coverage" | `/rtl-agent-team:coverage-analyze` |
| "regression", "리그레션", "다중 시드" | `/rtl-agent-team:regression-run` |
| "conformance", "적합성 테스트", "골든 비교" | `/rtl-agent-team:conformance-test` |
| "버그 재현", "bug repro", "파형 디버그" | `/rtl-agent-team:bug-repro` |
| "모델 일관성", "RTL-모델 비교", "model consistency" | `/rtl-agent-team:model-consistency` |

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
| **--- 설계 ---** | | |
| 사양서 분석 | `rtl-agent-team:spec-analyst` | Opus |
| 아키텍처 설계 | `rtl-agent-team:arch-designer` | Opus |
| 아키텍처 리뷰 | `rtl-agent-team:rtl-architect` | Opus |
| μArch 설계 | `rtl-agent-team:uarch-designer` | Opus |
| RTL 코딩 | `rtl-agent-team:rtl-coder` | Opus |
| RTL 리뷰 | `rtl-agent-team:rtl-critic` | Opus |
| 설계 계획 | `rtl-agent-team:rtl-planner` | Opus |
| 코드베이스 탐색 | `rtl-agent-team:rtl-explorer` | Sonnet |
| **--- 검증 ---** | | |
| 테스트벤치 작성 | `rtl-agent-team:testbench-dev` | Opus |
| 기능 검증 | `rtl-agent-team:func-verifier` | Sonnet |
| 성능 검증 | `rtl-agent-team:perf-verifier` | Sonnet |
| SVA 추출/작성 | `rtl-agent-team:sva-extractor` | Opus |
| 프로토콜 준수 검사 | `rtl-agent-team:protocol-checker` | Opus |
| 커버리지 분석 | `rtl-agent-team:coverage-analyst` | Opus |
| 파형 분석 | `rtl-agent-team:waveform-analyzer` | Opus |
| **--- EDA/합성 ---** | | |
| EDA 도구 실행 | `rtl-agent-team:eda-runner` | Sonnet |
| 합성 리포트 | `rtl-agent-team:synthesis-reporter` | Sonnet |
| 린트 검사 | `rtl-agent-team:lint-checker` | Opus |
| SDC 제약조건 생성 | `rtl-agent-team:constraint-writer` | Opus |
| 타이밍 분석 | `rtl-agent-team:timing-advisor` | Opus |
| CDC 분석 | `rtl-agent-team:cdc-checker` | Opus |
| **--- 인프라 ---** | | |
| IP-XACT 생성 | `rtl-agent-team:ipxact-generator` | Sonnet |
| BFM 개발 | `rtl-agent-team:bfm-dev` | Opus |
| Reference Model 개발 | `rtl-agent-team:ref-model-dev` | Opus |
| **--- 도메인 전문가 ---** | | |
| 코덱 표준 전문가 | `rtl-agent-team:codec-standards-expert` | Opus |
| 코덱 아키텍처 전문가 | `rtl-agent-team:codec-architecture-expert` | Opus |
| 비디오 처리 전문가 | `rtl-agent-team:video-processing-expert` | Opus |

## 코딩 컨벤션 (필수)

> **IMPORTANT — 핵심 오버라이드 3가지 (항상 적용)**
>
> 1. **포트 prefix**: `i_`, `o_`, `io_` (NOT suffix `_i`, `_o`)
> 2. **클럭**: `{domain}_clk` (예: `sys_clk`) — NOT `clk_i`
> 3. **리셋**: `{domain}_rst_n` (예: `sys_rst_n`) — NOT `rst_ni`

**확장자/Phase별 코딩 컨벤션 스킬 자동 적용:**

| 파일 확장자 / 컨텍스트 | 설계 Phase | 적용 스킬 |
|----------------------|-----------|----------|
| `.sv`, `.svh`, `.v`, `.vh` (RTL) | Phase 4 (RTL) | `/rtl-agent-team:systemverilog` |
| `.sv` (SVA, assertion, bind) | Phase 5 (Formal) | `/rtl-agent-team:systemverilog-assertion` |
| `.sv` (UVM testbench) | Phase 5 (UVM) | `/rtl-agent-team:uvm` |
| `.cpp`, `.h` (SystemC/TLM) | Phase 2 (Ref Model), Phase 3 (BFM) | `/rtl-agent-team:systemc` |

- `systemverilog`: lowRISC + 오버라이드, Power 최적화, FPGA, Pipelining
- `systemverilog-assertion`: SVA 패턴, bind 파일, SymbiYosys 통합, assume/assert/cover
- `uvm`: UVM 클래스 계층, factory, TLM 포트, coverage, phase callback
- `systemc`: TLM-2.0 패턴, BFM 규칙, Ref Model 규칙, cocotb 연동

## EDA 도구 사용

`eda-runner` 에이전트가 Bash를 통해 EDA CLI 도구를 직접 실행한다:
- 시뮬레이션: `verilator`, `iverilog` (Icarus Verilog)
- 합성: `yosys`
- Formal 검증: `sby` (SymbiYosys)
- Lint: `verilator --lint-only`, `verible-verilog-lint`, `slang`
- cocotb 테스트: `make SIM=icarus TOPLEVEL=<mod> MODULE=<test>`
- SystemC: `g++ -lsystemc` (로컬 빌드)

도구 미설치 시 `eda-runner`가 설치 안내를 제공한다.
`/rtl-agent-team:rtl-setup` 스킬로 환경 점검 및 프로젝트 초기화가 가능하다.

## 리뷰 산출물

각 Phase Gate 리뷰어가 생성한 리포트는 `reviews/` 디렉토리에 Markdown으로 저장한다.
블록 다이어그램, 데이터 흐름 등은 Mermaid chart로 표현한다.

```
reviews/
├── phase-1-research/
│   └── research-review.md          # 스펙 완전성 자기검증 + 실현가능성 평가
├── phase-2-architecture/
│   ├── feature-coverage.md         # Feature Coverage Checklist (REQ → Arch block 매핑)
│   ├── architecture-review.md      # rtl-architect 구조 리뷰
│   └── architecture-diagram.md     # Mermaid 블록 다이어그램
├── phase-3-uarch/
│   ├── feature-preservation.md     # Feature Preservation Checklist (Arch → μArch 매핑)
│   ├── uarch-review.md             # rtl-architect μArch 리뷰
│   └── pipeline-diagram.md         # Mermaid 파이프라인/데이터플로우 다이어그램
├── phase-4-rtl/
│   ├── functional-completeness.md  # Functional Completeness Check (REQ → RTL 매핑)
│   ├── design-review.md            # rtl-critic 설계 리뷰
│   └── lint-report.md              # lint-checker 리포트
└── phase-5-verify/
    ├── requirement-traceability.md # Requirement Traceability Matrix (REQ → Test 매핑)
    └── final-compliance.md         # 최종 스펙 준수 확인 리포트
```

### 리뷰 Markdown 형식

모든 리뷰 리포트는 다음 구조를 따른다:
```markdown
# [Phase] Review: [제목]
- Date: YYYY-MM-DD
- Reviewer: [에이전트 이름]
- Upper Spec: [참조한 상위 문서]
- Verdict: PASS | FAIL

## Feature Coverage Checklist
| REQ ID | 요구사항 | 상태 | 구현 위치 |
|--------|---------|------|----------|
| REQ-001 | ... | COVERED | module.sv:42 |
| REQ-002 | ... | MISSING | — |

## Block Diagram (Mermaid)
(해당하는 경우)

## Findings
### [severity] Finding-1: ...

## Verdict
PASS | FAIL: [사유]
```

## 상태 파일

설계 흐름 상태는 `.rtl-agent-team/state/` 하위에 저장한다:
- `.rtl-agent-team/state/rtl-design-state.json` — 설계 단계 추적
- `.rtl-agent-team/state/rtl-verification-state.json` — 검증 상태
- `.rtl-agent-team/state/rtl-lint-state.json` — 린트 상태
- `.rtl-agent-team/state/rtl-autopilot-state.json` — 파이프라인 진행 상태 (재개용)
- `.rtl-agent-team/rtl/{module}/phase-{n}-complete.json` — Phase 완료 게이트

<!-- RTL-AGENT-TEAM:END -->
