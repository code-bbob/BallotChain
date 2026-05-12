from __future__ import annotations

import argparse
import json
from pathlib import Path

from crypto_utils import generate_wallet_keys


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a voter wallet keypair.")
    parser.add_argument(
        "--out",
        help="Path to write wallet JSON. If omitted, prints to stdout.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    private_key, public_key = generate_wallet_keys()
    payload = {
        "private_key": private_key,
        "public_key": public_key,
    }

    if args.out:
        output_path = Path(args.out)
        if output_path.parent and not output_path.parent.exists():
            output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Wallet written to {output_path}")
    else:
        print(json.dumps(payload, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
