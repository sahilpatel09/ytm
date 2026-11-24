import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from importlib import metadata
from io import StringIO
from unittest.mock import call, patch, sentinel

from ytm import __main__ as cli


class CliTests(unittest.TestCase):
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