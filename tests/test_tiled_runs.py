import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from unittest import mock

from scriptrunner.lib import tiled_runs
from scriptrunner.lib import utilities as util

try:
    import tiled  # noqa: F401
    HAS_TILED = True
except ImportError:
    HAS_TILED = False


class TestRunArguments(unittest.TestCase):
    """Which script arguments get a 'Pick run...' button, and with what."""

    def test_run_argument_field(self):
        self.assertEqual(util.run_argument_field("uid"), "uid")
        self.assertEqual(util.run_argument_field("run-uid"), "uid")
        self.assertEqual(util.run_argument_field("scan_id"), "scan_id")
        self.assertEqual(util.run_argument_field("SCAN_ID"), "scan_id")
        self.assertIsNone(util.run_argument_field("file"))
        self.assertIsNone(util.run_argument_field("count"))

    def test_build_run_search_command(self):
        cmd = util.build_run_search_command(
            "/env/bin/python", "https://tiled.example", "hex/raw",
            "2026-10-01", "2026-10-29", plan_name="edxd_scan",
            data_session="pass-320610", limit=50)
        self.assertEqual(cmd[:2], ["/env/bin/python", util.TILED_RUNS_SCRIPT])
        self.assertTrue(os.path.isfile(cmd[1]))
        args = tiled_runs.parse_args(cmd[2:])
        self.assertEqual(args.uri, "https://tiled.example")
        self.assertEqual(args.catalog, "hex/raw")
        self.assertEqual(args.plan_name, "edxd_scan")
        self.assertEqual(args.data_session, "pass-320610")
        self.assertEqual(args.limit, 50)

    def test_optional_filters_left_out_when_empty(self):
        cmd = util.build_run_search_command("py", "u", "", "2026-10-01",
                                            "2026-10-01")
        self.assertNotIn("--plan-name", cmd)
        self.assertNotIn("--data-session", cmd)

    def test_parse_run_search_output(self):
        runs, error = util.parse_run_search_output(
            'a warning line\n{"runs": [{"uid": "abc", "scan_id": 5}]}\n')
        self.assertIsNone(error)
        self.assertEqual(runs, [{"uid": "abc", "scan_id": 5}])
        runs, error = util.parse_run_search_output('{"error": "no login"}')
        self.assertEqual((runs, error), ([], "no login"))
        self.assertTrue(util.parse_run_search_output("")[1])
        self.assertTrue(util.parse_run_search_output("Traceback ...")[1])


class TestConfig(unittest.TestCase):

    def test_update_config_keeps_other_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "sub", "config.json")
            with mock.patch.object(util, "get_config_path",
                                   return_value=path):
                util.save_config({"last_folder": "/data"})
                util.update_config(tiled_uri="https://tiled.example")
                util.update_config(last_folder="/other")
                self.assertEqual(util.load_config(),
                                 {"last_folder": "/other",
                                  "tiled_uri": "https://tiled.example"})


class TestDayBounds(unittest.TestCase):

    def test_until_is_inclusive(self):
        since, until = tiled_runs.day_bounds("2026-10-29", "2026-10-29")
        self.assertEqual(since, datetime(2026, 10, 29).timestamp())
        self.assertEqual(until, datetime(2026, 10, 30).timestamp())

    def test_reversed_range_rejected(self):
        with self.assertRaises(ValueError):
            tiled_runs.day_bounds("2026-10-29", "2026-10-28")


class TestSearchScript(unittest.TestCase):
    """The helper ScriptRunner runs in the script's interpreter."""

    def test_failure_is_reported_as_json(self):
        # Without Tiled this reports the missing package; with Tiled, the
        # unreachable server. Either way: one JSON error and exit code 1.
        proc = subprocess.run(
            [sys.executable, util.TILED_RUNS_SCRIPT,
             "--uri", "http://127.0.0.1:9", "--since", "2026-10-29",
             "--until", "2026-10-29"],
            stdin=subprocess.DEVNULL, capture_output=True, text=True,
            timeout=60)
        self.assertEqual(proc.returncode, 1, proc.stderr)
        runs, error = util.parse_run_search_output(proc.stdout)
        self.assertEqual(runs, [])
        self.assertTrue(error)


def _start(uid, scan_id, when, plan_name, data_session):
    return {"start": {"uid": uid, "scan_id": scan_id,
                      "time": datetime(*when).timestamp(),
                      "plan_name": plan_name, "data_session": data_session}}


@unittest.skipUnless(HAS_TILED, "tiled is not installed")
class TestSearchRunsAgainstTiled(unittest.TestCase):
    """search_runs against a real, in-process Tiled server."""

    @classmethod
    def setUpClass(cls):
        from tiled.adapters.mapping import MapAdapter
        from tiled.client import Context, from_context
        from tiled.server.app import build_app

        runs = {
            "uid-1": _start("uid-1", 1, (2026, 10, 28, 9), "edxd_scan",
                            "pass-320610"),
            "uid-2": _start("uid-2", 2, (2026, 10, 29, 10), "edxd_scan",
                            "pass-320610"),
            "uid-3": _start("uid-3", 3, (2026, 10, 29, 11), "count",
                            "pass-320610"),
            "uid-4": _start("uid-4", 4, (2026, 10, 29, 12), "edxd_scan",
                            "pass-999999"),
        }
        tree = MapAdapter({"hex": MapAdapter({"raw": MapAdapter(
            {uid: MapAdapter({}, metadata=md) for uid, md in runs.items()})})})
        cls.context = Context.from_app(build_app(tree))
        cls.client = from_context(cls.context)
        cls.catalog = cls.client["hex"]["raw"]

    @classmethod
    def tearDownClass(cls):
        cls.context.close()

    def search(self, **kwargs):
        since, until = tiled_runs.day_bounds(kwargs.pop("since", "2026-10-29"),
                                             kwargs.pop("until", "2026-10-29"))
        return tiled_runs.search_runs(self.catalog, since, until, **kwargs)

    def test_date_range_newest_first(self):
        runs = self.search()
        self.assertEqual([r["uid"] for r in runs], ["uid-4", "uid-3", "uid-2"])
        self.assertEqual(runs[0]["scan_id"], 4)
        self.assertEqual(runs[0]["plan_name"], "edxd_scan")
        self.assertEqual(runs[0]["data_session"], "pass-999999")
        json.dumps(runs)

    def test_plan_and_proposal_filters(self):
        runs = self.search(since="2026-10-28", plan_name="edxd_scan",
                           data_session="pass-320610")
        self.assertEqual([r["uid"] for r in runs], ["uid-2", "uid-1"])

    def test_limit(self):
        self.assertEqual(len(self.search(limit=1)), 1)


if __name__ == "__main__":
    unittest.main()
