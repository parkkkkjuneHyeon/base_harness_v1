---
name: harness-task
description: Execute a single task — pick up, implement, and complete one task. Use when the user says "태스크 시작", "다음 태스크", "구현해", "작업 시작", or when starting work on a specific task id.
argument-hint: [<task-id>]
allowed-tools: [Read, Write, Edit, Bash]
user-invocable: true
---

# /harness-task — 태스크 실행 사이클

인자: `$ARGUMENTS` (태스크 id를 넘기면 해당 태스크, 없으면 자동 픽업)

## 실행 순서

### 1. 태스크 선택

인자로 id가 넘어오면 해당 태스크를 사용한다.  
없으면 in_progress → backlog 순으로 첫 번째 태스크를 자동 픽업한다.

```bash
python flow.py status          # 전체 현황 확인
python flow.py task show <id>  # 선택된 태스크 상세 확인
```

태스크가 없으면 사용자에게 알리고 종료한다:
> "처리할 태스크가 없어요. `/harness-plan`으로 태스크를 추가하거나 `/harness-status`로 현황을 확인해보세요."

### 2. 태스크 시작

in_progress가 아닌 경우에만 시작한다 (이미 in_progress면 이어서 진행):

```bash
python flow.py task start <id>
```

태스크의 제목, 설명, 로그를 기반으로 **구현 컨텍스트를 요약**해 사용자에게 보여준다:
- 무엇을 구현해야 하는지
- 관련 파일이나 선행 태스크가 있다면 언급
- 예상 작업 범위

### 3. 구현

태스크 설명과 spec.md를 참고해 실제 코드를 작성한다.  
구현 중 예상치 못한 블로커가 발생하면:

```bash
python flow.py task block <id> "<이유>"
python flow.py task add "Fix: <이유>"
```

블로커 없이 완료되면 4단계로 진행한다.

### 4. 태스크 완료

```bash
python flow.py task done <id> --changelog "<변경 내용 한 줄 요약>"
python flow.py files snap
```

### 5. 다음 액션 제안

완료 후 남은 태스크 수를 확인한다:

```bash
python flow.py status
```

- **backlog 태스크가 남아 있음** → 다음 태스크 제안:
  > "태스크 #<id> 완료했어요. 다음은 #<next_id> [제목]이에요. 바로 시작할까요?"

- **모든 태스크 done/skipped** → 리뷰 및 phase 전환 제안:
  > "모든 태스크가 완료됐어요. `/harness-review`로 구현 상태를 점검한 뒤 testing phase로 넘어가는 걸 권장해요."
