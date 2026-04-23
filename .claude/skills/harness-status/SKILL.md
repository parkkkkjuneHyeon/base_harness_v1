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

### 2. Phase별 다음 액션 제안

**planning** 단계:
- spec.md가 비어있으면 → 기획서 작성 안내
- 태스크가 없으면 → `/harness-init` 실행 권장
- 태스크 있으면 → 구현 phase 전환 제안

**implementation** 단계:
- in_progress 태스크 있음 → 해당 태스크 이어서 작업
- in_progress 없고 backlog 있음 → 첫 번째 backlog 태스크 픽업 제안
  ```bash
  python flow.py task start <id>
  ```
- blocked 태스크 있음 → 블로킹 이유 분석 후 해결 방법 제안
- 모든 태스크 done → phase next 제안
  ```bash
  python flow.py phase next
  ```

**testing** 단계:
- 테스트 미실행 → 테스트 실행 제안
  ```bash
  python flow.py test
  ```
- 실패한 테스트 있음 → Fix 태스크 생성 안내
- 모든 테스트 통과 → 완료 선언, changelog 작성 제안

### 3. 블로킹 태스크 처리
blocked 태스크가 있으면:
- `logs/<phase>/task-<id>-blocked-*.md` 읽어서 상세 이유 파악
- 해결 방법 구체적으로 제안
- 해결 가능하면 Fix 태스크 생성:
  ```bash
  python flow.py task add "Fix: <이유>" --parent <blocked_id>
  ```

### 4. 요약 보고
- 현재 phase 및 진행률
- 지금 당장 해야 할 것 1가지
- 전체 완료까지 남은 태스크 수
