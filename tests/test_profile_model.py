from job_radar.profile_engine.models import CandidateProfile


def test_profile_save_load_roundtrip(tmp_path):
    profile = CandidateProfile(
        summary="Senior iOS engineer.",
        roles=["Senior iOS Engineer"],
        skills=["Swift", "UIKit"],
        seniority="Senior",
        years_experience=10,
        search_terms=["ios engineer"],
        excluded_roles=["Junior"],
    )
    path = tmp_path / "profile.json"
    profile.save(path)

    loaded = CandidateProfile.load(path)
    assert loaded == profile
    assert loaded.years_experience == 10
