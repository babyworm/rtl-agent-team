# RTL Agent Team 플러그인 테스트 가이드

## 개요

이 테스트 인프라는 `rtl-agent-team` 플러그인의 실행 가능한 코드(Bash 스크립트, Python 스크립트, Hook 스크립트)를 검증합니다.

**2계층 구조:**

| 계층 | 디렉토리 | EDA 도구 필요 | 테스트 수 | 실행 시간 |
|------|----------|:---:|:---:|:---:|
| Unit | `tests/unit/` | X | 1592 | ~30초 |
| Integration | `tests/integration/` | O (Docker/Yosys) | 47 | 일반 non-Docker 경로 ~1분; opt-in 최초 Docker build 10-30분 |

Docker image가 이미 있으면 통합 테스트는 더 빠를 수 있습니다. 최초 opt-in build 시간은
호스트와 네트워크 상태에 따라 달라집니다.

## 빠른 시작

```bash
# 1. 의존성 설치
cd tests
python3 -m venv .venv
".venv/bin/python" -m pip install -r requirements-test.txt
. .venv/bin/activate

# 2. 단위 테스트 실행 (EDA 도구 없이)
make test-unit

# 3. 통합 테스트 실행 (Docker 환경에서)
make test-integration
```

## 테스트 대상

### Unit 테스트 — Python 스크립트

| 테스트 파일 | 대상 스크립트 | 무엇을 검증하나 |
|------------|-------------|----------------|
| `test_bd_rate.py` | `bd_rate.py` | BD-rate/BD-PSNR 수학 계산, 입력 검증, 다항식 적분, NaN 처리 |
| `test_parse_yosys_stat.py` | `parse_yosys_stat.py` | Yosys stat 출력 파싱, 셀 카운트, 래치 감지, PASS/FAIL 판정 |
| `test_compare_output.py` | `compare_output.py` | MD5 비교, byte-by-byte 비교, PSNR 계산, golden MD5 로딩 |
| `test_run_eval.py` | `run_eval.py` | 인코더 출력 파싱, 크로마 가중치, 커스텀 regex, 설정 해석 |
| `test_run_conformance.py` | `run_conformance.py` | 스트림 자동 발견, 프로파일 필터링, DecodingResult 구조 |
| `test_aws_batch.py` | `aws_batch_submit.py` | 잡 이름 새니타이징, boto3 목킹, S3 결과 조회, 타임아웃 |

### Unit 테스트 — Bash 스크립트

| 테스트 파일 | 대상 스크립트 | 무엇을 검증하나 |
|------------|-------------|----------------|
| `test_check_conventions.py` | `check_conventions.sh` | 네이밍 규칙 6가지 (reg/wire, 포트 접두사, 클럭/리셋 명명, 인스턴스/generate 접두사) |
| `test_run_sim_args.py` | `run_sim.sh` | 인자 파싱, 필수 값 검증, 파일리스트 처리, define/param 플래그, 시뮬레이터 선택 |
| `test_build_scripts.py` | `build_encoder.sh`, `build_decoder.sh` | 인자 검증, 소스 디렉토리 확인, gcc 컴파일 (gcc 설치시), Makefile 감지 |
| `test_regression_coverage.py` | `run_regression.sh`, `merge_coverage.sh` | 시드 실행, 결과 리포트, 커버리지 포맷, 에러 처리 |

### Unit 테스트 — Hook 스크립트

| 테스트 파일 | 대상 스크립트 | 무엇을 검증하나 |
|------------|-------------|----------------|
| `test_hooks.py` | `rtl-edit-tracker.sh` | RTL 파일 추적, 비-RTL 파일 무시, 중복 방지, 파일 카운트 |
|  | `rtl-verify-stop-gate.sh` | 미검증 시 세션 종료 차단, verify-done/waiver 허용, 정리 |
|  | `stop-gate.sh` | autopilot 실행 중 종료 차단 |

### Unit 테스트 — JSON 설정 검증

| 테스트 파일 | 무엇을 검증하나 |
|------------|----------------|
| `test_json_schemas.py` | `hooks.json` 구조, `plugin.json` 구조, `package.json` 필드, 도메인 manifest, 모든 JSON 파일 파싱 가능 여부 |

### Unit 테스트 — Plugin 런타임 계약 검증

| 테스트 파일 | 무엇을 검증하나 |
|------------|----------------|
| `test_plugin_runtime_contract.py` | `hooks/hooks.json` 이벤트/순서/스크립트 경로/timeout 계약, `.claude-plugin/plugin.json` ↔ `.claude-plugin/marketplace.json` 버전/경로 일관성, SessionStart 라우팅의 Action Skill/Convention/user-invocable 계약, 위임 에이전트 존재성 |

### Integration 테스트

| 테스트 파일 | 필요 도구 | 무엇을 검증하나 |
|------------|----------|----------------|
| `test_sim_live.py` | iverilog, verilator | 실제 컴파일+실행, define 전달, 파일리스트 통합 |
| `test_lint_live.py` | verilator, verible | 실제 lint 결과, 경고 감지 |
| `test_synth_live.py` | yosys | 실제 합성, parse_yosys_stat 파이프라인 |

## 실행 방법

```bash
cd tests

# 전체 단위 테스트
make test-unit

# 병렬 실행 (빠름)
make test-fast

# 특정 카테고리만
make test-hooks           # hook 테스트만
make test-python-scripts  # Python 스크립트만
make test-bash-scripts    # Bash 스크립트만
make test-json            # JSON 검증만
make test-plugin-runtime  # plugin 런타임 계약 검증

# 특정 테스트 파일만
python3 -m pytest unit/test_bd_rate.py -v
python3 -m pytest unit/test_plugin_runtime_contract.py -v

# 특정 테스트 함수만
python3 -m pytest unit/test_bd_rate.py::TestBdRate::test_identical_curves_zero -v

# 통합 테스트 (Docker 환경에서)
make test-integration

# 전체 (단위 + 통합)
make test-all
```

## 테스트 작성 가이드

### 새 Python 스크립트 테스트 추가

```python
# tests/unit/test_새스크립트.py
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent.parent / "skills" / "스킬명" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from 스크립트명 import 함수명

class Test함수명:
    def test_정상_케이스(self):
        result = 함수명(정상_입력)
        assert result == 기대값

    def test_엣지_케이스(self):
        result = 함수명(경계값)
        assert ...
```

### 새 Bash 스크립트 테스트 추가

```python
# tests/unit/test_새스크립트.py
from tests.conftest import SKILLS_DIR, run_script

SCRIPT = SKILLS_DIR / "스킬명" / "scripts" / "스크립트.sh"

class Test스크립트:
    def test_인자_검증(self):
        result = run_script(SCRIPT, "--bad-flag")
        assert result.returncode != 0

    def test_정상_실행(self, tmp_path):
        result = run_script(SCRIPT, str(tmp_path), "--option", "value")
        assert result.returncode == 0
        assert "기대문자열" in result.stdout
```

### 새 Hook 테스트 추가

```python
# tests/unit/test_hooks.py에 추가
from tests.conftest import HOOKS_DIR, run_hook

class TestNewHook:
    HOOK = HOOKS_DIR / "new-hook.sh"

    def test_허용(self, tmp_project):
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is True

    def test_차단(self, tmp_project):
        # 차단 조건 설정
        (tmp_project / ".rat" / "state" / "block-file").touch()
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is False
```

## 발견된 버그

테스트 과정에서 발견된 기존 코드 버그:

| ID | 위치 | 심각도 | 설명 |
|----|------|--------|------|
| BUG-001 | `check_conventions.sh:17` | 높음 | **FIXED.** `((VIOLATIONS++))` → `VIOLATIONS=$((VIOLATIONS + 1))` |
| BUG-002 | `check_conventions.sh:52` | 중간 | **FIXED.** `grep -vE` 패턴에 `^[0-9]+:\s*` 접두사 추가로 라인번호 prefix 처리 |
| BUG-003 | `run_regression.sh:67` | 높음 | **FIXED.** `((TOTAL++))` → `TOTAL=$((TOTAL + 1))` |

## 디렉토리 구조

```
tests/
├── conftest.py                  # 공통 fixture (tmp_project, run_script, run_hook 등)
├── requirements-test.txt        # pip 의존성
├── Makefile                     # 편의 명령어
├── README.md                    # 이 문서
├── unit/                        # EDA 도구 불필요
│   ├── test_aws_batch.py        # AWS Batch (boto3 목킹)
│   ├── test_bd_rate.py          # BD-rate 계산
│   ├── test_build_scripts.py    # C 빌드 스크립트
│   ├── test_check_conventions.py # 네이밍 컨벤션
│   ├── test_compare_output.py   # 적합성 비교
│   ├── test_hooks.py            # Hook 스크립트 3종
│   ├── test_json_schemas.py     # JSON 설정 검증
│   ├── test_plugin_runtime_contract.py # Plugin 런타임 계약 검증
│   ├── test_parse_yosys_stat.py # Yosys 파싱
│   ├── test_regression_coverage.py # 리그레션/커버리지
│   ├── test_run_conformance.py  # 적합성 테스트
│   ├── test_run_eval.py         # RD 평가
│   └── test_run_sim_args.py     # 시뮬레이터 래퍼
└── integration/                 # EDA 도구 필요 (auto-skip)
    ├── conftest.py              # requires_* 마커
    ├── test_lint_live.py        # 실제 lint
    ├── test_sim_live.py         # 실제 시뮬레이션
    └── test_synth_live.py       # 실제 합성
```
