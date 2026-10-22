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

    def test_evaluator_reports_missing_markers_for_custom_tasks(self):
        task = BenchmarkTask("example", "prompt", ("def ", "return"))
        result = evaluate_response("not code", task)
        self.assertFalse(result["passed"])
        self.assertEqual(result["missing_markers"], ["def ", "return"])
        self.assertEqual(result["validation_method"], "required_markers")

    def test_evaluator_accepts_custom_markers_case_insensitively(self):
        task = BenchmarkTask("example", "prompt", ("DEF ", "RETURN"))
        result = evaluate_response("def add(a, b): return a + b", task)
        self.assertTrue(result["passed"])
        self.assertEqual(result["missing_markers"], [])

    def test_ast_validation_rejects_wrong_addition_even_when_markers_exist(self):
        result = evaluate_response(
            "def add(a, b):\n    return a - b",
            BENCHMARK_TASKS[0],
        )
        self.assertFalse(result["passed"])
        self.assertEqual(result["validation_method"], "python_ast_structure")
        self.assertIn("expected a return expression adding a and b", result["issues"])

    def test_ast_validation_rejects_required_keyword_only_argument(self):
        result = evaluate_response(
            "def add(a, b, *, extra):\n    return a + b",
            BENCHMARK_TASKS[0],
        )
        self.assertFalse(result["passed"])
        self.assertIn("expected exactly two plain parameters: a and b", result["issues"])

    def test_ast_validation_rejects_nested_return_only(self):
        result = evaluate_response(
            "def add(a, b):\n    def nested():\n        return a + b\n    return 0",
            BENCHMARK_TASKS[0],
        )
        self.assertFalse(result["passed"])
        self.assertIn("expected one direct return statement", result["issues"])

    def test_ast_validation_rejects_filtered_comprehension(self):
        result = evaluate_response(
            "[number ** 2 for number in numbers if number > 0]",
            BENCHMARK_TASKS[2],
        )
        self.assertFalse(result["passed"])
        self.assertIn("expected to square each item from numbers", result["issues"])

    def test_ast_validation_accepts_fenced_valid_function(self):
        result = evaluate_response(
            "```python\ndef add(a, b):\n    return a + b\n```",
            BENCHMARK_TASKS[0],
        )
        self.assertTrue(result["passed"])
        self.assertEqual(result["issues"], [])

    def test_ast_validation_rejects_wrong_dictionary_default(self):
        result = evaluate_response(
            "data.get('name', 'unknown')",
            BENCHMARK_TASKS[1],
        )
        self.assertFalse(result["passed"])
        self.assertIn("the optional default must be None", result["issues"])

    def test_is_even_ast_validation_accepts_correct_logic(self):
        result = evaluate_response(
            "def is_even(n):\n    return n % 2 == 0",
            next(task for task in BENCHMARK_TASKS if task.task_id == "python_is_even"),
        )
        self.assertTrue(result["passed"], result["issues"])

    def test_is_even_ast_validation_rejects_wrong_logic(self):
        result = evaluate_response(
            "def is_even(n):\n    return n % 2 == 1",
            next(task for task in BENCHMARK_TASKS if task.task_id == "python_is_even"),
        )
        self.assertFalse(result["passed"])
        self.assertIn("expected n % 2 == 0", result["issues"])

    def test_safe_divide_ast_validation_accepts_zero_guard_and_division(self):
        result = evaluate_response(
            "def safe_divide(a, b):\n    if b == 0:\n        return None\n    else:\n        return a / b",
            next(task for task in BENCHMARK_TASKS if task.task_id == "python_safe_divide"),
        )
        self.assertTrue(result["passed"], result["issues"])

    def test_safe_divide_ast_validation_rejects_missing_zero_guard(self):
        result = evaluate_response(
            "def safe_divide(a, b):\n    return a / b",
            next(task for task in BENCHMARK_TASKS if task.task_id == "python_safe_divide"),
        )
        self.assertFalse(result["passed"])
        self.assertIn("expected one if statement with explicit else branch", result["issues"])

    def test_ast_validation_rejects_wrong_comprehension(self):
        result = evaluate_response(
            "[number + 2 for number in numbers]",
            BENCHMARK_TASKS[2],
        )
        self.assertFalse(result["passed"])
        self.assertIn("expected to square each item from numbers", result["issues"])

    def test_ast_validation_rejects_invalid_python(self):
        result = evaluate_response(
            "def add(a, b) return a + b",
            BENCHMARK_TASKS[0],
        )
        self.assertFalse(result["passed"])
        self.assertEqual(result["issues"], ["response is not valid Python syntax"])

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
