"""
Tests for ollama_lock.py — the cross-process mutex that serializes CEO,
Engineering, and the vector store's RAG hook against the local Ollama
server, so two agent processes never race to load different models at
once (reproduced live: that race caused CEO timeouts and a crashed
Engineering worker — see ceo_agent.py / engineering_agent.py /
enterprise_router/vector_storage.py comments for the full story).
"""

from __future__ import annotations

import os
import threading
import time

import ollama_lock


def test_ollama_call_acquires_and_releases_the_lock_file(monkeypatch, tmp_path):
    lock_path = str(tmp_path / "test.lock")
    monkeypatch.setattr(ollama_lock, "_LOCK_PATH", lock_path)

    with ollama_lock.ollama_call() as acquired:
        assert acquired is True
        assert os.path.exists(lock_path)

    assert not os.path.exists(lock_path)


def test_ollama_call_serializes_concurrent_callers(monkeypatch, tmp_path):
    lock_path = str(tmp_path / "test.lock")
    monkeypatch.setattr(ollama_lock, "_LOCK_PATH", lock_path)

    order: list[str] = []
    barrier_entered = threading.Event()

    def hold_lock_briefly(name: str) -> None:
        with ollama_lock.ollama_call(max_wait_s=5):
            order.append(f"{name}-start")
            if name == "first":
                barrier_entered.set()
                time.sleep(0.2)
            order.append(f"{name}-end")

    t1 = threading.Thread(target=hold_lock_briefly, args=("first",))
    t2 = threading.Thread(target=hold_lock_briefly, args=("second",))
    t1.start()
    barrier_entered.wait(timeout=2)
    t2.start()
    t1.join(timeout=5)
    t2.join(timeout=5)

    # "second" must never start while "first" is still holding the lock —
    # i.e. the two calls never interleave.
    assert order == ["first-start", "first-end", "second-start", "second-end"]


def test_ollama_call_steals_a_stale_lock(monkeypatch, tmp_path):
    lock_path = str(tmp_path / "test.lock")
    monkeypatch.setattr(ollama_lock, "_LOCK_PATH", lock_path)
    monkeypatch.setattr(ollama_lock, "_STALE_AFTER_S", 0.05)

    # Simulate a holder that crashed (e.g. kill -9) without releasing —
    # write the lock file directly rather than going through the context
    # manager, and make it look old enough to be stolen.
    with open(lock_path, "wb") as f:
        f.write(b"99999")
    old_time = time.time() - 10
    os.utime(lock_path, (old_time, old_time))

    with ollama_lock.ollama_call(max_wait_s=2, poll_interval_s=0.01) as acquired:
        assert acquired is True


def test_ollama_call_gives_up_after_max_wait_instead_of_hanging_forever(monkeypatch, tmp_path):
    lock_path = str(tmp_path / "test.lock")
    monkeypatch.setattr(ollama_lock, "_LOCK_PATH", lock_path)
    # Make the held lock look fresh (not stale) so it can't be stolen.
    monkeypatch.setattr(ollama_lock, "_STALE_AFTER_S", 600)

    with open(lock_path, "wb") as f:
        f.write(b"99999")

    start = time.time()
    with ollama_lock.ollama_call(max_wait_s=0.2, poll_interval_s=0.05) as acquired:
        assert acquired is False
    elapsed = time.time() - start

    # Degrades to proceeding unserialized rather than hanging forever.
    assert elapsed < 2.0
    # The lock file is untouched (still held by the "other process") since
    # this caller never actually acquired it.
    assert os.path.exists(lock_path)
