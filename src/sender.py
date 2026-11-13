"""Stop-and-wait sender for DATA/ACK reliable transfer."""

import argparse
import socket
import sys
import time
from pathlib import Path

from host import DEFAULT_CONFIG, DEFAULT_HOP_LIMIT, load_host_config
from packet import PacketError, decode_packet, encode_packet


RECEIVE_POLL_SECONDS = 0.05

def wait_for_ack(sock, device, run_id, seq, deadline):
    while time.monotonic() < deadline:
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

        if (
            packet["type"] == "ACK"
            and packet["dst"] == device
            and packet["run_id"] == run_id
            and packet["seq"] == seq
        ):
            return True

        print(
            f"ignored {packet['type']} from {sender} "
            f"(dst={packet['dst']}, run_id={packet.get('run_id')}, "
            f"seq={packet.get('seq')}); waiting for ACK seq={seq}"
        )

    return False


def run_sender(device, count, timeout, retries, run_id, config_path):
    own, neighbor, neighbor_id, peer = load_host_config(config_path, device)
    own_endpoint = (own["host"], own["port"])
    neighbor_endpoint = (neighbor["host"], neighbor["port"])

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(own_endpoint)
        sock.settimeout(RECEIVE_POLL_SECONDS)
        print(f"{device} sender listening on {own_endpoint[0]}:{own_endpoint[1]}")

        delivered = 0
        retransmissions = 0
        failed = False

        for seq in range(count):
            packet = {
                "src": device,
                "dst": peer,
                "hop_limit": DEFAULT_HOP_LIMIT,
                "type": "DATA",
                "msg_id": seq,
                "payload": f"message {seq}",
                "seq": seq,
                "run_id": run_id,
            }
            encoded = encode_packet(packet)
            attempt = 0

            while True:
                sock.sendto(encoded, neighbor_endpoint)
                if attempt > 0:
                    retransmissions += 1
                    print(f"retransmit seq={seq} (attempt {attempt})")
                else:
                    print(f"sent DATA seq={seq} to {peer} via {neighbor_id}")

                deadline = time.monotonic() + timeout
                if wait_for_ack(sock, device, run_id, seq, deadline):
                    delivered += 1
                    print(f"ACK seq={seq}")
                    break

                print(f"timed out on seq={seq}")
                attempt += 1
                if attempt > retries:
                    print(f"FAILED: no ACK for seq={seq} after {retries} retries")
                    failed = True
                    break

            if failed:
                break

        print(f"delivered {delivered}/{count}, retransmissions={retransmissions}")

    return not failed

def main():
    parser = argparse.ArgumentParser(
        description="Send DATA messages with stop-and-wait reliability."
    )
    parser.add_argument("device", choices=("H1", "H2"), help="which host is sending")
    parser.add_argument("--count", type=int, default=10, help="number of messages")
    parser.add_argument(
        "--timeout", type=float, default=0.5, help="seconds to wait for an ACK"
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=5,
        help="resends after the first send (5 means up to 6 sends per message)",
    ) 
    parser.add_argument("--run-id", default="r1", help="run label")  
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="topology JSON path")
    args = parser.parse_args()

    if args.count < 0:
        parser.error("--count must be at least 0")
    if args.timeout <= 0:
        parser.error("--timeout must be greater than 0")
    if args.retries < 0:
        parser.error("--retries must be at least 0")

    try:
        ok = run_sender(
            args.device, args.count, args.timeout, args.retries,
            args.run_id, args.config,
        )
    except ValueError as exc:
        parser.error(str(exc))
    except OSError as exc:
        parser.error(f"sender socket error: {exc}")

    if not ok:
        sys.exit(1)

if __name__ == "__main__":
    main()