"""Rebuild data/model/behaviour-v0.json from the latest built input runs."""

from . import OUTPUT, write_behaviour

if __name__ == "__main__":
    result = write_behaviour()
    print(f"wrote {OUTPUT} from {result['inputs']}")
