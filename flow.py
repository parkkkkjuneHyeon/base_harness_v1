#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
import subprocess
from datetime import datetime
from pathlib import Path
# 클로드가 사용하는 코드
HARNESS_DIR = Path("harness")
LOGS_DIR = Path("logs")
PLAN_DIR = Path("plan")
CLAUDE_MD = Path("CLAUDE.md")

STATUS_START = "<!-- HARNESS:STATUS:START -->"
STATUS_END = "<!-- HARNESS:STATUS:END -->"

CLAUDE_MD_TEMPLATE = """\
# {name}

{status_start}
## 프로젝트 상태
Phase: **planning** | {ts} 초기화

## 대기 태스크
(아직 태스크 없음)

## 완료: 0 / 전체: 0
{status_end}

## 프로젝트 디렉토리
실제 코드는 `{project_dir}/` 에 작성한다.

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
- 태스크 완료: `python flow.py task done <id>` + `python flow.py changelog "<변경내용>"`
- 블로커 발생: `python flow.py task block <id> "<이유>"` + `python flow.py task add "Fix: <이유>"`
- 기획 로그: `python flow.py plan log "<내용>"`
- 세션 로그: `python flow.py log "<내용>"`
- 태스크 상세 로그: `python flow.py task log <id> "<내용>"`
- 전체 이벤트 추적: `python flow.py trace`
- 특정 태스크 추적: `python flow.py trace --task <id>`
- phase 완료 시: `python flow.py phase next`
"""


def _now():
    return datetime.now().strftime("%Y-%m-%dT%H:%M")


def _today():
    return datetime.now().strftime("%Y-%m-%d")


def _time():
    return datetime.now().strftime("%H:%M")


def _chdir_to_project_root():
    """flow.py가 있는 디렉토리를 기준으로 작동"""
    os.chdir(Path(__file__).parent)


def _slugify(title):
    slug = re.sub(r'[\\/:*?"<>|]', '', title[:30])
    return slug.replace(' ', '_')


def _read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _write_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _get_project():
    return _read_json(HARNESS_DIR / "project.json")


def _get_tasks():
    return _read_json(HARNESS_DIR / "tasks.json")


def _save_tasks(data):
    _write_json(HARNESS_DIR / "tasks.json", data)


def _get_phases():
    return _read_json(HARNESS_DIR / "phases.json")


def _save_phases(data):
    _write_json(HARNESS_DIR / "phases.json", data)


def _require_harness():
    if not (HARNESS_DIR / "project.json").exists():
        sys.exit("harness/project.json 없음 — 먼저 'python flow.py init <name>' 실행")


def _append_event(event):
    event["ts"] = _now()
    if "phase" not in event:
        proj_path = HARNESS_DIR / "project.json"
        if proj_path.exists():
            try:
                event["phase"] = _read_json(proj_path)["current_phase"]
            except Exception:
                pass
    path = LOGS_DIR / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def _read_events(task_id=None, phase=None):
    path = LOGS_DIR / "events.jsonl"
    if not path.exists():
        return []
    events = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            e = json.loads(line)
            if task_id is not None and e.get("id") != task_id:
                continue
            if phase is not None and e.get("phase") != phase:
                continue
            events.append(e)
    return events


def _update_claude_md():
    if not CLAUDE_MD.exists():
        return

    project = _get_project()
    tasks_data = _get_tasks()
    tasks = tasks_data["tasks"]

    in_progress = [t for t in tasks if t["status"] == "in_progress"]
    blocked = [t for t in tasks if t["status"] == "blocked"]
    backlog = [t for t in tasks if t["status"] == "backlog"]
    done = [t for t in tasks if t["status"] == "done"]

    recent = _read_events()[-5:]

    lines = [
        "## 프로젝트 상태",
        f"Phase: **{project['current_phase']}** | {_now()} 업데이트",
        "",
    ]

    if in_progress:
        lines.append("## 진행중 태스크")
        for t in in_progress:
            lines.append(f"- #{t['id']} [in_progress] {t['title']}")
        lines.append("")

    if blocked:
        lines.append("## 블로킹 태스크")
        for t in blocked:
            lines.append(f"- #{t['id']} [blocked] {t['title']} — {t.get('blocked_reason', '')}")
        lines.append("")

    if backlog:
        lines.append("## 대기 태스크")
        for t in backlog:
            lines.append(f"- #{t['id']} [backlog] {t['title']}")
        lines.append("")

    lines.append(f"## 완료: {len(done)} / 전체: {len(tasks)}")

    if recent:
        lines.append("")
        lines.append("## 최근 변경 (최근 5개)")
        for e in reversed(recent):
            ts = e.get("ts", "")[-5:]
            etype = e.get("type", "")
            if etype == "task_done":
                lines.append(f"- {ts} task#{e['id']} 완료 — {e.get('title', '')}")
            elif etype == "task_start":
                lines.append(f"- {ts} task#{e['id']} 시작 — {e.get('title', '')}")
            elif etype == "task_blocked":
                lines.append(f"- {ts} task#{e['id']} 블로킹 — {e.get('reason', '')}")
            elif etype == "task_add":
                parent = f" (task#{e['parent_id']} 블로커로 인해)" if e.get("parent_id") else ""
                lines.append(f"- {ts} task#{e['id']} 추가 — {e.get('title', '')}{parent}")
            elif etype == "phase_change":
                lines.append(f"- {ts} phase 전환 {e.get('from', '?')} → {e.get('to', '?')}")
            elif etype == "task_log":
                lines.append(f"- {ts} task#{e['id']} 로그: {e.get('message', '')}")
            elif etype == "plan_log":
                lines.append(f"- {ts} [기획] {e.get('message', '')}")
            elif etype == "log":
                lines.append(f"- {ts} {e.get('message', '')}")
            elif etype == "changelog":
                lines.append(f"- {ts} 변경: {e.get('message', '')}")
            elif etype == "test_run":
                result = "통과" if e.get("passed") else "실패"
                lines.append(f"- {ts} 테스트 #{e.get('run', '?')}: {result}")

    status_content = "\n".join(lines) + "\n"

    content = CLAUDE_MD.read_text(encoding="utf-8")
    start_idx = content.find(STATUS_START)
    end_idx = content.find(STATUS_END)
    if start_idx == -1 or end_idx == -1:
        return

    new_content = (
        content[:start_idx]
        + STATUS_START + "\n"
        + status_content
        + STATUS_END
        + content[end_idx + len(STATUS_END):]
    )
    CLAUDE_MD.write_text(new_content, encoding="utf-8")


# ── Commands ─────────────────────────────────────────────────────────────────

def _validate_project_name(name):
    if not name or not name.strip():
        sys.exit("프로젝트 이름이 비어있습니다.")
    invalid_chars = set('/\\:*?"<>| ')
    bad = sorted(set(c for c in name if c in invalid_chars))
    if bad:
        sys.exit(f"프로젝트 이름에 허용되지 않는 문자: {' '.join(repr(c) for c in bad)}")
    if name in ('.', '..'):
        sys.exit("'.' 또는 '..'는 프로젝트 이름으로 사용할 수 없습니다.")


def cmd_init(args):
    name = args.name
    _validate_project_name(name)
    test_cmd = args.test_cmd
    already_exists = (HARNESS_DIR / "project.json").exists()

    project_dir = Path(name)

    for d in [
        HARNESS_DIR,
        LOGS_DIR / "planning",
        LOGS_DIR / "implementation",
        LOGS_DIR / "testing",
        LOGS_DIR / "sessions",
        PLAN_DIR,
        project_dir,
    ]:
        d.mkdir(parents=True, exist_ok=True)

    if already_exists and not args.force:
        print(f"⚠ 이미 초기화된 프로젝트입니다. 기존 상태를 유지합니다.")
        print(f"  강제 재초기화: python flow.py init {name} --force")
    else:
        _write_json(HARNESS_DIR / "project.json", {
            "name": name,
            "project_dir": name,
            "current_phase": "planning",
            "test_cmd": test_cmd,
            "created_at": _today(),
        })

        _write_json(HARNESS_DIR / "phases.json", {
            "phases": [
                {"id": "planning",       "name": "기획",   "status": "in_progress"},
                {"id": "implementation", "name": "구현",   "status": "pending"},
                {"id": "testing",        "name": "테스트", "status": "pending"},
            ]
        })

        _write_json(HARNESS_DIR / "tasks.json", {"next_id": 1, "tasks": []})

        (LOGS_DIR / "events.jsonl").write_text("", encoding="utf-8")
        _append_event({"type": "phase_change", "from": None, "to": "planning"})

        print(f"✓ '{name}' 초기화 완료")
        print(f"  1. plan/spec.md 에 기획서 작성")
        print(f"  2. python flow.py task add '<태스크>'")
        print(f"  3. python flow.py phase next  (기획 완료 후)")

    if not Path("changelog.md").exists():
        Path("changelog.md").write_text(f"# Changelog\n\n## {name}\n\n", encoding="utf-8")

    if not (PLAN_DIR / "spec.md").exists():
        (PLAN_DIR / "spec.md").write_text(
            f"# {name} — 기획서\n\n## 목표\n\n## 범위\n\n## 기술 스택\n\n",
            encoding="utf-8",
        )

    if not CLAUDE_MD.exists() or (already_exists and args.force):
        CLAUDE_MD.write_text(
            CLAUDE_MD_TEMPLATE.format(
                name=name,
                project_dir=name,
                ts=_now(),
                status_start=STATUS_START,
                status_end=STATUS_END,
            ),
            encoding="utf-8",
        )

    if not Path(".gitignore").exists():
        Path(".gitignore").write_text(
            "# Python\n__pycache__/\n*.pyc\n*.pyo\n.env\n.venv/\n\n"
            "# Node\nnode_modules/\n\n"
            "# 테스트 출력 (대용량 가능)\nlogs/testing/\nlogs/sessions/\n\n"
            "# 커밋 권장: harness/*.json, CLAUDE.md, changelog.md, plan/, logs/events.jsonl\n",
            encoding="utf-8",
        )


def cmd_status():
    _require_harness()
    project = _get_project()
    tasks = _get_tasks()["tasks"]

    print(f"\n=== {project['name']} ===")
    print(f"Phase: {project['current_phase']}\n")

    groups = [
        ("진행중", "in_progress"),
        ("블로킹", "blocked"),
        ("대기",   "backlog"),
        ("완료",   "done"),
    ]
    for label, key in groups:
        items = [t for t in tasks if t["status"] == key]
        if not items:
            continue
        print(f"[{label}]")
        for t in items:
            extra = f" — {t['blocked_reason']}" if key == "blocked" else ""
            print(f"  #{t['id']} {t['title']}{extra}")
        print()

    done = sum(1 for t in tasks if t["status"] == "done")
    print(f"완료: {done} / 전체: {len(tasks)}")


def cmd_task(args):
    _require_harness()
    if args.task_cmd == "add":
        data = _get_tasks()
        project = _get_project()
        tid = data["next_id"]
        task = {
            "id": tid,
            "title": args.title,
            "phase": project["current_phase"],
            "status": "backlog",
            "created_at": _today(),
            "notes": "",
        }
        if args.parent:
            task["parent_id"] = args.parent
        data["tasks"].append(task)
        data["next_id"] += 1
        _save_tasks(data)

        event = {"type": "task_add", "id": tid, "title": args.title, "phase": project["current_phase"]}
        if args.parent:
            event["parent_id"] = args.parent
        _append_event(event)
        _update_claude_md()
        print(f"✓ task#{tid} 추가: {args.title}")

    elif args.task_cmd == "start":
        data = _get_tasks()
        task = next((t for t in data["tasks"] if t["id"] == args.id), None)
        if not task:
            sys.exit(f"task#{args.id} 없음")
        if task["status"] == "done":
            sys.exit(f"task#{args.id}는 이미 완료된 태스크입니다. 재작업이 필요하면 새 태스크를 추가하세요:\n  python flow.py task add \"Fix: <이유>\"")
        task["status"] = "in_progress"
        task.pop("blocked_reason", None)
        _save_tasks(data)
        _append_event({"type": "task_start", "id": args.id, "title": task["title"]})
        _update_claude_md()
        print(f"✓ task#{args.id} 시작: {task['title']}")

    elif args.task_cmd == "done":
        data = _get_tasks()
        task = next((t for t in data["tasks"] if t["id"] == args.id), None)
        if not task:
            sys.exit(f"task#{args.id} 없음")
        task["status"] = "done"
        task["completed_at"] = _today()
        _save_tasks(data)
        _append_event({"type": "task_done", "id": args.id, "title": task["title"]})
        _update_claude_md()
        print(f"✓ task#{args.id} 완료: {task['title']}")

    elif args.task_cmd == "block":
        data = _get_tasks()
        task = next((t for t in data["tasks"] if t["id"] == args.id), None)
        if not task:
            sys.exit(f"task#{args.id} 없음")
        task["status"] = "blocked"
        task["blocked_reason"] = args.reason
        _save_tasks(data)
        _append_event({"type": "task_blocked", "id": args.id, "title": task["title"], "reason": args.reason})

        phase = _get_project()["current_phase"]
        slug = _slugify(task["title"])
        log_path = LOGS_DIR / phase / f"task-{args.id:03d}-blocked-{slug}.md"
        log_path.write_text(
            f"# task#{args.id} 블로킹\n\n**이유:** {args.reason}\n\n**발생:** {_now()}\n",
            encoding="utf-8",
        )

        _update_claude_md()
        print(f"✓ task#{args.id} 블로킹: {args.reason}")

    elif args.task_cmd == "list":
        cmd_status()

    elif args.task_cmd == "log":
        data = _get_tasks()
        task = next((t for t in data["tasks"] if t["id"] == args.id), None)
        if not task:
            sys.exit(f"task#{args.id} 없음")

        phase = _get_project()["current_phase"]
        slug = _slugify(task["title"])
        log_path = LOGS_DIR / phase / f"task-{args.id:03d}-{slug}.md"

        if log_path.exists():
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"\n---\n**{_now()}**\n{args.content}\n")
        else:
            log_path.write_text(
                f"# task#{args.id}: {task['title']}\n\n---\n**{_now()}**\n{args.content}\n",
                encoding="utf-8",
            )

        _append_event({"type": "task_log", "id": args.id, "message": args.content[:60]})
        print(f"✓ task#{args.id} 로그 기록")


def cmd_log(message):
    _require_harness()
    phase = _get_project()["current_phase"]
    log_path = LOGS_DIR / "sessions" / f"{_today()}.md"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    if log_path.exists():
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n**{_time()}** {message}\n")
    else:
        log_path.write_text(f"# Session {_today()}\n\n**{_time()}** {message}\n", encoding="utf-8")

    _append_event({"type": "log", "message": message, "phase": phase})
    _update_claude_md()
    print(f"✓ 로그: {message}")


def cmd_plan_log(message):
    _require_harness()
    log_path = LOGS_DIR / "planning" / f"{_today()}.md"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    if log_path.exists():
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n**{_time()}** {message}\n")
    else:
        log_path.write_text(f"# Planning Log {_today()}\n\n**{_time()}** {message}\n", encoding="utf-8")

    _append_event({"type": "plan_log", "message": message, "phase": "planning"})
    _update_claude_md()
    print(f"✓ 기획 로그: {message}")


def cmd_changelog(message):
    _require_harness()
    path = Path("changelog.md")
    ts = _today()

    if path.exists():
        content = path.read_text(encoding="utf-8")
        lines = content.split("\n")
        # 첫 번째 ## 섹션 아래에 삽입
        insert_at = next(
            (i + 1 for i, l in enumerate(lines) if l.startswith("## ")),
            2,
        )
        lines.insert(insert_at, f"- [{ts}] {message}")
        path.write_text("\n".join(lines), encoding="utf-8")
    else:
        path.write_text(f"# Changelog\n\n- [{ts}] {message}\n", encoding="utf-8")

    _append_event({"type": "changelog", "message": message})
    _update_claude_md()
    print(f"✓ 변경사항 기록: {message}")


def cmd_phase_next():
    _require_harness()
    phases_data = _get_phases()
    project = _get_project()
    phases = phases_data["phases"]

    current_idx = next((i for i, p in enumerate(phases) if p["id"] == project["current_phase"]), None)
    if current_idx is None:
        sys.exit("현재 phase를 찾을 수 없음")
    if current_idx >= len(phases) - 1:
        print("이미 마지막 phase입니다.")
        return

    old_phase = phases[current_idx]["id"]
    phases[current_idx]["status"] = "done"
    phases[current_idx + 1]["status"] = "in_progress"
    new_phase = phases[current_idx + 1]["id"]

    project["current_phase"] = new_phase
    _save_phases(phases_data)
    _write_json(HARNESS_DIR / "project.json", project)

    _append_event({"type": "phase_change", "from": old_phase, "to": new_phase})
    _update_claude_md()
    print(f"✓ Phase 전환: {old_phase} → {new_phase}")


def cmd_trace(args):
    _require_harness()
    task_id = args.task
    phase = args.phase
    events = _read_events(task_id=task_id, phase=phase)

    if not events:
        print("이벤트 없음")
        return

    print("\n=== 이벤트 타임라인 ===")
    if task_id:
        print(f"(task#{task_id} 필터)")
    if phase:
        print(f"(phase:{phase} 필터)")
    print()

    icons = {
        "phase_change": "🔄",
        "task_add":     "➕",
        "task_start":   "▶ ",
        "task_done":    "✓ ",
        "task_blocked": "⛔",
        "task_log":     "📝",
        "log":          "💬",
        "changelog":    "📋",
        "test_run":     "🧪",
        "plan_log":     "📌",
    }

    for e in events:
        ts = e.get("ts", "")
        etype = e.get("type", "")
        icon = icons.get(etype, "  ")

        if etype == "phase_change":
            msg = f"PHASE: {e.get('from', '?')} → {e.get('to', '?')}"
        elif etype == "task_add":
            parent = f" (부모: task#{e['parent_id']})" if e.get("parent_id") else ""
            msg = f"task#{e['id']} 추가: {e.get('title', '')}{parent}"
        elif etype == "task_start":
            msg = f"task#{e['id']} 시작: {e.get('title', '')}"
        elif etype == "task_done":
            msg = f"task#{e['id']} 완료: {e.get('title', '')}"
        elif etype == "task_blocked":
            msg = f"task#{e['id']} 블로킹: {e.get('reason', '')}"
        elif etype == "task_log":
            msg = f"task#{e['id']} 로그: {e.get('message', '')}"
        elif etype == "plan_log":
            msg = f"[기획] {e.get('message', '')}"
        elif etype == "log":
            msg = e.get("message", "")
        elif etype == "changelog":
            msg = f"변경: {e.get('message', '')}"
        elif etype == "test_run":
            result = "통과" if e.get("passed") else "실패"
            msg = f"테스트 #{e.get('run', '?')}: {result}"
        else:
            msg = str(e)

        print(f"[{ts}] {icon} {msg}")


def cmd_test():
    _require_harness()
    project = _get_project()
    test_cmd = project.get("test_cmd", "pytest")

    project_dir = project.get("project_dir")
    cwd = Path(project_dir) if project_dir and Path(project_dir).exists() else None

    print(f"테스트 실행: {test_cmd}" + (f" (cwd: {project_dir})" if cwd else "") + "\n")
    try:
        result = subprocess.run(
            test_cmd,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )
        output = result.stdout + result.stderr
        passed = result.returncode == 0
    except subprocess.TimeoutExpired:
        output = "테스트 타임아웃 (300초 초과)"
        passed = False

    run_files = list((LOGS_DIR / "testing").glob("run-*.md"))
    run_num = len(run_files) + 1
    suffix = "-fix" if run_num > 1 else ""
    log_path = LOGS_DIR / "testing" / f"run-{run_num:03d}{suffix}.md"
    log_path.write_text(
        f"# 테스트 실행 #{run_num}\n\n"
        f"**시간:** {_now()}\n"
        f"**결과:** {'✓ 통과' if passed else '✗ 실패'}\n"
        f"**명령:** {test_cmd}\n\n"
        f"```\n{output}\n```\n",
        encoding="utf-8",
    )

    _append_event({"type": "test_run", "run": run_num, "passed": passed, "cmd": test_cmd})
    _update_claude_md()

    print(output)
    if passed:
        print("✓ 모든 테스트 통과")
    else:
        print('✗ 테스트 실패 — 수정 태스크 추가: python flow.py task add "Fix: <문제>"')


# ── Entrypoint ────────────────────────────────────────────────────────────────

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    _chdir_to_project_root()

    parser = argparse.ArgumentParser(prog="flow", description="프로젝트 워크플로우 하네스")
    sub = parser.add_subparsers(dest="command")

    # init
    p = sub.add_parser("init", help="프로젝트 초기화")
    p.add_argument("name", help="프로젝트 이름")
    p.add_argument("--test-cmd", default="pytest", dest="test_cmd", help="테스트 커맨드 (기본: pytest)")
    p.add_argument("--force", action="store_true", help="기존 harness 상태 강제 초기화")

    # status
    sub.add_parser("status", help="현재 상태 출력")

    # task
    task_p = sub.add_parser("task", help="태스크 관리")
    task_sub = task_p.add_subparsers(dest="task_cmd")

    p = task_sub.add_parser("add", help="태스크 추가")
    p.add_argument("title")
    p.add_argument("--parent", type=int, default=None, help="부모 태스크 ID")

    p = task_sub.add_parser("start", help="태스크 시작")
    p.add_argument("id", type=int)

    p = task_sub.add_parser("done", help="태스크 완료")
    p.add_argument("id", type=int)

    p = task_sub.add_parser("block", help="태스크 블로킹")
    p.add_argument("id", type=int)
    p.add_argument("reason", help="블로킹 이유")

    task_sub.add_parser("list", help="태스크 목록")

    p = task_sub.add_parser("log", help="태스크 상세 로그")
    p.add_argument("id", type=int)
    p.add_argument("content", help="로그 내용")

    # log
    p = sub.add_parser("log", help="세션 로그 기록")
    p.add_argument("message")

    # changelog
    p = sub.add_parser("changelog", help="변경사항 기록")
    p.add_argument("message")

    # plan
    plan_p = sub.add_parser("plan", help="기획 로그")
    plan_sub = plan_p.add_subparsers(dest="plan_cmd")
    p = plan_sub.add_parser("log", help="기획 로그 기록")
    p.add_argument("message")

    # phase
    phase_p = sub.add_parser("phase", help="Phase 관리")
    phase_sub = phase_p.add_subparsers(dest="phase_cmd")
    phase_sub.add_parser("next", help="다음 phase로 전환")

    # trace
    p = sub.add_parser("trace", help="이벤트 타임라인 추적")
    p.add_argument("--task", type=int, default=None, help="특정 태스크만 필터")
    p.add_argument("--phase", default=None, help="특정 phase만 필터")

    # test
    sub.add_parser("test", help="테스트 실행")

    args = parser.parse_args()

    dispatch = {
        "init":      lambda: cmd_init(args),
        "status":    cmd_status,
        "log":       lambda: cmd_log(args.message),
        "changelog": lambda: cmd_changelog(args.message),
        "trace":     lambda: cmd_trace(args),
        "test":      cmd_test,
    }

    if args.command in dispatch:
        dispatch[args.command]()
    elif args.command == "task":
        if not args.task_cmd:
            task_p.print_help()
        else:
            cmd_task(args)
    elif args.command == "plan":
        if not args.plan_cmd:
            plan_p.print_help()
        elif args.plan_cmd == "log":
            cmd_plan_log(args.message)
    elif args.command == "phase":
        if not args.phase_cmd:
            phase_p.print_help()
        elif args.phase_cmd == "next":
            cmd_phase_next()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
