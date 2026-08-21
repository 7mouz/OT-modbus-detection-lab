# Modbus baseline (what "normal" looks like)

Derived from a live loopback capture of the running pasteurizer lab.

- **Capture:** `captures/normal-baseline.pcap`
- **Interface:** `lo` (127.0.0.1) · **Filter:** `tcp port 502` · ~18,800 packets, ~2 min
- **Method:** `tcpdump` to pcap, decoded with `tshark`/Wireshark (Modbus dissector)

## Function codes observed (whole capture)
| FC | Meaning | Count (msgs) |
|---|---|---|
| 1  | Read Coils            | 8760 |
| 3  | Read Holding Registers| 5602 |
| 6  | Write Single Register | 2472 |

No FC5 / FC15 (write coils), no FC16 (write multiple registers), nothing else.

## Clients and their roles (distinguished by TCP source port)
> On loopback every client is `127.0.0.1`, so we identify them by connection/port,
> not IP. In a real plant these would be separate hosts on the OT segment.

| Src port | Identity | Reads | Writes (FC6) |
|---|---|---|---|
| 35760 | **plant.py** (physics)   | coils 1,8 (Pump, Discharge); reg 4 (HeaterPower) | **reg 0 (Temperature), reg 1 (Level)** |
| 53789 | **Node-RED HMI** (poll)  | all coils + all registers | none |
| 53250 | **Node-RED HMI** (control) | coils + registers | **reg 2 (TempSetpoint), reg 3 (LevelSetpoint)** |

Observed write breakdown (FC6 requests):
- plant  -> reg0 x605, reg1 x605
- HMI    -> reg2 x25, reg3 x1   (the operator moving setpoint sliders during capture)

## The baseline rules (the fingerprint)
1. The **plant** writes ONLY regs 0-1 (process values).
2. The **operator/HMI** writes ONLY regs 2-3 (setpoints).
3. **No client writes any coil** - the PLC owns all coils (%QX0.0-%QX1.0).
4. **No client writes regs 4-5** (HeaterPower, HoldSecs are PLC-computed, read-only).
5. Only FC1, FC3, FC6 appear on the wire.

## Therefore, anything below is anomalous
- A **coil write** (FC5/FC15) from anyone - e.g. forcing `BatchSafe` (coil 6) or
  `Discharge` (coil 8). Nothing legitimate ever writes a coil.
- A **write to a setpoint (reg 2/3) from a source that is not the HMI connection** -
  e.g. an attacker lowering `TempSetpoint` below 63 so unsafe milk passes.
- A **write to regs 0/1 from a non-plant source**, or a write to read-only regs 4/5.
- An **unusual function code** (anything other than 1/3/6).
- A **new/unexpected TCP connection** to :502 that wasn't in the baseline.

That last set is exactly the "why it was detectable" reasoning for the writeup.
