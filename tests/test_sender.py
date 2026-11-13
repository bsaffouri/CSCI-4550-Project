"""End-to-end tests: run sender.py against fake_neighbor.py and check the results."""

import subprocess
import sys
import time
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
FAKE_NEIGHBOR = PROJECT_ROOT / "tests" / "fake_neighbor.py"
SENDER = PROJECT_ROOT / "src" / "sender.py"
NEIGHBOR_STARTUP_SECONDS = 0.3


def run_scenario(neighbor_args, sender_args):
    """Start the fake neighbor, run the sender against it, and return the sender's result."""
    neighbor = subprocess.Popen(
        [sys.executable, str(FAKE_NEIGHBOR), "RA", *neighbor_args],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        time.sleep(NEIGHBOR_STARTUP_SECONDS)
        if neighbor.poll() is not None:
            raise RuntimeError(f"fake neighbor exited early: {neighbor.stderr.read()}")

        return subprocess.run(
            [sys.executable, str(SENDER), "H1", *sender_args],
            capture_output=True,
            text=True,
            timeout=15,
        )
    finally:
        neighbor.terminate()
        neighbor.communicate()


class SenderTests(unittest.TestCase):
    def assert_output(self, result, expected_text, expected_code):
        details = f"\n--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
        for text in expected_text:
            self.assertIn(text, result.stdout, details)
        self.assertEqual(result.returncode, expected_code, details)

    def test_no_loss(self):
        result = run_scenario(["--mode", "ack"], ["--count", "5"])
        self.assert_output(result, ["delivered 5/5", "retransmissions=0"], 0)

    def test_dropped_data_recovers(self):
        result = run_scenario(
            ["--mode", "ack", "--drop-number", "2"], ["--count", "5"]
        )
        self.assert_output(result, ["delivered 5/5", "retransmissions=1"], 0)

    def test_unreachable_fails(self):
        result = run_scenario(
            ["--mode", "silent"],
            ["--count", "5", "--timeout", "0.2", "--retries", "2"],
        )
        self.assert_output(result, ["FAILED"], 1)

    def test_best_effort_loses(self):
        result = run_scenario(
            ["--mode", "ack", "--drop-number", "3"],
            ["--mode", "best-effort", "--count", "5", "--observe", "0.5"],
        )
        self.assert_output(result, ["acked=4/5"], 0)


if __name__ == "__main__":
    unittest.main()