"""UDP host process for H1 or H2."""

import argparse
import json
import socket
import time
from pathlib import Path

from packet import PacketError, decode_packet, encode_packet


DEFAULT_HOP_LIMIT = 8
RECEIVE_POLL_SECONDS = 0.05
DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "topology.json"


def load_host_config(config_path, device):
    try:
        with config_path.open(encoding="utf-8") as config_file:
            topology = json.load(config_file)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load topology config {config_path}: {exc}") from exc

    devices = topology.get("devices") if isinstance(topology, dict) else None
    if not isinstance(devices, dict):
        raise ValueError("topology config must contain a 'devices' object")
    if device not in devices:
        raise ValueError(f"device {device!r} is not present in {config_path}")

    own = devices[device]
    if not isinstance(own, dict):
        raise ValueError(f"topology entry for {device} must be an object")
    neighbors = own.get("neighbors")
    if not isinstance(neighbors, list) or len(neighbors) != 1:
        raise ValueError(f"topology entry for {device} must have exactly one neighbor")

    neighbor_id = neighbors[0]
    neighbor = devices.get(neighbor_id)
    if not isinstance(neighbor, dict):
        raise ValueError(f"neighbor {neighbor_id!r} is not present in topology")

    for entry_id, entry in ((device, own), (neighbor_id, neighbor)):
        if not isinstance(entry.get("host"), str) or type(entry.get("port")) is not int:
            raise ValueError(
                f"topology entry for {entry_id} needs a text host and integer port"
            )
        if not 1 <= entry["port"] <= 65535:
            raise ValueError(f"topology port for {entry_id} must be between 1 and 65535")

    peers = [name for name in devices if name.startswith("H") and name != device]
    if len(peers) != 1:
        raise ValueError("topology must contain exactly one other host")
    return own, neighbor, neighbor_id, peers[0]


def run_host(device, count, interval, timeout, config_path):
    own, neighbor, neighbor_id, peer = load_host_config(config_path, device)
    own_endpoint = (own["host"], own["port"])
    neighbor_endpoint = (neighbor["host"], neighbor["port"])
    waiting = {}
    received = []
    timed_out = 0
    next_msg_id = 1
    sent = 0

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(own_endpoint)
        sock.settimeout(RECEIVE_POLL_SECONDS)
        print(f"{device} listening on {own_endpoint[0]}:{own_endpoint[1]}")

        def expire_probes(now):
            nonlocal timed_out
            expired = [
                msg_id
                for msg_id, sent_at in waiting.items()
                if now - sent_at > timeout
            ]
            for msg_id in expired:
                del waiting[msg_id]
                timed_out += 1
                print(f"probe {msg_id} timed out")

        next_send_at = time.monotonic()
        final_deadline = None
        while True:
            now = time.monotonic()
            expire_probes(now)

            if sent < count and now >= next_send_at:
                packet = {
                    "src": device,
                    "dst": peer,
                    "hop_limit": DEFAULT_HOP_LIMIT,
                    "type": "PROBE",
                    "msg_id": next_msg_id,
                    "payload": f"probe {next_msg_id}",
                }
                sock.sendto(encode_packet(packet), neighbor_endpoint)
                waiting[next_msg_id] = now
                print(
                    f"sent probe {next_msg_id} to {peer} via "
                    f"{neighbor_id} at {neighbor_endpoint[0]}:{neighbor_endpoint[1]}"
                )
                sent += 1
                next_msg_id += 1
                next_send_at = now + interval
                if sent == count:
                    final_deadline = now + timeout

            finished_sending = count > 0 and sent == count
            if finished_sending and (
                not waiting or time.monotonic() >= final_deadline
            ):
                expire_probes(time.monotonic())
                break

            try:
                data, sender = sock.recvfrom(65535)
            except socket.timeout:
                continue
            except ConnectionResetError as exc:
                print(f"neighbor reported an unreachable UDP destination: {exc}")
                continue

            try:
                packet = decode_packet(data)
            except PacketError as exc:
                print(f"invalid packet, dropped: {exc}")
                continue

            if packet["dst"] != device:
                print(f"packet for {packet['dst']} received by {device}, ignored")
                continue

            if packet["type"] == "PROBE":
                echo = {
                    "src": device,
                    "dst": packet["src"],
                    "hop_limit": DEFAULT_HOP_LIMIT,
                    "type": "ECHO",
                    "msg_id": packet["msg_id"],
                    "payload": packet["payload"],
                }
                sock.sendto(encode_packet(echo), neighbor_endpoint)
                print(
                    f"received probe {packet['msg_id']} from {packet['src']}; "
                    f"sent ECHO via {neighbor['host']}:{neighbor['port']}"
                )
            else:
                sent_at = waiting.pop(packet["msg_id"], None)
                if sent_at is None:
                    print(f"unmatched or late ECHO {packet['msg_id']} from {sender}")
                    continue
                elapsed = time.monotonic() - sent_at
                if elapsed > timeout:
                    timed_out += 1
                    print(f"late ECHO {packet['msg_id']} from {sender}; probe timed out")
                    continue
                received.append(elapsed)
                print(f"received ECHO {packet['msg_id']}; RTT {elapsed * 1000:.2f} ms")

    if count > 0:
        mean_rtt = sum(received) / len(received) if received else 0.0
        min_rtt = min(received) if received else 0.0
        max_rtt = max(received) if received else 0.0
        print(
            f"summary: sent={sent}, received={len(received)}, timeouts={timed_out}, "
            f"mean_rtt={mean_rtt * 1000:.2f} ms, min_rtt={min_rtt * 1000:.2f} ms, "
            f"max_rtt={max_rtt * 1000:.2f} ms"
        )


def main():
    parser = argparse.ArgumentParser(description="Run a UDP host for the mini internet.")
    parser.add_argument("device", choices=("H1", "H2"), help="host identity")
    parser.add_argument(
        "--count", type=int, default=0, help="number of probes to send (0 listens only)"
    )
    parser.add_argument(
        "--interval", type=float, default=1.0, help="seconds between probes"
    )
    parser.add_argument(
        "--timeout", type=float, default=2.0, help="probe timeout in seconds"
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="topology JSON path")
    args = parser.parse_args()

    if args.count < 0:
        parser.error("--count must be at least 0")
    if args.interval < 0:
        parser.error("--interval must be at least 0")
    if args.timeout <= 0:
        parser.error("--timeout must be greater than 0")

    try:
        run_host(args.device, args.count, args.interval, args.timeout, args.config)
    except ValueError as exc:
        parser.error(str(exc))
    except OSError as exc:
        parser.error(f"host socket error: {exc}")


if __name__ == "__main__":
    main()
