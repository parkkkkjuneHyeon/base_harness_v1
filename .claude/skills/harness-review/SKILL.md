---
name: harness-review
description: Review current implementation progress — check completed tasks vs actual code, file structure, changelog, and identify gaps or quality issues. Use when user says "검토해줘", "리뷰해줘", "잘 되고 있어?", "중간 점검".
allowed-tools: [Read, Bash, Glob, Grep]
user-invocable: true
---

# /harness-review — 구현 진행 상황 검토

## 실행 순서

### 1. 현재 상태 파악
```bash
python flow.py status
python flow.py trace
python flow.py files snap   # 항상 최신 스냅샷 찍고
python flow.py files list   # 그 결과 출력
```

### 2. spec vs 진행률 비교
- `plan/spec.md` 읽어서 목표/범위 파악
- done 태스크 목록과 spec 요구사항 비교
- backlog에 누락된 항목이 있으면 지적

### 3. 완료 태스크 vs 실제 코드 검토
- `harness/tasks.json`의 done 태스크 각각에 대해:
  - 해당 기능이 실제로 코드에 구현되었는지 확인 (Glob/Grep 활용)
  - `changelog.md` 항목과 코드 변경이 일치하는지 확인

### 4. 파일 구조 검토
- 설명 없는 파일이 많으면 `files describe` 권장
- 불필요하거나 고아 파일이 있으면 지적
- 파일 구조가 spec의 기술 스택/아키텍처와 맞는지 확인

### 5. 태스크 품질 체크
- in_progress 상태로 오래된 태스크가 있는지 (생성일 기준)
- blocked 태스크 해결 진척이 없는지
- skipped 태스크가 실제로 건너뛰어도 괜찮은 것인지

### 6. 현재 phase 완료 기준 체크

**implementation phase라면:**
- 모든 spec 요구사항이 태스크로 분해되었는가?
- 주요 태스크가 done 상태인가?
- 테스트 작성 태스크가 있는가?

**testing phase라면:**
- 테스트가 실행되었는가? (`logs/testing/` 확인)
- 마지막 테스트 결과가 통과인가?
- 실패 후 Fix 태스크가 처리되었는가?
- Fix의 규모 판단:
  - 소규모(버그·설정) → testing phase에서 Fix 태스크로 처리
  - 대규모(설계 오류·기능 누락) → `phase back`으로 implementation 복귀 권장

### 7. 보고 형식
다음 항목을 명확하게 정리:

**잘 되고 있는 점**
- 완료된 태스크와 구현 확인된 기능 나열

**주의가 필요한 점**
- 코드와 태스크 불일치, 누락 기능, 오래된 블로킹 등

**권장 다음 액션 (1가지)**
- 지금 당장 해야 할 것 하나만 구체적으로 제시
