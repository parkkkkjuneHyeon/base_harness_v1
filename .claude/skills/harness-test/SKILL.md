---
name: harness-test
description: Run tests, analyze results, and manage Fix tasks for the testing phase. Use when the user says "테스트", "테스트 실행", "test", "검증", or when in the testing phase.
allowed-tools: [Read, Write, Bash]
user-invocable: true
---

# /harness-test — 테스트 실행 & 결과 처리

## 실행 순서

### 1. 현재 phase 확인

```bash
python flow.py status
```

testing phase가 아니면 사용자에게 알린다:
> "현재 [phase] 단계예요. 테스트는 testing phase에서 실행해요. `python flow.py phase next`로 전환할까요?"

### 2. 테스트 실행

```bash
python flow.py test
```

### 3. 결과 분석

**전체 통과 시** → 5단계(shipped 전환)로 바로 이동한다.

**실패 시** → 실패 항목별로 규모를 판단한다:

| 규모 | 기준 | 처리 방법 |
|------|------|----------|
| 소규모 | 버그 픽스, 설정 오류, 엣지 케이스 | testing phase에서 Fix 태스크 처리 |
| 대규모 | 설계 오류, 기능 누락, 구조 변경 필요 | implementation으로 phase back |

판단이 애매하면 사용자에게 물어본다:
> "이 실패는 [설명]인데, 간단한 수정으로 해결 가능해 보여요 / 구조적인 재작업이 필요해 보여요. 어떻게 할까요?"

### 4. 실패 처리

**소규모 수정:**
```bash
python flow.py task add "Fix: <실패 내용>" --parent <failed_task_id>
python flow.py task start <fix_id>
```
Fix 태스크 구현 후 2단계부터 반복한다.

**대규모 재작업:**
```bash
python flow.py phase back
```
> "implementation으로 돌아갔어요. `/harness-task`로 수정 작업을 시작해요."

### 5. 전체 통과 — shipped 전환

```bash
python flow.py phase next
python flow.py files snap
```

> "모든 테스트를 통과했어요. shipped phase로 전환했어요.  
> `plan/retro.md`에 회고를 남기거나 `/harness-plan`으로 다음 기능을 기획할 수 있어요."
