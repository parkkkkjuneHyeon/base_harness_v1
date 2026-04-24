---
name: harness-status
description: This skill should be used when the user asks about project status, current tasks, what to work on next, progress overview, or says "상태", "현재 상태", "뭐 하면 돼", "어디까지 했어".
allowed-tools: [Read, Bash]
user-invocable: true
---

# /harness-status — 현재 상태 확인 & 다음 액션 제안

## 실행 순서

### 1. 현재 상태 출력
```bash
python flow.py status
python flow.py trace
```

in_progress 태스크가 있으면 상세 컨텍스트도 가져온다:
```bash
python flow.py task show <in_progress_id>
```
세션이 재개된 상황이라면 이 정보로 "어디까지 했는지"를 파악하고 요약해준다.

### 2. Phase별 다음 액션 제안

**planning** 단계:
- spec.md가 비어있고 태스크도 없음 → `/harness-init`으로 spec 대화 시작 권장
- spec.md가 있고 태스크도 없음 → review.md 확인 후 태스크 분해 제안 (`/harness-init` 4단계부터)
- 태스크가 있으면 → 구현 phase 전환 제안
  ```bash
  python flow.py phase next --force
  ```

**implementation** 단계:
- in_progress 태스크 있음 → `task show`로 로그 확인 후 해당 태스크 이어서 작업
- in_progress 없고 backlog 있음 → 첫 번째 backlog 태스크 픽업 제안
  ```bash
  python flow.py task start <id>
  ```
- blocked 태스크 있음 → 블로킹 이유 분석 후 해결 방법 제안
- 모든 태스크 done/skipped → phase next 제안
  ```bash
  python flow.py phase next
  ```
- 남은 태스크가 불필요해졌으면 → skip 제안
  ```bash
  python flow.py task skip <id> "<이유>"
  ```

**testing** 단계:
- 테스트 미실행 → 테스트 실행 제안
  ```bash
  python flow.py test
  ```
- 테스트 실패 시 Fix 태스크 처리:
  - **소규모 수정** (버그 픽스, 설정 등) → testing phase에서 그대로 Fix 태스크 진행
    ```bash
    python flow.py task add "Fix: <문제>" --parent <failed_task_id>
    python flow.py task start <fix_id>
    ```
  - **대규모 재구현** (설계 오류, 기능 누락 등) → implementation으로 phase back 후 진행
    ```bash
    python flow.py phase back
    ```
- 모든 테스트 통과 → shipped phase 전환 제안
  ```bash
  python flow.py phase next
  ```

**shipped** 단계:
- 프로젝트 완료 상태
- changelog.md 최종 정리 제안
- 회고가 필요하면 `plan/retro.md` 작성 제안

### 3. 블로킹 태스크 처리
blocked 태스크가 있으면:
- `logs/<phase>/task-<id>-blocked-*.md` 읽어서 상세 이유 파악
- 해결 방법 구체적으로 제안
- 해결 가능하면 Fix 태스크 생성:
  ```bash
  python flow.py task add "Fix: <이유>" --parent <blocked_id>
  ```

### 4. 요약 보고
- 현재 phase 및 진행률 (건너뜀 태스크는 분모에서 제외)
- 세션 재개라면: in_progress 태스크 기준으로 "어디까지 했는지" 한 줄 요약
- 지금 당장 해야 할 것 1가지
- 전체 완료까지 남은 태스크 수
