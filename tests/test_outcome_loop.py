from app.memory.outcome_log import OutcomeLogStore
from app.memory.retrieval import similar_outcomes
from tests.fakes import FakeEmbedder, FakeSupabaseClient


async def test_workspace_isolation_never_crosses_workspaces():
    client = FakeSupabaseClient()
    store = OutcomeLogStore(client)

    store.write(
        workspace="texhoma",
        agent="foreman",
        task_type="draft_email",
        input_summary="Texhoma buyer outreach draft",
        action_taken="Drafted outreach email",
    )
    store.write(
        workspace="acesn8s_dev",
        agent="foreman",
        task_type="draft_email",
        input_summary="Aces N 8s dev outreach draft",
        action_taken="Drafted outreach email",
    )

    texhoma_results = await similar_outcomes(
        task_type="draft_email",
        text="outreach draft",
        workspace="texhoma",
        client=client,
        embedder=FakeEmbedder(),
    )

    assert len(texhoma_results) == 1
    assert all(r["workspace"] == "texhoma" for r in texhoma_results)
    assert not any(r["workspace"] == "acesn8s_dev" for r in texhoma_results)


async def test_outcome_loop_correction_surfaces_in_similar_outcomes():
    client = FakeSupabaseClient()
    store = OutcomeLogStore(client)

    # 1. create task -> row written pending
    row = store.write(
        workspace="acesn8s_dev",
        agent="foreman",
        task_type="draft",
        input_summary="Draft a follow-up note to a land seller",
        action_taken="Drafted a generic follow-up note",
    )
    assert row["outcome_status"] == "pending"

    # 2. PATCH correction
    patched = store.patch(
        row["id"],
        outcome_status="corrected",
        outcome="Scott sent a revised version",
        correction="Always mention the recorded instrument by name, not just 'the deed'.",
    )
    assert patched["outcome_status"] == "corrected"
    assert patched["correction"]

    # 3. resubmit a similar task -> correction surfaces in retrieval
    results = await similar_outcomes(
        task_type="draft",
        text="Draft a follow-up note to a different land seller",
        workspace="acesn8s_dev",
        client=client,
        embedder=FakeEmbedder(),
    )

    assert len(results) == 1
    assert results[0]["correction"] == (
        "Always mention the recorded instrument by name, not just 'the deed'."
    )
