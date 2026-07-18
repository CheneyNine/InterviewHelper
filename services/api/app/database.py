"""SQLite persistence for interviews, media slices, jobs, analyses and reports."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


DEFAULT_DATABASE_PATH = Path(__file__).resolve().parents[1] / "data" / "interview_helper.db"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _load(value: str | None) -> Any:
    return None if value is None else json.loads(value)


@contextmanager
def connection(database_path: str | Path = DEFAULT_DATABASE_PATH) -> Iterator[sqlite3.Connection]:
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    database = sqlite3.connect(path, timeout=30)
    database.row_factory = sqlite3.Row
    database.execute("PRAGMA foreign_keys = ON")
    database.execute("PRAGMA journal_mode = WAL")
    try:
        yield database
        database.commit()
    except Exception:
        database.rollback()
        raise
    finally:
        database.close()


def init_database(database_path: str | Path = DEFAULT_DATABASE_PATH) -> Path:
    path = Path(database_path)
    with connection(path) as database:
        database.executescript(
            """
            CREATE TABLE IF NOT EXISTS interviews (
                id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS questions (
                id TEXT PRIMARY KEY,
                interview_id TEXT NOT NULL,
                order_index INTEGER NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (interview_id) REFERENCES interviews(id) ON DELETE CASCADE,
                UNIQUE (interview_id, order_index)
            );
            CREATE TABLE IF NOT EXISTS answers (
                id TEXT PRIMARY KEY,
                interview_id TEXT NOT NULL,
                question_id TEXT NOT NULL,
                status TEXT NOT NULL,
                duration_ms INTEGER NOT NULL,
                media_content_type TEXT NOT NULL,
                recorded_at TEXT,
                media_blob BLOB NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (interview_id) REFERENCES interviews(id) ON DELETE CASCADE,
                FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                resource_id TEXT NOT NULL,
                status TEXT NOT NULL,
                progress REAL,
                error TEXT,
                gpu_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS answer_analyses (
                answer_id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (answer_id) REFERENCES answers(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS interview_reports (
                interview_id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (interview_id) REFERENCES interviews(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS idempotency_records (
                scope TEXT NOT NULL,
                idempotency_key TEXT NOT NULL,
                request_hash TEXT NOT NULL,
                status_code INTEGER NOT NULL,
                response TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (scope, idempotency_key)
            );
            CREATE INDEX IF NOT EXISTS idx_questions_interview ON questions(interview_id);
            CREATE INDEX IF NOT EXISTS idx_answers_interview ON answers(interview_id);
            CREATE INDEX IF NOT EXISTS idx_jobs_resource ON jobs(resource_id);
            """
        )
    return path


def create_interview(payload: dict[str, Any], database_path: str | Path) -> dict[str, Any]:
    timestamp = utc_now()
    value = {
        **payload,
        "status": "GENERATING_QUESTIONS",
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    with connection(database_path) as database:
        database.execute(
            "INSERT INTO interviews (id, payload, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (value["id"], _dump(value), value["status"], timestamp, timestamp),
        )
    return value


def _interview_from_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    result = _load(row["payload"])
    result.update(status=row["status"], created_at=row["created_at"], updated_at=row["updated_at"])
    return result


def get_interview(interview_id: str, database_path: str | Path) -> dict[str, Any] | None:
    with connection(database_path) as database:
        row = database.execute("SELECT * FROM interviews WHERE id = ?", (interview_id,)).fetchone()
    return _interview_from_row(row)


def list_interviews(database_path: str | Path) -> list[dict[str, Any]]:
    with connection(database_path) as database:
        rows = database.execute("SELECT * FROM interviews ORDER BY updated_at DESC").fetchall()
    return [_interview_from_row(row) for row in rows]  # type: ignore[misc]


def update_interview_status(interview_id: str, status: str, database_path: str | Path) -> None:
    timestamp = utc_now()
    with connection(database_path) as database:
        row = database.execute("SELECT payload FROM interviews WHERE id = ?", (interview_id,)).fetchone()
        if row is None:
            return
        payload = _load(row["payload"])
        payload.update(status=status, updated_at=timestamp)
        database.execute(
            "UPDATE interviews SET payload = ?, status = ?, updated_at = ? WHERE id = ?",
            (_dump(payload), status, timestamp, interview_id),
        )


def delete_interview(interview_id: str, database_path: str | Path) -> bool:
    with connection(database_path) as database:
        answer_ids = [
            row["id"]
            for row in database.execute("SELECT id FROM answers WHERE interview_id = ?", (interview_id,))
        ]
        if answer_ids:
            placeholders = ",".join("?" for _ in answer_ids)
            database.execute(
                f"DELETE FROM jobs WHERE resource_id = ? OR resource_id IN ({placeholders})",
                (interview_id, *answer_ids),
            )
        else:
            database.execute("DELETE FROM jobs WHERE resource_id = ?", (interview_id,))
        cursor = database.execute("DELETE FROM interviews WHERE id = ?", (interview_id,))
    return cursor.rowcount > 0


def create_question(payload: dict[str, Any], database_path: str | Path) -> dict[str, Any]:
    timestamp = utc_now()
    with connection(database_path) as database:
        database.execute(
            "INSERT INTO questions (id, interview_id, order_index, payload, created_at) VALUES (?, ?, ?, ?, ?)",
            (payload["id"], payload["interview_id"], payload["order"], _dump(payload), timestamp),
        )
    return payload


def get_question(question_id: str, database_path: str | Path) -> dict[str, Any] | None:
    with connection(database_path) as database:
        row = database.execute("SELECT payload FROM questions WHERE id = ?", (question_id,)).fetchone()
    return None if row is None else _load(row["payload"])


def list_questions(interview_id: str, database_path: str | Path) -> list[dict[str, Any]]:
    with connection(database_path) as database:
        rows = database.execute(
            "SELECT payload FROM questions WHERE interview_id = ? ORDER BY order_index", (interview_id,)
        ).fetchall()
    return [_load(row["payload"]) for row in rows]


def create_answer(
    payload: dict[str, Any], media: bytes, database_path: str | Path
) -> dict[str, Any]:
    timestamp = utc_now()
    value = {**payload, "created_at": timestamp, "updated_at": timestamp}
    with connection(database_path) as database:
        database.execute(
            """
            INSERT INTO answers (
                id, interview_id, question_id, status, duration_ms, media_content_type,
                recorded_at, media_blob, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                value["id"], value["interview_id"], value["question_id"], value["status"],
                value["duration_ms"], value["media_content_type"], value.get("recorded_at"),
                sqlite3.Binary(media), timestamp, timestamp,
            ),
        )
    return value


def _answer_from_row(row: sqlite3.Row | None, include_media: bool = False) -> dict[str, Any] | None:
    if row is None:
        return None
    result = {
        key: row[key]
        for key in (
            "id", "interview_id", "question_id", "status", "duration_ms",
            "media_content_type", "recorded_at", "created_at", "updated_at",
        )
    }
    if include_media:
        result["media"] = bytes(row["media_blob"])
    return result


def get_answer(
    answer_id: str, database_path: str | Path, *, include_media: bool = False
) -> dict[str, Any] | None:
    with connection(database_path) as database:
        row = database.execute("SELECT * FROM answers WHERE id = ?", (answer_id,)).fetchone()
    return _answer_from_row(row, include_media)


def list_answers(interview_id: str, database_path: str | Path) -> list[dict[str, Any]]:
    with connection(database_path) as database:
        rows = database.execute(
            """
            SELECT answers.* FROM answers
            JOIN questions ON questions.id = answers.question_id
            WHERE answers.interview_id = ?
            ORDER BY questions.order_index
            """,
            (interview_id,),
        ).fetchall()
    return [_answer_from_row(row) for row in rows]  # type: ignore[misc]


def update_answer_status(answer_id: str, status: str, database_path: str | Path) -> None:
    with connection(database_path) as database:
        database.execute(
            "UPDATE answers SET status = ?, updated_at = ? WHERE id = ?",
            (status, utc_now(), answer_id),
        )


def create_job(job_type: str, resource_id: str, job_id: str, database_path: str | Path) -> dict[str, Any]:
    timestamp = utc_now()
    value = {
        "id": job_id, "type": job_type, "status": "QUEUED", "resource_id": resource_id,
        "progress": 0.0, "error": None, "gpu_id": None,
        "created_at": timestamp, "updated_at": timestamp,
    }
    with connection(database_path) as database:
        database.execute(
            """
            INSERT INTO jobs (id, type, resource_id, status, progress, error, gpu_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (job_id, job_type, resource_id, "QUEUED", 0.0, None, None, timestamp, timestamp),
        )
    return value


def _job_from_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    result = dict(row)
    result["error"] = _load(result["error"])
    return result


def get_job(job_id: str, database_path: str | Path) -> dict[str, Any] | None:
    with connection(database_path) as database:
        row = database.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return _job_from_row(row)


def list_recoverable_analysis_jobs(database_path: str | Path) -> list[dict[str, Any]]:
    with connection(database_path) as database:
        rows = database.execute(
            """
            SELECT * FROM jobs
            WHERE type = 'ANSWER_ANALYSIS' AND status IN ('QUEUED', 'RUNNING')
            ORDER BY created_at
            """
        ).fetchall()
    return [_job_from_row(row) for row in rows]  # type: ignore[misc]


def find_job_for_resource(resource_id: str, database_path: str | Path) -> dict[str, Any] | None:
    with connection(database_path) as database:
        row = database.execute(
            "SELECT * FROM jobs WHERE resource_id = ? ORDER BY created_at DESC LIMIT 1", (resource_id,)
        ).fetchone()
    return _job_from_row(row)


def update_job(
    job_id: str,
    status: str,
    progress: float,
    database_path: str | Path,
    *,
    error: dict[str, str] | None = None,
    gpu_id: str | None = None,
) -> None:
    with connection(database_path) as database:
        database.execute(
            """
            UPDATE jobs SET status = ?, progress = ?, error = ?, gpu_id = ?, updated_at = ?
            WHERE id = ?
            """,
            (status, progress, _dump(error) if error else None, gpu_id, utc_now(), job_id),
        )


def save_analysis(answer_id: str, payload: dict[str, Any], database_path: str | Path) -> dict[str, Any]:
    timestamp = utc_now()
    with connection(database_path) as database:
        database.execute(
            """
            INSERT INTO answer_analyses (answer_id, payload, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(answer_id) DO UPDATE SET payload = excluded.payload, updated_at = excluded.updated_at
            """,
            (answer_id, _dump(payload), timestamp, timestamp),
        )
    return payload


def get_analysis(answer_id: str, database_path: str | Path) -> dict[str, Any] | None:
    with connection(database_path) as database:
        row = database.execute(
            "SELECT payload FROM answer_analyses WHERE answer_id = ?", (answer_id,)
        ).fetchone()
    return None if row is None else _load(row["payload"])


def save_report(interview_id: str, payload: dict[str, Any], database_path: str | Path) -> dict[str, Any]:
    timestamp = utc_now()
    with connection(database_path) as database:
        database.execute(
            """
            INSERT INTO interview_reports (interview_id, payload, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(interview_id) DO UPDATE SET payload = excluded.payload, updated_at = excluded.updated_at
            """,
            (interview_id, _dump(payload), timestamp, timestamp),
        )
    return payload


def get_report(interview_id: str, database_path: str | Path) -> dict[str, Any] | None:
    with connection(database_path) as database:
        row = database.execute(
            "SELECT payload FROM interview_reports WHERE interview_id = ?", (interview_id,)
        ).fetchone()
    return None if row is None else _load(row["payload"])


def save_idempotency(
    scope: str,
    key: str,
    request_hash: str,
    status_code: int,
    response: dict[str, Any],
    database_path: str | Path,
) -> None:
    with connection(database_path) as database:
        database.execute(
            """
            INSERT INTO idempotency_records
                (scope, idempotency_key, request_hash, status_code, response, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (scope, key, request_hash, status_code, _dump(response), utc_now()),
        )


def get_idempotency(scope: str, key: str, database_path: str | Path) -> dict[str, Any] | None:
    with connection(database_path) as database:
        row = database.execute(
            """
            SELECT request_hash, status_code, response FROM idempotency_records
            WHERE scope = ? AND idempotency_key = ?
            """,
            (scope, key),
        ).fetchone()
    if row is None:
        return None
    return {
        "request_hash": row["request_hash"],
        "status_code": row["status_code"],
        "response": _load(row["response"]),
    }
