"""Offline tests for the deterministic coding smoke benchmark."""

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import Mock, patch

from src.benchmark import (
    BENCHMARK_TASKS,
    BenchmarkTask,
    evaluate_response,
    main,
    run_benchmark,
)


class BenchmarkTests(unittest.TestCase):
    def test_imported_tasks_are_fixed_and_have_unique_ids(self):
        ids = [task.task_id for task in BENCHMARK_TASKS]
        self.assertTrue(ids)
        self.assertEqual(len(ids), len(set(ids)))

    def test_evaluator_reports_missing_markers(self):
        task = BenchmarkTask("example", "prompt", ("def ", "return"))
        result = evaluate_response("not code", task)
        self.assertFalse(result["passed"])
        self.assertEqual(result["missing_markers"], ["def ", "return"])

    def test_evaluator_accepts_all_required_markers_case_insensitively(self):
        task = BenchmarkTask("example", "prompt", ("DEF ", "RETURN"))
        result = evaluate_response("def add(a, b): return a + b", task)
        self.assertTrue(result["passed"])
        self.assertEqual(result["missing_markers"], [])

    def test_evaluator_rejects_non_string_response(self):
        with self.assertRaises(TypeError):
            evaluate_response(None, BENCHMARK_TASKS[0])

    def test_runner_uses_fast_profile_and_returns_summary(self):
        client = Mock()
        client.generate.side_effect = [
            "def add(a, b): return a + b",
            "data.get('name')",
        ]
        tasks = BENCHMARK_TASKS[:2]
        result = run_benchmark(client, tasks)
        self.assertEqual(result["tasks_total"], 2)
        self.assertEqual(result["tasks_passed"], 2)
        self.assertEqual(result["tasks_failed"], 0)
        self.assertEqual(result["score_percent"], 100.0)
        self.assertEqual(client.generate.call_count, 2)
        self.assertTrue(all(
            call.kwargs["profile"] == "fast"
            for call in client.generate.call_args_list
        ))

    def test_runner_continues_after_a_task_error(self):
        client = Mock()
        client.generate.side_effect = [
            RuntimeError("private machine details should not be retained"),
            "data.get('name')",
        ]
        result = run_benchmark(client, BENCHMARK_TASKS[:2])
        self.assertEqual(result["tasks_failed"], 1)
        self.assertEqual(result["results"][0]["error_type"], "RuntimeError")
        self.assertNotIn("private machine details", str(result))
        self.assertTrue(result["results"][1]["passed"])

    def test_cli_without_run_flag_performs_no_inference(self):
        output = io.StringIO()
        errors = io.StringIO()
        with patch("src.benchmark.OllamaClient") as client_factory:
            with redirect_stdout(output), redirect_stderr(errors):
                status = main(["--model", "already-installed-model"])
        self.assertEqual(status, 2)
        client_factory.assert_not_called()
        self.assertIn("No inference was run", errors.getvalue())

    def test_empty_task_set_returns_zero_score(self):
        result = run_benchmark(Mock(), ())
        self.assertEqual(result["tasks_total"], 0)
        self.assertEqual(result["score_percent"], 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
