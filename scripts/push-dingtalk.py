#!/usr/bin/env python3
"""Send a Markdown message to a DingTalk custom-robot webhook.

The webhook is read from the DINGTALK_ROBOT environment variable so the token
never has to live in a command line or in this file. On Windows, if the
variable is missing from the current process, the user-level registry value is
used as a fallback.

If the robot uses the "custom keyword" security setting, export that keyword as
DINGTALK_KEYWORD; it is appended automatically when the text lacks it.

Usage:
    python push-dingtalk.py --title "Standup brief" --text-file brief.md
    python push-dingtalk.py --title "..." --text "inline markdown"
    python push-dingtalk.py --title "..." --text-file brief.md --dry-run
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request


def _user_env(name: str) -> str:
    """Read a Windows user-level environment variable set after this shell started."""
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


def load_webhook() -> str:
    url = env("DINGTALK_ROBOT")
    if not url:
        print(json.dumps({"ok": False, "error": "DINGTALK_ROBOT is not set"}, ensure_ascii=False))
        sys.exit(2)
    if not url.startswith("https://oapi.dingtalk.com/robot/send"):
        print(json.dumps({"ok": False, "error": "unexpected webhook host"}, ensure_ascii=False))
        sys.exit(2)
    return url


def ensure_keyword(text: str) -> str:
    keyword = env("DINGTALK_KEYWORD")
    if not keyword or keyword in text:
        return text
    return text.rstrip() + "\n\n—— " + keyword


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        pass

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--title", required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text-file")
    group.add_argument("--text")
    parser.add_argument("--dry-run", action="store_true", help="print the payload without sending")
    args = parser.parse_args()

    if args.text_file:
        with open(args.text_file, "r", encoding="utf-8") as stream:
            text = stream.read()
    else:
        text = args.text

    keyword = env("DINGTALK_KEYWORD")
    title = args.title
    if keyword and keyword not in title:
        title = title + " · " + keyword
    text = ensure_keyword(text)

    payload = {"msgtype": "markdown", "markdown": {"title": title, "text": text}}
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    request = urllib.request.Request(
        load_webhook(),
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1

    ok = result.get("errcode") == 0
    print(json.dumps({"ok": ok, "errcode": result.get("errcode"),
                      "errmsg": result.get("errmsg"), "bytes": len(body)},
                     ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
