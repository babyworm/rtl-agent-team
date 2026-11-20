[English](README.md)

# RTL Agent Team

RTL 설계와 검증을 위한 Claude Code 플러그인입니다. 91개 전문 AI 에이전트와
스킬 55개가 명세, 아키텍처, 마이크로아키텍처, RTL 구현, 검증, 설계 노트
작성을 지원합니다.

## 빠른 시작

Claude Code에서 배포 버전(v0.14.6)을 설치합니다.

```text
/plugin marketplace add babyworm/rtl-agent-team
/plugin install rtl-agent-team
```

RTL 프로젝트 디렉토리에서 도구를 준비하고 프로젝트를 초기화한 뒤, 명세를
지정해 설계를 시작합니다.

```text
/rtl-agent-team:rat-setup
/rtl-agent-team:rat-init-project
/rtl-agent-team:rat-auto-design specs/design.md
```

원격 EDA를 사용할 때는 `rat-setup`에 SSH 별칭과 실행할 단계를 알려 주세요.
필요하면 사이트 초기화 스크립트도 지정합니다. 접속 정보와 생성된 설정은
이 플러그인 저장소 밖에 보관합니다. [EDA 및 Docker 설정](plugin_docs/eda-setup-guide.md)

## 작업별 스킬

| 목표 | 스킬 |
| --- | --- |
| P1~P6 전체 실행 | `rat-auto-design` |
| 마이크로아키텍처와 BFM까지 설계 대안 탐색 | `rat-dse` |
| RTL 구현 전 설계 검토 | `rat-p1p3-spec-uarch` |
| 승인된 마이크로아키텍처로 RTL 구현 및 검증 | `rat-p4p5-impl-verify` |
| 기능 검증 완료 여부 확인 | `rtl-p5a-functional-closure` |
| P5A 통과 후 합성·타이밍·CDC 확인 | `rtl-p5b-silicon-validation` |

스킬 이름 앞에 `/rtl-agent-team:`을 붙여 실행합니다. 전체 자동화는 팀 도구를
사용할 수 있을 때 팀 모드로 진행하며, Phase 5는 통합 검증을 실행합니다.
순차 실행은 `--no-team`을 지정합니다. 같은 명령으로 재개하면 유효한 검증
결과를 재사용합니다.

Codex 교차검증은 기본적으로 꺼져 있습니다. 실행할 때 전체 또는 특정 단계의
교차검증을 요청하거나, 프로젝트의 `rat_config.json`에서
`review.codex_cross_review`를 `true`로 설정합니다. [교차검증 동작](runtime/phase-dispatch.md)

## 로컬 플러그인 개발

이미 `try-2.0`을 받아 뒀다면 해당 디렉토리에서 `claude --plugin-dir .`로
현재 작업 트리를 읽습니다. 새로 받는 경우에는 아래 명령을 실행합니다.

```bash
git clone --branch try-2.0 https://github.com/babyworm/rtl-agent-team.git
cd rtl-agent-team
claude --plugin-dir .
```

- [기여 안내](CONTRIBUTING_kr.md) · [테스트](tests/README_kr.md)
- [기술 문서](plugin_docs/README.md) · [모델 선택](runtime/model-selection.md)
- [변경 이력](CHANGELOG.md) · [MIT 라이선스](LICENSE)
