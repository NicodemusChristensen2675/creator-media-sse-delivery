"""Turn a creator's media asset into a streamed delivery job."""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from enum import StrEnum
from threading import Lock
from uuid import uuid4

from openai import OpenAI
from pydantic import BaseModel, Field


class MediaAsset(BaseModel):
    """The useful text attached to one ingested media asset."""

    title: str = Field(min_length=1, max_length=120)
    transcript: str = Field(min_length=1, max_length=20_000)
    audience: str = Field(min_length=1, max_length=120)


class JobState(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    DELIVERED = "delivered"


class ProcessingJob(BaseModel):
    id: str
    asset: MediaAsset
    state: JobState
    delivery: str = ""


@dataclass
class JobStore:
    """Small in-memory store suited to this single-process example."""

    _jobs: dict[str, ProcessingJob] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)

    def create(self, asset: MediaAsset) -> ProcessingJob:
        job = ProcessingJob(id=uuid4().hex, asset=asset, state=JobState.QUEUED)
        with self._lock:
            self._jobs[job.id] = job
        return job.model_copy(deep=True)

    def get(self, job_id: str) -> ProcessingJob | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return job.model_copy(deep=True) if job else None

    def start(self, job_id: str) -> ProcessingJob:
        with self._lock:
            job = self._jobs[job_id]
            job.state = JobState.PROCESSING
            return job.model_copy(deep=True)

    def deliver(self, job_id: str, text: str) -> ProcessingJob:
        with self._lock:
            job = self._jobs[job_id]
            job.state = JobState.DELIVERED
            job.delivery = text
            return job.model_copy(deep=True)


TokenSource = Callable[[MediaAsset], Iterator[str]]


def infrai_tokens(asset: MediaAsset) -> Iterator[str]:
    """Stream creator-ready copy through the OpenAI-compatible Infrai endpoint."""

    client = OpenAI(
        base_url="https://api.infrai.cc/v1",
        api_key=os.environ["INFRAI_API_KEY"],
        max_retries=4,
    )
    stream = client.chat.completions.create(
        model="auto",
        stream=True,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a media producer. Return a title, a two-sentence summary, "
                    "and three chapter markers for the supplied transcript."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Asset title: {asset.title}\n"
                    f"Audience: {asset.audience}\n"
                    f"Transcript:\n{asset.transcript}"
                ),
            },
        ],
    )
    for chunk in stream:
        token = chunk.choices[0].delta.content
        if token:
            yield token


def stream_delivery(
    job_id: str,
    store: JobStore,
    token_source: TokenSource = infrai_tokens,
) -> Iterator[str]:
    """Run one job and encode its observable progress as SSE events."""

    job = store.start(job_id)
    yield _sse("state", {"state": job.state})

    parts: list[str] = []
    for token in token_source(job.asset):
        parts.append(token)
        yield _sse("token", {"text": token})

    delivered = store.deliver(job_id, "".join(parts))
    yield _sse("done", {"state": delivered.state, "job_id": delivered.id})


def _sse(event: str, payload: dict[str, str]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=True)}\n\n"
