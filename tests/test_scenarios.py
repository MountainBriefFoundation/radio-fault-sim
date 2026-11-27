import json
import subprocess
import sys
import unittest
from unittest.mock import patch

from radio_fault_sim.scenarios import SCENARIOS, run_scenario


class ScenarioTests(unittest.TestCase):
    def test_all_scenarios_are_deterministic(self):
        for name in SCENARIOS:
            with self.subTest(name=name):
                self.assertEqual(run_scenario(name), run_scenario(name))

    def test_scenarios_open_no_external_resources_or_wait_on_real_time(self):
        with patch("builtins.open", side_effect=AssertionError("file I/O")), \
             patch("socket.socket", side_effect=AssertionError("socket I/O")), \
             patch("subprocess.Popen", side_effect=AssertionError("process I/O")), \
             patch("time.sleep", side_effect=AssertionError("wall-clock wait")):
            for name in SCENARIOS:
                run_scenario(name)

    def test_normal_and_coarse_scenarios_finish_idle(self):
        for name in ("normal", "coarse-clock"):
            final = run_scenario(name)["samples"][-1]
            self.assertFalse(final["queued"])
            self.assertFalse(final["ptt_line"])

    def test_partial_write_demonstrates_prefix_and_cancellation(self):
        result = run_scenario("partial-write")
        self.assertTrue(result["samples"][0]["partial"])
        self.assertEqual(result["samples"][0]["payload_bytes"], 1)
        self.assertTrue(result["outcomes"]["cancel_acknowledged"])
        self.assertFalse(result["samples"][-1]["queued"])

    def test_stuck_and_crash_scenarios_remain_keyed(self):
        for name in ("stuck-ptt", "crash-latched"):
            result = run_scenario(name)
            self.assertFalse(result["outcomes"]["release_acknowledged"])
            self.assertTrue(result["samples"][-1]["ptt_line"])

    def test_lying_release_demonstrates_acknowledgment_state_disagreement(self):
        result = run_scenario("release-lies")
        sample = next(x for x in result["samples"] if x["label"] == "after-release-command")
        self.assertTrue(result["outcomes"]["release_acknowledged"])
        self.assertTrue(sample["ptt_line"])

    def test_unknown_scenario_is_rejected(self):
        with self.assertRaises(ValueError):
            run_scenario("unknown")

    def test_cli_json_and_scenario_selection(self):
        result = subprocess.run(
            [sys.executable, "-m", "radio_fault_sim", "--scenario", "stuck-ptt", "--json"],
            capture_output=True, text=True, check=True,
        )
        output = json.loads(result.stdout)
        self.assertEqual(output["model_version"], "0.1.0")
        self.assertEqual(len(output["scenarios"]), 1)
        self.assertTrue(output["scenarios"][0]["samples"][-1]["ptt_line"])

    def test_cli_rejects_unknown_scenario(self):
        result = subprocess.run(
            [sys.executable, "-m", "radio_fault_sim", "--scenario", "unknown"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("invalid choice", result.stderr)


if __name__ == "__main__":
    unittest.main()
