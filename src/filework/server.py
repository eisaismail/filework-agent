"""Loopback-only demo server. Tasks and approvals persist across restarts."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .agent import run
from .documents import DocumentError, Workspace
from .tools import write_report


class TaskInput(BaseModel):
    request: str = Field(min_length=3, max_length=2000)
    mode: str = "baseline"


def create_app(workspace_path: Path | None = None, state_path: Path | None = None):
    workspace = Workspace(workspace_path or Path(os.getenv("FILEWORK_WORKSPACE", "demo/documents")))
    state = (state_path or Path(os.getenv("FILEWORK_STATE", ".runtime"))).resolve()
    if state.is_relative_to(workspace.root):
        raise ValueError("State directory must be outside the document workspace.")
    (state / "reports").mkdir(parents=True, exist_ok=True)
    database = state / "tasks.db"
    lock = threading.Lock()

    def db():
        return sqlite3.connect(database, timeout=10)

    with db() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")

    def save(task):
        with db() as conn:
            conn.execute("INSERT OR REPLACE INTO tasks VALUES (?, ?)", (task["id"], json.dumps(task)))

    def load(task_id):
        with db() as conn:
            row = conn.execute("SELECT payload FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Task not found")
        return json.loads(row[0])

    app = FastAPI(title="Filework", version="0.1.0")
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"])
    static = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static), name="static")

    @app.middleware("http")
    async def local_requests(request: Request, call_next):
        # A custom header blocks cross-origin form submissions. No CORS is enabled.
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            if request.headers.get("x-filework") != "1":
                from fastapi.responses import JSONResponse
                return JSONResponse({"detail": "Use the local Filework interface."}, status_code=403)
            origin = request.headers.get("origin")
            if origin and origin != str(request.base_url).rstrip("/"):
                from fastapi.responses import JSONResponse
                return JSONResponse({"detail": "Cross-origin requests are not allowed."}, status_code=403)
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.get("/")
    def index():
        return FileResponse(static / "index.html")

    @app.get("/api/workspace")
    def info():
        return {"name": workspace.root.name, "files": workspace.files(),
                "llm_configured": bool(os.getenv("FILEWORK_MODEL")), "max_steps": 10}

    @app.get("/api/history")
    def history():
        with db() as conn:
            rows = conn.execute("SELECT payload FROM tasks ORDER BY rowid DESC LIMIT 20").fetchall()
        return [{k: t[k] for k in ["id", "request", "status", "mode"]}
                for t in [json.loads(row[0]) for row in rows]]

    @app.post("/api/tasks")
    def task(data: TaskInput):
        if data.mode not in {"baseline", "llm"}:
            raise HTTPException(422, "Choose baseline or llm mode")
        if not lock.acquire(blocking=False):
            raise HTTPException(409, "Another task is running. Please wait.")
        try:
            result = run(data.request, workspace, data.mode)
            result.update(id=uuid.uuid4().hex, request=data.request)
            save(result)
            return result
        finally:
            lock.release()

    @app.get("/api/tasks/{task_id}")
    def get_task(task_id: str):
        return load(task_id)

    @app.post("/api/tasks/{task_id}/approve")
    def approve(task_id: str):
        with lock:
            task = load(task_id)
            if task["status"] != "awaiting_approval":
                raise HTTPException(409, "This task is not waiting for approval.")
            artifact = state / "reports" / (task["id"] + ".csv")
            try:
                write_report(workspace, task["proposal"], artifact)
            except (DocumentError, FileExistsError) as exc:
                raise HTTPException(409, str(exc)) from exc
            task.update(status="completed", download_url=f"/api/tasks/{task_id}/report",
                        answer=f"Saved {len(task['proposal']['rows'])} checked invoice rows to a new CSV.")
            task["events"].append({"tool": "save_report", "arguments": {}, "summary": "Approved CSV saved"})
            save(task)
            return task

    @app.get("/api/tasks/{task_id}/report")
    def report(task_id: str):
        task = load(task_id)
        artifact = state / "reports" / (task["id"] + ".csv")
        if task["status"] != "completed" or not artifact.is_file():
            raise HTTPException(404, "No approved report exists.")
        return FileResponse(artifact, filename="invoice-report.csv", media_type="text/csv")

    return app
