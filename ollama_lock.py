"""
ollama_lock.py

Cross-process mutex so CEO, Engineering, and the vector store's RAG
embedding hook never call the local Ollama server at the same time.

Why this exists (reproduced live, repeatedly): on a memory-constrained
machine, Ollama evicts and reloads whichever model it isn't currently
serving. When two of this project's agent processes call Ollama
concurrently for two *different* models (e.g. CEO's chat model and
Engineering's CrewAI coding model, or either of those against the vector
store's embedding model), each request evicts the other's model, and
cold-reload latency (10-20s+, sometimes much more under real memory
pressure) can exceed either call's timeout -- producing a "Strategic Link
Error", or in Engineering's case a crashed worker, even though nothing
is actually broken. Serializing Ollama calls across all of this
project's local processes means each call either gets an already-warm
model or reliably finishes loading before the next call starts.

This is a plain filesystem lock (atomic file creation), not a network
service or a Python-level lock -- it has to work across separate OS
processes (each department agent is its own process), which is exactly
this project's local-dev deployment model (single machine, shared repo
checkout).
"""

from __future__ import annotations

import contextlib
import os
import time

_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
_LOCK_PATH = os.path.join(_REPO_ROOT, ".ollama_call.lock")

# Generous on purpose. The longest single thing this project holds the
# lock for is one CrewAI crew.kickoff() call, which on a slow local model
# can legitimately run for a couple of minutes. A lock older than this
# almost certainly means its holder crashed (e.g. was killed -9) rather
# than being a real, still-in-progress call, so it's safe to steal.
_STALE_AFTER_S = 600


@contextlib.contextmanager
def ollama_call(*, max_wait_s: float = 300.0, poll_interval_s: float = 0.5):
    """
    Block until exclusive access to the local Ollama server is held
    across all of this project's agent processes, run the wrapped call,
    then release.

    Degrades to proceeding unserialized (never raises, never hangs the
    caller forever) if the lock can't be acquired within ``max_wait_s``
    or the lock file can't be created at all (e.g. a read-only
    filesystem) -- a slow or stuck Ollama call from another agent
    shouldn't also make this one hang indefinitely.
    """
    acquired = False
    deadline = time.time() + max_wait_s
    while time.time() < deadline:
        try:
            fd = os.open(_LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                os.write(fd, str(os.getpid()).encode())
            finally:
                os.close(fd)
            acquired = True
            break
        except FileExistsError:
            try:
                age = time.time() - os.path.getmtime(_LOCK_PATH)
                if age > _STALE_AFTER_S:
                    os.remove(_LOCK_PATH)
                    continue
            except OSError:
                pass
            time.sleep(poll_interval_s)
        except OSError:
            break

    try:
        yield acquired
    finally:
        if acquired:
            try:
                os.remove(_LOCK_PATH)
            except OSError:
                pass
