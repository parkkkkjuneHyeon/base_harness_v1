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

세션이 재개된 상황이라면 이 정보로 "어디까지 했는지"를 한 줄로 요약해준다.

### 2. Phase별 다음 액션 제안 (1가지만)

**planning** 단계:
- spec.md 없음 → `/harness-plan` 시작 권장
- spec.md 있고 태스크 없음 → `/harness-plan` 4단계(태스크 분해)부터 권장
- 태스크 있음 → implementation 전환 제안
  ```bash
  python flow.py phase next --force
  ```

**implementation** 단계:
- in_progress 태스크 있음 → `/harness-task`로 이어서 작업 권장
- backlog 태스크 있음 → `/harness-task`로 다음 태스크 픽업 권장
- blocked 태스크 있음 → `/harness-task`로 블로커 해결 권장
- **모든 태스크 done/skipped** → 리뷰 후 phase 전환 강력 권장:
  > "모든 태스크가 완료됐어요. `/harness-review`로 구현을 점검한 뒤 testing phase로 넘어가세요."
  ```bash
  python flow.py phase next
  ```

**testing** 단계:
- `/harness-test` 실행 권장 (테스트 실행·결과 분석·Fix 처리는 harness-test가 담당)

**shipped** 단계:
- 완료 상태. `plan/retro.md` 회고 작성 또는 `/harness-plan`으로 다음 기능 기획 제안

### 3. 요약 보고

- 현재 phase 및 진행률 (건너뜀 태스크는 분모에서 제외)
- 세션 재개라면: in_progress 태스크 기준 "어디까지 했는지" 한 줄
- **지금 당장 해야 할 것 1가지만** 구체적으로 제시
- 전체 완료까지 남은 태스크 수
