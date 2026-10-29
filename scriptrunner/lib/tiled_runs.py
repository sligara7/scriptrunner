"""Search a Tiled catalog of Bluesky runs and print the matches as JSON.

ScriptRunner runs this file with the interpreter it would use for the selected
script, so Tiled only needs to be installed in that environment, not in
ScriptRunner's own. It uses only the standard library plus ``tiled``.

Output (stdout), one JSON object:
    {"runs": [{"uid", "scan_id", "time", "plan_name", "data_session"}, ...]}
or, on failure (exit code 1):
    {"error": "<message>"}
"""

import argparse
import json
import sys
from datetime import datetime, timedelta


def day_bounds(since, until):
    """Return POSIX times for the start of ``since`` and the end of ``until``.

    Both are local dates written as YYYY-MM-DD; ``until`` is inclusive.
    """
    start = datetime.strptime(since, "%Y-%m-%d")
    end = datetime.strptime(until, "%Y-%m-%d") + timedelta(days=1)
    if end <= start:
        raise ValueError(f"'until' ({until}) is before 'since' ({since})")
    return start.timestamp(), end.timestamp()


def search_runs(client, since, until, plan_name=None, data_session=None,
                limit=200):
    """Return runs in ``client`` started in ``[since, until)``, newest first.

    ``since`` and ``until`` are POSIX times. Each run is summarised as a dict
    with its uid, scan_id, start time, plan_name and data_session.
    """
    from tiled.queries import Key

    results = client.search(Key("start.time") >= since).search(
        Key("start.time") < until)
    if plan_name:
        results = results.search(Key("start.plan_name") == plan_name)
    if data_session:
        results = results.search(Key("start.data_session") == data_session)
    runs = []
    for uid, run in results.items():
        start = dict(run.metadata).get("start", {})
        runs.append({
            "uid": start.get("uid", uid),
            "scan_id": start.get("scan_id"),
            "time": start.get("time", 0.0),
            "plan_name": start.get("plan_name"),
            "data_session": start.get("data_session"),
        })
    runs.sort(key=lambda r: r["time"] or 0.0, reverse=True)
    return runs[:limit]


def open_catalog(uri, catalog_path):
    """Connect to ``uri`` and walk down ``catalog_path`` (e.g. 'hex/raw')."""
    from tiled.client import from_uri

    node = from_uri(uri)
    for part in [p for p in catalog_path.split("/") if p]:
        node = node[part]
    return node


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--uri", required=True, help="Tiled server URI")
    parser.add_argument("--catalog", default="",
                        help="Path below the server root, e.g. hex/raw")
    parser.add_argument("--since", required=True, help="First day, YYYY-MM-DD")
    parser.add_argument("--until", required=True,
                        help="Last day (inclusive), YYYY-MM-DD")
    parser.add_argument("--plan-name", default="", help="start.plan_name")
    parser.add_argument("--data-session", default="",
                        help="start.data_session, e.g. pass-123456")
    parser.add_argument("--limit", type=int, default=200)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        since, until = day_bounds(args.since, args.until)
        client = open_catalog(args.uri, args.catalog)
        runs = search_runs(client, since, until, args.plan_name or None,
                           args.data_session or None, args.limit)
    except ImportError as e:
        print(json.dumps({"error": f"Tiled is not installed in this "
                                   f"interpreter ({sys.executable}): {e}"}))
        return 1
    except Exception as e:
        print(json.dumps({"error": f"{type(e).__name__}: {e}"}))
        return 1
    print(json.dumps({"runs": runs}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
