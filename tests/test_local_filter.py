from job_radar.common.models import Job
from job_radar.profile_engine.models import CandidateProfile
from job_radar.search_engine.ranking.local_filter import local_filter


def _profile() -> CandidateProfile:
    return CandidateProfile(
        roles=["iOS Engineer"],
        skills=["Swift", "SwiftUI"],
        search_terms=["ios engineer", "swift developer"],
        excluded_roles=["Junior", "Intern"],
    )


def _job(external_id: str, title: str, region: str = "Worldwide", desc: str = "") -> Job:
    return Job(
        source="test",
        external_id=external_id,
        title=title,
        company="Acme",
        remote_region=region,
        url=f"https://example.com/{external_id}",
        description=desc,
    )


def test_matching_job_scores_above_zero_and_excluded_dropped():
    jobs = [
        _job("1", "Senior iOS Engineer", desc="Swift and SwiftUI"),
        _job("2", "Junior iOS Engineer"),          # excluded by role
        _job("3", "Marketing Manager", desc="SEO"),  # no overlap
    ]
    result = local_filter(jobs, _profile(), top_n=10, region_priority=["Worldwide"])
    titles = [s.job.title for s in result]
    assert "Senior iOS Engineer" in titles
    assert "Junior iOS Engineer" not in titles
    assert "Marketing Manager" not in titles


def test_region_priority_breaks_ties():
    jobs = [
        _job("1", "iOS Engineer", region="US"),
        _job("2", "iOS Engineer", region="Worldwide"),
    ]
    result = local_filter(
        jobs, _profile(), top_n=10, region_priority=["Worldwide", "Europe"]
    )
    assert result[0].job.remote_region == "Worldwide"
