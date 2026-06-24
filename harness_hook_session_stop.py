#!/usr/bin/env python3
"""Stop hook: 세션 종료 시 파일 구조 스냅샷을 자동으로 기록한다."""
import subprocess
from pathlib import Path


def run(cmd):
    r = subprocess.run(
        cmd, shell=True, capture_output=True,
        text=True, encoding="utf-8", errors="replace",
    )
    return (r.stdout + r.stderr).strip()


if Path("harness/project.json").exists():
    run("python flow.py files snap")
    run('python flow.py log "세션 종료 — 파일 스냅샷 자동 저장"')
