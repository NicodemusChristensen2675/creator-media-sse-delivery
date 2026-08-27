import json

from creator_delivery import JobState, JobStore, MediaAsset, stream_delivery


def test_stream_marks_job_delivered_with_complete_creator_copy() -> None:
    store = JobStore()
    job = store.create(
        MediaAsset(
            title="Tool orchestration",
            transcript="An agent calls a tool, observes the result, and chooses its next action.",
            audience="agent builders",
        )
    )

    def fixed_tokens(_asset: MediaAsset):
        yield "Tool-aware agents"
        yield "\nA concise creator delivery."

    events = list(stream_delivery(job.id, store, fixed_tokens))

    assert events[0].startswith("event: state\n")
    done_payload = json.loads(events[-1].split("data: ", 1)[1])
    assert done_payload == {"state": "delivered", "job_id": job.id}
    saved = store.get(job.id)
    assert saved is not None
    assert saved.state is JobState.DELIVERED
    assert saved.delivery == "Tool-aware agents\nA concise creator delivery."
