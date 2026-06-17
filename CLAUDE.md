# crawling_search

<!-- HARNESS:STATUS:START -->
## 프로젝트 상태
Phase: **implementation** | 2026-04-24T23:52 업데이트

## 진행중 태스크
- #20 [in_progress] 셀렉터 패턴 개선 — 19-1: nth-child 나열 금지 프롬프트(good/bad 예시). 19-2: 테이블 감지시 컬럼→필드 매핑 전용 프롬프트. 19-3: 배열→단일 패턴 후처리 폴백.

## 대기 태스크
- #21 [backlog] 셀렉터 검증 강화 — 20-1: nth-child 배열 즉시 거부→재시도. 20-2: 리스트 결과 최소 2개 이상. 20-3: 다중 리스트 필드 수 일관성 체크(±1). 20-4: LLM 의미 재확인(off 기본).

## 완료: 19 / 21

## 최근 변경 (최근 5개)
- 23:52 task#20 시작 — 셀렉터 패턴 개선
- 23:52 변경: 18-1~18-4 구현: nav/layout 노이즈 조건부 제거, 테이블 우선탐지, 데이터밀도 스코어, 제목맥락 포함, 키워드→테이블 우선순위 재조정. 결과: 2→5 PASS
- 23:52 task#19 완료 — HTML 섹션 선택 개선
- 23:46 task#19 시작 — HTML 섹션 선택 개선
- 23:46 변경: pytest 골든 테스트 작성 완료. 기준선: 7개 중 2 PASS / 4 FAIL / 1 SKIP. Case A 상한가 전부 실패, Case B 1개만 추출. tests/test_selector_agent_golden.py
<!-- HARNESS:STATUS:END -->

<!-- HARNESS:FILES:START -->
## 파일 인덱스
마지막 스냅: 2026-04-25T00:26

(설명 있는 파일 없음 — `python flow.py files describe <path> "<설명>"` 실행)
<!-- HARNESS:FILES:END -->

## 프로젝트 디렉토리
실제 코드는 `crawling_search/` 에 작성한다.

## 프로젝트 개요
<!-- 프로젝트 설명을 여기에 작성하세요 -->

## 코딩 규칙
<!-- 코딩 컨벤션, 주의사항 등을 여기에 작성하세요 -->

## 세션 시작 프로토콜
새 세션 시작 시 반드시:
1. 위 상태 섹션 확인
2. `python flow.py status` 실행
3. in_progress 태스크부터 재개, 없으면 backlog에서 픽업

## 작업 규칙
- 태스크 시작: `python flow.py task start <id>`
- 태스크 완료: `python flow.py task done <id> --changelog "<변경내용>"`
- 태스크 재개: `python flow.py task reopen <id>`  ← 완료 실수 복구
- 태스크 수정: `python flow.py task edit <id> --title "<새 제목>"`
- 태스크 건너뜀: `python flow.py task skip <id> ["<이유>"]`
- 태스크 설명: `python flow.py task desc <id> "<설명>"`
- 태스크 상세: `python flow.py task show <id>`
- 블로커 발생: `python flow.py task block <id> "<이유>"` + `python flow.py task add "Fix: <이유>"`
- 기획 로그: `python flow.py plan log "<내용>"`
- 세션 로그: `python flow.py log "<내용>"`
- 태스크 상세 로그: `python flow.py task log <id> "<내용>"`
- 전체 이벤트 추적: `python flow.py trace`
- 특정 태스크 추적: `python flow.py trace --task <id>`
- phase 완료 시: `python flow.py phase next`  (미완 태스크 있으면 경고)
- phase 강제 전환: `python flow.py phase next --force`
- phase 롤백: `python flow.py phase back`
- 파일 구조 갱신: `python flow.py files snap`
- 파일 설명 추가: `python flow.py files describe <path> "<설명>" [--task <id>]`
- 파일 목록: `python flow.py files list`
