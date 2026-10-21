"""Deterministic, low-volume coding smoke checks for an Ollama client.

Importing this module performs no network requests. Calling run_benchmark()
does perform inference, one bounded request per task, through the supplied
client. Results are smoke-test signals, not a statistically valid accuracy
benchmark and not proof that generated code works.
"""

from dataclasses import dataclass
from time import perf_counter


@dataclass(frozen=True)
class BenchmarkTask:
    """One small, fixed prompt and its conservative response checks."""

    task_id: str
    prompt: str
    required_markers: tuple[str, ...]


BENCHMARK_TASKS = (
    BenchmarkTask(
        task_id="python_add_function",
        prompt=(
            "Write only a minimal Python function named add(a, b) that returns "
            "the sum of its two arguments. Include the function body."
        ),
        required_markers=("def add(", "return", "+"),
    ),
    BenchmarkTask(
        task_id="python_safe_dict_lookup",
        prompt=(
            "Write only one Python expression that safely reads key 'name' "
            "from dictionary variable data, returning None when absent."
        ),
        required_markers=("data", "name", ".get("),
    ),
    BenchmarkTask(
        task_id="python_list_comprehension",
        prompt=(
            "Write only a Python list comprehension that squares each number "
            "in list numbers."
        ),
        required_markers=("[", "for", "in numbers", "** 2"),
    ),
)


def evaluate_response(response, task):
    """Return transparent marker checks; do not execute model-generated code."""
    if not isinstance(response, str):
        raise TypeError("Model response must be a string.")
    lowered = response.casefold()
    missing = [
        marker for marker in task.required_markers
        if marker.casefold() not in lowered
    ]
    return {
        "passed": not missing,
        "required_markers": list(task.required_markers),
        "missing_markers": missing,
    }


def run_benchmark(client, tasks=BENCHMARK_TASKS):
    """Run fixed smoke tasks sequentially using the client's fast profile.

    Per-task exceptions are summarized by type only; exception messages may
    contain machine-specific details and are intentionally not retained.
    """
    results = []
    for task in tasks:
        started = perf_counter()
        try:
            response = client.generate(task.prompt, profile="fast")
            evaluation = evaluate_response(response, task)
            results.append({
                "task_id": task.task_id,
                **evaluation,
                "response_chars": len(response),
                "error_type": None,
            })
        except Exception as exc:
            results.append({
                "task_id": task.task_id,
                "passed": False,
                "required_markers": list(task.required_markers),
                "missing_markers": list(task.required_markers),
                "response_chars": None,
                "error_type": type(exc).__name__,
            })
        results[-1]["elapsed_ms"] = round(
            (perf_counter() - started) * 1000, 2
        )

    passed = sum(result["passed"] for result in results)
    return {
        "benchmark_type": "deterministic_coding_smoke_checks",
        "tasks_total": len(results),
        "tasks_passed": passed,
        "tasks_failed": len(results) - passed,
        "score_percent": round(100 * passed / len(results), 2) if results else 0.0,
        "results": results,
        "limitations": [
            "Marker checks are heuristic and can accept incorrect code.",
            "Generated code is not executed.",
            "No unit tests, security checks, or behavioral equivalence checks run.",
            "A single run is not a statistically valid model accuracy comparison.",
        ],
    }
