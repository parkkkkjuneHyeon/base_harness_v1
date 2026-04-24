# base_harness_v1

Claude Code / Codex 같은 AI 코딩 도구로 **바이브코딩**할 때 쓰는 프로젝트 워크플로우 하네스.

기획 → 구현 → 테스트 → 완료 사이클을 체계적으로 관리하고, 태스크 추적·이벤트 로깅·파일 인덱스를 자동화한다.

---

## 핵심 개념: 역할 분리

이 하네스는 **사람(유저)** 과 **AI** 의 역할을 명확히 나눈다.

| 구분 | 역할 |
|------|------|
| **유저** | 방향 결정, 선택, 확인 |
| **AI** | CLI 실행, spec 작성, 태스크 분해·추적, 구현, 로깅, 테스트 |

유저는 스킬 명령어(`/harness-init`, `/harness-status`, `/harness-review`)만 입력하면 된다.  
`python flow.py ...` CLI는 AI가 직접 실행한다. 유저가 치는 명령어가 아니다.

---

## 시작하기

### 1. Claude Code를 base_harness_v1 디렉토리에서 열기

`base_harness_v1/`이 워크스페이스다. 복사할 필요 없다.

### 2. 새 프로젝트 초기화

```
/harness-init aa
```

AI가 `python flow.py init aa`를 실행하고 `aa/` 디렉토리와 하네스 파일들을 생성한다.

### 3. spec 대화

AI가 "어떤 걸 만들고 싶으세요?"로 시작해서 대화를 주도한다.  
항목별로 옵션을 제안하고 → 유저가 선택하면 → 해당 항목을 `plan/spec.md`에 즉시 추가한다.  
대화가 끝날 때 spec.md는 이미 완성되어 있다.

### 4. 이후는 AI가 진행

AI가 spec.md를 검토하고 결과를 보여준다 → 유저 확인 → 태스크 분해 목록을 제안한다 → 유저 확인 → 구현 시작.  
이후엔 `/harness-status`로 현황 확인 및 다음 액션을 받으면 된다.

---

## 유저가 쓰는 명령어 (스킬)

Claude Code 채팅창에서 입력한다.

| 명령어 | 설명 |
|--------|------|
| `/harness-init <프로젝트명>` | 새 프로젝트 초기화 + spec 대화 + 태스크 분해 |
| `/harness-status` | 현재 phase·태스크 현황 + 다음 할 일 제안 |
| `/harness-review` | 진행 상황 검토 — spec 대비 누락 기능, 코드 일치 여부 확인 |

---

## Phase 흐름

```
planning → implementation → testing → shipped
```

각 phase는 `phase next`로 전진, `phase back`으로 롤백할 수 있다.  
`phase next` 실행 시 미완 태스크(backlog/in_progress)가 있으면 경고 후 중단된다. `--force`로 강제 전환 가능.

### planning
1. AI와 대화로 `plan/spec.md` 작성 — 항목 확정마다 즉시 파일에 추가
2. AI가 `plan/review.md`에 검토 결과 작성 → 유저 확인
3. AI가 태스크 분해 목록 제안 → 유저 확인 → 일괄 등록
4. `phase next --force`로 구현 단계로 이동

### implementation
- AI가 backlog 태스크를 순서대로 픽업하여 구현
- 블로커 발생 시 `blocked` 상태로 전환 + Fix 태스크 생성
- 불필요해진 태스크는 `task skip`으로 건너뜀 처리 (완료율 분모에서 제외)
- 태스크 완료 시 `task done --changelog "..."` 로 완료 + changelog 동시 기록
- 모든 태스크 done/skipped → `phase next`로 테스트 단계로 이동

### testing
- AI가 `python flow.py test` 실행
- 테스트 실패 시 Fix 태스크 처리:
  - **소규모** (버그 픽스, 설정) → testing phase에서 Fix 태스크 진행
  - **대규모** (설계 오류, 기능 누락) → `phase back`으로 implementation 복귀
- 전체 통과 → `phase next`로 완료 단계로 이동

### shipped
- 프로젝트 완료 선언
- `changelog.md` 최종 정리 권장

---

## spec.md 구조

`python flow.py init <name>` 실행 시 `plan/spec.md`가 아래 구조로 생성된다.  
AI가 대화 중 각 섹션에 내용을 추가한다.

```markdown
## 목표
## 핵심 기능
## 기술 스택
## 범위 제외
## 제약 조건
## 기타 결정 사항
```

---

## 파일 구조

`python flow.py init aa` 실행 시 생성되는 구조:

```
base_harness_v1/
├── flow.py                       # CLI (AI가 실행)
├── harness_hook_session_start.py # SessionStart 훅 스크립트
├── CLAUDE.md                     # 상태 자동 업데이트 (세션 간 컨텍스트)
├── changelog.md                  # 변경 이력
├── .gitignore
├── .claude/
│   ├── settings.json             # SessionStart 훅 설정
│   ├── settings.local.json       # 개인 권한 설정 (gitignore)
│   └── skills/
│       ├── harness-init/         # /harness-init 스킬
│       ├── harness-status/       # /harness-status 스킬
│       └── harness-review/       # /harness-review 스킬
├── plan/
│   ├── spec.md                   # 기획서 (AI와 대화로 작성)
│   └── review.md                 # AI의 기획 검토 결과
├── harness/
│   ├── project.json              # 현재 phase, 프로젝트 설정
│   ├── tasks.json                # 전체 태스크 목록
│   ├── phases.json               # phase 진행 상태
│   └── files.json                # 파일 인덱스 (경로·설명·태스크 연결)
├── logs/
│   ├── events.jsonl              # append-only 전체 이벤트 로그
│   ├── planning/                 # 기획 단계 로그
│   ├── implementation/           # 구현 단계 로그 (태스크별 .md)
│   ├── testing/                  # 테스트 실행 결과
│   └── sessions/                 # 세션별 일지
└── aa/                           # 실제 프로젝트 코드 (AI가 여기에 구현)
    └── ...
```

하네스 관리 파일(`harness/`, `logs/`, `plan/`)은 루트에, 실제 코드는 `aa/` 안에 분리된다.

---

## AI가 사용하는 CLI 레퍼런스

유저가 직접 칠 필요는 없다. AI가 자동으로 호출한다.

```bash
# 초기화
python flow.py init <name> [--test-cmd "npm test"]

# 상태 확인
python flow.py status

# 태스크 관리
python flow.py task add "<제목>" [--desc "<설명>"] [--parent <id>]
python flow.py task start <id>
python flow.py task done <id> --changelog "<변경내용>"   # 완료 + changelog 동시 기록
python flow.py task done <id> --no-changelog             # changelog 없이 완료
python flow.py task reopen <id>                          # 완료 실수 복구 → in_progress
python flow.py task edit <id> --title "<새 제목>"        # 제목 수정
python flow.py task desc <id> "<설명>"                   # 설명 추가/수정
python flow.py task show <id>                            # 상세 조회 (설명·로그 포함)
python flow.py task block <id> "<이유>"
python flow.py task skip <id> ["<이유>"]                 # 불필요 태스크 건너뜀
python flow.py task log <id> "<내용>"

# 로깅
python flow.py log "<세션 메모>"
python flow.py plan log "<기획 메모>"
python flow.py changelog "<변경 내용>"

# Phase
python flow.py phase next           # 다음 phase로 전진 (미완 태스크 있으면 경고)
python flow.py phase next --force   # 미완 태스크 있어도 강제 전환
python flow.py phase back           # 이전 phase로 롤백

# 이벤트 추적
python flow.py trace
python flow.py trace --task <id>
python flow.py trace --phase planning

# 테스트
python flow.py test

# 파일 인덱스
python flow.py files snap                                        # 프로젝트 디렉토리 스캔·등록
python flow.py files describe <path> "<설명>" [--task <id>]     # 파일/디렉토리 설명 추가
python flow.py files list                                        # 트리 + 설명 목록 출력
python flow.py files add <path> ["<설명>"] [--task <id>]        # 수동 등록 (snap 전)
python flow.py files remove <path>                              # 항목 제거
```

---

## 태스크 상태

```
backlog → in_progress → done
              ↓              ↓
           blocked        reopen → in_progress
              ↓
           skipped
```

| 상태 | 설명 |
|------|------|
| `backlog` | 대기 중 |
| `in_progress` | 진행 중 |
| `done` | 완료 |
| `blocked` | 블로킹 — Fix 태스크로 해결 |
| `skipped` | 건너뜀 — 완료율 분모에서 제외 |

완료율 표시: `완료: X / Y (건너뜀: Z)` — skipped는 분모에서 제외된다.

---

## 세션 재개

새 세션 시작 시 `SessionStart` 훅이 자동으로 실행된다:

1. `python flow.py status` — 전체 현황 주입
2. `python flow.py task show <id>` — in_progress 태스크가 있으면 상세 로그도 주입

AI는 이 정보로 "어디까지 했는지"를 파악하고 바로 이어서 작업한다.  
(`harness/project.json`이 없으면 훅은 실행되지 않는다.)

---

## CLAUDE.md 역할

세션이 끊겨도 AI가 상태를 파악할 수 있도록 `CLAUDE.md`에 현황이 자동 기록된다.

- `<!-- HARNESS:STATUS:START -->` ~ `<!-- HARNESS:STATUS:END -->` — 태스크 현황 자동 업데이트  
  (backlog는 최대 10개까지 표시, 초과분은 `python flow.py status`로 확인)
- `<!-- HARNESS:FILES:START -->` ~ `<!-- HARNESS:FILES:END -->` — 설명 있는 파일 인덱스 자동 업데이트
- 나머지 영역(프로젝트 개요, 코딩 규칙 등)은 유저가 자유롭게 편집 가능

---

## 파일 인덱스 활용법

파일 인덱스는 세션 간 "어떤 파일이 무슨 역할인지"를 CLAUDE.md에 유지하여, 새 세션에서 불필요한 파일 탐색을 줄여준다.

```bash
# 구현 시작 후 파일 생성 → snap으로 등록
python flow.py files snap

# 각 파일에 설명 추가 (태스크와 연결 가능)
python flow.py files describe aa/main.py "앱 진입점" --task 1
python flow.py files describe aa/models/ "데이터 모델 디렉토리"

# 파일 삭제·리팩토링 후 snap → stale 항목 정리
python flow.py files snap
python flow.py files remove aa/old_module.py
```

`files snap`은 삭제된 파일을 자동으로 `[stale]` 마킹하며, 설명이 있는 stale 항목은 CLAUDE.md에 별도 표시된다.
