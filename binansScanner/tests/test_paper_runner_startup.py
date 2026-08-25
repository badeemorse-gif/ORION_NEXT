from __future__ import annotations

import json
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import tools.orion_paper_8h_runner as runner


class _FakePipeline:
    def __init__(self, *args, **kwargs):
        pass

    def discover(self):
        return type("Result", (), {"candidates": [type("Candidate", (), {"symbol": "BTCUSDT"})()]})()


class _FailingPipeline:
    def __init__(self, *args, **kwargs):
        pass

    def discover(self):
        raise RuntimeError("discovery failed")


class PaperRunnerStartupTests(unittest.TestCase):
    def _config(self, directory: Path) -> runner.Paper8HConfig:
        return runner.Paper8HConfig(output_dir=directory, starting_capital=50.0, top_n=10)

    def test_output_directory_and_run_start_exist_before_discovery(self):
        with TemporaryDirectory() as tmp:
            config = self._config(Path(tmp) / "run")
            log = runner._startup_log(config)
            events = Path(tmp) / "run" / "events.jsonl"
            self.assertTrue(events.exists())
            first = json.loads(events.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(first["event_type"], "run_start")
            self.assertEqual(first["startup_phase"], "initialization")
            self.assertTrue(first["paper_only"])
            self.assertFalse(first["live_execution"])
            log.close()

    def test_bounded_source_rejects_expired_deadline_without_network(self):
        source = runner._BoundedBinanceSpotOpportunitySource(deadline=time.monotonic() - 1)
        with self.assertRaises(TimeoutError):
            source._get_json("exchangeInfo")

    def test_bounded_source_never_exceeds_remaining_deadline(self):
        import binansScanner.providers.binance_opportunity_source as source_module

        observed = {}

        class Response:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self):
                return b"{}"

        def fake_urlopen(request, timeout):
            observed["timeout"] = timeout
            return Response()

        source = runner._BoundedBinanceSpotOpportunitySource(deadline=time.monotonic() + 0.5)
        with patch.object(source_module, "urlopen", fake_urlopen):
            source._get_json("exchangeInfo")
        self.assertGreater(observed["timeout"], 0)
        self.assertLessEqual(observed["timeout"], 0.5)

    def test_discovery_exception_writes_startup_failure(self):
        with TemporaryDirectory() as tmp:
            config = self._config(Path(tmp) / "run")
            with patch.object(runner._legacy, "ScalpingOpportunityPipeline", _FailingPipeline):
                with self.assertRaises(RuntimeError):
                    runner.Paper8HRunner.create(config)
            lines = [json.loads(line) for line in (Path(tmp) / "run" / "events.jsonl").read_text(encoding="utf-8").splitlines()]
            failure = lines[-1]
            self.assertEqual(failure["event_type"], "startup_failure")
            self.assertEqual(failure["startup_phase"], "failed")
            self.assertEqual(failure["failure_kind"], "discovery_exception")

    def test_deadline_timeout_writes_startup_failure(self):
        with TemporaryDirectory() as tmp:
            config = self._config(Path(tmp) / "run")
            with patch.object(runner, "STARTUP_DISCOVERY_TIMEOUT_SECONDS", 0.0):
                with patch.object(runner._legacy, "ScalpingOpportunityPipeline", _FakePipeline):
                    with self.assertRaises(TimeoutError):
                        runner.Paper8HRunner.create(config)
            lines = [json.loads(line) for line in (Path(tmp) / "run" / "events.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(lines[-1]["failure_kind"], "discovery_timeout")

    def test_successful_discovery_records_runtime_phases(self):
        with TemporaryDirectory() as tmp:
            config = self._config(Path(tmp) / "run")
            with patch.object(runner._legacy, "ScalpingOpportunityPipeline", _FakePipeline):
                with patch.object(runner._legacy.Paper8HRunner, "__post_init__", lambda self: None):
                    result = runner.Paper8HRunner.create(config)
            lines = [json.loads(line) for line in (Path(tmp) / "run" / "events.jsonl").read_text(encoding="utf-8").splitlines()]
            phases = [line.get("startup_phase") for line in lines if line["event_type"] == "startup_phase"]
            self.assertEqual(phases, ["market_discovery", "runtime_initialization", "running"])
            self.assertEqual(result.config.output_dir, Path(tmp) / "run")

    def test_failed_discovery_does_not_initialize_stream_runtime(self):
        with TemporaryDirectory() as tmp:
            config = self._config(Path(tmp) / "run")
            with patch.object(runner._legacy, "ScalpingOpportunityPipeline", _FailingPipeline), patch.object(runner._legacy, "PaperRealtimeLifecycle") as lifecycle:
                with self.assertRaises(RuntimeError):
                    runner.Paper8HRunner.create(config)
            lifecycle.assert_not_called()

    def test_startup_failure_directory_is_retained(self):
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "failed-run"
            config = self._config(output)
            with patch.object(runner._legacy, "ScalpingOpportunityPipeline", _FailingPipeline):
                with self.assertRaises(RuntimeError):
                    runner.Paper8HRunner.create(config)
            self.assertTrue(output.is_dir())
            self.assertTrue((output / "events.jsonl").is_file())


if __name__ == "__main__":
    unittest.main()
