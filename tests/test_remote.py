from job_radar.search_engine.remote import classify_region, is_remote


def test_rejects_hybrid_and_onsite():
    assert not is_remote("Hybrid - Berlin")
    assert not is_remote("On-site", "Full time")
    assert not is_remote("In office only")


def test_accepts_remote():
    assert is_remote("Anywhere")
    assert is_remote("Remote", "Europe")
    assert is_remote("")  # unknown defaults to remote-eligible


def test_region_priority_labels():
    assert classify_region("Worldwide") == "Worldwide"
    assert classify_region("Europe only") == "Europe"
    assert classify_region("EMEA") == "EMEA"
    assert classify_region("USA only") == "US"
    assert classify_region("") == "Unknown"
