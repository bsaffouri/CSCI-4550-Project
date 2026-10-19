import argparse
import json
import socket
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from packet import PacketError, decode_packet, encode_packet

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "topology.json"

def run(args):
    print(args.device, args.forwarding, args.config)

def main():
    parser = argparse.ArgumentParser(
        description="Run a static router for the mini internet."
    )
    parser.add_argument("device", choices=("RA", "RD", "RB", "RC"), help="router identity")

    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--forwarding", type=Path, required=True)

    args = parser.parse_args()
    try:
        run(args)
    except (ValueError, PacketError) as exc:
        parser.error(str(exc))
    except OSError as exc:
            parser.error(f"router socket error: {exc}")

if __name__ == "__main__":
    main()