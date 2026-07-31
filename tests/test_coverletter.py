from job_radar.coverletter import generate_cover_letter
from job_radar.profile_engine.models import CandidateProfile


class FakeTextProvider:
    def __init__(self):
        self.last_user = ""

    def complete_json(self, **kwargs):
        return {}

    def complete_text(self, *, system, user, max_tokens=1024):
        self.last_user = user
        return "  Dear Hiring Team,\nI'd love to join. [Your Name]  "


def test_generate_cover_letter_uses_profile_and_job():
    p = FakeTextProvider()
    prof = CandidateProfile(skills=["Swift", "Kotlin"], search_terms=["ios"])
    out = generate_cover_letter(
        p, prof, title="iOS Engineer", company="Acme", description="Build the app"
    )
    assert out == "Dear Hiring Team,\nI'd love to join. [Your Name]"  # trimmed
    # The prompt carries the job + the candidate's real skills.
    assert "iOS Engineer" in p.last_user
    assert "Acme" in p.last_user
    assert "Swift" in p.last_user
