"""Read-only local API bridge. No cloud, login, discovery, sync or file export."""
import argparse
import json
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import HTTPRedirectHandler, ProxyHandler, build_opener

BASE = "http://127.0.0.1:8090"
SCOPE_PATH = Path(__file__).with_name("allowed_groups.json")


def load_scope():
    """Fail closed: no configuration means no access to any conversation."""
    with SCOPE_PATH.open(encoding="utf-8") as stream:
        scope = json.load(stream)
    if not isinstance(scope, dict) or scope.get("schema_version") != 1:
        raise ValueError("Unsupported group scope")
    groups = scope.get("groups")
    if not isinstance(groups, list) or not groups:
        raise ValueError("No allowed groups configured")
    ids = []
    for group in groups:
        if not isinstance(group, dict) or not isinstance(group.get("cid"), str) or not group["cid"].isdigit():
            raise ValueError("Invalid group scope")
        ids.append(group["cid"])
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate group IDs")
    return scope


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise HTTPError(req.full_url, code, "Redirects disabled", headers, fp)


def minimize_message(row, include_media=False):
    result = {key: row.get(key) for key in
              ("id", "sender_name", "created_at", "content_type", "text")}
    if include_media:
        # Metadata only: never propagate remote URLs, tokens or arbitrary JSON.
        result["attachments"] = [
            {key: att.get(key) for key in
             ("type", "filename", "file_size", "file_type", "local_available", "local_path")}
            for att in row.get("attachments", []) if isinstance(att, dict)
        ]
        info = row.get("image_info") or {}
        result["images"] = [
            {key: img.get(key) for key in ("file_size", "cached", "local_path")}
            for img in info.get("images", []) if isinstance(img, dict)
        ]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("scope", help="Show configured groups without reading the service")
    groups = commands.add_parser("groups", help="List group names and IDs only")
    groups.add_argument("--keyword", default="")
    groups.add_argument("--offset", type=int, default=0)
    messages = commands.add_parser("messages", help="Read one explicitly chosen conversation")
    messages.add_argument("--cid", required=True)
    messages.add_argument("--since", type=int, required=True, help="Exclusive lower timestamp in milliseconds")
    messages.add_argument("--until", type=int, required=True, help="Inclusive upper timestamp in milliseconds")
    messages.add_argument("--offset", type=int, default=0)
    messages.add_argument("--limit", type=int, default=100, choices=range(1, 501), metavar="1..500")
    messages.add_argument("--include-media", action="store_true", help="Include message-linked local media metadata; no download or cloud upload")
    args = parser.parse_args()
    try:
        scope = load_scope()
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": "scope_unavailable", "detail": str(exc)}, ensure_ascii=True))
        return 2
    allowed_ids = {group["cid"] for group in scope["groups"]}
    if args.command == "scope":
        print(json.dumps(scope, ensure_ascii=True))
        return 0
    if args.offset < 0:
        parser.error("offset must be nonnegative")
    if args.command == "messages":
        if args.cid not in allowed_ids:
            print(json.dumps({"error": "group_not_allowed"}))
            return 2
        if not 0 <= args.since < args.until:
            parser.error("timestamps must satisfy 0 <= since < until")
    if args.command == "groups":
        query = {"limit": 500, "offset": args.offset, "keyword": args.keyword}
        endpoint = "/api/conversations"
    else:
        query = {"limit": args.limit, "offset": args.offset}
        if args.since is not None:
            query["since"] = args.since
        if args.until is not None:
            query["until"] = args.until
        endpoint = "/api/conversations/" + quote(args.cid, safe="") + "/messages"
    # Never send private query parameters through a system HTTP proxy.
    opener = build_opener(ProxyHandler({}), NoRedirect())
    try:
        with opener.open(BASE + endpoint + "?" + urlencode(query), timeout=30) as response:
            data = json.load(response)
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        print(json.dumps({"error": type(exc).__name__, "hint": "Start and validate the local service first."}))
        return 1
    if args.command == "groups":
        items = data["conversations"]
        output = {"cached_only": True, "complete": args.offset + len(items) >= data["total"],
                  "next_offset": args.offset + len(items),
                  "groups": [{key: row.get(key) for key in ("cid", "title", "member_count")}
                             for row in items if row.get("type") == "group" and str(row.get("cid")) in allowed_ids]}
    else:
        items = data["messages"]
        output = {"cached_only": True, "cid": args.cid, "total": data["total"],
                  "complete": args.offset + len(items) >= data["total"],
                  "paging": "Newest window first; increase offset by limit for older windows; deduplicate IDs.",
                  "messages": [minimize_message(row, args.include_media) for row in items]}
    print(json.dumps(output, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
