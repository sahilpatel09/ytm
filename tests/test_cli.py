import sys
import unittest
from types import SimpleNamespace
from contextlib import redirect_stderr, redirect_stdout
from importlib import metadata
from io import StringIO
from unittest.mock import call, patch, sentinel

from ytm import __main__ as cli


class CliTests(unittest.TestCase):
    def test_web_bypasses_terminal_startup(self):
        calls = []
        server = SimpleNamespace(serve=lambda: calls.append("serve"))
        with (
            patch.object(sys, "argv", ["ytm", "--web"]),
            patch.dict(sys.modules, {"ytm.web": server}),
            patch.object(cli, "native_cover_widget", side_effect=AssertionError("terminal probe")),
        ):
            cli.main()
        self.assertEqual(calls, ["serve"])

    def test_terminal_launch_cleans_up_on_error(self):
        with (
            patch.object(sys, "argv", ["ytm"]),
            patch.object(cli, "native_cover_widget", return_value=None),
            patch("ytm.app.YtmApp") as app_type,
        ):
            app = app_type.return_value
            app.run.side_effect = RuntimeError("startup failed")
            with self.assertRaisesRegex(RuntimeError, "startup failed"):
                cli.main()
            self.assertEqual(app.mock_calls, [call.run(), call.cleanup()])

    def test_version_bypasses_startup(self):
        stdout, stderr = StringIO(), StringIO()
        with (
            patch.object(sys, "argv", ["ytm", "--version"]),
            patch.object(metadata, "version", return_value="8.9.10") as version,
            patch.object(
                cli,
                "native_cover_widget",
                side_effect=AssertionError("--version must bypass the terminal probe"),
            ),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            self.assertIsNone(cli.main())

        version.assert_called_once_with("ytm")
        self.assertEqual(stdout.getvalue(), "ytm 8.9.10\n")
        self.assertEqual(stderr.getvalue(), "")
