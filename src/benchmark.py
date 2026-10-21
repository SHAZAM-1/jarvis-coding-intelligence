"""Deterministic, low-volume coding smoke checks for an Ollama client.

Importing this module performs no network requests. Calling run_benchmark()
does perform inference, one bounded request per task, through the supplied
client. Results are smoke-test signals, not a statistically valid accuracy
benchmark and not proof that generated code works.
"""

import argparse
import ast
import json
import sys
from dataclasses import dataclass
from time import perf_counter

from src.model_client import DEFAULT_MODEL, OllamaClient


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


def _remove_code_fence(response):
    """Remove one conventional outer Markdown code fence, if present."""
    lines = response.strip().splitlines()
    if len(lines) >= 2 and lines[0].strip().startswith("```") and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return response.strip()


def _ast_issues(response, task_id):
    """Check expected syntax structure without executing generated Python."""
    source = _remove_code_fence(response)
    try:
        tree = ast.parse(source, mode="exec")
    except (SyntaxError, ValueError, TypeError):
        return ["response is not valid Python syntax"]

    if task_id == "python_add_function":
        if len(tree.body) != 1 or not isinstance(tree.body[0], (ast.FunctionDef, ast.AsyncFunctionDef)):
            return ["expected exactly one function definition"]
        function = tree.body[0]
        if isinstance(function, ast.AsyncFunctionDef) or function.name != "add":
            return ["expected a synchronous function named add"]
        args = [arg.arg for arg in function.args.args]
        if (
            args != ["a", "b"]
            or function.args.posonlyargs
            or function.args.vararg
            or function.args.kwonlyargs
            or function.args.kwarg
            or function.args.defaults
            or any(default is not None for default in function.args.kw_defaults)
            or function.decorator_list
        ):
            return ["expected exactly two plain parameters: a and b"]
        if len(function.body) != 1 or not isinstance(function.body[0], ast.Return):
            return ["expected one direct return statement"]
        value = function.body[0].value
        valid_return = (
            isinstance(value, ast.BinOp)
            and isinstance(value.op, ast.Add)
            and isinstance(value.left, ast.Name)
            and value.left.id == "a"
            and isinstance(value.right, ast.Name)
            and value.right.id == "b"
        )
        return [] if valid_return else ["expected a return expression adding a and b"]

    if task_id == "python_safe_dict_lookup":
        if len(tree.body) != 1 or not isinstance(tree.body[0], ast.Expr):
            return ["expected exactly one expression"]
        expression = tree.body[0].value
        if not (
            isinstance(expression, ast.Call)
            and isinstance(expression.func, ast.Attribute)
            and isinstance(expression.func.value, ast.Name)
            and expression.func.value.id == "data"
            and expression.func.attr == "get"
            and len(expression.args) in (1, 2)
            and isinstance(expression.args[0], ast.Constant)
            and expression.args[0].value == "name"
            and not expression.keywords
        ):
            return ["expected data.get('name') with an optional default"]
        if len(expression.args) == 2 and not (
            isinstance(expression.args[1], ast.Constant)
            and expression.args[1].value is None
        ):
            return ["the optional default must be None"]
        return []

    if task_id == "python_list_comprehension":
        if len(tree.body) != 1 or not isinstance(tree.body[0], ast.Expr):
            return ["expected exactly one expression"]
        expression = tree.body[0].value
        if not isinstance(expression, ast.ListComp) or len(expression.generators) != 1:
            return ["expected a list comprehension with one generator"]
        generator = expression.generators[0]
        if not (
            isinstance(generator.target, ast.Name)
            and isinstance(generator.iter, ast.Name)
            and generator.iter.id == "numbers"
            and not generator.ifs
            and not generator.is_async
            and isinstance(expression.elt, ast.BinOp)
            and isinstance(expression.elt.op, ast.Pow)
            and isinstance(expression.elt.left, ast.Name)
            and expression.elt.left.id == generator.target.id
            and isinstance(expression.elt.right, ast.Constant)
            and expression.elt.right.value == 2
        ):
            return ["expected to square each item from numbers"]
        return []

    return None


def evaluate_response(response, task):
    """Check expected AST shape for built-in tasks; never execute model code."""
    if not isinstance(response, str):
        raise TypeError("Model response must be a string.")

    issues = _ast_issues(response, task.task_id)
    if issues is not None:
        return {
            "passed": not issues,
            "validation_method": "python_ast_structure",
            "required_markers": list(task.required_markers),
            "missing_markers": [],
            "issues": issues,
        }

    lowered = response.casefold()
    missing = [
        marker for marker in task.required_markers
        if marker.casefold() not in lowered
    ]
    return {
        "passed": not missing,
        "validation_method": "required_markers",
        "required_markers": list(task.required_markers),
        "missing_markers": missing,
        "issues": [],
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
                "validation_method": "error",
                "required_markers": list(task.required_markers),
                "missing_markers": list(task.required_markers),
                "issues": [],
                "response_chars": None,
                "error_type": type(exc).__name__,
            })
        results[-1]["elapsed_ms"] = round(
            (perf_counter() - started) * 1000, 2
        )

    passed = sum(result["passed"] for result in results)
    return {
        "benchmark_type": "deterministic_coding_smoke_checks",
        "model": getattr(client, "model", None),
        "tasks_total": len(results),
        "tasks_passed": passed,
        "tasks_failed": len(results) - passed,
        "score_percent": round(100 * passed / len(results), 2) if results else 0.0,
        "results": results,
        "limitations": [
            "AST checks validate syntax shape, not runtime behavior or full semantics.",
            "Generated code is parsed but never executed.",
            "No unit tests, security checks, or behavioral equivalence checks run.",
            "A single run is not a statistically valid model accuracy comparison.",
        ],
    }


def main(argv=None):
    """Run only when the user explicitly supplies --run; never download models."""
    parser = argparse.ArgumentParser(
        description="Run three small coding smoke checks against local Ollama."
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="explicitly allow three local inference requests",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="already-installed Ollama model name (no model is downloaded)",
    )
    args = parser.parse_args(argv)

    if not args.run:
        parser.print_help()
        print(
            "\nNo inference was run. Re-run with --run only when enough RAM "
            "is available.",
            file=sys.stderr,
        )
        return 2

    try:
        client = OllamaClient(model=args.model)
    except (TypeError, ValueError) as exc:
        print(f"Invalid benchmark configuration: {type(exc).__name__}", file=sys.stderr)
        return 2

    report = run_benchmark(client)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["tasks_passed"] == report["tasks_total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
