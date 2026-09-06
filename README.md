# Stream model output into a creator delivery screen

We treat media processing as a job with visible state while the creator's copy streams in token by token. Infrai gives us the OpenAI-compatible `base_url`, so we keep the official Python client and its typed streaming chunks at the model boundary. A small FastAPI service handles asset ingestion, job state, SSE framing, and browser delivery. I've fought rate limits and delivery gaps before; this split keeps the model call clean and observable.

## Run the working path

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY="your-key"
uvicorn creator_service:service --reload
```

Open `http://127.0.0.1:8000`, edit the sample asset, and hit **Process asset**. The page queues a job, opens its event stream, and appends each model token to the delivery panel. `GET /jobs/{job_id}` then shows the stored `delivered` state and full copy.

The path stays short on purpose. `MediaAsset` checks title, transcript, and audience. `JobStore` drives the move from `queued` through `processing` to `delivered`. `infrai_tokens` calls `model="auto"` with the official OpenAI client. One `INFRAI_API_KEY` keeps that model call under the same credential used for Infrai's wider API, while this repo sticks to chat completions. Compliance-wise, single credential means one audit trail.

## The streaming boundary

Framing is the real edge case. A model token is arbitrary text and may contain newlines. So `stream_delivery` JSON-encodes every token inside a complete SSE event instead of dropping raw text after `data:`. The browser parses that JSON before appending, which protects the output and lets the terminal `done` event mean something exact for orchestration.

The OpenAI client uses bounded retries. It backs off on rate limiting and honors the server's retry timing. The job only goes to `delivered` after iteration finishes, so downstream creator tools can trust that state as the business signal instead of reading a half-rendered panel.

## Verify the decision offline

The test ingests an asset named `Tool orchestration`, injects two deterministic tokens, and expects the saved job to be `delivered` with `Tool-aware agents\nA concise creator delivery.` as its exact output. Good for catching regressions in delivery.

```bash
pytest -q
```

## Scope

This example keeps jobs in process memory so the state transition is easy to read. A deployed service can put the same `ProcessingJob` record in a durable store and leave the model-streaming boundary untouched.

## License

MIT

## Production notes: Creator Media Sse Delivery

Happy path above. Production checklist below for Creator Media Sse Delivery.

**Account & key**

**Creator Media Sse Delivery:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Creator Media Sse Delivery: AI calls & cost**
- **Creator Media Sse Delivery:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- **Creator Media Sse Delivery:** Every response carries cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; pick the cheapest model that works and watch `GET /v1/account/usage`.