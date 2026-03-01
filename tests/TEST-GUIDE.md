# rtl-agent-team 테스트 가이드

## 개요

이 문서는 `rtl-agent-team` Claude Code 플러그인의 테스트 인프라를 설명합니다.
테스트는 **pytest** 기반이며, EDA 도구 없이 실행 가능한 **유닛 테스트**와 EDA 도구가 필요한 **통합 테스트** 두 계층으로 구성됩니다.

### 테스트 현황

| 구분 | 테스트 수 | 상태 |
|------|----------|------|
| 유닛 테스트 | 219개 | 모두 PASS |
| 통합 테스트 (EDA 도구) | 12개 | EDA 도구 없으면 SKIP |
| 통합 테스트 (Docker 빌드) | 33개 | Docker daemon 없으면 SKIP |
| **합계** | **264개** | **231 passed, 45 skipped** |

---

## 디렉토리 구조

```
tests/
├── conftest.py                    # 공통 fixture 및 helper 함수
├── Makefile                       # make test, make unit, make integration 등
├── requirements-test.txt          # 테스트 의존성 (pytest, pytest-xdist)
├── TEST-GUIDE.md                  # 이 문서
├── unit/                          # EDA 도구 불필요 — 로컬에서 바로 실행 가능
│   ├── test_agent_skill_structure.py  # 에이전트/스킬 구조 검증
│   ├── test_aws_batch.py              # AWS Batch 작업 관리 (boto3 mock)
│   ├── test_bd_rate.py                # BD-rate/BD-PSNR 수학 계산
│   ├── test_build_scripts.py          # build_encoder.sh, build_decoder.sh
│   ├── test_check_conventions.py      # RTL 코딩 컨벤션 검사 스크립트
│   ├── test_compare_output.py         # MD5/bitexact 비교
│   ├── test_hooks.py                  # 훅 스크립트 (edit-tracker, stop-gate)
│   ├── test_json_schemas.py           # JSON 설정 파일 구조 검증
│   ├── test_parse_yosys_stat.py       # Yosys 합성 결과 파싱
│   ├── test_regression_coverage.py    # regression/coverage 스크립트
│   ├── test_run_conformance.py        # 적합성 테스트 스트림 탐색
│   ├── test_run_eval.py               # 인코더 출력 파싱, BD-rate 설정
│   └── test_run_sim_args.py           # run_sim.sh 인자 검증
└── integration/                   # EDA 도구 필요 (Docker 환경)
    ├── conftest.py                # requires_iverilog, requires_verilator 등
    ├── test_docker_build.py       # Docker 이미지 빌드 + EDA 도구 검증 (33개)
    ├── test_lint_live.py          # verilator/verible 실제 lint
    ├── test_sim_live.py           # iverilog/verilator 실제 시뮬레이션
    └── test_synth_live.py         # yosys 실제 합성
```

---

## 실행 방법

### 전제 조건

```bash
pip install pytest pytest-xdist
```

### 전체 테스트 실행

```bash
# 프로젝트 루트에서
python -m pytest tests/ -v

# 또는 Makefile 사용
cd tests && make test
```

### 유닛 테스트만 실행

```bash
python -m pytest tests/unit/ -v

# 또는
cd tests && make unit
```

### 통합 테스트만 실행 (Docker/EDA 환경)

```bash
python -m pytest tests/integration/ -v

# 또는
cd tests && make integration
```

### 특정 파일만 실행

```bash
python -m pytest tests/unit/test_hooks.py -v
```

### 병렬 실행 (빠른 테스트)

```bash
python -m pytest tests/unit/ -n auto
```

---

## 테스트 대상별 상세 설명

### 1. 훅 스크립트 테스트 (`test_hooks.py`)

플러그인의 핵심 동작인 **훅 시스템**을 검증합니다.

| 훅 | 역할 | 테스트 항목 |
|----|------|------------|
| `rtl-edit-tracker.sh` | RTL 파일(.sv/.svh/.v/.vh) 수정 추적 | 파일 확장자 필터링, 중복 방지, 카운트 |
| `rtl-verify-stop-gate.sh` | RTL 수정 후 검증 완료 전 세션 종료 차단 | 차단/허용 조건, 정리(cleanup) |
| `stop-gate.sh` | autopilot 실행 중 세션 종료 차단 | 상태 파일 유무에 따른 차단 |

**동작 원리:** 훅은 stdin으로 JSON을 받고, stdout으로 `{"continue": true/false}` JSON을 출력합니다.
테스트는 `run_hook()` helper로 실제 셸 스크립트를 실행하고 출력 JSON을 검증합니다.

### 2. Python 스크립트 테스트

| 테스트 파일 | 대상 스크립트 | 검증 내용 |
|------------|-------------|----------|
| `test_bd_rate.py` | `bd_rate.py` | BD-rate/BD-PSNR 수학 계산 정확성, 에지 케이스 |
| `test_parse_yosys_stat.py` | `parse_yosys_stat.py` | Yosys 합성 보고서 파싱, 래치 감지, 빈 디자인 |
| `test_compare_output.py` | `compare_output.py` | MD5 비교, bitexact 판정, 누락 파일 처리 |
| `test_run_eval.py` | `run_eval.py` | 인코더 출력 파싱, 크로마 가중치, 커스텀 패턴 |
| `test_run_conformance.py` | `run_conformance.py` | 스트림 탐색, MD5 계산, 디코딩 결과 구조 |
| `test_aws_batch.py` | `aws_batch_conformance.py` | AWS Batch 작업 제출/대기/결과 (boto3 mock) |

### 3. Bash 스크립트 테스트

| 테스트 파일 | 대상 스크립트 | 검증 내용 |
|------------|-------------|----------|
| `test_run_sim_args.py` | `run_sim.sh` | 시뮬레이터 인자 검증, 도움말, 미지원 옵션 |
| `test_check_conventions.py` | `check_conventions.sh` | RTL 코딩 컨벤션 검사 (버그 2건 문서화) |
| `test_build_scripts.py` | `build_encoder.sh`, `build_decoder.sh` | 빌드 인자 검증, 실제 컴파일 |
| `test_regression_coverage.py` | `run_regression.sh`, `merge_coverage.sh` | 회귀 테스트 인자, 커버리지 병합 |

### 4. 구조 검증 테스트 (`test_agent_skill_structure.py`)

플러그인의 **선언적 구조**를 검증합니다.

| 검증 항목 | 설명 |
|----------|------|
| 에이전트 YAML frontmatter | 50개 에이전트의 `name`, `model`, `description` 필드 존재 확인 |
| 에이전트 이름-파일명 일치 | `agents/rtl-coder.md`의 `name: rtl-coder` 일치 확인 |
| 스킬 SKILL.md 존재 | 40개 스킬 디렉토리마다 `SKILL.md` 존재 확인 |
| 스킬 이름-디렉토리 일치 | `skills/rtl-p4-implement/SKILL.md`의 `name: rtl-p4-implement` 일치 확인 |
| CLAUDE.md 교차 참조 | 핵심 에이전트/스킬이 실제로 존재하는지 확인 |
| hooks.json 구조 | PostToolUse, Stop 이벤트 훅 설정 검증 |
| plugin.json 구조 | 플러그인 이름, 버전, 설명 검증 |

### 5. JSON 스키마 테스트 (`test_json_schemas.py`)

| 검증 항목 | 파일 |
|----------|------|
| hooks.json | 훅 이벤트, matcher, command 구조 |
| plugin.json | 플러그인 메타데이터 |
| autopilot-state.json | Phase 1-6 상태 템플릿 |
| context-manifest | 각 Phase별 컨텍스트 매니페스트 구조 |
| conformance-config.json | 적합성 테스트 설정 |
| domain manifest | 도메인 패키지 매니페스트 |

### 6. Docker 빌드 + EDA 도구 검증 (`test_docker_build.py`)

`docker/Dockerfile`로 이미지를 빌드하고, 컨테이너 안에서 모든 EDA 도구가 사용 가능한지 검증합니다.

| 클래스 | 테스트 수 | 검증 내용 |
|--------|----------|----------|
| `TestDockerBuild` | 2개 | 이미지 빌드 성공, `/workspace` 디렉토리 확인 |
| `TestEDAToolsAvailable` | 25개 | 도구별 버전 확인 (아래 표) |
| `TestDockerToolchain` | 6개 | 실제 컴파일/시뮬레이션 E2E 검증 |

**검증하는 EDA 도구 목록:**

| 카테고리 | 도구 | 검증 방법 |
|---------|------|----------|
| 시뮬레이터 | Verilator 5.x, Icarus Verilog | `--version`, 실제 SV 컴파일 |
| 합성 | Yosys | `--version`, 실제 합성 실행 |
| 린트 | Verilator lint, Verible, slang | `--version`, lint 모드 확인 |
| 정형 검증 | SymbiYosys, Z3, Boolector | `--version` / `--help` |
| SystemC | SystemC 3.x 헤더/라이브러리 | 헤더 존재 확인, 실제 컴파일+실행 |
| Python | cocotb, cocotb-bus, cocotbext-axi, cocotb-coverage, numpy | `import` 확인 |
| 빌드 도구 | gcc, g++, cmake, make | `--version` |
| 파형 뷰어 | GTKWave | `which gtkwave` |
| LSP | slang-server | `--version` |

**실행 방법:**

```bash
# Docker daemon이 실행 중이어야 합니다
python -m pytest tests/integration/test_docker_build.py -v --timeout=3600

# 또는 Makefile 사용
cd tests && make test-docker
```

> **참고:** 첫 빌드는 Verilator, slang 등을 소스 빌드하므로 10~30분 소요됩니다.
> 이후 Docker 캐시 덕분에 재실행은 빠릅니다. Docker daemon이 없으면 33개 테스트 모두 SKIP됩니다.

---

## 테스트 아키텍처 설계 원칙

### Mock/Stub 전략

```
유닛 테스트                          통합 테스트
┌──────────────┐                  ┌──────────────┐
│  Python 함수  │  직접 import     │  실제 EDA    │
│  Bash 스크립트 │  subprocess     │  도구 실행    │
│  boto3 mock  │  MagicMock      │  Docker 환경  │
└──────────────┘                  └──────────────┘
   EDA 도구 불필요                    EDA 도구 필수
   로컬에서 즉시 실행                  CI/CD 또는 Docker
```

- **Python 함수**: `sys.path`에 스크립트 디렉토리를 추가하여 직접 import
- **Bash 스크립트**: `subprocess.run()`으로 실행하고 returncode/stdout/stderr 검증
- **AWS SDK**: `unittest.mock.MagicMock`으로 boto3 클라이언트를 대체
- **훅 스크립트**: `run_hook()` helper — stdin JSON → 셸 실행 → stdout JSON 파싱

### 발견된 버그 (테스트로 문서화)

| ID | 파일 | 설명 | 상태 |
|----|------|------|------|
| BUG-001 | `check_conventions.sh` | `((VIOLATIONS++))` + `set -e` 조합으로 인한 조기 종료 | 문서화됨 |
| BUG-002 | `check_conventions.sh` | `grep -n` 줄번호 접두어가 모듈 필터를 우회 | 문서화됨 |
| LIM-001 | `parse_yosys_stat.py` | Wire 수가 `Statistics:` 앞에 나오면 파싱 안 됨 | 문서화됨 |

---

## CI/CD 통합

### GitHub Actions 예시

```yaml
name: Plugin Tests
on: [push, pull_request]
jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install pytest pytest-xdist
      - run: python -m pytest tests/unit/ -v --tb=short

  integration-tests:
    runs-on: ubuntu-latest
    container:
      image: your-eda-docker-image:latest  # iverilog, verilator, yosys 포함
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install pytest
      - run: python -m pytest tests/integration/ -v --tb=short
```

---

## 새 테스트 추가 방법

### Python 스크립트용 테스트

```python
# tests/unit/test_my_script.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "skills" / "my-skill" / "scripts"))

from my_script import my_function

def test_basic():
    assert my_function("input") == "expected"
```

### Bash 스크립트용 테스트

```python
# tests/unit/test_my_bash.py
from tests.conftest import SCRIPTS_DIR, run_script

MY_SCRIPT = SCRIPTS_DIR / "my_script.sh"

def test_help():
    result = run_script(MY_SCRIPT, "--help")
    assert result.returncode == 0
    assert "Usage" in result.stdout
```

### 훅 스크립트용 테스트

```python
# tests/unit/test_my_hook.py
from tests.conftest import HOOKS_DIR, run_hook

MY_HOOK = HOOKS_DIR / "my-hook.sh"

def test_allows_continue(tmp_project):
    result = run_hook(MY_HOOK, {"cwd": str(tmp_project)})
    assert result["continue"] is True
```

---

## 자주 묻는 질문

**Q: 통합 테스트가 전부 SKIP되는데?**
A: EDA 도구(iverilog, verilator, yosys)가 설치되지 않아서입니다. Docker 환경에서 실행하거나 해당 도구를 설치하세요.

**Q: boto3 없이 AWS 테스트가 되나요?**
A: 네. 테스트에서 boto3를 mock 모듈로 대체하므로 실제 AWS 연결 없이 동작을 검증합니다.

**Q: 테스트를 병렬로 실행할 수 있나요?**
A: `pip install pytest-xdist` 후 `pytest -n auto`로 실행하면 CPU 코어 수만큼 병렬 실행됩니다.

**Q: 새로운 에이전트를 추가하면 테스트가 깨지나요?**
A: `test_agent_skill_structure.py`가 자동으로 새 에이전트의 YAML frontmatter 구조를 검증합니다. `name`, `model`, `description` 필드가 있으면 통과합니다.
