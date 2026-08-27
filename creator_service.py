"""Explanatory entry point for asset ingestion and streamed creator delivery."""

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse

from creator_delivery import JobStore, MediaAsset, ProcessingJob, stream_delivery

service = FastAPI(title="Creator delivery stream")
jobs = JobStore()


@service.get("/", response_class=HTMLResponse)
def creator_console() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Creator delivery stream</title>
  <style>
    body { font: 16px/1.5 system-ui; margin: 0; color: #202124; background: #f5f6f8; }
    main { max-width: 760px; margin: 48px auto; padding: 0 20px; }
    form, pre { background: white; border: 1px solid #d8dce3; border-radius: 6px; padding: 20px; }
    label { display: block; margin: 12px 0 4px; font-weight: 650; }
    input, textarea { box-sizing: border-box; width: 100%; padding: 10px; font: inherit; }
    textarea { min-height: 150px; resize: vertical; }
    button { margin-top: 16px; padding: 10px 14px; font: inherit; cursor: pointer; }
    pre { min-height: 160px; white-space: pre-wrap; }
  </style>
</head>
<body><main>
  <h1>Creator delivery stream</h1>
  <form id="asset-form">
    <label for="title">Asset title</label><input id="title" required value="Agent field notes">
    <label for="audience">Audience</label><input id="audience" required value="LLM agent engineers">
    <label for="transcript">Transcript</label><textarea id="transcript" required>Tools turn a model response into an action. An orchestrator should keep tool results visible and decide the next step from explicit state.</textarea>
    <button type="submit">Process asset</button>
  </form>
  <h2>Delivery</h2><pre id="delivery">Waiting for an asset.</pre>
</main><script>
const form = document.querySelector('#asset-form');
const delivery = document.querySelector('#delivery');
form.addEventListener('submit', async (event) => {
  event.preventDefault();
  delivery.textContent = '';
  const response = await fetch('/assets', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      title: document.querySelector('#title').value,
      audience: document.querySelector('#audience').value,
      transcript: document.querySelector('#transcript').value
    })
  });
  const job = await response.json();
  const events = new EventSource(`/jobs/${job.id}/stream`);
  events.addEventListener('token', (message) => {
    delivery.textContent += JSON.parse(message.data).text;
  });
  events.addEventListener('done', () => events.close());
});
</script></body></html>"""


@service.post("/assets", response_model=ProcessingJob, status_code=202)
def ingest_asset(asset: MediaAsset) -> ProcessingJob:
    return jobs.create(asset)


@service.get("/jobs/{job_id}", response_model=ProcessingJob)
def read_job(job_id: str) -> ProcessingJob:
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job was not found")
    return job


@service.get("/jobs/{job_id}/stream")
def deliver_job(job_id: str) -> StreamingResponse:
    if jobs.get(job_id) is None:
        raise HTTPException(status_code=404, detail="Job was not found")
    return StreamingResponse(
        stream_delivery(job_id, jobs),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
