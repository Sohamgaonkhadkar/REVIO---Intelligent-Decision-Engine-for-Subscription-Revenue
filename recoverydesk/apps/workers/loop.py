"""Worker entrypoint (`python -m apps.workers.loop` in compose)."""
from apps.workers.loop_worker import main

if __name__ == "__main__":
    raise SystemExit(main())
