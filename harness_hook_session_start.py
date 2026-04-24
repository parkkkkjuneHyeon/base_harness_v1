#!/usr/bin/env python3
"""SessionStart hook: harness/project.json이 있을 때 상태와 진행 중 태스크 로그를 컨텍스트에 주입."""
import subprocess
import json
from pathlib import Path


def run(cmd):
    r = subprocess.run(
        cmd, shell=True, capture_output=True,
        text=True, encoding="utf-8", errors="replace",
    )
    return (r.stdout + r.stderr).strip()


if Path("harness/project.json").exists():
    sections = []

    # 전체 상태
    status_out = run("python flow.py status")
    if status_out:
        sections.append("[현재 상태]\n" + status_out)

    # in_progress 태스크 상세 로그 (세션 재개 컨텍스트 복원)
    try:
        tasks_data = json.loads(Path("harness/tasks.json").read_text(encoding="utf-8"))
        in_progress = [t for t in tasks_data.get("tasks", []) if t["status"] == "in_progress"]
        for task in in_progress:
            detail = run(f"python flow.py task show {task['id']}")
            if detail:
                sections.append(f"[진행 중 태스크 #{task['id']} 상세]\n" + detail)
    except Exception:
        pass

    if sections:
        context = "\n\n".join(sections)
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": context,
            }
        }))
