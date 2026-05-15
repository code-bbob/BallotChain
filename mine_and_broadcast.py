from __future__ import annotations

import argparse
import sys

import requests


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Mine pending votes on a node and trigger broadcast.",
    )
    parser.add_argument(
        "--node",
        default="http://127.0.0.1:8001",
        help="Base URL of the node (default: http://127.0.0.1:8001)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60,
        help="Request timeout in seconds (default: 60)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    node = args.node.rstrip("/")

    try:
        response = requests.post(f"{node}/mine/cluster?limit=100", timeout=args.timeout)
    except requests.RequestException as error:
        print(f"Request failed: {error}", file=sys.stderr)
        return 1

    if not response.ok:
        print(f"Node returned {response.status_code}: {response.text}", file=sys.stderr)
        return 1

    data = response.json()
    message = data.get("message", "")
    print(message)

    if message == "No pending transactions to mine":
        return 0

    local = data.get("local", {})
    print(f"index={local.get('index') or data.get('index')}")
    print(f"hash={local.get('hash') or data.get('hash')}")
    print(f"nonce={local.get('nonce') or data.get('nonce')}")
    print(f"mining_time_seconds={local.get('mining_time_seconds') or data.get('mining_time_seconds')}")

    broadcast = local.get("broadcast", data.get("broadcast", {}))
    print(
        "broadcast="
        f"accepted:{broadcast.get('accepted', 0)},"
        f"rejected:{broadcast.get('rejected', 0)},"
        f"unreachable:{broadcast.get('unreachable', 0)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
