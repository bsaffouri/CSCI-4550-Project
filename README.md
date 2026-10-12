# CSCI 4550 Mini Internet Project

A small virtual internet built in Python 3 using UDP sockets. Two hosts exchange messages through four routers, each running as its own process on one machine. After the common network works, we extend it with **Track B: reliable transfer** (stop-and-wait with ACKs, timeouts, retransmission and duplicate detection).

## Team

| Member | Area |
|---|---|
| Aida Bah | Packets & Hosts |
| Breona Saffouri | Routers & Configs |
| Sahand Darwish | Conditions, Logs & Evidence |

## Topology

```
              RB
             /  \
H1 —— RA          RD —— H2
             \  /
              RC
```

All links are bidirectional. H1 and H2 are never neighbors, so all traffic passes through the routers. The upper path goes through RB and the lower path through RC; the active path is chosen by the static forwarding tables.

### Devices

| Device | Virtual address | UDP endpoint |
|---|---|---|
| Host 1 | H1 | 127.0.0.1:50001 |
| Router A | RA | 127.0.0.1:50002 |
| Router B | RB | 127.0.0.1:50003 |
| Router C | RC | 127.0.0.1:50004 |
| Router D | RD | 127.0.0.1:50005 |
| Host 2 | H2 | 127.0.0.1:50006 |

Ports 50001–50006 avoid conflicts with port 5000, which macOS uses.

### Links

| Link | Role |
|---|---|
| H1 ↔ RA | edge |
| RA ↔ RB | upper path |
| RB ↔ RD | upper path |
| RA ↔ RC | lower path |
| RC ↔ RD | lower path |
| RD ↔ H2 | edge |

## Requirements

- Python 3 
- Wireshark (for packet captures)

## Setup and launch

Use Python 3. Start each process in a separate terminal from the project root.
For an initial host-only check, start the fake router first and then the host:

```powershell
python tests\fake_neighbor.py RA --mode echo
python src\host.py H1 --count 4 --interval 1 --timeout 2
```

The fake neighbor supports `echo`, `drop`, and `silent` modes for probe tests.
Use `--mode send --target H1` to send a packet to a host and check its responder
behavior. `python -m unittest discover -s tests` runs the packet tests.

The host's `--count` defaults to `0`, which leaves it listening and responding
without sending probes. H1 listens on port 50001 and sends to its configured
neighbor RA on port 50002; H2 listens on port 50006 and sends to RD on port
50005. The topology is defined in `config\topology.json`.

## Wireshark

Capture on the loopback interface and filter to project ports:

```
udp.port >= 50001 && udp.port <= 50006
```
