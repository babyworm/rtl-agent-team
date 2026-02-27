<!-- RTL-AGENT-TEAM:START -->
# RTL Agent Team - 플러그인 지침

## 스킬 호출 규칙

RTL/HDL/FPGA/ASIC 관련 작업이 감지되면 이 플러그인의 전문 스킬을 사용한다.

| 패턴 감지 | 호출할 스킬 |
|-----------|------------|
| **--- 전체 파이프라인 ---** | |
| "RTL 설계", "verilog", "FPGA", "ASIC", "칩 설계", "rtl-autopilot" | `/rtl-agent-team:rtl-autopilot` |
| "setup", "초기화", "프로젝트 시작", "init", "docker image", "EDA 도커" | `/rtl-agent-team:rtl-setup` |
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
| "버그 수정", "RTL 수정", "bug fix", "RTL 버그", "기능 오류" | `/rtl-agent-team:rtl-bugfix` |
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
| **--- 전문 리뷰 ---** | |
| "CDC 리뷰", "CDC 설계 리뷰", "동기화 전략 리뷰" | `cdc-reviewer` 에이전트 직접 위임 |
| "프로토콜 리뷰", "AXI 설계 리뷰", "인터페이스 리뷰" | `protocol-reviewer` 에이전트 직접 위임 |
| "formal 리뷰", "SVA 리뷰", "assertion 품질" | `formal-reviewer` 에이전트 직접 위임 |
| "전력 분석", "power analysis", "clock gating 리뷰" | `power-analyzer` 에이전트 직접 위임 |
| "합성 리뷰", "synthesis review", "면적/타이밍 리뷰" | `synthesis-reviewer` 에이전트 직접 위임 |
| "UVM 리뷰", "testbench 리뷰", "TB 품질" | `uvm-reviewer` 에이전트 직접 위임 |
| "요구사항 추적", "traceability", "feature coverage", "스펙 검증 상태" | `requirement-tracer` 에이전트 직접 위임 |
| "cocotb 리뷰", "cocotb 품질", "Python TB 리뷰" | `cocotb-reviewer` 에이전트 직접 위임 |
| "레퍼런스 모델 리뷰", "ref model 검증", "golden model 리뷰" | `ref-model-reviewer` 에이전트 직접 위임 |
| "리그레션 분석", "flaky test", "시드 분석", "커버리지 수렴" | `regression-analyzer` 에이전트 직접 위임 |
| "등가 검증", "equivalence", "RTL vs netlist" | `equivalence-checker` 에이전트 직접 위임 |
| "통합 검증", "integration", "모듈 연결 확인", "top-level" | `integration-verifier` 에이전트 직접 위임 |
| "보안 리뷰", "security", "side-channel", "fault injection" | `security-reviewer` 에이전트 직접 위임 |
| **--- EDA 전문가 ---** | |
| "DFT", "scan chain", "BIST", "JTAG", "testability" | `dft-designer` 에이전트 직접 위임 |
| "클럭 아키텍처", "clock tree", "PLL", "clock gating 리뷰" | `clock-architect` 에이전트 직접 위임 |
| **--- Phase 6: Design Note ---** | |
| "설계 리뷰", "design review", "Phase 6", "design note", "코드 리뷰 문서화" | `/rtl-agent-team:design-review-phase` |
| **--- Phase 7: Exploration (선택적) ---** | |
| "자유 탐색", "exploration", "Phase 7", "개선 탐색", "실험적 개선" | `/rtl-agent-team:design-review-phase` (탐색 모드) |
| **--- 기타 검증 ---** | |
| "regression", "리그레션", "다중 시드" | `/rtl-agent-team:regression-run` |
| "conformance", "적합성 테스트", "골든 비교" | `/rtl-agent-team:conformance-test` |
| "버그 재현", "bug repro", "파형 디버그" | `/rtl-agent-team:bug-repro` |
| "모델 일관성", "RTL-모델 비교", "model consistency" | `/rtl-agent-team:model-consistency` |

## IMPORTANT — Phase 1 요구사항 명확화 (Proactive Requirement Clarification)

> **Phase 1에서 사용자 요청이 모호하거나 불완전하면, AskUserQuestion을 적극적으로 사용하여 요구사항을 명확히 한다.**
>
> Phase 1의 목적은 완전하고 명확한 요구사항을 확보하는 것이다.
> 모호한 상태로 Phase 2에 진입하면, 아키텍처 전체를 재설계해야 할 수 있다.
>
> **AskUserQuestion을 사용해야 하는 경우:**
> - 타겟 해상도/프레임레이트/코덱이 명시되지 않은 경우
> - 인터페이스 프로토콜(AXI/APB/custom)이 지정되지 않은 경우
> - 클럭 주파수, 타이밍 제약이 불명확한 경우
> - 기능 범위가 모호한 경우 (인코더/디코더/양쪽, 지원 프로파일/레벨 등)
> - spec-analyst가 `[AMBIGUITY]` 또는 `[CONFLICT]`를 플래그한 경우
> - 도메인 전문가 간 해석이 충돌하는 경우
>
> **AskUserQuestion 사용하지 않는 경우:**
> - 사용자가 상세한 스펙 문서를 이미 제공한 경우
> - 표준에서 유일한 해석이 존재하는 경우
> - 설계 관례로 결정 가능한 사항 (예: active-low 리셋)
>
> **흐름:**
> ```
> 사용자 요청 수신 → 요구사항 완전성 판단 → 부족하면 AskUserQuestion
> → 답변 반영 → spec-analyst/도메인 전문가 위임 → [AMBIGUITY] 발견 시 재질문
> → 요구사항 확정 → Phase 2 진행
> ```

## 절대 규칙

1. 사양서 없이 RTL 코딩 시작 금지 (spec-analyst 먼저)
2. Reference Model 없이 Testbench 작성 금지
3. RTL 코딩 없이 합성 실행 금지
4. Lint 통과 없이 Formal 검증 실행 금지
5. **RTL 수정 후 기능 검증 없이 완료 선언 금지** (lint만으로는 불충분)
6. **Phase 4 완료 시 모듈별 unit test 없이 Phase 5 진행 금지** (tb/unit/tb_{module}.sv 필수)
7. **Phase 5 FAIL 시 최대 2회 Phase 4 feedback loop 허용, 초과 시 user 에스컬레이션**
8. **Phase 5 PASS 없이 Phase 6 진행 금지** (final-compliance.md verdict=PASS 필수)
9. **Phase 7은 절대 규칙에서 면제된다** — 파이프라인 Gate 없이 자유 탐색 허용

## IMPORTANT — RTL 수정 후 필수 검증 (Mandatory Verification After RTL Changes)

> **이 규칙은 .sv/.svh/.v/.vh 파일을 수정하는 모든 작업에 적용된다.**
>
> **lint 통과 ≠ 기능 정확성 검증. lint는 필요 조건이지 충분 조건이 아니다.**
>
> RTL 파일 수정 시 다음 4단계를 반드시 완료해야 한다:
>
> | 단계 | 내용 | 필수 여부 |
> |------|------|----------|
> | 1. 수정 | RTL 코드 변경 | 필수 |
> | 2. Lint | `verilator --lint-only -Wall` 통과 | 필수 |
> | 3. TB | 수정된 모듈의 테스트벤치 생성 또는 업데이트 | **필수** |
> | 4. 기능 검증 | cocotb/verilator 시뮬레이션 실행 및 PASS | **필수** |
>
> **Hook 기반 강제 메커니즘:**
> - `PostToolUse:Edit/Write` 훅이 .sv 파일 수정을 자동 추적
> - `Stop` 훅이 기능 검증 없이 세션 종료 시 차단
> - 검증 완료 시 `touch .rtl-agent-team/state/rtl-verify-done`으로 게이트 해제
> - 검증이 불필요한 경우 (주석만 변경 등): `touch .rtl-agent-team/state/rtl-verify-waiver`
>
> **Anti-pattern (금지):**
> ```
> RTL 수정 → lint 통과 → "완료" ← 이것은 완료가 아님
> ```
>
> **올바른 흐름:**
> ```
> RTL 수정 → lint 통과 → TB 생성/업데이트 → 시뮬레이션 PASS → "완료"
> ```
>
> | 5. Phase 5 연동 | Phase 5 FAIL 시 자동 feedback → rtl-bugfix → 수정 → 재검증 (max 2회) | 자동 |
>
> 이 규칙을 스킬로 구조화한 것이 `/rtl-agent-team:rtl-bugfix`이다.

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

## 6-Phase 설계 파이프라인 (+Phase 7 선택적 탐색)

각 Phase의 설계 산출물은 `docs/phase-N-*/`에 저장되며, 다음 Phase의 입력(가이드)으로 사용된다.
상위 스펙 준수 여부 검증 결과(verdict)는 `reviews/phase-N-*/`에 저장된다.

```
Phase 1: Research    → docs/phase-1-research/      (자연어 스펙, 도메인 지식)
Phase 2: Arch/Ref    → docs/phase-2-architecture/   (블록 아키텍처) + ref_model/ (C++ 골든)
Phase 3: μArch/TLM   → docs/phase-3-uarch/         (마이크로아키텍처) + BFM
Phase 4: RTL+Unit    → rtl/src/ + tb/unit/ + docs/phase-4-rtl/ (모듈 설계문서, 유닛 설계)
Phase 5: Verify      → tb/formal/ + docs/phase-5-verify/ (검증 리포트, lint, 합성추정)
Phase 6: Design Note → docs/phase-6-design-note/    (설계문서, 개선 권고)
Phase 7: Exploration → docs/phase-7-exploration/    (자유 탐색, 파이프라인 규칙 미적용)
```

> **Phase 7은 선택적 단계이다.** 파이프라인 절대 규칙(Phase Gate)이 적용되지 않으며,
> 기존 설계의 개선점을 자유롭게 탐색하는 과정이다.

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
| 코드베이스 탐색 | `rtl-agent-team:rtl-explorer` | Opus |
| **--- 검증 ---** | | |
| 테스트벤치 작성 | `rtl-agent-team:testbench-dev` | Opus |
| 기능 검증 | `rtl-agent-team:func-verifier` | Opus |
| 성능 검증 | `rtl-agent-team:perf-verifier` | Opus |
| SVA 추출/작성 | `rtl-agent-team:sva-extractor` | Opus |
| 프로토콜 준수 검사 | `rtl-agent-team:protocol-checker` | Opus |
| 커버리지 분석 | `rtl-agent-team:coverage-analyst` | Opus |
| 파형 분석 | `rtl-agent-team:waveform-analyzer` | Opus |
| **--- 전문 리뷰 ---** | | |
| CDC 설계 리뷰 | `rtl-agent-team:cdc-reviewer` | Opus |
| 프로토콜 설계 리뷰 | `rtl-agent-team:protocol-reviewer` | Opus |
| Formal 품질 리뷰 | `rtl-agent-team:formal-reviewer` | Opus |
| 전력 분석 | `rtl-agent-team:power-analyzer` | Opus |
| 합성 결과 리뷰 | `rtl-agent-team:synthesis-reviewer` | Opus |
| UVM TB 품질 리뷰 | `rtl-agent-team:uvm-reviewer` | Opus |
| 요구사항 추적성 | `rtl-agent-team:requirement-tracer` | Opus |
| cocotb TB 품질 리뷰 | `rtl-agent-team:cocotb-reviewer` | Opus |
| 레퍼런스 모델 리뷰 | `rtl-agent-team:ref-model-reviewer` | Opus |
| 리그레션 분석 | `rtl-agent-team:regression-analyzer` | Opus |
| 등가 검증 | `rtl-agent-team:equivalence-checker` | Opus |
| 통합 검증 | `rtl-agent-team:integration-verifier` | Opus |
| 하드웨어 보안 리뷰 | `rtl-agent-team:security-reviewer` | Opus |
| **--- Phase 6: Design Note ---** | | |
| 코드 품질 심층 리뷰 | `rtl-agent-team:code-quality-reviewer` | Opus |
| 설계 품질 리뷰 | `rtl-agent-team:design-quality-reviewer` | Opus |
| 설계 문서 작성 | `rtl-agent-team:design-note-writer` | Opus |
| 개선 분석 | `rtl-agent-team:improvement-analyst` | Opus |
| **--- EDA/합성 ---** | | |
| EDA 도구 실행 | `rtl-agent-team:eda-runner` | Opus |
| 합성 메트릭 추출 | `rtl-agent-team:synthesis-reporter` | Opus |
| 린트 검사 | `rtl-agent-team:lint-checker` | Opus |
| SDC 제약조건 생성 | `rtl-agent-team:constraint-writer` | Opus |
| 타이밍 분석 (STA) | `rtl-agent-team:timing-advisor` | Opus |
| CDC 정적 분석 | `rtl-agent-team:cdc-checker` | Opus |
| 클럭 아키텍처 리뷰 | `rtl-agent-team:clock-architect` | Opus |
| DFT 설계 | `rtl-agent-team:dft-designer` | Opus |
| **--- 인프라 ---** | | |
| IP-XACT 생성 | `rtl-agent-team:ipxact-generator` | Opus |
| BFM 개발 | `rtl-agent-team:bfm-dev` | Opus |
| Reference Model 개발 | `rtl-agent-team:ref-model-dev` | Opus |
| **--- 도메인 전문가 ---** | | |
| 코덱 Chief 전문가 | `rtl-agent-team:vcodec-chief-standard-expert` | Opus |
| 구문/엔트로피 전문가 | `rtl-agent-team:vcodec-syntax-entropy-expert` | Opus |
| 예측 전문가 | `rtl-agent-team:vcodec-prediction-expert` | Opus |
| 변환/양자화 전문가 | `rtl-agent-team:vcodec-transform-quant-expert` | Opus |
| 필터/복원 전문가 | `rtl-agent-team:vcodec-filter-recon-expert` | Opus |
| 코덱 아키텍처 전문가 | `rtl-agent-team:vcodec-architecture-expert` | Opus |
| 비디오 처리 전문가 | `rtl-agent-team:video-processing-expert` | Opus |

## 코딩 컨벤션 (필수)

> **IMPORTANT — 언어 표준 (프로젝트 기본)**
>
> | 언어 | 표준 | 비고 |
> |------|------|------|
> | **SystemVerilog (RTL)** | **IEEE 1800-2009** | 합성 가능 RTL 코드의 기준. 2012 이후 추가 기능은 검증 전용 |
> | **SystemVerilog (검증)** | **IEEE 1800-2012** | SVA, UVM TB에서 2012 기능 허용 (checker, interface class 등) |
> | **C++ (Ref Model, BFM)** | **C++17** (`-std=c++17`) | SystemC 3.0, cocotb DPI 등 모든 C++ 코드에 적용 |
>
> - iverilog 플래그는 `-g2012` 사용 (SV 기본 문법 지원)
> - **iverilog 미지원**: `interface`, unpacked `struct`/`union` — 에이전트 생성 금지
> - `typedef struct packed` / `typedef union packed`는 지원됨 (사용 가능)
> - 사용자가 직접 추가하거나 기존 코드에 존재하는 경우 수정하지 않는다
> - verilator/slang은 기본 설정으로 2009 기능을 완전 지원
> - 2012 이후 합성 관련 추가 기능 없음 (2017은 errata만, 2023은 도구 지원 초기)

> **IMPORTANT — 핵심 오버라이드 (항상 적용)**
>
> 1. **포트 prefix**: `i_`, `o_`, `io_` 필수 (NOT suffix `_i`, `_o`). 단, **클럭과 리셋은 예외** (prefix 불필요)
> 2. **클럭**: `clk` (단일) 또는 `{domain}_clk` (다중, 예: `sys_clk`) — NOT `clk_i`. `i_` prefix 불필요
> 3. **리셋**: `rst_n` (단일) 또는 `{domain}_rst_n` (다중, 예: `sys_rst_n`) — NOT `rst_ni`. Active-low 비동기 리셋 필수. `i_` prefix 불필요
> 4. **CamelCase 전면 금지**: Parameter → `ALL_CAPS` (`DATA_WIDTH`). 내부 localparam → `L_` prefix (`L_ADDR_BITS`). Enum 값 → `ALL_CAPS` (`ST_IDLE`). 모든 식별자는 `snake_case` 또는 `ALL_CAPS`만 허용
> 5. **UVM 예외**: UVM 클래스 내부 멤버 핸들은 `m_` prefix 허용 (업계 관행). `u_`는 RTL 인스턴스 전용

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
- `systemc`: TLM-2.0 AT non-blocking, AMBA-PV (AXI/AHB/APB), Memory Manager, PEQ, cocotb 연동

## EDA 도구 사용

`eda-runner` 에이전트가 Bash를 통해 EDA CLI 도구를 직접 실행한다:
- 시뮬레이션: `verilator`, `iverilog` (Icarus Verilog)
- 합성: `yosys`
- Formal 검증: `sby` (SymbiYosys)
- Lint: `verilator --lint-only`, `verible-verilog-lint`, `slang`
- cocotb 테스트: `make SIM=icarus TOPLEVEL=<mod> MODULE=<test>`
- SystemC: `g++ -lsystemc` (로컬 빌드)
- 파형 뷰어: `gtkwave` (VCD/FST 파형 분석)

도구 미설치 시 `eda-runner`가 설치 안내를 제공한다.
`/rtl-agent-team:rtl-setup` 스킬로 환경 점검 및 프로젝트 초기화가 가능하다.

## 산출물 구조

설계 산출물은 두 가지로 분리된다:
- **`docs/`** = Phase별 설계 문서. Phase N의 산출물이 Phase N+1의 가이드/입력이 되는 파이프라인
- **`reviews/`** = 상위 스펙/요구사항 준수 여부만 검증하는 verdict 문서

### docs/ — 설계 산출물 (Phase 가이드 파이프라인)

```
docs/
├── phase-1-research/                    # → Phase 2의 입력
│   ├── requirements.json                # 요구사항 목록
│   ├── io_definition.json               # I/O 포트 스펙
│   └── domain-analysis.md               # 도메인 분석 (알고리즘, 표준)
├── phase-2-architecture/                # → Phase 3의 입력
│   └── architecture.md                  # 블록 아키텍처 (모듈 계층, 데이터패스, 타이밍)
├── phase-3-uarch/                       # → Phase 4의 입력
│   └── {module_name}.md                 # 모듈별 마이크로아키텍처
├── phase-4-rtl/                         # → Phase 5의 입력
│   ├── module-descriptions.md           # 모듈별 설계 요약 (포트, 기능, 의존관계)
│   └── unit-test-design.md              # 단위 테스트 설계 (테스트 전략, 커버리지 목표)
├── phase-5-verify/                      # → Phase 6의 입력
│   ├── unit-test-report.md              # 유닛 테스트 결과 요약
│   ├── integration-report.md            # 통합 테스트 결과
│   ├── ref-model-consistency.md         # RTL vs C++ 골든 모델 정합성 비교
│   ├── lint-report.md                   # Verilator lint 결과 요약
│   └── synthesis-estimate.md            # Yosys 합성 추정치 (면적, 타이밍)
├── phase-6-design-note/                 # 최종 설계 문서
│   ├── design-note.md                   # 상세 설계 문서 (알고리즘, HW 구현, 트레이드오프)
│   └── improvements.md                  # 개선 권고사항 (must-fix, should-fix, nice-to-have)
└── phase-7-exploration/                 # 자유 탐색 (파이프라인 규칙 미적용)
    └── exploration-notes.md             # 개선점 탐색, 실험적 아이디어
```

### reviews/ — 검증 verdict (상위 스펙 준수 확인)

```
reviews/
├── phase-1-research/
│   └── research-review.md               # 스펙 완전성 + 실현가능성 verdict
├── phase-2-architecture/
│   └── architecture-review.md           # Arch가 Spec 준수하는지 verdict
├── phase-3-uarch/
│   └── uarch-review.md                  # μArch가 Arch 준수하는지 verdict
├── phase-4-rtl/
│   └── design-review.md                 # RTL이 μArch 준수하는지 verdict
├── phase-5-verify/
│   └── final-compliance.md              # 원래 Spec 기준 최종 준수 verdict
├── phase-6-review/
│   ├── code-review.md                   # 코드 품질 verdict
│   └── design-review.md                 # 설계 품질 verdict
└── phase-7-exploration/
    └── exploration-review.md            # 탐색 결과 리뷰 verdict
```

### 코드 산출물

```
rtl/src/                                 # RTL 소스코드 (Phase 4)
tb/                                      # 테스트벤치 (Phase 4-5)
├── unit/                                # 단위 테스트
└── formal/                              # SVA formal 검증
ref_model/                               # C++ 골든 레퍼런스 (Phase 2)
```

> **원칙**: `docs/`에는 데이터/수치/설계 내용을, `reviews/`에는 verdict(PASS/FAIL)만 저장한다.
> 예: formal 검증 데이터는 `docs/phase-5-verify/`에, 스펙 준수 판정은 `reviews/phase-5-verify/final-compliance.md`에.

### 리뷰 Markdown 형식

모든 verdict 리포트(`reviews/`)는 다음 구조를 따른다:
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

## Findings
### [severity] Finding-1: ...

## Verdict
PASS | FAIL: [사유]
```

## 상태 파일

설계 흐름 상태는 `.rtl-agent-team/state/` 하위에 저장한다:
- `.rtl-agent-team/state/rtl-autopilot-state.json` — 파이프라인 진행 상태 (재개용)
- `.rtl-agent-team/rtl/{module}/phase-{n}-complete.json` — Phase 완료 게이트

<!-- RTL-AGENT-TEAM:END -->
