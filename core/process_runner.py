"""Controlled subprocess execution with live output streaming.

Always invokes argument lists (never a shell string built from untrusted
input). Streams stdout/stderr line-by-line into a queue so a background
thread can run a long build while the UI thread stays responsive.
"""
from __future__ import annotations

import queue
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class OutputLine:
    stream: str  # "stdout" or "stderr"
    text: str


@dataclass(frozen=True)
class ProcessFinished:
    exit_code: int | None
    cancelled: bool


class ProcessRunner:
    """Runs one external process, streaming output into `output_queue`.

    Usage:
        runner = ProcessRunner()
        runner.start(["python", "-m", "PyInstaller", ...], cwd=project_dir)
        while True:
            item = runner.output_queue.get()
            if isinstance(item, ProcessFinished):
                break
            # item is an OutputLine
    """

    def __init__(self) -> None:
        self.output_queue: "queue.Queue[OutputLine | ProcessFinished]" = queue.Queue()
        self._process: subprocess.Popen | None = None
        self._cancelled = False
        self._thread: threading.Thread | None = None

    def start(self, args: list[str], cwd: Path, env: dict[str, str] | None = None) -> None:
        if self._process is not None:
            raise RuntimeError("ProcessRunner instance is already running a process.")

        self._cancelled = False
        self._process = subprocess.Popen(
            args,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            encoding="utf-8",
            errors="replace",
            env=env,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP") else 0,
        )
        self._thread = threading.Thread(target=self._pump, daemon=True)
        self._thread.start()

    def _pump(self) -> None:
        assert self._process is not None
        proc = self._process

        stdout_thread = threading.Thread(target=self._pump_stream, args=(proc.stdout, "stdout"), daemon=True)
        stderr_thread = threading.Thread(target=self._pump_stream, args=(proc.stderr, "stderr"), daemon=True)
        stdout_thread.start()
        stderr_thread.start()
        stdout_thread.join()
        stderr_thread.join()

        exit_code = proc.wait()
        self.output_queue.put(ProcessFinished(exit_code=exit_code, cancelled=self._cancelled))

    def _pump_stream(self, stream, name: str) -> None:
        if stream is None:
            return
        try:
            for line in iter(stream.readline, ""):
                if line == "":
                    break
                self.output_queue.put(OutputLine(stream=name, text=line.rstrip("\n")))
        finally:
            stream.close()

    def cancel(self) -> None:
        if self._process is None or self._process.poll() is not None:
            return
        self._cancelled = True
        try:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
        except OSError:
            pass

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def reset(self) -> None:
        """Allow this runner instance to be reused for a new process."""
        self._process = None
        self._thread = None
