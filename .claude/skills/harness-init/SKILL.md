---
name: harness-init
description: This skill should be used when the user wants to initialize a new project, start a new project with the harness workflow, or says "프로젝트 시작", "init", "초기화".
argument-hint: <project-name> [--test-cmd <command>]
allowed-tools: [Read, Write, Edit, Bash]
user-invocable: true
---

# /harness-init — 프로젝트 초기화

인자: `$ARGUMENTS`

## 실행 순서

### 1. 초기화

인자에서 프로젝트 이름 파싱. 없으면 현재 디렉토리 이름 사용.

```bash
python flow.py init <name>
# 테스트 커맨드가 pytest가 아닌 경우:
python flow.py init <name> --test-cmd "npm test"
```

### 2. 기획 시작

초기화 완료 후 `/harness-plan`을 이어서 실행한다.  
기획의 모든 단계(spec 대화, 검토, 태스크 분해, phase 전환)는 `/harness-plan`이 담당한다.

## Phase 흐름

planning → implementation → testing → shipped (완료)

## 완료 기준

- `harness/project.json`의 `current_phase`가 `implementation`
- `harness/tasks.json`에 최소 1개 이상의 태스크
- `plan/review.md` 작성 완료
- `CLAUDE.md` 상태 섹션 업데이트됨
