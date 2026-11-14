import time
from contextlib import contextmanager


@contextmanager
def timed(stage: str):
    # one line per stage in the logs (CloudWatch on Lambda), so a slow request shows where the time went
    start = time.perf_counter()
    yield
    print(f"timing {stage}: {time.perf_counter() - start:.1f}s", flush=True)
