#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
import subprocess
from datetime import datetime
from pathlib import Path

HARNESS_DIR = Path("harness")
LOGS_DIR = Path("logs")
PLAN_DIR = Path("plan")
CLAUDE_MD = Path("CLAUDE.md")

STATUS_START = "<!-- HARNESS:STATUS:START -->"
STATUS_END = "<!-- HARNESS:STATUS:END -->"
FILES_START = "<!-- HARNESS:FILES:START -->"
FILES_END = "<!-- HARNESS:FILES:END -->"

BACKLOG_DISPLAY_LIMIT = 10

# 스캔 시 제외할 디렉토리/파일 이름. 필요 시 여기에 추가.
SNAP_SKIP = {
    ".git", "__pycache__", "node_modules",
    ".venv", "venv", "env",
    ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".tox", "dist", "build", ".eggs",
}

CLAUDE_MD_TEMPLATE = """\
# {name}

{status_start}
## 프로젝트 상태
Phase: **planning** | {ts} 초기화

## 대기 태스크
(아직 태스크 없음)

## 완료: 0 / 전체: 0
{status_end}

{files_start}
## 파일 인덱스
(아직 스냅샷 없음 — `python flow.py files snap` 실행)
{files_end}

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
- 태스크 완료: `python flow.py task done <id> --changelog "<변경내용>"` → 완료 후 `python flow.py files snap` 실행
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
"""


def _now():
    return datetime.now().strftime("%Y-%m-%dT%H:%M")


def _today():
    return datetime.now().strftime("%Y-%m-%d")


def _time():
    return datetime.now().strftime("%H:%M")


def _chdir_to_project_root():
    os.chdir(Path(__file__).parent)


def _slugify(title):
    slug = re.sub(r'[\\/:*?"<>|]', '', title[:30])
    return slug.replace(' ', '_')


def _read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _write_json(path, data):
    """원자적 쓰기: .tmp 파일로 쓴 뒤 os.replace로 교체 (Ctrl+C 부분 손상 방지)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def _atomic_write_text(path, text):
    """텍스트 파일 원자적 쓰기 (CLAUDE.md, changelog.md 손상 방지)."""
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


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


def _get_files():
    path = HARNESS_DIR / "files.json"
    if not path.exists():
        return {"last_snap": None, "entries": []}
    return _read_json(path)


def _save_files(data):
    _write_json(HARNESS_DIR / "files.json", data)


def _do_snap():
    files_path = HARNESS_DIR / "files.json"
    if not files_path.exists():
        _write_json(files_path, {"last_snap": None, "entries": []})
    data = _get_files()
    project = _get_project()
    project_dir = Path(project.get("project_dir", ""))
    if not project_dir.exists():
        return
    found_paths = set()
    for f in project_dir.rglob("*"):
        if not f.is_file():
            continue
        if any(part in SNAP_SKIP or part.endswith(".pyc") for part in f.parts):
            continue
        found_paths.add(str(f).replace("\\", "/"))
    existing_paths = {e["path"].replace("\\", "/") for e in data.get("entries", [])}
    new_count = 0
    for p in sorted(found_paths):
        if p not in existing_paths:
            data.setdefault("entries", []).append({
                "path": p, "description": "", "task_id": None, "added_at": _today(),
            })
            new_count += 1
    stale_count = 0
    for e in data.get("entries", []):
        if not Path(e["path"]).exists():
            if not e.get("stale"):
                e["stale"] = True
                stale_count += 1
        else:
            e.pop("stale", None)
    data["last_snap"] = _now()
    _save_files(data)
    _update_files_md()
    parts = [f"✓ 스냅샷 완료: {data['last_snap']}"]
    if new_count:
        parts.append(f"신규 {new_count}개")
    if stale_count:
        parts.append(f"stale {stale_count}개 (삭제됨)")
    print(" | ".join(parts))


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
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue  # 손상된 라인 무시
            if task_id is not None and e.get("id") != task_id:
                continue
            if phase is not None and e.get("phase") != phase:
                continue
            events.append(e)
    return events


def _completion_stats(tasks):
    """완료/전체/건너뜀 카운트 반환. skipped는 분모에서 제외."""
    done = sum(1 for t in tasks if t["status"] == "done")
    skipped = sum(1 for t in tasks if t["status"] == "skipped")
    total = len(tasks)
    active = total - skipped
    return done, active, skipped


def _update_claude_md():
    if not CLAUDE_MD.exists():
        return

    project = _get_project()
    tasks_data = _get_tasks()
    tasks = tasks_data["tasks"]

    in_progress = [t for t in tasks if t["status"] == "in_progress"]
    blocked = [t for t in tasks if t["status"] == "blocked"]
    backlog = [t for t in tasks if t["status"] == "backlog"]
    skipped = [t for t in tasks if t["status"] == "skipped"]
    done_tasks = [t for t in tasks if t["status"] == "done"]

    done_count, active_count, skipped_count = _completion_stats(tasks)

    recent = _read_events()[-5:]

    lines = [
        "## 프로젝트 상태",
        f"Phase: **{project['current_phase']}** | {_now()} 업데이트",
        "",
    ]

    if in_progress:
        lines.append("## 진행중 태스크")
        for t in in_progress:
            desc = f" — {t['notes']}" if t.get("notes") else ""
            lines.append(f"- #{t['id']} [in_progress] {t['title']}{desc}")
        lines.append("")

    if blocked:
        lines.append("## 블로킹 태스크")
        for t in blocked:
            lines.append(f"- #{t['id']} [blocked] {t['title']} — {t.get('blocked_reason', '')}")
        lines.append("")

    if backlog:
        lines.append("## 대기 태스크")
        for t in backlog[:BACKLOG_DISPLAY_LIMIT]:
            desc = f" — {t['notes']}" if t.get("notes") else ""
            lines.append(f"- #{t['id']} [backlog] {t['title']}{desc}")
        if len(backlog) > BACKLOG_DISPLAY_LIMIT:
            lines.append(f"- … 외 {len(backlog) - BACKLOG_DISPLAY_LIMIT}개 (python flow.py status)")
        lines.append("")

    if skipped:
        lines.append("## 건너뜀 태스크")
        for t in skipped:
            reason = f" — {t.get('skipped_reason', '')}" if t.get("skipped_reason") else ""
            lines.append(f"- #{t['id']} [skipped] {t['title']}{reason}")
        lines.append("")

    suffix = f" (건너뜀: {skipped_count})" if skipped_count else ""
    lines.append(f"## 완료: {done_count} / {active_count}{suffix}")

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
            elif etype == "task_reopen":
                lines.append(f"- {ts} task#{e['id']} 재개 — {e.get('title', '')}")
            elif etype == "task_edit":
                lines.append(f"- {ts} task#{e['id']} 수정 — {e.get('new_title', '')}")
            elif etype == "task_blocked":
                lines.append(f"- {ts} task#{e['id']} 블로킹 — {e.get('reason', '')}")
            elif etype == "task_skip":
                lines.append(f"- {ts} task#{e['id']} 건너뜀 — {e.get('title', '')}")
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
    _atomic_write_text(CLAUDE_MD, new_content)


def _update_files_md():
    """FILES 섹션에 설명 있는 파일/디렉토리 목록만 주입 (트리 전체는 files list 명령으로)."""
    if not CLAUDE_MD.exists():
        return

    content = CLAUDE_MD.read_text(encoding="utf-8")
    start_idx = content.find(FILES_START)
    end_idx = content.find(FILES_END)
    if start_idx == -1 or end_idx == -1:
        return

    data = _get_files()
    described = [e for e in data.get("entries", []) if e.get("description") and not e.get("stale")]
    stale_described = [e for e in data.get("entries", []) if e.get("description") and e.get("stale")]

    lines = ["## 파일 인덱스"]
    if data.get("last_snap"):
        lines.append(f"마지막 스냅: {data['last_snap']}")
    lines.append("")

    if described:
        for e in described:
            tid = f" [task#{e['task_id']}]" if e.get("task_id") else ""
            lines.append(f"- `{e['path']}`{tid} — {e['description']}")
    else:
        lines.append("(설명 있는 파일 없음 — `python flow.py files describe <path> \"<설명>\"` 실행)")

    if stale_described:
        lines.append("")
        lines.append("**[stale — 파일/디렉토리 없음]**")
        for e in stale_described:
            lines.append(f"- `{e['path']}` — {e['description']}")

    files_content = "\n".join(lines) + "\n"

    new_content = (
        content[:start_idx]
        + FILES_START + "\n"
        + files_content
        + FILES_END
        + content[end_idx + len(FILES_END):]
    )
    _atomic_write_text(CLAUDE_MD, new_content)


def _build_tree(dir_path, entries_map, prefix=""):
    """ASCII 트리. entries_map: {normalized_path: entry} — 파일/디렉토리 모두 설명 표시."""
    try:
        items = sorted(dir_path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    except PermissionError:
        return []

    items = [i for i in items if i.name not in SNAP_SKIP and not i.name.endswith(".pyc")]

    lines = []
    for idx, item in enumerate(items):
        is_last = (idx == len(items) - 1)
        connector = "└── " if is_last else "├── "
        ext = "    " if is_last else "│   "

        rel_path = str(item).replace("\\", "/")
        desc = ""
        stale_mark = ""
        if rel_path in entries_map:
            e = entries_map[rel_path]
            if e.get("stale"):
                stale_mark = " [stale]"
            if e.get("description"):
                tid = f" [task#{e['task_id']}]" if e.get("task_id") else ""
                desc = f" — {e['description']}{tid}"

        lines.append(f"{prefix}{connector}{item.name}{stale_mark}{desc}")
        if item.is_dir():
            lines.extend(_build_tree(item, entries_map, prefix + ext))
    return lines


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
                {"id": "shipped",        "name": "완료",   "status": "pending"},
            ]
        })

        _write_json(HARNESS_DIR / "tasks.json", {"next_id": 1, "tasks": []})
        _write_json(HARNESS_DIR / "files.json", {"last_snap": None, "entries": []})

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
            f"# {name} — 기획서\n\n"
            "## 목표\n<!-- 무엇을 만드는가, 왜 만드는가 -->\n\n"
            "## 핵심 기능\n<!-- 반드시 있어야 할 기능 목록 -->\n\n"
            "## 기술 스택\n<!-- 언어, 프레임워크, DB, 인프라 등 -->\n\n"
            "## 범위 제외\n<!-- 이번 버전에서 하지 않을 것 -->\n\n"
            "## 제약 조건\n<!-- 성능, 보안, 호환성 등 비기능 요구사항 -->\n\n"
            "## 기타 결정 사항\n<!-- 위 섹션에 맞지 않는 결정들 -->\n",
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
                files_start=FILES_START,
                files_end=FILES_END,
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
        ("건너뜀", "skipped"),
        ("완료",   "done"),
    ]
    for label, key in groups:
        items = [t for t in tasks if t["status"] == key]
        if not items:
            continue
        print(f"[{label}]")
        for t in items:
            if key == "blocked":
                extra = f" — {t['blocked_reason']}"
            elif key == "skipped" and t.get("skipped_reason"):
                extra = f" — {t['skipped_reason']}"
            else:
                extra = ""
            desc = f" ({t['notes']})" if t.get("notes") and key not in ("blocked", "skipped") else ""
            print(f"  #{t['id']} {t['title']}{desc}{extra}")
        print()

    done_count, active_count, skipped_count = _completion_stats(tasks)
    suffix = f" (건너뜀: {skipped_count})" if skipped_count else ""
    print(f"완료: {done_count} / {active_count}{suffix}")


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
            "notes": getattr(args, "desc", "") or "",
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
            sys.exit(f"task#{args.id}는 이미 완료된 태스크입니다.\n  재개: python flow.py task reopen {args.id}\n  새 태스크: python flow.py task add \"Fix: <이유>\"")
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

        changelog_msg = getattr(args, "changelog_msg", None)
        no_changelog = getattr(args, "no_changelog", False)
        if changelog_msg:
            _do_changelog(changelog_msg)
        elif not no_changelog:
            print(f"  → changelog 기록 권장: python flow.py task done {args.id} --changelog \"<변경내용>\"")
            print(f"  → 생략 시: python flow.py task done {args.id} --no-changelog")
        _do_snap()

    elif args.task_cmd == "reopen":
        data = _get_tasks()
        task = next((t for t in data["tasks"] if t["id"] == args.id), None)
        if not task:
            sys.exit(f"task#{args.id} 없음")
        if task["status"] != "done":
            sys.exit(f"task#{args.id}는 완료 상태가 아닙니다 (현재: {task['status']})")
        task["status"] = "in_progress"
        task.pop("completed_at", None)
        _save_tasks(data)
        _append_event({"type": "task_reopen", "id": args.id, "title": task["title"]})
        _update_claude_md()
        print(f"✓ task#{args.id} 재개: {task['title']}")

    elif args.task_cmd == "edit":
        data = _get_tasks()
        task = next((t for t in data["tasks"] if t["id"] == args.id), None)
        if not task:
            sys.exit(f"task#{args.id} 없음")
        old_title = task["title"]
        task["title"] = args.title
        _save_tasks(data)
        _append_event({"type": "task_edit", "id": args.id, "old_title": old_title, "new_title": args.title})
        _update_claude_md()
        print(f"✓ task#{args.id} 수정: {old_title} → {args.title}")

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

    elif args.task_cmd == "skip":
        data = _get_tasks()
        task = next((t for t in data["tasks"] if t["id"] == args.id), None)
        if not task:
            sys.exit(f"task#{args.id} 없음")
        if task["status"] == "done":
            sys.exit(f"task#{args.id}는 이미 완료된 태스크입니다. skip할 수 없습니다.")
        task["status"] = "skipped"
        reason = getattr(args, "reason", "") or ""
        task["skipped_reason"] = reason
        _save_tasks(data)
        _append_event({"type": "task_skip", "id": args.id, "title": task["title"], "reason": reason})
        _update_claude_md()
        reason_str = f": {reason}" if reason else ""
        print(f"✓ task#{args.id} 건너뜀{reason_str} — {task['title']}")

    elif args.task_cmd == "desc":
        data = _get_tasks()
        task = next((t for t in data["tasks"] if t["id"] == args.id), None)
        if not task:
            sys.exit(f"task#{args.id} 없음")
        task["notes"] = args.description
        _save_tasks(data)
        _update_claude_md()
        print(f"✓ task#{args.id} 설명 업데이트: {args.description}")

    elif args.task_cmd == "show":
        data = _get_tasks()
        task = next((t for t in data["tasks"] if t["id"] == args.id), None)
        if not task:
            sys.exit(f"task#{args.id} 없음")

        print(f"\n=== task#{task['id']} ===")
        print(f"제목:   {task['title']}")
        print(f"상태:   {task['status']}")
        print(f"Phase:  {task.get('phase', '')}")
        print(f"생성:   {task.get('created_at', '')}")
        if task.get("completed_at"):
            print(f"완료:   {task['completed_at']}")
        if task.get("notes"):
            print(f"설명:   {task['notes']}")
        if task.get("blocked_reason"):
            print(f"블로킹: {task['blocked_reason']}")
        if task.get("skipped_reason"):
            print(f"건너뜀: {task['skipped_reason']}")
        if task.get("parent_id"):
            print(f"부모:   task#{task['parent_id']}")

        # 모든 phase 디렉토리에서 로그 파일 탐색 (생성 phase와 기록 phase가 다를 수 있음)
        slug = _slugify(task["title"])
        log_filename = f"task-{args.id:03d}-{slug}.md"
        for phase_dir in LOGS_DIR.iterdir():
            if not phase_dir.is_dir():
                continue
            log_path = phase_dir / log_filename
            if log_path.exists():
                print(f"\n[로그 — {phase_dir.name}]\n{log_path.read_text(encoding='utf-8')}")

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


def _do_changelog(message):
    """changelog 기록 내부 공통 함수."""
    path = Path("changelog.md")
    ts = _today()

    if path.exists():
        content = path.read_text(encoding="utf-8")
        lines = content.split("\n")
        insert_at = next(
            (i + 1 for i, l in enumerate(lines) if l.startswith("## ")),
            2,
        )
        lines.insert(insert_at, f"- [{ts}] {message}")
        _atomic_write_text(path, "\n".join(lines))
    else:
        _atomic_write_text(path, f"# Changelog\n\n- [{ts}] {message}\n")

    _append_event({"type": "changelog", "message": message})
    _update_claude_md()
    print(f"✓ 변경사항 기록: {message}")


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
    _do_changelog(message)


def cmd_phase_next(args):
    _require_harness()
    phases_data = _get_phases()
    project = _get_project()
    tasks_data = _get_tasks()
    phases = phases_data["phases"]

    current_idx = next((i for i, p in enumerate(phases) if p["id"] == project["current_phase"]), None)
    if current_idx is None:
        sys.exit("현재 phase를 찾을 수 없음")
    if current_idx >= len(phases) - 1:
        print("이미 마지막 phase입니다.")
        return

    # 미완 태스크 경고 (--force 없을 때)
    if not getattr(args, "force", False):
        incomplete = [t for t in tasks_data["tasks"] if t["status"] in ("in_progress", "backlog")]
        if incomplete:
            print(f"⚠ 미완 태스크 {len(incomplete)}개가 있습니다:")
            for t in incomplete[:5]:
                print(f"  #{t['id']} [{t['status']}] {t['title']}")
            if len(incomplete) > 5:
                print(f"  … 외 {len(incomplete) - 5}개")
            print(f"\n강제 전환: python flow.py phase next --force")
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

    if new_phase == "shipped":
        print("\n🎉 프로젝트 완료! changelog.md를 최종 정리하세요.")


def cmd_phase_back():
    _require_harness()
    phases_data = _get_phases()
    project = _get_project()
    phases = phases_data["phases"]

    current_idx = next((i for i, p in enumerate(phases) if p["id"] == project["current_phase"]), None)
    if current_idx is None:
        sys.exit("현재 phase를 찾을 수 없음")
    if current_idx == 0:
        print("이미 첫 번째 phase입니다.")
        return

    old_phase = phases[current_idx]["id"]
    phases[current_idx]["status"] = "pending"
    phases[current_idx - 1]["status"] = "in_progress"
    new_phase = phases[current_idx - 1]["id"]

    project["current_phase"] = new_phase
    _save_phases(phases_data)
    _write_json(HARNESS_DIR / "project.json", project)

    _append_event({"type": "phase_change", "from": old_phase, "to": new_phase})
    _update_claude_md()
    print(f"✓ Phase 롤백: {old_phase} → {new_phase}")


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
        "task_reopen":  "↩ ",
        "task_edit":    "✏ ",
        "task_blocked": "⛔",
        "task_skip":    "⏭ ",
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
        elif etype == "task_reopen":
            msg = f"task#{e['id']} 재개: {e.get('title', '')}"
        elif etype == "task_edit":
            msg = f"task#{e['id']} 수정: {e.get('old_title', '')} → {e.get('new_title', '')}"
        elif etype == "task_blocked":
            msg = f"task#{e['id']} 블로킹: {e.get('reason', '')}"
        elif etype == "task_skip":
            reason = f" ({e.get('reason', '')})" if e.get("reason") else ""
            msg = f"task#{e['id']} 건너뜀: {e.get('title', '')}{reason}"
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


def cmd_files(args, files_p):
    _require_harness()

    files_path = HARNESS_DIR / "files.json"
    if not files_path.exists():
        _write_json(files_path, {"last_snap": None, "entries": []})

    if args.files_cmd == "snap":
        _do_snap()

    elif args.files_cmd == "describe":
        data = _get_files()
        path_str = args.path.replace("\\", "/")
        entry = next((e for e in data.get("entries", []) if e["path"].replace("\\", "/") == path_str), None)

        if entry is None:
            entry = {
                "path": path_str,
                "description": "",
                "task_id": None,
                "added_at": _today(),
            }
            data.setdefault("entries", []).append(entry)

        entry["description"] = args.description
        if args.task:
            entry["task_id"] = args.task
        entry.pop("stale", None)

        _save_files(data)
        _update_files_md()
        tid = f" [task#{args.task}]" if args.task else ""
        print(f"✓ 설명 등록: {path_str}{tid} — {args.description}")

    elif args.files_cmd == "add":
        data = _get_files()
        path_str = args.path.replace("\\", "/")
        existing = next((e for e in data.get("entries", []) if e["path"].replace("\\", "/") == path_str), None)
        if existing:
            print(f"이미 등록됨: {path_str}  (설명 변경은 'files describe' 사용)")
        else:
            entry = {
                "path": path_str,
                "description": args.description or "",
                "task_id": args.task,
                "added_at": _today(),
            }
            data.setdefault("entries", []).append(entry)
            _save_files(data)
            _update_files_md()
            print(f"✓ 등록: {path_str}")

    elif args.files_cmd == "remove":
        data = _get_files()
        path_str = args.path.replace("\\", "/")
        before = len(data.get("entries", []))
        data["entries"] = [e for e in data.get("entries", []) if e["path"].replace("\\", "/") != path_str]
        if len(data["entries"]) < before:
            _save_files(data)
            _update_files_md()
            print(f"✓ 제거: {path_str}")
        else:
            print(f"없음: {path_str}")

    elif args.files_cmd == "list":
        data = _get_files()
        project = _get_project()
        project_dir = Path(project.get("project_dir", ""))

        if data.get("last_snap"):
            print(f"\n=== 파일 구조 (스냅: {data['last_snap']}) ===\n")
            entries_map = {e["path"].replace("\\", "/"): e for e in data.get("entries", [])}
            if project_dir.exists():
                print(f"{project_dir.name}/")
                for line in _build_tree(project_dir, entries_map):
                    print(line)
            else:
                print(f"(프로젝트 디렉토리 없음: {project_dir})")
        else:
            print("스냅샷 없음 — python flow.py files snap 실행")

        described = [e for e in data.get("entries", []) if e.get("description")]
        stale_undescribed = [e for e in data.get("entries", []) if e.get("stale") and not e.get("description")]

        if described:
            print(f"\n[설명 있는 항목 ({len(described)}개)]")
            for e in described:
                tid = f" [task#{e['task_id']}]" if e.get("task_id") else ""
                stale_mark = " [stale]" if e.get("stale") else ""
                print(f"  {e['path']}{tid}{stale_mark}")
                print(f"    → {e['description']}")

        if stale_undescribed:
            print(f"\n[stale 파일 ({len(stale_undescribed)}개) — 삭제됨]")
            for e in stale_undescribed:
                print(f"  {e['path']}  →  python flow.py files remove {e['path']}")

    else:
        files_p.print_help()


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
    p.add_argument("--desc", default="", help="태스크 상세 설명")
    p.add_argument("--parent", type=int, default=None, help="부모 태스크 ID")

    p = task_sub.add_parser("start", help="태스크 시작")
    p.add_argument("id", type=int)

    p = task_sub.add_parser("done", help="태스크 완료")
    p.add_argument("id", type=int)
    p.add_argument("--changelog", default=None, dest="changelog_msg", metavar="MSG",
                   help="changelog 메시지 동시 기록")
    p.add_argument("--no-changelog", action="store_true", dest="no_changelog",
                   help="changelog 기록 없이 완료 처리")

    p = task_sub.add_parser("reopen", help="완료된 태스크 재개 (실수 복구)")
    p.add_argument("id", type=int)

    p = task_sub.add_parser("edit", help="태스크 제목 수정")
    p.add_argument("id", type=int)
    p.add_argument("--title", required=True, help="새 제목")

    p = task_sub.add_parser("block", help="태스크 블로킹")
    p.add_argument("id", type=int)
    p.add_argument("reason", help="블로킹 이유")

    p = task_sub.add_parser("skip", help="태스크 건너뜀 (불필요/취소)")
    p.add_argument("id", type=int)
    p.add_argument("reason", nargs="?", default="", help="건너뜀 이유 (선택)")

    p = task_sub.add_parser("desc", help="태스크 설명 추가/수정")
    p.add_argument("id", type=int)
    p.add_argument("description", help="설명 내용")

    p = task_sub.add_parser("show", help="태스크 상세 조회")
    p.add_argument("id", type=int)

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
    p = phase_sub.add_parser("next", help="다음 phase로 전환")
    p.add_argument("--force", action="store_true", help="미완 태스크 있어도 강제 전환")
    phase_sub.add_parser("back", help="이전 phase로 롤백")

    # trace
    p = sub.add_parser("trace", help="이벤트 타임라인 추적")
    p.add_argument("--task", type=int, default=None, help="특정 태스크만 필터")
    p.add_argument("--phase", default=None, help="특정 phase만 필터")

    # test
    sub.add_parser("test", help="테스트 실행")

    # files
    files_p = sub.add_parser("files", help="파일 인덱스 관리")
    files_sub = files_p.add_subparsers(dest="files_cmd")

    files_sub.add_parser("snap", help="프로젝트 디렉토리 스캔 및 구조 저장")
    files_sub.add_parser("list", help="파일 구조 및 인덱스 출력")

    p = files_sub.add_parser("describe", help="파일/디렉토리 설명 추가/수정")
    p.add_argument("path", help="파일 또는 디렉토리 경로")
    p.add_argument("description", help="설명")
    p.add_argument("--task", type=int, default=None, help="연관 태스크 ID")

    p = files_sub.add_parser("add", help="파일 수동 등록 (snap 전 미리 등록)")
    p.add_argument("path", help="파일 경로")
    p.add_argument("description", nargs="?", default="", help="파일 설명")
    p.add_argument("--task", type=int, default=None, help="연관 태스크 ID")

    p = files_sub.add_parser("remove", help="파일 항목 제거")
    p.add_argument("path", help="파일 경로")

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
            cmd_phase_next(args)
        elif args.phase_cmd == "back":
            cmd_phase_back()
    elif args.command == "files":
        cmd_files(args, files_p)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
