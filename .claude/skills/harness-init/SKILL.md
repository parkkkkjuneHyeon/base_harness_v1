---
name: harness-init
description: This skill should be used when the user wants to initialize a new project, start a new project with the harness workflow, or says "프로젝트 시작", "init", "초기화".
argument-hint: <project-name> [--test-cmd <command>]
allowed-tools: [Read, Write, Edit, Bash]
user-invocable: true
---

# /harness-init — 프로젝트 초기화 & 기획 단계

인자: `$ARGUMENTS`

## 실행 순서

### 1. 초기화
인자에서 프로젝트 이름 파싱. 없으면 현재 디렉토리 이름 사용.

```bash
python flow.py init <name>
# 테스트 커맨드가 pytest가 아닌 경우:
python flow.py init <name> --test-cmd "npm test"
```

### 2. 기획서 작성 안내
사용자에게 `plan/spec.md`를 작성하도록 안내한다.
사용자가 "작성했어", "됐어", "완료" 등을 말하면 3단계로 진행.

### 3. 기획서 검토
`plan/spec.md`를 읽고 `plan/review.md`에 검토 결과 작성:
- 목표가 명확한가?
- 범위가 적절한가?
- 빠진 고려사항은?
- 기술 스택이 적합한가?

### 4. 태스크 분해
spec.md 기반으로 태스크를 분해한다:
- 각 태스크는 독립적으로 완료 가능해야 함
- 너무 크면 세분화 (하루 이내 완료 기준)
- planning 로그에 분해 근거 기록

```bash
# 분해 근거 먼저 기록
python flow.py plan log "태스크 분해 근거: ..."

# 태스크 추가
python flow.py task add "태스크 제목"
python flow.py task add "태스크 제목"
# ...

# 블로커 관계가 있는 경우
python flow.py task add "의존 태스크" --parent <부모id>
```

### 5. 기획 로그 기록
```bash
python flow.py log "기획 완료: <태스크 수>개 태스크 생성"
```

### 6. 구현 phase로 전환
```bash
python flow.py phase next
python flow.py status
```

### 7. 사용자에게 보고
- 생성된 태스크 목록
- 다음 할 일: `/harness-status` 또는 첫 번째 태스크 바로 시작

## 완료 기준
- `harness/project.json`의 `current_phase`가 `implementation`
- `harness/tasks.json`에 최소 1개 이상의 태스크
- `plan/review.md` 작성 완료
- `CLAUDE.md` 상태 섹션 업데이트됨
