"""Lightweight Inspect AI (UKGovernmentBEIS/inspect_ai) execution & log contract.

Mirrors the core composable architecture of Inspect AI without external
dependencies:
1. ``Task(dataset, solver, scorer, sandbox)`` decomposition.
2. Expected vs. Unexpected error boundary inside ``Sandbox`` tools:
   - ``ExpectedToolError`` (e.g. non-zero shell exit, missing file, bad tool
     arguments) is fed back into the agent's message stream so the model can
     self-correct.
   - ``UnexpectedSandboxError`` (e.g. container crash, unreachable daemon,
     network drop) is NOT fed to the model and marks the sample ``error``
     (excluded from model failure via ``SuiteOutcome``).
3. ``EvalLog`` bridge to ``evals.metrics.reliability.SuiteOutcome`` and
   ``evals.prefix_regression.locator.TrajectoryStep``.
"""

from __future__ import annotations

import json
import shlex
import subprocess
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import TracebackType
from typing import Any, Self

from evals.metrics.reliability import SuiteOutcome
from evals.prefix_regression.locator import TrajectoryStep


class ExpectedToolError(RuntimeError):
    """Tool-level error reported back to the model for recovery."""


class UnexpectedSandboxError(RuntimeError):
    """Infrastructure/sandbox failure that aborts the sample as ``error``."""


@dataclass(frozen=True)
class SandboxExecResult:
    """Result of executing a command inside a sandbox environment."""

    success: bool
    returncode: int
    stdout: str
    stderr: str


class LocalTempSandbox:
    """Minimal isolated temporary-directory sandbox for offline demos/tests.

    Uses ``tempfile.TemporaryDirectory`` per sample so tool mutations never
    leak across samples or into the repository working tree.
    """

    def __init__(self, files: dict[str, str] | None = None, *, broken_infra: bool = False) -> None:
        self._files = dict(files or {})
        self._broken_infra = broken_infra
        self._tmpdir: tempfile.TemporaryDirectory[str] | None = None
        self.root: Path | None = None

    def __enter__(self) -> Self:
        if self._broken_infra:
            raise UnexpectedSandboxError("Sandbox container failed to start (simulated infra failure)")
        self._tmpdir = tempfile.TemporaryDirectory(prefix="inspect_sandbox_")
        self.root = Path(self._tmpdir.name)
        for rel_path, content in self._files.items():
            target = self._safe_resolve(rel_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._tmpdir is not None:
            self._tmpdir.cleanup()
            self._tmpdir = None
            self.root = None

    def _safe_resolve(self, rel_path: str) -> Path:
        if self.root is None:
            raise UnexpectedSandboxError("Sandbox is not active")
        candidate = (self.root / rel_path).resolve()
        root_resolved = self.root.resolve()
        if candidate != root_resolved and root_resolved not in candidate.parents:
            raise ExpectedToolError(f"Path escapes sandbox root: {rel_path}")
        return candidate

    def read_file(self, rel_path: str) -> str:
        target = self._safe_resolve(rel_path)
        if not target.exists():
            raise ExpectedToolError(f"File not found: {rel_path}")
        return target.read_text(encoding="utf-8")

    def write_file(self, rel_path: str, content: str) -> str:
        target = self._safe_resolve(rel_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} bytes to {rel_path}"

    def exec(self, cmd: Sequence[str], *, timeout_sec: float = 10.0) -> SandboxExecResult:
        if self.root is None:
            raise UnexpectedSandboxError("Sandbox is not active")
        try:
            proc = subprocess.run(
                list(cmd),
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                check=False,
            )
        except OSError as exc:
            raise UnexpectedSandboxError(f"Sandbox exec failed at OS layer: {exc}") from exc
        except subprocess.TimeoutExpired as exc:
            raise ExpectedToolError(f"Command timed out after {timeout_sec}s: {shlex.join(cmd)}") from exc
        return SandboxExecResult(
            success=proc.returncode == 0,
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )


@dataclass(frozen=True)
class ToolDef:
    """Declarative tool registered with a Solver."""

    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[[dict[str, Any], LocalTempSandbox], str]

    def to_openai_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass(frozen=True)
class Sample:
    """Single labeled Inspect evaluation sample."""

    sample_id: str
    input: str
    target: str = ""
    files: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskState:
    """Mutable state passed through Inspect Solvers."""

    sample: Sample
    messages: list[dict[str, Any]]
    output_text: str = ""
    completed: bool = False
    turns: int = 0
    tool_events: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Score:
    """Scorer verdict for one sample."""

    value: float
    answer: str
    explanation: str = ""
    passed: bool = False


ModelGenerateFn = Callable[[list[dict[str, Any]], list[dict[str, Any]]], dict[str, Any]]
SolverFn = Callable[[TaskState, LocalTempSandbox, ModelGenerateFn], TaskState]
ScorerFn = Callable[[TaskState, LocalTempSandbox], Score]


@dataclass(frozen=True)
class Task:
    """Composable Inspect Task uniting dataset, solver, scorer, and sandbox."""

    name: str
    dataset: Sequence[Sample]
    solver: SolverFn
    scorer: ScorerFn
    sandbox_type: str = "local_temp"
    broken_sandbox: bool = False


@dataclass(frozen=True)
class SampleLog:
    """Per-sample execution record in an EvalLog."""

    sample_id: str
    status: str  # "passed" | "failed" | "error"
    score: Score | None
    turns: int
    messages: list[dict[str, Any]]
    tool_events: list[dict[str, Any]]
    error: str = ""


@dataclass(frozen=True)
class EvalLog:
    """Task-level log analogous to Inspect's EvalLog."""

    task_name: str
    model: str
    sandbox_type: str
    samples: list[SampleLog]

    @property
    def passed(self) -> int:
        return sum(1 for s in self.samples if s.status == "passed")

    @property
    def failed(self) -> int:
        return sum(1 for s in self.samples if s.status == "failed")

    @property
    def errors(self) -> int:
        return sum(1 for s in self.samples if s.status == "error")

    @property
    def accuracy(self) -> float | None:
        scored = self.passed + self.failed
        if scored == 0:
            return None
        return round(self.passed / scored, 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_name": self.task_name,
            "model": self.model,
            "sandbox_type": self.sandbox_type,
            "summary": {
                "total": len(self.samples),
                "passed": self.passed,
                "failed": self.failed,
                "errors": self.errors,
                "accuracy": self.accuracy,
            },
            "samples": [
                {
                    "sample_id": s.sample_id,
                    "status": s.status,
                    "turns": s.turns,
                    "error": s.error,
                    "score": None
                    if s.score is None
                    else {
                        "value": s.score.value,
                        "passed": s.score.passed,
                        "answer": s.score.answer,
                        "explanation": s.score.explanation,
                    },
                    "tool_events": s.tool_events,
                }
                for s in self.samples
            ],
        }


def react_solver(
    *,
    prompt: str,
    tools: Sequence[ToolDef],
    max_turns: int = 8,
) -> SolverFn:
    """Build a ReAct tool-use Solver with Inspect-style error isolation."""
    tool_map = {t.name: t for t in tools}
    tool_schemas = [t.to_openai_tool() for t in tools]

    def _solve(
        state: TaskState,
        sandbox: LocalTempSandbox,
        generate_fn: ModelGenerateFn,
    ) -> TaskState:
        if prompt:
            state.messages.insert(0, {"role": "system", "content": prompt})

        for _ in range(max_turns):
            state.turns += 1
            response = generate_fn(state.messages, tool_schemas)
            choices = response.get("choices") or []
            if not choices:
                raise UnexpectedSandboxError("Model returned empty choices")
            msg = choices[0].get("message") or {}
            content = msg.get("content") or ""
            tool_calls = msg.get("tool_calls") or []
            assistant_entry: dict[str, Any] = {"role": "assistant", "content": content}
            if tool_calls:
                assistant_entry["tool_calls"] = tool_calls
            state.messages.append(assistant_entry)

            if not tool_calls:
                state.output_text = str(content)
                state.completed = True
                return state

            for idx, tc in enumerate(tool_calls):
                tc_id = str(tc.get("id") or f"call_{state.turns}_{idx}")
                fn = tc.get("function") or {}
                fn_name = str(fn.get("name") or "")
                raw_args = fn.get("arguments") or "{}"
                try:
                    parsed_args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
                except (json.JSONDecodeError, TypeError) as exc:
                    tool_output = f"ToolError: invalid JSON arguments: {exc}"
                    is_expected_err = True
                else:
                    tool_def = tool_map.get(fn_name)
                    if tool_def is None:
                        tool_output = f"ToolError: unknown tool '{fn_name}'"
                        is_expected_err = True
                    else:
                        try:
                            tool_output = tool_def.handler(parsed_args, sandbox)
                            is_expected_err = False
                        except ExpectedToolError as exc:
                            tool_output = f"ToolError: {exc}"
                            is_expected_err = True

                state.tool_events.append(
                    {
                        "turn": state.turns,
                        "tool": fn_name,
                        "expected_error": is_expected_err,
                        "output_preview": tool_output[:200],
                    }
                )
                state.messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "name": fn_name,
                        "content": tool_output,
                    }
                )

        state.output_text = str(state.messages[-1].get("content", ""))
        state.completed = False
        return state

    return _solve


def includes_scorer(*, ignore_case: bool = True) -> ScorerFn:
    """Scorer passing when ``sample.target`` appears in ``state.output_text``."""

    def _score(state: TaskState, _sandbox: LocalTempSandbox) -> Score:
        target = state.sample.target
        output = state.output_text
        haystack = output.lower() if ignore_case else output
        needle = target.lower() if ignore_case else target
        ok = needle in haystack
        return Score(
            value=1.0 if ok else 0.0,
            answer=output,
            explanation=f"Expected substring '{target}' {'found' if ok else 'missing'}",
            passed=ok,
        )

    return _score


def exact_scorer(*, strip: bool = True) -> ScorerFn:
    """Scorer passing when ``state.output_text`` equals ``sample.target``."""

    def _score(state: TaskState, _sandbox: LocalTempSandbox) -> Score:
        out = state.output_text.strip() if strip else state.output_text
        tgt = state.sample.target.strip() if strip else state.sample.target
        ok = out == tgt
        return Score(
            value=1.0 if ok else 0.0,
            answer=out,
            explanation=f"Exact match={'yes' if ok else 'no'} (expected '{tgt}')",
            passed=ok,
        )

    return _score


def run_inspect_task(
    task: Task,
    *,
    model: str,
    generate_fn: ModelGenerateFn,
) -> EvalLog:
    """Execute an Inspect-style ``Task`` across all samples with sandbox isolation."""
    logs: list[SampleLog] = []
    for sample in task.dataset:
        state = TaskState(
            sample=sample,
            messages=[{"role": "user", "content": sample.input}],
        )
        try:
            with LocalTempSandbox(sample.files, broken_infra=task.broken_sandbox) as sb:
                final_state = task.solver(state, sb, generate_fn)
                score = task.scorer(final_state, sb)
            logs.append(
                SampleLog(
                    sample_id=sample.sample_id,
                    status="passed" if score.passed else "failed",
                    score=score,
                    turns=final_state.turns,
                    messages=final_state.messages,
                    tool_events=final_state.tool_events,
                )
            )
        except UnexpectedSandboxError as exc:
            logs.append(
                SampleLog(
                    sample_id=sample.sample_id,
                    status="error",
                    score=None,
                    turns=state.turns,
                    messages=state.messages,
                    tool_events=state.tool_events,
                    error=str(exc),
                )
            )
    return EvalLog(
        task_name=task.name,
        model=model,
        sandbox_type=task.sandbox_type,
        samples=logs,
    )


def eval_log_to_suite_outcome(
    log: EvalLog,
    *,
    non_canonical_reasons: tuple[str, ...] = (),
) -> SuiteOutcome:
    """Convert an ``EvalLog`` into ``evals.metrics.reliability.SuiteOutcome``."""
    total = len(log.samples)
    infra_blocked = total > 0 and log.errors == total
    return SuiteOutcome(
        suite_id=f"inspect:{log.task_name}",
        passed=log.passed,
        failed=log.failed,
        errors=log.errors,
        infra_required=infra_blocked,
        infra_reason="All Inspect samples failed due to sandbox/infra error" if infra_blocked else "",
        non_canonical_reasons=non_canonical_reasons,
    )


def eval_log_to_trajectory_steps(
    sample_log: SampleLog,
    *,
    fault_classifier: Callable[[int, dict[str, Any]], tuple[bool, str, str]] | None = None,
) -> list[TrajectoryStep]:
    """Convert an Inspect ``SampleLog`` message trace into ``TrajectoryStep``s."""
    steps: list[TrajectoryStep] = []
    for idx, msg in enumerate(sample_log.messages, start=1):
        role = str(msg.get("role", "assistant"))
        if role == "system":
            continue
        if role == "assistant" and msg.get("tool_calls"):
            calls = [
                f"{tc.get('function', {}).get('name', '?')}({tc.get('function', {}).get('arguments', '')})"
                for tc in msg["tool_calls"]
            ]
            action = "; ".join(calls)
            observation = str(msg.get("content") or "")
        elif role == "tool":
            action = str(msg.get("name") or "tool")
            observation = str(msg.get("content") or "")
        else:
            action = str(msg.get("content") or "")
            observation = ""

        is_valid: bool | None = None
        fault_layer = ""
        reason = ""
        if fault_classifier is not None:
            is_valid, fault_layer, reason = fault_classifier(idx, msg)

        steps.append(
            TrajectoryStep(
                step_index=len(steps) + 1,
                role=role,
                action=action,
                observation=observation,
                is_valid=is_valid,
                fault_layer=fault_layer,
                reason=reason,
            )
        )
    return steps
