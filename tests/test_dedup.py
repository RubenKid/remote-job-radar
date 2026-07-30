from job_radar.common.models import Job
from job_radar.search_engine.pipeline import _dedupe_by_company_title


def _job(source, ext, title, company):
    return Job(source=source, external_id=ext, title=title, company=company,
               url=f"https://e/{source}/{ext}")


def test_collapses_same_role_across_sources_and_cities():
    jobs = [
        _job("greenhouse", "1", "Staff Software Engineer, Product (Montevideo)", "LawnStarter"),
        _job("greenhouse", "2", "Staff Software Engineer, Product (Campinas)", "LawnStarter"),
        _job("findwork", "9", "Staff Software Engineer, Product", "LawnStarter"),
        _job("findwork", "3", "Senior iOS Engineer", "Reddit"),
    ]
    out = _dedupe_by_company_title(jobs)
    titles = [(j.company, j.title) for j in out]
    # LawnStarter "Staff Software Engineer, Product" collapses to one entry.
    assert sum(1 for c, _ in titles if c == "LawnStarter") == 1
    assert ("Reddit", "Senior iOS Engineer") in titles
    assert len(out) == 2


def test_collapses_dash_location_suffixes():
    jobs = [
        _job("a", "1", "Software Engineer, iOS Core Product - Munich, Germany", "Speechify"),
        _job("a", "2", "Software Engineer, iOS Core Product - Edinburgh, United Kingdom", "speechify"),
        _job("a", "3", "Software Engineer, iOS Core Product - Birmingham, UK", "Speechify"),
    ]
    assert len(_dedupe_by_company_title(jobs)) == 1


def test_keeps_first_occurrence():
    jobs = [
        _job("a", "1", "iOS Engineer", "Acme"),
        _job("b", "2", "iOS Engineer", "Acme"),
    ]
    out = _dedupe_by_company_title(jobs)
    assert len(out) == 1 and out[0].source == "a"
