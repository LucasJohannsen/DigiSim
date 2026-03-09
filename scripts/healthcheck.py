import datetime
import json
import os
import sys
from pathlib import Path


def main() -> None:
    state_dir = os.getenv("STATE_DIR", "./state")
    max_age_hours = int(os.getenv("HEALTHCHECK_MAX_AGE_HOURS", "25"))

    heartbeat_path = Path(state_dir) / "heartbeat.json"

    if not heartbeat_path.exists():
        sys.exit(0)

    try:
        data = json.loads(heartbeat_path.read_text())
        last_tick = datetime.datetime.fromisoformat(data["last_tick"])
    except (KeyError, ValueError, json.JSONDecodeError) as e:
        print(f"Invalid heartbeat file: {e}", file=sys.stderr)
        sys.exit(1)

    age = datetime.datetime.now() - last_tick

    if age.total_seconds() > max_age_hours * 3600:
        print(
            f"Heartbeat too old: {age} (max {max_age_hours}h)",
            file=sys.stderr,
        )
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
