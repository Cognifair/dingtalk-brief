#!/usr/bin/env python3
"""Create tasks in Dida365 (婊寸瓟娓呭崟) through the official MCP endpoint.

The endpoint speaks MCP Streamable HTTP; this script wraps the few calls we
need (initialize -> tools/call) so the brief pipeline can run without an MCP
client. Auth uses a Bearer token from the web app:
澶村儚 -> 璁剧疆 -> 璐︽埛涓庡畨鍏?-> API 鍙ｄ护.

Token: environment variable DIDA_TOKEN (Windows user env is used as fallback).

Commands:
    python dida-task.py projects
    python dida-task.py today
    python dida-task.py add --file tasks.json [--project-id <id>] [--dry-run]

tasks.json: a list of objects, e.g.
    [{"title": "鏁板浣滀笟涓ゅ", "dueDate": "2026-10-19", "isAllDay": true,
      "priority": 5, "content": "浠婃櫄鏅氳嚜涔犳敹锛堟潵婧愶細琚佺珛瓒?10-16 14:53锛?}]
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone

URL = "https://mcp.dida365.com"
TZ = "Asia/Shanghai"


def _user_env(name: str) -> str:
    try:
        import winreg  # noqa: WPS433 - Windows-only fallback
    except ImportError:
        return ""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            value, _ = winreg.QueryValueEx(key, name)
            return str(value or "")
    except OSError:
        return ""


def env(name: str) -> str:
    return (os.environ.get(name) or _user_env(name)).strip()


class Mcp:
    def __init__(self, token: str):
        self.token = token
        self.session = None
        self.next_id = 1

    def _post(self, payload: dict) -> dict:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": "Bearer " + self.token,
        }
        if self.session:
            headers["Mcp-Session-Id"] = self.session
            headers["MCP-Protocol-Version"] = "2025-03-26"
        request = urllib.request.Request(
            URL, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
        )
        with urllib.request.urlopen(request, timeout=45) as response:
            session = response.headers.get("Mcp-Session-Id")
            if session:
                self.session = session
            raw = response.read().decode("utf-8", "replace")
        return self._parse(raw)

    @staticmethod
    def _parse(raw: str) -> dict:
        if raw.lstrip().startswith("{"):
            return json.loads(raw)
        for line in raw.splitlines():
            if line.startswith("data:"):
                return json.loads(line[5:].strip())
        raise ValueError("unexpected MCP response: " + raw[:200])

    def call(self, method: str, params: dict | None = None) -> dict:
        payload = {"jsonrpc": "2.0", "id": self.next_id, "method": method}
        self.next_id += 1
        if params is not None:
            payload["params"] = params
        return self._post(payload)

    def initialize(self) -> dict:
        result = self.call("initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "dingtalk-brief", "version": "1.0.0"},
        })
        return result.get("result", result)

    def tool(self, name: str, arguments: dict) -> dict:
        result = self.call("tools/call", {"name": name, "arguments": arguments})
        if "error" in result:
            raise RuntimeError(f"{name}: {result['error']}")
        payload = result.get("result", {})
        if payload.get("isError"):
            raise RuntimeError(f"{name}: {payload.get('content')}")
        if isinstance(payload.get("structuredContent"), (dict, list)):
            return payload["structuredContent"]
        content = payload.get("content") or []
        texts = [item.get("text", "") for item in content if item.get("type") == "text"]
        if len(texts) == 1:
            try:
                return json.loads(texts[0])
            except ValueError:
                return {"text": texts[0]}
        parsed = []
        for text in texts:
            try:
                parsed.append(json.loads(text))
            except ValueError:
                parsed.append(text)
        return {"items": parsed}


def iso_day(day: str, end_of_day: bool = False) -> str:
    """Accept YYYY-MM-DD and return a TickTick-friendly ISO timestamp in +08:00."""
    if "T" in day:
        return day
    suffix = "T23:59:59+0800" if end_of_day else "T00:00:00+0800"
    return day + suffix


def normalize(text: str) -> str:
    return "".join((text or "").split()).lower()


def project_list(cli: Mcp) -> list:
    data = cli.tool("list_projects", {})
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("result", "projects", "data", "items"):
            if isinstance(data.get(key), list):
                return data[key]
    return []


def cmd_projects(cli: Mcp) -> int:
    for project in project_list(cli):
        print(json.dumps({
            "id": project.get("id"),
            "name": project.get("name"),
            "kind": project.get("kind"),
            "closed": project.get("closed"),
        }, ensure_ascii=False))
    return 0


def cmd_today(cli: Mcp) -> int:
    today = datetime.now(timezone(timedelta(hours=8))).date().isoformat()
    data = cli.tool("list_undone_tasks_by_date", {
        "search": {"startDate": iso_day(today), "endDate": iso_day(today, end_of_day=True)},
        "client_timezone": TZ,
    })
    print(json.dumps(data, ensure_ascii=False)[:4000])
    return 0


def cmd_add(cli: Mcp, path: str, project_id: str, dry_run: bool) -> int:
    with open(path, "r", encoding="utf-8") as stream:
        tasks = json.load(stream)
    if isinstance(tasks, dict):
        tasks = [tasks]

    today = datetime.now(timezone(timedelta(hours=8))).date()
    window_end = (today + timedelta(days=13)).isoformat()
    existing = set()
    try:
        data = cli.tool("list_undone_tasks_by_date", {
            "search": {"startDate": iso_day(today.isoformat()),
                       "endDate": iso_day(window_end, end_of_day=True)},
            "client_timezone": TZ,
        })
        items = data if isinstance(data, list) else data.get("result") or data.get("tasks") or data.get("data") or []
        existing = {normalize(item.get("title", "")) for item in items if isinstance(item, dict)}
    except Exception as exc:  # noqa: BLE001 - dedupe is best effort
        print(json.dumps({"dedupe": "skipped", "reason": str(exc)[:200]}, ensure_ascii=False))

    # A task the user already ticked off should not come back on the next run,
    # even though it no longer appears in the "undone" list.
    try:
        done = cli.tool("list_completed_tasks_by_date", {
            "search": {"startDate": iso_day(today.isoformat()),
                       "endDate": iso_day(window_end, end_of_day=True)},
            "client_timezone": TZ,
        })
        done_items = done if isinstance(done, list) else done.get("result") or done.get("tasks") or []
        existing |= {normalize(item.get("title", "")) for item in done_items if isinstance(item, dict)}
    except Exception as exc:  # noqa: BLE001 - dedupe is best effort
        print(json.dumps({"dedupe_completed": "skipped", "reason": str(exc)[:200]}, ensure_ascii=False))

    created, skipped = [], []
    for task in tasks:
        title = (task.get("title") or "").strip()
        if not title:
            continue
        if normalize(title) in existing:
            skipped.append(title)
            continue
        payload = dict(task)
        payload.setdefault("kind", "TEXT")
        if project_id:
            payload.setdefault("projectId", project_id)
        if dry_run:
            created.append({"dry_run": payload})
            continue
        result = cli.tool("create_task", {"task": payload, "client_timezone": TZ})
        created.append(result)
        existing.add(normalize(title))

    print(json.dumps({"created": len(created), "skipped": len(skipped),
                      "skipped_titles": skipped, "results": created},
                     ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("projects")
    sub.add_parser("today")
    add = sub.add_parser("add")
    add.add_argument("--file", required=True)
    add.add_argument("--project-id", default="")
    add.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    token = env("DIDA_TOKEN")
    if not token:
        print(json.dumps({"ok": False, "error": "DIDA_TOKEN is not set"}, ensure_ascii=False))
        return 2

    cli = Mcp(token)
    try:
        cli.initialize()
        if args.command == "projects":
            return cmd_projects(cli)
        if args.command == "today":
            return cmd_today(cli)
        return cmd_add(cli, args.file, args.project_id, args.dry_run)
    except (urllib.error.URLError, TimeoutError, RuntimeError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)[:400]}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
