#!/usr/bin/env python3
"""
pipeline_api.py — FastAPI webhook for n8n to trigger the article pipeline.

Runs on VPS host (not inside Docker). n8n calls this via HTTP Request node.
Endpoint: POST http://172.17.0.1:5050/run-pipeline

Usage:
    uvicorn pipeline_api:app --host 0.0.0.0 --port 5050
    # Or via systemd service (see deploy/README.md)
"""

import asyncio
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel

app = FastAPI(title="Bulk Affiliate Pipeline API", version="1.0.0")

PROJECT_DIR = Path("/opt/bulk-affiliate")
SCRIPTS_DIR = PROJECT_DIR / "scripts"
LOGS_DIR = PROJECT_DIR / "logs"
OUTPUTS_DIR = PROJECT_DIR / "outputs"
PYTHON = str(PROJECT_DIR / "venv" / "bin" / "python3")

# Track running jobs to prevent double-runs
_running_jobs = {}


class PipelineRequest(BaseModel):
    """Request body for pipeline trigger."""
    niche: str | None = None        # Specific niche, or None for auto (next in schedule)
    limit: int | None = None        # Article limit per run (default: all)
    steps: list[str] | None = None  # Which steps: ["research", "generate", "cleanup", "qa"]
    dry_run: bool = False           # If true, just report what would run


class PipelineStatus(BaseModel):
    """Response body for pipeline status."""
    status: str
    job_id: str | None = None
    message: str
    started_at: str | None = None
    niche: str | None = None
    details: dict | None = None


def run_command(cmd: list[str], timeout: int = 7200) -> dict:
    """Run a command and return stdout, stderr, returncode."""
    env = os.environ.copy()
    # Load .env.cowork if exists
    env_file = PROJECT_DIR / ".env.cowork"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip()

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=timeout, cwd=str(PROJECT_DIR), env=env,
        )
        return {
            "stdout": result.stdout[-3000:],  # Last 3K chars
            "stderr": result.stderr[-1000:],
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "TIMEOUT", "returncode": -1}
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "returncode": -1}


def run_pipeline_sync(niche: str | None, limit: int | None, steps: list[str] | None):
    """Run the full pipeline synchronously. Called as a background task."""
    job_id = f"pipeline-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    log_file = LOGS_DIR / f"{job_id}.json"
    _running_jobs[job_id] = {"status": "running", "started": datetime.now().isoformat()}

    results = {"job_id": job_id, "started": datetime.now().isoformat(), "steps": []}
    all_steps = steps or ["research", "serp_real", "generate", "cleanup", "enhance", "qa"]

    # Determine niche
    if niche:
        target_niche = niche
    else:
        # Use daily_runner to get next niche
        status_result = run_command(
            [PYTHON, str(SCRIPTS_DIR / "daily_runner.py"), "--status"],
            timeout=30,
        )
        # Parse first PENDING niche from output
        target_niche = None
        for line in status_result["stdout"].split("\n"):
            if "PENDING" in line:
                # Extract niche name from status output
                parts = line.strip().split(":")
                if len(parts) >= 2:
                    niche_part = parts[1].strip().split()[0]
                    # Map display name back to slug
                    from scripts.config import NICHE_NAMES
                    for slug, name in NICHE_NAMES.items():
                        if name.lower().startswith(niche_part.lower()):
                            target_niche = slug
                            break
                if target_niche:
                    break
        if not target_niche:
            results["error"] = "No pending niche found"
            log_file.write_text(json.dumps(results, indent=2))
            _running_jobs[job_id] = {"status": "error", "error": "No pending niche"}
            return

    results["niche"] = target_niche
    limit_args = ["--limit", str(limit)] if limit else []

    # Step 1: Perplexity SERP Research (fact-grounding, content gaps)
    if "research" in all_steps:
        res = run_command(
            [PYTHON, str(SCRIPTS_DIR / "serp_researcher.py"), target_niche] + limit_args,
            timeout=1800,
        )
        results["steps"].append({"step": "research", **res})

    # Step 1b: DataForSEO real SERP (live Google rankings, PAA, SERP features)
    if "serp_real" in all_steps:
        res = run_command(
            [PYTHON, str(SCRIPTS_DIR / "serp_dataforseo.py"), target_niche] + limit_args,
            timeout=1800,
        )
        results["steps"].append({"step": "serp_real", **res})

    # Step 2: Article Generation
    if "generate" in all_steps:
        res = run_command(
            [PYTHON, str(SCRIPTS_DIR / "article_generator.py"), target_niche] + limit_args,
            timeout=7200,
        )
        results["steps"].append({"step": "generate", **res})

    # Step 3: HTML Cleanup
    if "cleanup" in all_steps:
        res = run_command(
            [PYTHON, str(SCRIPTS_DIR / "html_cleanup.py"), target_niche],
            timeout=300,
        )
        results["steps"].append({"step": "cleanup", **res})

    # Step 4: Enhancement (E-E-A-T signals, visual elements, expert quotes — 0 API cost)
    if "enhance" in all_steps:
        res = run_command(
            [PYTHON, str(SCRIPTS_DIR / "article_enhancer.py"), target_niche],
            timeout=300,
        )
        results["steps"].append({"step": "enhance", **res})

    # Step 5: QA
    if "qa" in all_steps:
        res = run_command(
            [PYTHON, str(SCRIPTS_DIR / "article_qa.py"), target_niche],
            timeout=300,
        )
        results["steps"].append({"step": "qa", **res})

    # Check for cowork queue
    cowork_path = OUTPUTS_DIR / target_niche / "articles" / "cowork-queue.json"
    if cowork_path.exists():
        queue = json.loads(cowork_path.read_text())
        results["cowork_queue"] = queue.get("slugs", [])

    results["finished"] = datetime.now().isoformat()
    results["success"] = all(
        s.get("returncode", -1) == 0 for s in results["steps"]
    )

    # Save log
    log_file.write_text(json.dumps(results, indent=2))
    _running_jobs[job_id] = {
        "status": "completed" if results["success"] else "failed",
        "finished": results["finished"],
        "niche": target_niche,
    }


@app.get("/health")
def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "time": datetime.now().isoformat(),
        "project_dir": str(PROJECT_DIR),
        "scripts_exist": SCRIPTS_DIR.exists(),
        "env_exists": (PROJECT_DIR / ".env.cowork").exists(),
    }


@app.post("/run-pipeline", response_model=PipelineStatus)
def trigger_pipeline(req: PipelineRequest, background_tasks: BackgroundTasks):
    """Trigger the article pipeline. Runs in background, returns job ID."""

    # Check if a job is already running
    for job_id, info in _running_jobs.items():
        if info.get("status") == "running":
            return PipelineStatus(
                status="already_running",
                job_id=job_id,
                message=f"Pipeline already running since {info.get('started')}",
                started_at=info.get("started"),
            )

    if req.dry_run:
        return PipelineStatus(
            status="dry_run",
            message=f"Would run pipeline for niche={req.niche or 'auto'}, limit={req.limit or 'all'}",
        )

    # Launch pipeline in background
    background_tasks.add_task(run_pipeline_sync, req.niche, req.limit, req.steps)

    job_id = f"pipeline-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    return PipelineStatus(
        status="started",
        job_id=job_id,
        message=f"Pipeline started for niche={req.niche or 'auto'}, limit={req.limit or 'all'}",
        started_at=datetime.now().isoformat(),
        niche=req.niche,
    )


@app.get("/status")
def get_status():
    """Get status of running/recent jobs."""
    return {
        "jobs": _running_jobs,
        "logs": sorted([f.name for f in LOGS_DIR.glob("pipeline-*.json")])[-5:]
        if LOGS_DIR.exists() else [],
    }


@app.get("/status/{job_id}")
def get_job_status(job_id: str):
    """Get status of a specific job."""
    if job_id in _running_jobs:
        return _running_jobs[job_id]

    log_file = LOGS_DIR / f"{job_id}.json"
    if log_file.exists():
        return json.loads(log_file.read_text())

    raise HTTPException(status_code=404, detail=f"Job {job_id} not found")


@app.get("/schedule")
def get_schedule():
    """Get the generation schedule status."""
    result = run_command(
        [PYTHON, str(SCRIPTS_DIR / "daily_runner.py"), "--status"],
        timeout=30,
    )
    return {"output": result["stdout"], "returncode": result["returncode"]}


@app.get("/read-article/{niche}/{slug}")
def read_article(niche: str, slug: str):
    """Read a generated article for QA inspection."""
    html_path = OUTPUTS_DIR / niche / "articles" / f"{slug}.html"
    json_path = OUTPUTS_DIR / niche / "articles" / f"{slug}.json"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail=f"Article {slug} not found")
    html = html_path.read_text(encoding="utf-8")
    schema = json.loads(json_path.read_text(encoding="utf-8")) if json_path.exists() else None
    word_count = len(html.split())
    return {"slug": slug, "niche": niche, "word_count": word_count, "html": html[:5000], "schema": schema}


@app.get("/read-log/{job_id}")
def read_log(job_id: str):
    """Read full pipeline log."""
    log_path = LOGS_DIR / f"{job_id}.json"
    if not log_path.exists():
        raise HTTPException(status_code=404, detail=f"Log {job_id} not found")
    return json.loads(log_path.read_text())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5050)
