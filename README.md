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

TODO: add exact commands once the launcher or startup steps are finalized.

## Wireshark

Capture on the loopback interface and filter to project ports:

```
udp.port >= 50001 && udp.port <= 50006
```
