import uuid

MAX_ATTEMPTS = 3

_jobs = {}
_dedupe_index = {}


def enqueue(name, payload, dedupe_key=None):
    """Add a job and return its id. A repeated dedupe_key returns the first job id."""
    if dedupe_key is not None and dedupe_key in _dedupe_index:
        return _dedupe_index[dedupe_key]
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {"name": name, "payload": payload, "attempts": 0}
    if dedupe_key is not None:
        _dedupe_index[dedupe_key] = job_id
    return job_id


def record_failure(job_id):
    """Count a failed attempt and report whether the job may run again."""
    job = _jobs[job_id]
    job["attempts"] += 1
    return job["attempts"] < MAX_ATTEMPTS
