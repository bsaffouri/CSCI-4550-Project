import argparse
import json
import socket
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from packet import PacketError, decode_packet, encode_packet

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "topology.json"

def endpoint_for(config_path, device):
    try:
        with config_path.open(encoding="utf-8") as config_file:
            topology = json.load(config_file)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load topology config {config_path}: {exc}") from exc
    devices = topology.get("devices") if isinstance(topology, dict) else None
    if not isinstance(devices, dict) or device not in devices:
        raise ValueError(f"device {device!r} is not present in topology")
    entry = devices[device]
    if not isinstance(entry, dict) or not isinstance(entry.get("host"), str):
        raise ValueError(f"topology entry for {device} needs a text host and port")
    port = entry.get("port")
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError(f"topology port for {device} must be between 1 and 65535")
    return entry["host"], port

def run(args):
    my_endpoint =endpoint_for(args.config, args.device)
    try:
        with args.config.open(encoding="utf-8") as config_file:
            topology = json.load(config_file)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load topology config {args.config}: {exc}") from exc
    neighbors = topology["devices"][args.device]["neighbors"]
    try:
        with args.forwarding.open(encoding="utf-8") as forwarding_file:
            forwarding = json.load(forwarding_file)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load forwarding table {args.forwarding}: {exc}") from exc
    table = forwarding.get(args.device)
    if table is None:
        raise ValueError(f"{args.device} has no entries in {args.forwarding}")

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(my_endpoint)
        sock.settimeout(0.2)
        print(
            f"router {args.device} listening on "
            f"{my_endpoint[0]}:{my_endpoint[1]}"
        )
        while True:
            try:
                data, sender = sock.recvfrom(65535)
            except socket.timeout:
                continue
            try:
                packet = decode_packet(data)
            except PacketError as exc:
                print(f"received invalid packet from {sender}: {exc}")
                continue

            print(f"received from {sender}: {packet}")

            if packet["hop_limit"] <= 1:
                print(f"{args.device} DROP hop limit: {packet}")
                continue
            next_hop = table.get(packet["dst"])

            if next_hop is None:
                print(f"{args.device} DROP unknown destination {packet['dst']}")
                continue

            if next_hop not in neighbors:
              print (f"{args.device} DROP invalid next hop {next_hop}")
              continue   

            packet["hop_limit"] -= 1
            sock.sendto(encode_packet(packet), endpoint_for(args.config, next_hop))
            print(f"{args.device} FORWARD to {next_hop}: {packet}")
            
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