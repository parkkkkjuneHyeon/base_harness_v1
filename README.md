# base_harness_v1

Claude Code / Codex 같은 AI 코딩 도구로 **바이브코딩**할 때 쓰는 프로젝트 워크플로우 하네스.

기획 → 구현 → 테스트 사이클을 체계적으로 관리하고, 태스크 추적·이벤트 로깅·파일 인덱스를 자동화한다.

---

## 핵심 개념: 역할 분리

이 하네스는 **사람(유저)** 과 **AI** 의 역할을 명확히 나눈다.

| 구분 | 역할 |
|------|------|
| **유저** | 기획서 작성, 방향 결정, 완료 확인 |
| **AI** | CLI 실행, 태스크 분해·추적, 구현, 로깅, 테스트 |

유저는 스킬 명령어(`/harness-init`, `/harness-status`)만 입력하면 된다.  
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
실제 코드는 `aa/` 안에, 하네스 관리 파일은 루트에 분리된다.

### 3. 기획서 작성

`plan/spec.md`를 열어 아래 항목을 채운다:
- **목표**: 무엇을 만드는가
- **범위**: 포함/제외 기능
- **기술 스택**: 언어, 프레임워크 등

완성하면 AI에게 "기획서 작성했어" 라고 알린다.

### 4. 이후는 AI가 진행

AI가 기획서를 검토하고, 태스크를 분해하고, 구현 phase로 넘어간다.  
이후엔 `/harness-status`로 현황 확인 및 다음 액션을 받으면 된다.

---

## 유저가 쓰는 명령어 (스킬)

Claude Code 채팅창에서 입력한다.

| 명령어 | 설명 |
|--------|------|
| `/harness-init <프로젝트명>` | 새 프로젝트 초기화 + 기획 단계 시작 |
| `/harness-status` | 현재 phase·태스크 현황 + 다음 할 일 제안 |

---

## Phase 흐름

```
planning → implementation → testing
```

각 phase는 `phase next`로 전진, `phase back`으로 롤백할 수 있다.

### planning
- 기획서(`plan/spec.md`) 작성
- AI가 검토(`plan/review.md`) 후 태스크 분해
- 태스크 생성 완료 → `phase next`로 구현 단계로 이동

### implementation
- AI가 backlog 태스크를 순서대로 픽업하여 구현
- 블로커 발생 시 `blocked` 상태로 전환 + Fix 태스크 자동 생성
- 태스크 완료 시 `task done --changelog "..."` 로 완료 + changelog 동시 기록
- 모든 태스크 완료 → `phase next`로 테스트 단계로 이동

### testing
- AI가 `python flow.py test` 실행
- 실패 시 Fix 태스크 생성 후 implementation으로 회귀
- 전체 통과 → 완료 선언

---

## 파일 구조

`python flow.py init aa` 실행 시 생성되는 구조:

```
base_harness_v1/
├── flow.py                  # CLI (AI가 실행)
├── CLAUDE.md                # 상태 자동 업데이트 (세션 간 컨텍스트)
├── changelog.md             # 변경 이력
├── .gitignore
├── plan/
│   ├── spec.md              # 기획서 (유저 작성)
│   └── review.md            # AI의 기획 검토 결과
├── harness/
│   ├── project.json         # 현재 phase, 프로젝트 설정
│   ├── tasks.json           # 전체 태스크 목록
│   ├── phases.json          # phase 진행 상태
│   └── files.json           # 파일 인덱스 (경로·설명·태스크 연결)
├── logs/
│   ├── events.jsonl         # append-only 전체 이벤트 로그
│   ├── planning/            # 기획 단계 로그
│   ├── implementation/      # 구현 단계 로그 (태스크별 .md)
│   ├── testing/             # 테스트 실행 결과
│   └── sessions/            # 세션별 일지
└── aa/                      # 실제 프로젝트 코드 (AI가 여기에 구현)
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
python flow.py task add "<제목>" [--parent <id>]
python flow.py task start <id>
python flow.py task done <id> --changelog "<변경내용>"   # 완료 + changelog 동시 기록
python flow.py task reopen <id>                          # 완료 실수 복구 → in_progress
python flow.py task edit <id> --title "<새 제목>"        # 제목 수정
python flow.py task block <id> "<이유>"
python flow.py task log <id> "<내용>"

# 로깅
python flow.py log "<세션 메모>"
python flow.py plan log "<기획 메모>"
python flow.py changelog "<변경 내용>"

# Phase
python flow.py phase next    # 다음 phase로 전진
python flow.py phase back    # 이전 phase로 롤백

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

## CLAUDE.md 역할

세션이 끊겨도 AI가 상태를 파악할 수 있도록 `CLAUDE.md`에 현황이 자동 기록된다.

- `<!-- HARNESS:STATUS:START -->` ~ `<!-- HARNESS:STATUS:END -->` — 태스크 현황 자동 업데이트  
  (backlog는 최대 10개까지 표시, 초과분은 `python flow.py status`로 확인)
- `<!-- HARNESS:FILES:START -->` ~ `<!-- HARNESS:FILES:END -->` — 설명 있는 파일 인덱스 자동 업데이트
- 나머지 영역(프로젝트 개요, 코딩 규칙 등)은 유저가 자유롭게 편집 가능

새 세션 시작 시 AI는 `CLAUDE.md` → `python flow.py status` 순서로 컨텍스트를 복원한다.

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
