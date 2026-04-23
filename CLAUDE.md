# seoul_bus_root_v1

<!-- HARNESS:STATUS:START -->
## 프로젝트 상태
Phase: **planning** | 2026-04-24T00:23 초기화

## 대기 태스크
(아직 태스크 없음)

## 완료: 0 / 전체: 0
<!-- HARNESS:STATUS:END -->

<!-- HARNESS:FILES:START -->
## 파일 인덱스
(아직 스냅샷 없음 — `python flow.py files snap` 실행)
<!-- HARNESS:FILES:END -->

## 프로젝트 디렉토리
실제 코드는 `seoul_bus_root_v1/` 에 작성한다.

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
- 블로커 발생: `python flow.py task block <id> "<이유>"` + `python flow.py task add "Fix: <이유>"`
- 기획 로그: `python flow.py plan log "<내용>"`
- 세션 로그: `python flow.py log "<내용>"`
- 태스크 상세 로그: `python flow.py task log <id> "<내용>"`
- 전체 이벤트 추적: `python flow.py trace`
- 특정 태스크 추적: `python flow.py trace --task <id>`
- phase 완료 시: `python flow.py phase next`
- phase 롤백: `python flow.py phase back`
- 파일 구조 갱신: `python flow.py files snap`
- 파일 설명 추가: `python flow.py files describe <path> "<설명>" [--task <id>]`
- 파일 목록: `python flow.py files list`
