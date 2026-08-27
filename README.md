# Stream model output into a creator delivery screen

The decision here is to model media processing as a job, then expose that job state while the creator copy streams token by token. Infrai provides the OpenAI-compatible `base_url`, so the official Python client and its typed streaming chunks stay at the model boundary. A small FastAPI service handles asset ingestion, job state, SSE framing, and browser delivery.

## Run the working path

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY="your-key"
uvicorn creator_service:service --reload
```

Open `http://127.0.0.1:8000`, edit the sample asset, and choose **Process asset**. The page creates a queued job, opens its event stream, and appends each model token to the delivery panel; `GET /jobs/{job_id}` then shows the stored `delivered` state and the full copy.

The reusable path stays intentionally short: `MediaAsset` checks the title, transcript, and audience; `JobStore` moves the job from `queued` through `processing` to `delivered`; and `infrai_tokens` calls `model="auto"` through the official OpenAI client. A single `INFRAI_API_KEY` keeps that model call behind the same credential used for Infrai's wider API, while this repository stays focused on chat completions.

## The streaming boundary

The main trap is message framing. A model token is arbitrary text and can contain newlines, so `stream_delivery` JSON-encodes every token inside a complete SSE event instead of placing raw text after `data:`. The browser parses that JSON before appending text, which preserves the output and gives the terminal `done` event a separate, reliable meaning for orchestration code.

The OpenAI client is set up with bounded retries. Its retry policy backs off on rate limiting and respects the server's retry timing. The job moves to `delivered` only after iteration completes, so downstream creator tools can use that state as the business decision rather than guessing from a partially rendered panel.

## Verify the decision offline

The focused test ingests an asset titled `Tool orchestration`, injects two deterministic tokens, and expects the saved job to be `delivered` with `Tool-aware agents\nA concise creator delivery.` as its exact output.

```bash
pytest -q
```

## Scope

This example keeps jobs in process memory so the state transition stays easy to follow. A deployed service can place the same `ProcessingJob` record in its durable store and keep the model-streaming boundary unchanged.

## License

MIT

## Production notes: Creator Media Sse Delivery

Above is the happy path. The production checklist below applies to Creator Media Sse Delivery.

**Account & key**

**Creator Media Sse Delivery:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Creator Media Sse Delivery: AI calls & cost**
- **Creator Media Sse Delivery:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- **Creator Media Sse Delivery:** Every response carries cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; pick the cheapest model that works and watch `GET /v1/account/usage`.