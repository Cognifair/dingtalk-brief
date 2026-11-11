#!/usr/bin/env python3
"""Send a Markdown message to a DingTalk custom-robot webhook.

Reads the webhook from the DINGTALK_ROBOT environment variable so the token
never has to live in a command line or in this file.

The robot was configured with a keyword security setting, so every message
must contain the keyword (default: Cognifair); it is appended if missing.

Usage:
    python push-dingtalk.py --title "Cognifair · 钉钉简报 10-19" --text-file brief.md
    python push-dingtalk.py --title "..." --text "inline markdown"
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

KEYWORD = "Cognifair"


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


def load_webhook() -> str:
    url = (os.environ.get("DINGTALK_ROBOT") or _user_env("DINGTALK_ROBOT")).strip()
    if not url:
        print(json.dumps({"ok": False, "error": "DINGTALK_ROBOT is not set"}, ensure_ascii=False))
        sys.exit(2)
    if not url.startswith("https://oapi.dingtalk.com/robot/send"):
        print(json.dumps({"ok": False, "error": "unexpected webhook host"}, ensure_ascii=False))
        sys.exit(2)
    return url


def ensure_keyword(text: str) -> str:
    if KEYWORD in text:
        return text
    return text.rstrip() + "\n\n—— " + KEYWORD


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
    parser.add_argument("--at-mobile", action="append", default=[],
                        help="mobile number to @ (repeatable); also inserted into the text")
    parser.add_argument("--at-userid", action="append", default=[],
                        help="DingTalk userId to @ (repeatable); needs the text mention too")
    parser.add_argument("--at-all", action="store_true", help="@ everyone in the group")
    args = parser.parse_args()

    if args.text_file:
        with open(args.text_file, "r", encoding="utf-8-sig") as stream:
            text = stream.read()
    else:
        text = args.text
    text = text.lstrip("\ufeff")

    # Guard: never push an empty or near-empty card (happened once when a template
    # extraction silently produced an empty file and the group got a blank message).
    if len(text.strip()) < 20:
        print(json.dumps({
            "ok": False,
            "error": "refusing to send empty/near-empty message",
            "chars": len(text.strip()),
        }, ensure_ascii=False))
        return 2

    title = args.title if KEYWORD in args.title else args.title + " · " + KEYWORD
    text = ensure_keyword(text)

    payload = {
        "msgtype": "markdown",
        "markdown": {"title": title, "text": text},
    }
    if args.at_mobile or args.at_userid or args.at_all:
        mentions = " ".join("@" + m for m in args.at_mobile)
        if mentions:
            # DingTalk only renders the @ when the text contains it as well.
            payload["markdown"]["text"] = text + "\n\n" + mentions
        payload["at"] = {
            "atMobiles": args.at_mobile,
            "atUserIds": args.at_userid,
            "isAtAll": args.at_all,
        }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    url = load_webhook()
    request = urllib.request.Request(
        url,
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
