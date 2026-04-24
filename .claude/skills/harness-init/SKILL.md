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

### 2. spec 대화 루프
AI가 대화를 주도하며 스펙을 **결정될 때마다 즉시 spec.md에 추가**해 차곡차곡 쌓아간다.  
전체를 완성한 뒤 한꺼번에 쓰지 않는다. 확정된 항목만 그때그때 파일에 기록한다.

#### 시작
첫 질문은 하나만, 열린 형태로:
> "어떤 걸 만들고 싶으세요? 거칠게라도 말씀해 주시면 제가 구체화해 드릴게요."

#### 반복 사이클 (항목별로 반복)
하나의 항목(목표 / 기능 / 기술스택 / 범위 등)에 대해 아래 사이클을 돈다.

**① 대화로 탐색**  
자유롭게 대화하며 해당 항목을 구체화한다.  
선택지가 있으면 옵션을 번호로 제시한다:
> "인증 방식은 어떻게 할까요?  
> 1안. JWT (stateless, 모바일 친화적)  
> 2안. 세션 쿠키 (서버 관리 필요, 웹에 적합)"

사용자가 떠올리지 못한 고려사항이 있으면 AI가 먼저 제안한다.

**② 확정 확인**  
방향이 잡히면 spec.md 추가 전에 반드시 확인한다:
> "1안 JWT로 spec에 추가할까요?"

**③ 즉시 기록**  
사용자가 OK하면 (`그래`, `ㅇㅇ`, `좋아` 등) 해당 항목을 바로 `plan/spec.md`에 append한다:
```bash
# spec.md가 없으면 헤더 먼저 생성, 있으면 append
```
추가 후 짧게 확인:
> "추가했어요. 다음은 [다음 항목] 얘기해 볼까요?"

**④ 다음 항목으로**  
모든 항목이 끝날 때까지 반복한다.  
권장 순서 (spec.md 섹션 순서와 동일):

| 순서 | 항목 | spec.md 섹션 |
|------|------|-------------|
| 1 | 목표 | `## 목표` |
| 2 | 핵심 기능 | `## 핵심 기능` |
| 3 | 기술 스택 | `## 기술 스택` |
| 4 | 범위 제외 | `## 범위 제외` |
| 5 | 제약 조건 | `## 제약 조건` |
| 6 | 기타 결정 | `## 기타 결정 사항` |

항목이 해당 없으면 섹션에 "해당 없음"으로 기록하고 넘어간다.

#### 종료 조건
사용자가 "됐어", "이걸로 가자", "완료" 등을 말하거나 모든 섹션이 기록되면 루프 종료.  
`plan/spec.md`는 이미 대화 중 완성되어 있다. → 3단계로 진행.

### 3. 기획서 검토
`plan/spec.md`를 읽고 `plan/review.md`에 검토 결과 작성:
- 목표가 명확한가?
- 핵심 기능이 구체적인가?
- 범위가 적절한가? (너무 많거나 너무 적지 않은가)
- 기술 스택이 목표에 적합한가?
- 빠진 고려사항이 있는가?

작성 후 사용자에게 검토 결과를 요약해서 보여주고 확인을 구한다:
> "검토 결과예요. [주요 피드백 요약]. 이 방향으로 태스크 분해할까요?"

사용자가 수정을 요청하면 spec.md를 업데이트하고 검토를 다시 수행한다.  
OK가 나오면 4단계로 진행한다.

### 4. 태스크 분해
spec.md 기반으로 태스크를 **먼저 목록으로 제시**하고, 사용자 확인 후 추가한다.

**① 분해 목록 제시**  
spec의 핵심 기능을 기준으로 태스크를 나눠 채팅에 보여준다:
```
[제안 태스크 목록]
1. 태스크 제목 (설명)
2. 태스크 제목
3. 태스크 제목 (태스크 2 완료 후 가능)
...
```
- 각 태스크는 독립적으로 완료 가능해야 함
- 너무 크면 세분화 (하루 이내 완료 기준)
- 의존 관계가 있으면 명시

**② 사용자 확인**  
> "이렇게 나눌까요? 추가하거나 빼고 싶은 태스크 있으신가요?"

수정 요청이 있으면 목록을 조정하고 재제시한다. OK가 나오면 ③으로 진행.

**③ 일괄 추가**
```bash
python flow.py plan log "태스크 분해 근거: ..."

python flow.py task add "태스크 제목"
python flow.py task add "태스크 제목" --desc "상세 조건이나 구현 힌트"
python flow.py task add "의존 태스크" --parent <부모id>
# ...
```

### 5. 기획 로그 기록
```bash
python flow.py plan log "기획 완료: <태스크 수>개 태스크 생성"
```

### 6. 구현 phase로 전환
```bash
python flow.py phase next --force   # 기획 phase는 태스크가 backlog 상태이므로 --force 필요
python flow.py status
```

### 7. 사용자에게 보고
- 생성된 태스크 목록
- 실제 코드는 `<name>/` 디렉토리에 작성함을 안내 (예: `aa/` 안에 구현)
- 다음 할 일: `/harness-status` 또는 첫 번째 태스크 바로 시작

## Phase 흐름
planning → implementation → testing → shipped (완료)

## 완료 기준
- `harness/project.json`의 `current_phase`가 `implementation`
- `harness/tasks.json`에 최소 1개 이상의 태스크
- `plan/review.md` 작성 완료
- `CLAUDE.md` 상태 섹션 업데이트됨
