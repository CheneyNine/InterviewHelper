"""Durable in-process answer queue with one worker per available GPU (maximum four)."""

from __future__ import annotations

import asyncio
import os
import subprocess
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Optional

from .database import list_recoverable_analysis_jobs, update_job


AnalysisRunner = Callable[[str, str, Optional[str]], Awaitable[None]]


def _configured_gpu_ids(value: str) -> list[str]:
    source = value or os.getenv("CUDA_VISIBLE_DEVICES", "").strip()
    if source in {"", "-1"}:
        return []
    return [item.strip() for item in source.split(",") if item.strip()][:4]


def detect_idle_gpu_ids(configured: str = "") -> list[str]:
    """Return up to four usable GPUs.

    Explicit ``VLM_GPU_IDS``/``CUDA_VISIBLE_DEVICES`` values are authoritative.
    Otherwise GPUs with at least 80% free memory are considered idle.
    """

    selected = _configured_gpu_ids(configured)
    if selected:
        return selected
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,memory.free,memory.total",
                "--format=csv,noheader,nounits",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return []
    idle: list[str] = []
    for line in result.stdout.splitlines():
        try:
            gpu_id, free, total = (part.strip() for part in line.split(","))
            if float(total) > 0 and float(free) / float(total) >= 0.8:
                idle.append(gpu_id)
        except (TypeError, ValueError):
            continue
        if len(idle) == 4:
            break
    return idle


class PersistentAnalysisQueue:
    def __init__(
        self,
        database_path: Path,
        runner: AnalysisRunner,
        configured_gpu_ids: str = "",
    ) -> None:
        self.database_path = database_path
        self.runner = runner
        detected = detect_idle_gpu_ids(configured_gpu_ids)
        # A GPU-less Core API can still dispatch one job to a remote VLM server.
        self.gpu_ids: list[str | None] = detected or [None]
        self.queue: Optional[asyncio.Queue[tuple[str, str]]] = None
        self.workers: list[asyncio.Task[None]] = []
        self.enqueued: set[str] = set()

    async def start(self) -> None:
        self.queue = asyncio.Queue()
        for gpu_id in self.gpu_ids:
            self.workers.append(asyncio.create_task(self._worker(gpu_id)))
        for job in list_recoverable_analysis_jobs(self.database_path):
            update_job(job["id"], "QUEUED", 0.0, self.database_path)
            await self.submit(job["resource_id"], job["id"])

    async def stop(self) -> None:
        for worker in self.workers:
            worker.cancel()
        await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers.clear()

    async def submit(self, answer_id: str, job_id: str) -> None:
        if self.queue is None:
            raise RuntimeError("Analysis queue has not been started.")
        if job_id in self.enqueued:
            return
        self.enqueued.add(job_id)
        await self.queue.put((answer_id, job_id))

    async def _worker(self, gpu_id: str | None) -> None:
        if self.queue is None:
            return
        while True:
            answer_id, job_id = await self.queue.get()
            try:
                await self.runner(answer_id, job_id, gpu_id)
            finally:
                self.enqueued.discard(job_id)
                self.queue.task_done()
