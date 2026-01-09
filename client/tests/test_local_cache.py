"""Tests for local cache module."""


def test_queue_sync(temp_cache_dir):
    """Test queuing a sync."""
    from forgeclient.local_cache import queue_sync, get_pending_count

    queue_sync({"protocol_version": 1, "hostname": "test"})
    assert get_pending_count() == 1


def test_queue_max_limit(temp_cache_dir):
    """Test that queue respects max limit."""
    from forgeclient.local_cache import queue_sync, get_pending_count, MAX_PENDING_SYNCS

    for i in range(MAX_PENDING_SYNCS + 10):
        queue_sync({"protocol_version": 1, "hostname": f"test-{i}"})

    assert get_pending_count() == MAX_PENDING_SYNCS


def test_list_pending(temp_cache_dir):
    """Test listing pending syncs."""
    from forgeclient.local_cache import queue_sync, list_pending

    queue_sync({"protocol_version": 1, "hostname": "test1"})
    queue_sync({"protocol_version": 1, "hostname": "test2"})

    pending = list_pending()
    assert len(pending) == 2
    assert pending[0]["payload"]["hostname"] == "test1"


def test_clear_pending(temp_cache_dir):
    """Test clearing pending syncs."""
    from forgeclient.local_cache import queue_sync, clear_pending, get_pending_count

    queue_sync({"protocol_version": 1, "hostname": "test"})
    assert get_pending_count() == 1

    clear_pending()
    assert get_pending_count() == 0
