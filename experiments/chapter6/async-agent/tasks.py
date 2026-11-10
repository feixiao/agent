"""实验 6-2 的「真实、有界」异步终端任务管理。

安全设计：
  - 命令不经 shell 解析，且必须命中显式白名单（analyze_fast/mid/slow、
    analyze_logs、re_run_summary），实际统一解析为 analysis_worker.py 子进程；
  - 每个任务都是真实操作系统子进程（shell=False），stdout 里的 PROGRESS 行
    驱动进度条；取消 = 终止该 OS 进程；
  - 完成时返回由真实输入文件（book/chapter4.md）算出的指标，
    而不是伪造的结果字符串——这是「真实子进程收据」的根基。

TaskManager 提供 start / query / cancel / cancel_all / snapshot / restore，
支撑 demo.py 与 run_real_experiment.py 的全部场景。
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shlex
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Awaitable, Callable, Dict, Optional

HERE = Path(__file__).resolve().parent
WORKER = HERE / "analysis_worker.py"
DEFAULT_INPUT = HERE.parent.parent / "book" / "chapter4.md"


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = float(raw)
        if value <= 0:
            raise ValueError
        return value
    except ValueError:
        print(f"⚠️ 环境变量 {name}={raw!r} 非法（应为正数），使用默认值 {default}")
        return default


# One logical second maps to this many wall-clock seconds. The default retains
# the manuscript's 3/2/1-percent ratios while keeping the demo practical.
TICK_REAL = _env_float("FLUX_TICK_REAL", 0.4)

_COMMANDS = {
    "analyze_fast.py": ("fast", 3.0),
    "analyze_mid.py": ("mid", 2.0),
    "analyze_slow.py": ("slow", 1.0),
    "analyze_logs.py": ("logs", 4.5),
    "re_run_summary.py": ("recovery", 4.5),
}


def resolve_job(command: str) -> tuple[str, float]:
    """把展示用终端命令解析成一个安全的可执行画像（白名单校验）。

    只允许 `python <白名单脚本>.py` 两词形式；拒绝一切其它命令，
    返回 (worker 任务名, 每逻辑秒进度百分比)。
    """
    parts = shlex.split(command)
    if len(parts) != 2 or Path(parts[0]).name not in {"python", "python3", Path(sys.executable).name}:
        raise ValueError("only `python <approved-analysis-script>.py` commands are allowed")
    script = Path(parts[1]).name
    if script not in _COMMANDS:
        raise ValueError(f"unapproved experiment command: {script}")
    return _COMMANDS[script]


def resolve_rate(command: str) -> float:
    return resolve_job(command)[1]


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass
class TaskState:
    task_id: str
    command: str
    rate: float
    progress: float = 0.0
    status: str = "running"       # running | completed | cancelled | failed | suspended
    result: str = ""
    pid: int | None = None
    returncode: int | None = None
    started_at: float | None = None
    completed_at: float | None = None
    stdout_sha256: str | None = None
    stderr_tail: str = ""
    executable_receipt: dict = field(default_factory=dict)
    _task: Optional[asyncio.Task] = field(default=None, repr=False)
    _process: Optional[asyncio.subprocess.Process] = field(default=None, repr=False)


class TaskManager:
    """启动、观察、查询并终止「白名单内」的真实子进程任务。"""

    def __init__(self, on_complete: Callable[[TaskState], Awaitable[None]],
                 log: Callable[[str, str], None]):
        self._on_complete = on_complete
        self._log = log
        self._tasks: Dict[str, TaskState] = {}
        self._counter = 0

    def start(self, command: str) -> TaskState:
        job, rate = resolve_job(command)  # reject before allocating a task id
        if not WORKER.is_file() or not DEFAULT_INPUT.is_file():
            raise FileNotFoundError("analysis worker or Chapter 4 input is missing")
        self._counter += 1
        task_id = f"T{self._counter}"
        state = TaskState(task_id=task_id, command=command, rate=rate)
        state.executable_receipt = {
            "mode": "real_subprocess", "shell": False,
            "worker": str(WORKER), "worker_sha256": _hash_file(WORKER),
            "input": str(DEFAULT_INPUT), "input_sha256": _hash_file(DEFAULT_INPUT),
            "job": job, "rate_percent_per_logical_second": rate,
            "tick_real_seconds": TICK_REAL,
        }
        self._tasks[task_id] = state
        state._task = asyncio.create_task(self._run(state, job))
        self._log("TASK", f"启动真实子进程任务 {task_id}: `{command}` "
                          f"(速度 {rate:.0f}%/逻辑秒)")
        return state

    async def _terminate_process(self, state: TaskState) -> None:
        process = state._process
        if not process or process.returncode is not None:
            return
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=2)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
        state.returncode = process.returncode

    async def _run(self, state: TaskState, job: str) -> None:
        stdout_lines: list[str] = []
        state.started_at = time.time()
        argv = [
            sys.executable, "-I", "-u", str(WORKER),
            "--job", job, "--rate", str(state.rate),
            "--tick-real", str(TICK_REAL), "--input", str(DEFAULT_INPUT),
        ]
        state.executable_receipt["argv_sha256"] = hashlib.sha256(
            json.dumps(argv, separators=(",", ":")).encode()
        ).hexdigest()
        next_milestone = 20.0
        try:
            process = await asyncio.create_subprocess_exec(
                *argv, cwd=str(HERE),
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            state._process = process
            state.pid = process.pid
            state.executable_receipt["pid"] = process.pid
            assert process.stdout is not None
            while True:
                raw = await process.stdout.readline()
                if not raw:
                    break
                line = raw.decode("utf-8", errors="replace").rstrip()
                stdout_lines.append(line)
                if line.startswith("PROGRESS "):
                    try:
                        state.progress = max(
                            state.progress, min(100.0, float(line.split()[1]))
                        )
                    except (IndexError, ValueError):
                        raise RuntimeError(f"worker emitted invalid progress: {line!r}")
                    if state.progress >= next_milestone:
                        self._log("TASK", f"{state.task_id} `{state.command}` "
                                          f"进度 {state.progress:.0f}% (pid={state.pid})")
                        next_milestone += 20.0
                elif line.startswith("RESULT "):
                    payload = json.loads(line.removeprefix("RESULT "))
                    state.result = json.dumps(payload, ensure_ascii=False, sort_keys=True)
            assert process.stderr is not None
            stderr = (await process.stderr.read()).decode("utf-8", errors="replace")
            state.stderr_tail = stderr[-4000:]
            state.returncode = await process.wait()
            state.completed_at = time.time()
            stdout = "\n".join(stdout_lines) + ("\n" if stdout_lines else "")
            state.stdout_sha256 = hashlib.sha256(stdout.encode()).hexdigest()
            state.executable_receipt.update({
                "returncode": state.returncode,
                "stdout_sha256": state.stdout_sha256,
                "stdout_lines": len(stdout_lines),
                "stderr_sha256": hashlib.sha256(stderr.encode()).hexdigest(),
                "elapsed_seconds": round(state.completed_at - state.started_at, 3),
            })
            if state.returncode != 0:
                state.status = "failed"
                raise RuntimeError(
                    f"worker exited {state.returncode}: {state.stderr_tail[-500:]}"
                )
            if state.progress != 100.0 or not state.result:
                state.status = "failed"
                raise RuntimeError("worker completed without 100% progress and a RESULT receipt")
            state.status = "completed"
            self._log("TASK", f"{state.task_id} 完成 ✅ (pid={state.pid}, "
                              f"returncode={state.returncode})")
            await self._on_complete(state)
        except asyncio.CancelledError:
            await self._terminate_process(state)
            state.status = "cancelled"
            state.completed_at = time.time()
            state.executable_receipt.update({
                "returncode": state.returncode,
                "cancelled": True,
                "elapsed_seconds": round(state.completed_at - state.started_at, 3)
                                   if state.started_at else None,
            })
            self._log("TASK", f"{state.task_id} 子进程已终止 🛑 "
                              f"(pid={state.pid}, 进度 {state.progress:.0f}%)")
            raise
        except Exception as exc:
            await self._terminate_process(state)
            state.status = "failed"
            state.result = state.result or f"{type(exc).__name__}: {exc}"
            state.completed_at = time.time()
            self._log("TASK", f"{state.task_id} 失败 ❌: {exc}")

    def query(self, task_id: str) -> Optional[TaskState]:
        return self._tasks.get(task_id)

    def cancel(self, task_id: str) -> bool:
        state = self._tasks.get(task_id)
        if state and state.status == "running":
            if state._task:
                state._task.cancel()
            return True
        return False

    def cancel_all(self) -> list[str]:
        cancelled = []
        for task_id, state in self._tasks.items():
            if state.status == "running":
                if state._task:
                    state._task.cancel()
                cancelled.append(task_id)
        return cancelled

    def any_running(self) -> bool:
        return any(state.status == "running" for state in self._tasks.values())

    def all_states(self) -> list[TaskState]:
        return list(self._tasks.values())

    def snapshot(self) -> list[dict]:
        return [
            {"task_id": state.task_id, "command": state.command,
             "rate": state.rate, "progress": state.progress,
             "status": state.status, "result": state.result,
             "pid": state.pid, "returncode": state.returncode,
             "started_at": state.started_at, "completed_at": state.completed_at,
             "stdout_sha256": state.stdout_sha256,
             "executable_receipt": state.executable_receipt}
            for state in self._tasks.values()
        ]

    def restore(self, records: list[dict]) -> None:
        for record in records:
            status = "suspended" if record["status"] == "running" else record["status"]
            receipt = record.get("executable_receipt")
            state = TaskState(
                task_id=record["task_id"], command=record["command"],
                rate=record["rate"], progress=record["progress"], status=status,
                result=record.get("result") or "", pid=record.get("pid"),
                returncode=record.get("returncode"),
                started_at=record.get("started_at"), completed_at=record.get("completed_at"),
                stdout_sha256=record.get("stdout_sha256"),
                executable_receipt=receipt if isinstance(receipt, dict) else {},
            )
            self._tasks[state.task_id] = state
            try:
                self._counter = max(self._counter, int(state.task_id.lstrip("T") or 0))
            except ValueError:
                pass
