from job_radar.common.models import Job, ScoredJob
from job_radar.profile_engine.models import CandidateProfile
from job_radar.search_engine.ranking.ai_ranker import AIRanker


class FakeProvider:
    """Stub LLM provider that records calls and returns a canned payload."""

    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def complete_json(self, *, system, user, max_tokens=4096):
        self.calls += 1
        return self.payload


def _jobs(n):
    return [
        ScoredJob(
            job=Job(
                source="t", external_id=str(i), title=f"Job {i}",
                company="C", url=f"https://e/{i}",
            ),
            local_score=1.0,
        )
        for i in range(n)
    ]


def test_batched_single_call_and_index_mapping():
    jobs = _jobs(3)
    payload = {
        "evaluations": [
            {"index": 0, "score": 90, "recommendation": True, "reasons": ["good"], "missing_skills": []},
            {"index": 1, "score": 40, "recommendation": False, "reasons": ["meh"], "missing_skills": ["x"]},
            # index 2 intentionally omitted -> should fall back to local score
        ]
    }
    fp = FakeProvider(payload)
    out = AIRanker(fp).evaluate(jobs, CandidateProfile())

    assert fp.calls == 1  # all jobs scored in ONE batched call
    by_id = {s.job.external_id: s for s in out}
    assert by_id["0"].evaluation.score == 90
    assert by_id["1"].evaluation.missing_skills == ["x"]
    assert by_id["2"].evaluation is None  # missing entry -> local fallback
    assert out[0].job.external_id == "0"  # sorted by score desc


def test_score_is_clamped():
    jobs = _jobs(1)
    fp = FakeProvider({"evaluations": [{"index": 0, "score": 250, "recommendation": True}]})
    out = AIRanker(fp).evaluate(jobs, CandidateProfile())
    assert out[0].evaluation.score == 100


def test_empty_shortlist_makes_no_call():
    fp = FakeProvider({"evaluations": []})
    assert AIRanker(fp).evaluate([], CandidateProfile()) == []
    assert fp.calls == 0
