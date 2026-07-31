from job_radar.analysis import generate_analysis
from job_radar.profile_engine.models import CandidateProfile


class FakeJsonProvider:
    def __init__(self):
        self.last_user = ""

    def complete_json(self, *, system, user, max_tokens=1024):
        self.last_user = user
        return {
            "fit": "Strong fit for a senior iOS role.",
            "matching_skills": ["Swift", "SwiftUI"],
            "missing_skills": ["Combine"],
            "suggestions": ["Highlight your App Store launches"],
        }

    def complete_text(self, **kwargs):
        return ""


def test_generate_analysis_shapes_output_and_uses_profile():
    p = FakeJsonProvider()
    prof = CandidateProfile(skills=["Swift", "SwiftUI"], search_terms=["ios"])
    out = generate_analysis(
        p, prof, title="Senior iOS Engineer", company="Acme", description="Build the app"
    )
    assert out["fit"].startswith("Strong fit")
    assert out["matching_skills"] == ["Swift", "SwiftUI"]
    assert out["missing_skills"] == ["Combine"]
    assert out["suggestions"] == ["Highlight your App Store launches"]
    # The prompt carries the job + the candidate's real profile.
    assert "Senior iOS Engineer" in p.last_user
    assert "Acme" in p.last_user
    assert "Swift" in p.last_user


def test_generate_analysis_tolerates_missing_keys():
    class Sparse:
        def complete_json(self, **kwargs):
            return {"fit": "ok"}

        def complete_text(self, **kwargs):
            return ""

    out = generate_analysis(Sparse(), CandidateProfile(), title="x", company="y")
    assert out["fit"] == "ok"
    assert out["matching_skills"] == []
    assert out["missing_skills"] == []
    assert out["suggestions"] == []
