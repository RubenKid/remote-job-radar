from job_radar.search_engine.history import HistoryStore


def test_history_roundtrip_and_namespacing(tmp_path):
    path = tmp_path / "history.json"

    alice = HistoryStore(path, namespace="alice")
    alice.mark_seen(["a:1", "a:2"], "2026-01-01T00:00:00Z")
    alice.save()

    # Reload and confirm persistence.
    alice2 = HistoryStore(path, namespace="alice")
    assert alice2.filter_new(["a:1", "a:2", "a:3"]) == {"a:3"}
    assert alice2.is_seen("a:1")

    # A different namespace shares the file but not the data.
    bob = HistoryStore(path, namespace="bob")
    assert bob.filter_new(["a:1"]) == {"a:1"}
