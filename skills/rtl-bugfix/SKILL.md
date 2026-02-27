---
name: rtl-bugfix
description: "RTL 버그 수정 워크플로우. 분석→수정→lint→TB 생성/업데이트→기능 검증의 전체 사이클을 강제합니다. RTL 수정이 lint만으로 완결되는 것을 방지합니다."
---

<Purpose>
RTL 버그를 수정할 때 설계→검증 흐름을 강제하는 워크플로우 스킬.
단순 lint 통과가 아닌, TB 생성과 기능 시뮬레이션까지 완료해야 수정이 완결된 것으로 판정.

**핵심 원칙: lint는 문법 검사일 뿐, 기능 정확성의 증거가 아니다.**

이 스킬은 PostToolUse:Edit 훅의 추적 시스템과 연동됩니다.
수정된 .sv 파일은 자동 추적되며, 기능 검증 없이 세션 종료가 차단됩니다.
</Purpose>

<Use_When>
- Phase 4 리뷰에서 발견된 RTL 버그 수정
- RTL 모듈의 기능 오류 수정
- 기존 RTL에 기능 추가 또는 변경
- 리팩토링 후 기능 회귀 확인
- 여러 모듈에 걸친 통합 버그 수정
- **Phase 5→4 Feedback Loop**: Phase 5 검증 FAIL 시 자동 호출되는 수정 경로
</Use_When>

<Do_Not_Use_When>
- 코딩 컨벤션만 변경 (포트 이름 변경 등 기능 무변경) → rtl-refactor 사용
- 새 모듈 처음 작성 → rtl-code 사용
- 단순 lint 에러 수정 (미사용 신호 제거 등) → lint-check 사용
</Do_Not_Use_When>

<Why_This_Exists>
이전 세션에서 9개 RTL 버그를 수정하면서 lint만 수행하고 TB/시뮬레이션을 건너뛴 경험에서 탄생.
lint 통과는 "컴파일 성공"일 뿐이며, 수정된 기능이 올바른지 증명하려면 반드시 시뮬레이션이 필요.

**Anti-pattern 사례:**
- 5개 Wave에 걸쳐 312줄 RTL 수정 → verilator --lint-only만 실행 → TB 0개, sim 0회
- 결과: 기능 정확성이 전혀 검증되지 않은 채 "완료"로 판정됨
</Why_This_Exists>

<Execution_Policy>
- 4단계 필수 순서: 분석 → 수정+lint → TB → 기능 검증
- 각 단계는 이전 단계 완료 후에만 진행 가능
- TB가 이미 존재하는 경우: 기존 TB 업데이트 (새 테스트 케이스 추가)
- TB가 없는 경우: 최소 smoke test TB 생성 필수
- 기능 검증 PASS 후에만 검증 완료 마커 생성
- Stop hook이 검증 완료 마커를 확인하여 세션 종료 허용
</Execution_Policy>

<Steps>
1. **분석 단계**: 버그 이해 및 영향 범위 파악
   - rtl-explorer로 관련 모듈/신호 탐색
   - 버그의 root cause 식별
   - 영향받는 모듈 목록 작성
   - 수정 계획 수립 (어떤 파일, 어떤 변경)

2. **수정+lint 단계**: RTL 코드 수정 및 문법 검증
   - rtl-coder가 버그 수정 구현
   - lint-checker가 수정된 파일에 lint 실행: `verilator --lint-only -Wall`
   - lint 에러 시 수정 반복 (최대 3회)
   - **이 단계는 필요 조건이지 충분 조건이 아님**

3. **TB 생성/업데이트 단계**: 수정 사항을 검증할 테스트 작성
   - 기존 TB 확인: `ls tb/cocotb/test_*.py tb/unit/*.sv 2>/dev/null`
   - **TB가 없는 경우**: testbench-dev가 최소 smoke test TB 생성
     - 수정된 모듈당 최소 1개 테스트 파일
     - 버그 재현 시나리오를 테스트 케이스로 포함
   - **TB가 있는 경우**: testbench-dev가 버그 관련 테스트 케이스 추가
     - 버그 트리거 조건을 재현하는 테스트 벡터
     - 수정 후 정상 동작을 확인하는 assertion
   - TB 신호 이름 규칙: `dut.sys_clk`, `dut.i_*`, `dut.o_*`

4. **기능 검증 단계**: 시뮬레이션 실행 및 결과 확인
   - eda-runner가 시뮬레이션 실행:
     ```bash
     # cocotb (Python TB)
     make -C tb/cocotb SIM=icarus TOPLEVEL={module} MODULE=test_{module}
     # 또는 Verilator sim
     verilator --cc --exe --build --trace rtl/src/{module}.sv tb/sim_main.cpp
     ```
   - 실패 시: waveform-analyzer로 파형 디버그
   - **모든 테스트 PASS** 확인
   - 검증 완료 마커 생성:
     ```bash
     touch .rtl-agent-team/state/rtl-verify-done
     ```
   - 이 마커가 있어야 Stop hook이 세션 종료를 허용함

5. **(Phase 5→4 Feedback Mode)**: Phase 5 sub-phase 복귀
   - `feedback_origin`이 지정된 경우 (e.g., "5a-formal", "5b-cdc", "5c-integration")
   - 수정 완료 후 검증 완료 마커 생성: `touch .rtl-agent-team/state/rtl-verify-done`
   - rtl-autopilot에 복귀 신호: Phase 5 해당 sub-phase 재실행 요청
   - feedback_origin이 없으면 이 단계는 건너뜀 (일반 버그 수정 모드)
   - **FAIL 유형별 처리:**
     - UNIT_FIX: 단일 모듈 수정 → lint → unit TB → unit sim → PASS 후 복귀
     - INTEGRATION_FIX: 다중 모듈 수정 → lint → unit TB + integration TB → sim → PASS 후 복귀

6. **(선택) 리뷰 리포트 저장**
   - 복잡한 버그의 경우 `reviews/` 디렉토리에 수정 리포트 저장
   - 버그 원인, 수정 내용, 검증 결과 기록
</Steps>

<Tool_Usage>
```
# ============================================================
# Step 1: 분석
# ============================================================
Task(subagent_type="rtl-agent-team:rtl-explorer",
     prompt="Analyze bug: [bug description]. Identify affected modules, root cause, and impact scope in rtl/src/. List all files that need modification.")

# ============================================================
# Step 2: 수정 + lint
# ============================================================
Task(subagent_type="rtl-agent-team:rtl-coder",
     prompt="Fix bug in rtl/src/{module}.sv: [fix description]. Follow coding conventions: i_/o_ port prefix, sys_clk/sys_rst_n, logic only, always_ff/always_comb. After fix, run: verilator --lint-only -Wall rtl/src/{module}.sv")

# ============================================================
# Step 3: TB 생성/업데이트
# ============================================================
# 기존 TB 확인
Bash("ls tb/cocotb/test_*.py tb/unit/*.sv 2>/dev/null || echo 'NO_TB_EXISTS'")

# TB 없는 경우: 새로 생성
Task(subagent_type="rtl-agent-team:testbench-dev",
     prompt="Create cocotb smoke test for rtl/src/{module}.sv at tb/cocotb/test_{module}.py. Include: (1) basic reset sequence, (2) bug reproduction scenario: [describe], (3) normal operation check. Signal naming: dut.sys_clk, dut.sys_rst_n, dut.i_*/dut.o_*.")

# TB 있는 경우: 테스트 케이스 추가
Task(subagent_type="rtl-agent-team:testbench-dev",
     prompt="Add test case to tb/cocotb/test_{module}.py for bug fix verification: [describe bug and fix]. Add assertion checking correct behavior after fix. Signal naming: dut.sys_clk, dut.sys_rst_n, dut.i_*/dut.o_*.")

# ============================================================
# Step 4: 기능 검증 실행
# ============================================================
Task(subagent_type="rtl-agent-team:eda-runner",
     prompt="Run cocotb test via Bash CLI: make -C tb/cocotb SIM=icarus TOPLEVEL={module} MODULE=test_{module}. Report pass/fail. On failure, capture waveform for debug.")

# 모든 테스트 PASS 시 검증 완료 마커 생성
Bash("touch .rtl-agent-team/state/rtl-verify-done")

# ============================================================
# Step 5: Phase 5→4 Feedback Mode (feedback_origin 지정 시)
# ============================================================
# Phase 5 sub-phase에서 FAIL 후 rtl-bugfix가 호출된 경우:
# feedback_origin이 지정되면, 수정 완료 후 Phase 5 해당 sub-phase로 복귀
#
# Example: Phase 5a formal verification FAIL
# → rtl-bugfix 호출 (feedback_origin=5a-formal)
# → Step 1-4 실행 (분석 → 수정 → lint → TB → sim)
# → Step 5: verify-done 마커 생성 + Phase 5a 재실행 요청
#
# feedback_origin이 없으면 Step 5는 건너뜀 (일반 버그 수정 모드)
Bash("touch .rtl-agent-team/state/rtl-verify-done")
# rtl-autopilot이 feedback_origin을 읽고 해당 Phase 5 sub-phase를 재실행
```
</Tool_Usage>

<Examples>
<Good>
5-Wave 버그 수정 계획:
  Wave 1-5: 6개 파일, 312줄 RTL 수정
  → 각 Wave마다: lint 실행 (syntax 검증)
  → 전체 수정 완료 후: smoke test TB 생성 (test_h264_tq_top.py)
  → cocotb 기능 시뮬레이션 실행 (10개 테스트 벡터)
  → RTL 출력 vs C reference model 비교
  → 모든 테스트 PASS → touch rtl-verify-done
  → 세션 정상 종료
</Good>
<Bad>
5-Wave 버그 수정 계획:
  Wave 1-5: 6개 파일, 312줄 RTL 수정
  → 각 Wave마다: verilator --lint-only -Wall (lint만 실행)
  → "lint 통과, 버그 수정 완료" 선언
  → TB 0개, 시뮬레이션 0회
  → 기능 정확성 미검증 상태로 완료 판정 ← 이것이 이 스킬이 방지하려는 anti-pattern
</Bad>
</Examples>

<Escalation_And_Stop_Conditions>
- lint 3회 실패 → rtl-architect에게 설계 리뷰 에스컬레이션
- TB 작성 불가 (ref model 없음) → 최소 self-checking TB 작성 후 user에게 ref model 필요성 보고
- 시뮬레이션 실패 후 2회 수정 반복 실패 → waveform-analyzer + bug-repro 스킬로 에스컬레이션
- 시뮬레이터 미설치 → eda-runner가 설치 안내 제공 (`pip install cocotb`, `apt install iverilog`)
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] 버그 root cause 식별됨
- [ ] RTL 수정 완료
- [ ] lint 통과 (verilator --lint-only -Wall, 에러 0)
- [ ] TB 생성 또는 업데이트됨 (수정된 모듈당 최소 1개 테스트)
- [ ] 버그 재현 시나리오가 테스트 케이스에 포함됨
- [ ] **기능 시뮬레이션 실행됨 (cocotb 또는 verilator sim)**
- [ ] **모든 테스트 PASS**
- [ ] **검증 완료 마커 생성됨 (.rtl-agent-team/state/rtl-verify-done)**
- [ ] TB 신호 이름 규칙 준수 (dut.sys_clk, dut.i_*, dut.o_*)
</Final_Checklist>

<Advanced>
**여러 모듈에 걸친 통합 버그의 경우:**
- 모듈별 단위 TB + top-level 통합 TB 모두 필요
- 단위 TB: 개별 모듈 입출력 검증
- 통합 TB: 모듈 간 데이터 흐름 검증

**기존 regression suite가 있는 경우:**
- 버그 수정 후 전체 regression 재실행 권장
- regression-run 스킬 활용: `/rtl-agent-team:regression-run`

**MODE_RECON 같은 복합 모드 버그의 경우:**
- 단일 모드 (MODE_FWD_TQ, MODE_INV_TQ) 테스트 먼저
- 복합 모드 테스트 별도 추가
- 모드 전환 시나리오 포함
</Advanced>
