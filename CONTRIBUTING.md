# Contributing

RTL Agent Marketplace에 기여하는 방법을 설명합니다.

기여 유형은 크게 세 가지입니다:
1. **기존 플러그인 개선** — 에이전트, 스킬, 레퍼런스 추가/수정
2. **도메인 에이전트 추가** — 새로운 도메인 전문가 에이전트 통합
3. **새 플러그인 추가** — marketplace에 독립 플러그인 등록

---

## 1. 기존 플러그인 (rtl-agent-team) 개선

### 에이전트 추가

`agents/` 디렉토리에 Markdown 파일을 생성합니다.

**파일**: `agents/{agent-name}.md`

```markdown
---
name: {agent-name}
description: 에이전트가 하는 일을 한 문장으로. 언제 사용하는지, 어떤 전문성을 가지는지 포함.
model: opus
color: blue
---

<Agent_Prompt>
  <Role>
    에이전트의 역할과 전문 영역을 정의합니다.
  </Role>

  <Why_This_Matters>
    이 에이전트가 왜 필요한지, 없으면 어떤 문제가 발생하는지.
  </Why_This_Matters>

  <Constraints>
    - 해야 할 것과 하지 말아야 할 것
  </Constraints>

  <Tool_Usage>
    사용할 도구와 예시
  </Tool_Usage>

  <Output_Format>
    출력 형식 정의
  </Output_Format>

  <Examples>
    <Good>좋은 출력 예시</Good>
    <Bad>나쁜 출력 예시</Bad>
  </Examples>
</Agent_Prompt>
```

**frontmatter 필드**:

| 필드 | 필수 | 설명 |
|------|------|------|
| `name` | 필수 | 파일명과 동일 (`.md` 제외), kebab-case |
| `description` | 필수 | 한 문장 설명. Claude가 에이전트 선택 시 이 텍스트를 읽음 |
| `model` | 필수 | `opus` (복잡한 분석), `sonnet` (표준 작업), `haiku` (단순 조회) |
| `color` | 선택 | UI 표시색 |
| `disallowedTools` | 선택 | 금지할 도구 (예: `Write, Edit` — 읽기 전용 에이전트) |

**체크리스트**:
- [ ] `name:` 필드가 파일명과 일치하는가
- [ ] `description:`이 에이전트의 전문성과 사용 시점을 설명하는가
- [ ] CLAUDE.md 위임 테이블에 에이전트를 추가했는가
- [ ] README.md 에이전트 카운트를 업데이트했는가
- [ ] marketplace.json의 에이전트 카운트 설명을 업데이트했는가

### 스킬 추가

`skills/{skill-name}/SKILL.md` 파일을 생성합니다.

```markdown
---
name: {skill-name}
description: "이 스킬을 사용해야 하는 상황을 설명합니다."
---

<Purpose>
스킬의 목적
</Purpose>

<Use_When>
- 사용해야 하는 상황 1
- 사용해야 하는 상황 2
</Use_When>

<Do_Not_Use_When>
- 사용하지 말아야 하는 상황
</Do_Not_Use_When>

<Steps>
1. 실행 단계
2. ...
</Steps>

<Tool_Usage>
에이전트 위임 예시 (Task 호출)
</Tool_Usage>

<Examples>
<Good>좋은 결과 예시</Good>
<Bad>나쁜 결과 예시</Bad>
</Examples>

<Final_Checklist>
- [ ] 완료 조건
</Final_Checklist>
```

**스킬 하위 디렉토리** (선택):

```
skills/{skill-name}/
├── SKILL.md              # 스킬 정의 (필수)
├── templates/            # 출력 템플릿, JSON 스키마 등
└── examples/             # 예시 입출력
```

**체크리스트**:
- [ ] `description:`이 Claude의 자동 라우팅에 충분한 정보를 제공하는가
- [ ] CLAUDE.md 스킬 호출 규칙 테이블에 패턴을 추가했는가
- [ ] README.md 스킬 카운트를 업데이트했는가
- [ ] 스킬이 review artifact를 생성하면 `review-checklist.md`에 추가했는가
- [ ] 스킬이 Phase 입출력을 변경하면 해당 orchestrator의 Context Preload 섹션을 업데이트했는가

### 레퍼런스 문서 추가

`references/{topic}.md`에 상세 레퍼런스를 추가합니다. 레퍼런스는 에이전트가 필요할 때만 읽는 3계층 문서 중 최하위 계층입니다.

### 수정 후 필수 업데이트 파일

에이전트나 스킬을 추가/삭제하면 다음 파일의 카운트와 목록을 반드시 업데이트해야 합니다:

| 파일 | 업데이트 내용 |
|------|-------------|
| `skills/rtl-orchestrate/SKILL.md` | 스킬 라우팅 테이블 + Action Skill→Orchestrator→Policy 매핑 + SessionStart export block (single source of truth) |
| `scripts/sync_orchestrator_inject.sh` | `rtl-orchestrate`의 export block을 `hooks/rtl-orchestrator-inject.sh` generated block으로 동기화 |
| `hooks/rtl-orchestrator-inject.sh` | SessionStart 축약 라우팅 (generated block 직접 수동 수정 금지) |
| `README.md` | 에이전트/스킬 카운트, 에이전트 팀 테이블 |
| `.claude-plugin/marketplace.json` | 플러그인 description의 카운트 |
| `skills/rtl-autopilot/references/review-checklist.md` | review artifact 추가/삭제 시 체크리스트 업데이트 |
| `agents/*-orchestrator.md` (Context Preload 섹션) | Phase별 입출력 artifact 변경 시 inline preload 목록 업데이트 |

라우팅/위임 변경 시 반드시 아래를 실행하세요:

```bash
sh scripts/sync_orchestrator_inject.sh
python -m pytest -q tests/unit/test_agent_skill_structure.py tests/unit/test_hooks.py tests/unit/test_plugin_runtime_contract.py
```

### 플러그인 캐시 동기화 (필수)

에이전트나 스킬을 추가/삭제/리네임한 후에는 **반드시 플러그인 캐시를 갱신**해야 합니다.
캐시를 갱신하지 않으면 Claude Code 세션에서 변경 사항이 반영되지 않습니다.

**배경**: Claude Code는 `~/.claude/plugins/cache/`에 캐시된 복사본에서 스킬을 로드합니다. 작업 디렉토리의 파일을 직접 읽지 않습니다.

```
작업 디렉토리 (~/works/rtl-agent-team/)
  ↓  git push
GitHub (babyworm/rtl-agent-team)
  ↓  claude plugin marketplace update rtl-agent-marketplace
Marketplace (~/.claude/plugins/marketplaces/rtl-agent-marketplace/)
  ↓  claude plugin update rtl-agent-team
Cache (~/.claude/plugins/cache/.../0.1.0/)
  ↓  세션 재시작
System skill list (런타임 로드)
```

**변경 후 실행할 명령**:

```bash
# 1. 변경 사항 commit & push
git add -A && git commit -m "Add/rename skills" && git push

# 2. marketplace 갱신 (GitHub에서 git pull)
claude plugin marketplace update rtl-agent-marketplace

# 3. 플러그인 재설치 (강제 cache 갱신)
claude plugin uninstall rtl-agent-team@rtl-agent-marketplace
claude plugin install rtl-agent-team@rtl-agent-marketplace

# 4. Claude Code 세션 재시작 (새 세션에서 변경 반영)
```

> **주의**: `claude plugin update`는 version이 동일하면 스킵합니다.
> 개발 중에는 반드시 `uninstall` → `install` 조합을 사용해야 합니다.
> 3번 단계를 빠뜨리면 marketplace는 최신이지만 cache는 구버전인 상태가 되어,
> CLAUDE.md의 skill 참조와 시스템 등록명이 불일치하는 문제가 발생합니다.

---

## 2. 도메인 에이전트 추가

새로운 하드웨어 설계 도메인(예: DDR 컨트롤러, PCIe, 오디오 코덱)의 전문가 에이전트를 추가하는 방법입니다.

### 네이밍 규칙

도메인 에이전트는 `{domain}-` 접두사를 사용합니다:

| 도메인 | 접두사 | 예시 |
|--------|--------|------|
| Video codec | `vcodec-` | `vcodec-syntax-entropy-expert` |
| Video processing | `vproc-` | `vproc-color-format-expert` |
| DDR/메모리 | `ddr-` | `ddr-timing-expert` |
| PCIe | `pcie-` | `pcie-ltssm-expert` |
| 오디오 | `audio-` | `audio-dsp-expert` |

### 도메인 패키지 (선택)

전문가 에이전트가 3개 이상이면 **도메인 패키지**로 묶는 것을 권장합니다.

**디렉토리 구조**:

```
domain-packages/{domain}/
├── manifest.json          # 에이전트 목록, 표준, coordination workflow
├── knowledge/             # 도메인 지식 (표준 요약, 알고리즘 등)
├── conformance/           # 적합성 테스트 데이터
└── templates/             # 도메인 전용 코드 템플릿
```

**manifest.json 구조**:

```json
{
  "domain": "{domain}",
  "version": "1.0.0",
  "description": "도메인 설명",

  "standards": [
    {
      "id": "표준 ID",
      "full_name": "표준 전체 이름",
      "url": "표준 문서 URL"
    }
  ],

  "agents": [
    {
      "id": "{domain}-{role}-expert",
      "file": "agents/{domain}-{role}-expert.md",
      "role": "역할 설명",
      "expertise": ["전문 영역 1", "전문 영역 2"]
    }
  ],

  "agent_coordination": {
    "phase_1_research": {
      "primary_domain_agents": ["에이전트 목록"],
      "workflow": "워크플로우 설명"
    }
  }
}
```

### Chief 에이전트 패턴

도메인 전문가가 4개 이상이면 **Chief 에이전트**를 추가하는 것을 권장합니다.

Chief 에이전트의 역할:
- 서브 도메인 전문가 출력을 cross-review
- 블록 간 의존성 식별
- 반복 리뷰를 통한 품질 수렴 (기본 3회 강제)

참조: `agents/vcodec-chief-standard-expert.md`

### 체크리스트

- [ ] 에이전트 파일 생성 (`agents/{domain}-{role}-expert.md`)
- [ ] 에이전트 frontmatter `name:`이 파일명과 일치
- [ ] CLAUDE.md 위임 테이블에 추가
- [ ] README.md 에이전트 팀 테이블에 도메인 카테고리 추가
- [ ] (3+ 에이전트) 도메인 패키지 `domain-packages/{domain}/manifest.json` 생성
- [ ] (4+ 에이전트) Chief 에이전트 추가 권장
- [ ] 기존 스킬(p1-spec-research, domain-consult 등)의 라우팅 테이블에 새 도메인 추가
- [ ] 에이전트/스킬 카운트 업데이트 (README.md, marketplace.json)

---

## 2.5 Video Codec Standard Onboarding (H.264/H.265/AV1/VVC ...)

새로운 video codec 표준을 도메인 패키지에 추가하는 가이드입니다. 일반 도메인 에이전트 추가(§2)와 달리,
codec 표준은 지식 파일 세트, 전문가 프롬프트 동기화, 라우팅 갱신, 테스트 게이트가 함께 필요합니다.

### 지원 티어

| 티어 | 범위 | 예시 |
|------|------|------|
| **full** | 분석 + RD eval + conformance + expert prompts | H.264, H.265 |
| **analysis_only** | 분석만 (knowledge + expert `<Domain_Knowledge>` 갱신) | AV1 (초기) |
| **roadmap** | 계획 단계 (manifest 등록만, 지식 파일 없음) | VVC |

### 표준 지원 매트릭스 (manifest.json)

`domain-packages/video-codec/manifest.json`에 `standard_support_matrix` 필드를 유지합니다:

```json
"standard_support_matrix": {
  "H.264": {
    "tier": "full",
    "agent_coverage": ["syntax", "prediction", "tq", "filter", "chief", "arch", "perf"],
    "conformance_available": true,
    "rd_eval_available": true,
    "owner": "rtl-agent-team",
    "maturity": "stable"
  }
}
```

### 지식 파일 최소 세트

표준별로 다음 파일을 `domain-packages/video-codec/knowledge/`에 생성합니다:

| 파일 | 필수 (full) | 필수 (analysis_only) | 내용 |
|------|:-----------:|:--------------------:|------|
| `{std}-spec-summary.md` | O | O | 표준 알고리즘 블록 요약 + clause 참조 |
| `{std}-function-map.md` | O | - | 레퍼런스 SW 함수 → spec clause 매핑 |
| `{std}-fixed-point.md` | O | - | 고정소수점 산술 규칙 (비트폭, 라운딩) |
| `{std}-throughput.md` | O | - | 해상도/프레임레이트별 throughput 테이블 |
| `{std}-conformance-notes.md` | O | - | 적합성 테스트 벡터 및 검증 주의사항 |

> `{std}`는 소문자 하이픈 형식: `h264`, `h265`, `av1`, `vvc`
>
> **공용 파일 허용**: 여러 표준에 공통되는 지식(예: `fixed-point-conventions.md`, `throughput-tables.md`)은
> 표준별로 분리하지 않고 공용 파일로 유지할 수 있습니다. 이 경우 manifest의 `standard_id`를 배열로 지정합니다
> (예: `"standard_id": ["H.264", "H.265"]`).

### Expert 프롬프트 표준 스코프 동기화

새 표준 추가 시 다음 6개 expert의 `<Domain_Knowledge>` 섹션을 업데이트해야 합니다:

1. `vcodec-syntax-entropy-expert` — 새 표준의 entropy coding 알고리즘
2. `vcodec-prediction-expert` — 새 표준의 prediction 알고리즘
3. `vcodec-transform-quant-expert` — 새 표준의 transform/quant 알고리즘
4. `vcodec-filter-recon-expert` — 새 표준의 in-loop filter 알고리즘
5. `vcodec-chief-standard-expert` — cross-block 의존성에 새 표준 추가
6. `vcodec-architecture-expert` — HW 아키텍처 패턴에 새 표준 추가

### 라우팅 동기화

3곳을 동시에 갱신해야 합니다:

1. `skills/domain-consult/SKILL.md` — 라우팅 테이블에 새 표준 키워드 추가
2. `skills/rtl-orchestrate/SKILL.md` — SSOT 라우팅 블록 (hook export 소스)
3. `hooks/rtl-orchestrator-inject.sh` — `sh scripts/sync_orchestrator_inject.sh` 실행

### Non-Codec Video Processing 분리

Codec 성능 분석(`video-processing-expert`)과 일반 영상 처리(color space, HDR, ISP)는 별도 도메인으로 관리합니다:

- **`domain-packages/video-codec/`** — `video-processing-expert`는 여기에 유지 (codec throughput 전문가)
- **`domain-packages/video-processing/`** — non-codec 영상 처리 전문가 등록 (active, 3 agents: color-format, denoise, image-processing)

라우팅은 이미 분리되어 있습니다 (`domain-consult/SKILL.md` 참조).

### 스킬 호환성 매트릭스

| 스킬 | H.264 | H.265 | AV1 | VVC |
|------|:-----:|:-----:|:---:|:---:|
| `codec-rd-eval` (encoder RD) | O | O | - | - |
| `codec-conformance-eval` (decoder) | O | O | - | - |
| `rtl-conformance-test` (RTL) | O | O | - | - |

새 표준 추가 시 이 테이블을 업데이트하세요.

### 테스트 게이트

PR merge 조건으로 다음 4종 테스트를 통과해야 합니다:

1. **manifest schema pass** — `test_json_schemas.py::TestDomainManifest` 통과
2. **routing keyword coverage pass** — `test_expert_quality.py::TestRoutingKeywordCoverage` 통과 (vcodec + vproc 라우팅)
3. **expert contract pass** — `test_expert_quality.py::TestExpertQualityContract` + `TestVprocExpertQuality` 통과
4. **knowledge version consistency pass** — `test_expert_quality.py::TestKnowledgeVersionConsistency` 통과
5. **vproc manifest consistency pass** — `test_expert_quality.py::TestVprocManifestConsistency` 통과

### Definition of Done

"새 표준 추가" PR은 최소 다음 5종 변경이 포함되어야 합니다:

- [ ] `manifest.json` — standards 배열 + standard_support_matrix + knowledge_base 항목
- [ ] `knowledge/` — 지식 파일 최소 세트 (티어에 따라)
- [ ] 라우팅 — domain-consult + rtl-orchestrate + hook inject 동기화
- [ ] 테스트 — 4종 테스트 게이트 통과
- [ ] README.md — 지원 표준 목록 업데이트

---

## 3. 새 플러그인 추가

이 marketplace에 독립 플러그인을 추가하는 방법입니다.

### 같은 repo 내 플러그인

`plugins/` 디렉토리에 플러그인을 추가합니다.

```
plugins/{plugin-name}/
├── .claude-plugin/
│   └── plugin.json        # 플러그인 매니페스트 (strict: true인 경우)
├── agents/                # (선택) 에이전트
├── skills/                # (선택) 스킬
└── hooks/                 # (선택) 훅
```

**marketplace.json에 등록**:

```json
{
  "name": "{plugin-name}",
  "source": "./plugins/{plugin-name}",
  "description": "플러그인 설명",
  "version": "1.0.0",
  "category": "development",
  "tags": ["태그1", "태그2"]
}
```

### 경량 플러그인 (plugin.json 없이)

LSP 서버나 MCP 서버처럼 단순한 플러그인은 `strict: false`로 marketplace.json에서 직접 정의할 수 있습니다.

```json
{
  "name": "{plugin-name}",
  "source": "./plugins/{plugin-name}",
  "description": "플러그인 설명",
  "version": "1.0.0",
  "strict": false,
  "lspServers": { ... },
  "mcpServers": { ... }
}
```

참조: marketplace.json의 `systemverilog-lsp` 항목

### 외부 repo 플러그인

다른 repository에 있는 플러그인을 marketplace에 등록합니다.

```json
{
  "name": "{plugin-name}",
  "source": {
    "source": "github",
    "repo": "owner/repo"
  },
  "description": "플러그인 설명",
  "version": "1.0.0"
}
```

### 체크리스트

- [ ] 플러그인 소스 준비 (같은 repo: `plugins/`, 외부: 별도 repo)
- [ ] `.claude-plugin/marketplace.json`의 `plugins` 배열에 항목 추가
- [ ] JSON 유효성 검증 (`python3 -c "import json; json.load(open('.claude-plugin/marketplace.json'))"`)
- [ ] README.md Marketplace 테이블에 새 플러그인 추가
- [ ] 설치 테스트: `/plugin install {plugin-name}`

---

## 코딩 컨벤션

### 언어 표준

| 언어 | 표준 | 용도 |
|------|------|------|
| **SystemVerilog (RTL)** | IEEE 1800-2009 | 합성 가능 RTL. 2012+ 기능은 RTL에서 사용 금지 |
| **SystemVerilog (검증)** | IEEE 1800-2012 | SVA, UVM TB. checker, interface class 등 허용 |
| **C** | C11 (`-std=c11`) | Ref Model (DPI-C 호환). `gcc -Wall -Wextra -Werror` |
| **C++** | C++17 (`-std=c++17`) | BFM (SystemC/TLM), DPI. C++20 사용 금지 |

- iverilog 플래그: `-g2012` (2009 하위 호환 파싱)
- 2012 이후 합성 관련 추가 기능 없음 (2017은 errata만, 2023은 도구 지원 초기)

### iverilog 호환성

iverilog는 `-g2012` 옵션으로 SystemVerilog 기본 문법을 지원하지만 일부 기능은 미지원:

| 구문 | iverilog 지원 | 대체 |
|------|-------------|------|
| `logic`, `always_ff`, `always_comb` | 지원 | — |
| `typedef enum` | 지원 | — |
| `typedef struct packed` | 지원 | — |
| `typedef union packed` | 지원 | — |
| `interface` / `modport` | 미지원 | 포트 리스트 |
| unpacked `struct` / `union` | 미지원 | 개별 signal 또는 packed 버전 |

코딩 에이전트는 미지원 구문을 생성하지 않는다.
사용자가 직접 추가하거나 기존 코드에 존재하는 경우 수정하지 않는다.

### RTL 네이밍 규칙

| 항목 | 규칙 |
|------|------|
| 포트 prefix | `i_`, `o_`, `io_` (NOT suffix `_i`, `_o`) |
| 클럭 | `clk` (단일) 또는 `{domain}_clk` (다중) — NOT `clk_i` |
| 리셋 | `rst_n` (단일) 또는 `{domain}_rst_n` (다중) — active-low 비동기 |
| 네이밍 | `snake_case` 또는 `ALL_CAPS`만 허용 (CamelCase 금지) |
| Parameter | `ALL_CAPS` (`DATA_WIDTH`) |
| 인스턴스 | `u_` prefix (`u_fifo`) |
| FSM 상태 | `typedef enum logic` + `UPPER_SNAKE_CASE` (`ST_IDLE`) |
| UVM 멤버 핸들 | `m_` prefix 허용 (업계 관행). `u_`는 RTL 인스턴스 전용 |

상세: `references/coding-style-guide.md`, `skills/systemverilog/SKILL.md`
