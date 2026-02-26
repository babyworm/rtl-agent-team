# Gate Failure Handling Reference

> 이 문서는 `rtl-autopilot` 스킬의 상세 레퍼런스이다.
> 핵심 규칙은 `skills/rtl-autopilot/SKILL.md`의 `<Steps>` 참조.

## 1. Phase Gate 개요

5-Phase 파이프라인의 각 Phase 완료 시 Gate Review를 수행한다:

```
Phase 1 → [Gate 1] → Phase 2 → [Gate 2] → Phase 3 → [Gate 3] → Phase 4 → [Gate 4] → Phase 5 → [Gate 5]
Research    Review    Arch/Ref    Review    μArch/BFM    Review    RTL         Review    Verify      Final
```

## 2. Gate Review Checklist

### Gate 1: Research → Architecture

| 항목 | 검증 내용 | 실패 시 |
|------|----------|--------|
| 요구사항 완전성 | 모든 기능 요구사항이 문서화됨 | Phase 1로 복귀 |
| 실현 가능성 | 기술적 제약 분석 완료 | 사용자 확인 요청 |
| 도메인 지식 | 필요한 전문 지식 확보 | domain-consult 호출 |

### Gate 2: Architecture → μArch

| 항목 | 검증 내용 | 실패 시 |
|------|----------|--------|
| Feature Coverage | 모든 REQ가 Arch 블록에 매핑됨 | Phase 2로 복귀 |
| 인터페이스 정의 | io_definition.json 완전성 | 누락 포트 추가 |
| Reference Model | ref_model 빌드 + 기본 테스트 통과 | ref-model-dev 재실행 |
| 블록 다이어그램 | Mermaid 다이어그램 존재 | arch-designer 보완 |

### Gate 3: μArch → RTL

| 항목 | 검증 내용 | 실패 시 |
|------|----------|--------|
| Feature Preservation | Arch 기능이 μArch에 보존됨 | Phase 3로 복귀 |
| 타이밍 분석 | Critical path 예측 | μArch 파이프라인 조정 |
| BFM smoke test | AT 트랜잭션 1회 성공 | bfm-dev 수정 |

### Gate 4: RTL → Verify

| 항목 | 검증 내용 | 실패 시 |
|------|----------|--------|
| Functional Completeness | 모든 REQ가 RTL에 구현됨 | Phase 4로 복귀 |
| Lint PASS | Verilator + Verible 경고 0 | rtl-coder 수정 |
| 합성 PASS | Yosys latch-free | rtl-coder 수정 |
| 컨벤션 준수 | i_/o_, sys_clk, ALL_CAPS 등 | rtl-coder 수정 |

### Gate 5: Final

| 항목 | 검증 내용 | 실패 시 |
|------|----------|--------|
| Regression PASS | 모든 시드 통과 | 버그 수정 후 재실행 |
| Coverage ≥ 목표 | Line ≥ 95%, Func ≥ 90% | 추가 테스트 작성 |
| Requirement Traceability | 모든 REQ에 테스트 존재 | 누락 테스트 추가 |

## 3. Gate Failure Retry Flow

```
Gate Review
    │
    ├── PASS → 다음 Phase로 진행
    │
    └── FAIL
         │
         ├── Severity: MINOR (1-2 항목 미달)
         │    └── 해당 항목만 수정 → 재검증 (최대 2회)
         │
         ├── Severity: MAJOR (3+ 항목 또는 핵심 항목)
         │    └── 이전 Phase로 복귀 → 전체 재작업
         │
         └── Severity: BLOCKER (상위 스펙 위반)
              └── 사용자에게 보고 → 스펙 변경 승인 필요
```

### Retry 규칙

| 규칙 | 설명 |
|------|------|
| 최대 2회 retry | MINOR 실패 시 같은 Phase에서 2회 수정 시도 |
| 2회 초과 실패 | 이전 Phase로 복귀 (구조적 문제 가능성) |
| BLOCKER는 즉시 중단 | 사용자 승인 없이 진행 불가 |

## 4. 상위 스펙 위반 처리

> **핵심 원칙: 하위 단계는 상위 단계의 스펙을 절대 위반할 수 없다.**

### 4.1 위반 감지

| 위반 유형 | 감지 방법 | 예시 |
|----------|----------|------|
| 기능 누락 | Feature Coverage Checklist | REQ-003이 Arch에 없음 |
| 인터페이스 변경 | io_definition 비교 | 포트 추가/삭제 |
| 성능 미달 | 타이밍 분석 | 타겟 주파수 미달 |
| 프로토콜 변경 | Arch 리뷰 | AXI → APB 임의 변경 |

### 4.2 위반 시 처리

```
위반 감지
    │
    ├── 기능 누락
    │    ├── 구현 가능 → 현재 Phase에서 추가 구현
    │    └── 구현 불가 → 상위 Phase로 복귀 + 사용자 승인
    │
    ├── 인터페이스 변경
    │    ├── 호환 가능 (포트 추가) → Arch 문서 업데이트 후 진행
    │    └── 비호환 (포트 삭제/변경) → Arch Phase로 복귀
    │
    └── 성능 미달
         ├── μArch 최적화로 해결 가능 → μArch 수정
         └── 근본적 구조 변경 필요 → Arch Phase로 복귀
```

### 4.3 사용자 승인 요청 형식

```markdown
## ⚠️ Upper Spec Violation Detected

**Phase**: Phase 3 (μArch) → Phase 2 (Architecture) 위반
**Type**: Feature Omission
**Detail**: REQ-003 (burst transfer support)이 μArch에서 구현 불가
**Reason**: 단일 사이클 처리 구조에서 burst 지원 시 파이프라인 전면 재설계 필요
**Options**:
1. Architecture로 복귀하여 burst 지원 구조로 재설계
2. REQ-003을 v2로 연기 (사용자 승인 필요)
3. 성능 타협: burst 길이 제한 (max 4 beats)

**Recommendation**: Option 1 (완전한 burst 지원)
```

## 5. Phase Gate 리포트 위치

```
reviews/
├── phase-1-research/research-review.md
├── phase-2-architecture/
│   ├── feature-coverage.md          ← REQ → Arch 매핑
│   └── architecture-review.md
├── phase-3-uarch/
│   ├── feature-preservation.md      ← Arch → μArch 매핑
│   └── uarch-review.md
├── phase-4-rtl/
│   ├── functional-completeness.md   ← REQ → RTL 매핑
│   ├── design-review.md
│   └── lint-report.md
└── phase-5-verify/
    ├── requirement-traceability.md  ← REQ → Test 매핑
    └── final-compliance.md
```

## 6. 자동 상태 추적

Gate 통과/실패는 `.rtl-agent-team/state/rtl-autopilot-state.json`에 기록:

```json
{
  "current_phase": 3,
  "gates": {
    "gate_1": { "status": "PASS", "date": "2025-01-15" },
    "gate_2": { "status": "PASS", "date": "2025-01-16", "retries": 1 },
    "gate_3": { "status": "PENDING" }
  },
  "violations": [],
  "blocked": false
}
```
