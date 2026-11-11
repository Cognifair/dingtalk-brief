#!/usr/bin/env python3
"""Push the same task list into several Dida365 accounts.

- Accounts come from references/dida-accounts.json: name + env var holding the token.
- Tokens never appear in this file or in output.
- Dedupe is per account (undone + recently completed, normalized title).
- A failing account is reported and skipped; the others still run.
- Accounts are processed sequentially with a small delay to stay polite.
"""

import argparse
import importlib.util
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

TZ = timezone(timedelta(hours=8))
SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACCOUNTS = os.path.join(SKILL, "references", "dida-accounts.json")
WINDOW_DAYS = 14


def load_dida():
    spec = importlib.util.spec_from_file_location("dida", os.path.join(SKILL, "scripts", "dida-task.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def token_for(dida, entry):
    name = entry.get("tokenEnv") or ""
    value = dida.env(name) if name else ""
    return value.strip()


def existing_titles(dida, cli):
    today = datetime.now(TZ).date()
    titles = set()
    try:
        undone = cli.tool("filter_tasks", {"filter": {"status": [0]}}).get("result", [])
    except Exception:
        undone = []
    for task in undone:
        titles.add(dida.normalize(task.get("title") or ""))
    try:
        done = cli.tool("list_completed_tasks_by_date", {
            "search": {
                "startDate": dida.iso_day((today - timedelta(days=WINDOW_DAYS)).isoformat()),
                "endDate": dida.iso_day(today.isoformat(), True),
            },
            "client_timezone": "Asia/Shanghai",
        }).get("result", [])
        for task in done:
            titles.add(dida.normalize(task.get("title") or ""))
    except Exception:
        pass
    return titles


def push(dida, entry, tasks, dry_run):
    token = token_for(dida, entry)
    if not token:
        return {"account": entry.get("name"), "ok": False,
                "error": "token env missing: " + str(entry.get("tokenEnv"))}
    cli = dida.Mcp(token)
    try:
        cli.initialize()
    except Exception as exc:  # noqa: BLE001
        return {"account": entry.get("name"), "ok": False, "error": f"auth failed: {type(exc).__name__}"}

    have = existing_titles(dida, cli)
    created, skipped = [], []
    for task in tasks:
        title = task.get("title") or ""
        if dida.normalize(title) in have:
            skipped.append(title[:30])
            continue
        if dry_run:
            created.append(title[:30])
            have.add(dida.normalize(title))
            continue
        payload = dict(task)
        payload.setdefault("projectId", entry.get("projectId") or "inbox")
        try:
            cli.tool("create_task", {"task": payload, "client_timezone": "Asia/Shanghai"})
            created.append(title[:30])
            have.add(dida.normalize(title))
        except Exception as exc:  # noqa: BLE001
            skipped.append(f"{title[:24]} (error {type(exc).__name__})")
        time.sleep(0.25)
    return {"account": entry.get("name"), "ok": True,
            "created": len(created), "skipped": len(skipped),
            "created_titles": created, "skipped_titles": skipped}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True, help="任务 JSON 数组")
    parser.add_argument("--to", default="all", help="all 或逗号分隔的账号名")
    parser.add_argument("--accounts", default=ACCOUNTS, help="账号表路径")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    dida = load_dida()
    with open(args.accounts, "r", encoding="utf-8-sig") as stream:
        accounts = json.load(stream)
    with open(args.file, "r", encoding="utf-8-sig") as stream:
        tasks = json.load(stream)
    if isinstance(tasks, dict):
        tasks = [tasks]

    wanted = None if args.to.strip().lower() == "all" else {x.strip() for x in args.to.split(",") if x.strip()}
    selected = [a for a in accounts if wanted is None or a.get("name") in wanted]
    if not selected:
        print(json.dumps({"ok": False, "error": "no matching account", "accounts": [a.get("name") for a in accounts]}, ensure_ascii=False))
        return 2

    results = []
    for entry in selected:
        results.append(push(dida, entry, tasks, args.dry_run))
        time.sleep(0.4)

    print(json.dumps({
        "ok": all(r.get("ok") for r in results),
        "accounts": len(selected),
        "results": results,
        "dry_run": args.dry_run,
    }, ensure_ascii=False, indent=None))
    return 0 if all(r.get("ok") for r in results) else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
