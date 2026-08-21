# Pasteurizer - tag / register map

**Process:** batch (vat) milk pasteurization. Fill the vat, heat the milk to the
pasteurization setpoint (63 C), hold at temperature for the hold time (30 min real,
compressed to ~30 s in simulation), then release only if the hold was met, otherwise
divert. Under-pasteurized milk must never be released.

**Modbus:** OpenPLC is the Modbus TCP server on `:502`. IEC `%QX` bits map to Modbus
coils; IEC `%QW` words map to Modbus holding registers.

---

## Holding registers (`%QW`, FC3 read / FC6 write)

| Tag | IEC | Reg | Type | Units | Written by | Description |
|---|---|---|---|---|---|---|
| `Temperature`   | `%QW0` | 0 | INT | C | **plant**    | milk temperature in the vat |
| `Level`         | `%QW1` | 1 | INT | % | **plant**    | milk level in the vat |
| `TempSetpoint`  | `%QW2` | 2 | INT | C | **operator** | pasteurization target (63) |
| `LevelSetpoint` | `%QW3` | 3 | INT | % | **operator** | fill-level target |
| `HeaterPower`   | `%QW4` | 4 | INT | % | **PLC**      | PID heater command 0-100; read by the plant |
| `HoldSecs`      | `%QW5` | 5 | INT | s | **PLC**      | elapsed hold seconds 0-30; read by the HMI |

## Coils (`%QX`, FC1 read / FC5 write)

| Tag | IEC | Coil | Written by | Read by | Description |
|---|---|---|---|---|---|
| `Heater`       | `%QX0.0` | 0 | **PLC** | HMI   | status lamp: TRUE when HeaterPower > 0 |
| `Pump`         | `%QX0.1` | 1 | **PLC** | plant | fill-pump command |
| `AlmPastTemp`  | `%QX0.2` | 2 | **PLC** | HMI   | ALARM: milk below setpoint during the cook |
| `AlmHighTemp`  | `%QX0.3` | 3 | **PLC** | HMI   | ALARM: overheat / scorch |
| `AlmLowLevel`  | `%QX0.4` | 4 | **PLC** | HMI   | ALARM: level low, dry-fire risk (inhibits heater) |
| `AlmHighLevel` | `%QX0.5` | 5 | **PLC** | HMI   | ALARM: overflow risk |
| `BatchSafe`    | `%QX0.6` | 6 | **PLC** | HMI   | pasteurization complete, safe to release |
| `Divert`       | `%QX0.7` | 7 | **PLC** | HMI   | divert / reject (batch not proven safe) |
| `Discharge`    | `%QX1.0` | 8 | **PLC** | plant | discharge valve, open only while emptying |

## Internal (no Modbus location)

| Tag | Type | Purpose |
|---|---|---|
| `AtTemp`       | BOOL | Temperature >= TempSetpoint (enables the hold timer) |
| `TankFull`     | BOOL | Level >= LevelSetpoint (triggers the cook phase) |
| `TankEmpty`    | BOOL | Level <= 3 (ends the empty phase) |
| `Cooking`      | BOOL | state latch: heat + hold phase |
| `Emptying`     | BOOL | state latch: discharge phase |
| `HeatInhibit`  | BOOL | AlmLowLevel OR NOT Cooking (feeds the PID Inhibit) |
| `BelowSP`      | BOOL | Temperature < TempSetpoint (feeds AlmPastTemp) |
| `LevelLow`, `LevelHigh` | BOOL | pump hysteresis flags |
| `LevelLowInt`, `LevelHighInt` | INT | pump band, LevelSetpoint -/+ 5 |
| `TempHiThr`    | INT  | TempSetpoint + 5 (overheat alarm threshold) |
| `HoldTimer`    | TON  | IN = AtTemp AND Cooking, PT = T#30s, Q sets BatchSafe |
| `TempCtrl0`    | TempCtrl | PI temperature controller (anti-windup), outputs HeaterPower |

---

## Control logic summary

- **State machine:** `Cooking := (TankFull OR Cooking) AND NOT Emptying`,
  `Emptying := (BatchSafe OR Emptying) AND NOT TankEmpty`. Together they sequence
  Fill -> Cook -> Empty.
- **Pump:** `(LevelLow OR Pump) AND NOT LevelHigh AND NOT Emptying` (hysteresis, off while emptying).
- **Heat:** the `TempCtrl` PI block drives `HeaterPower`, gated by `HeatInhibit`
  (heat only during the cook, plus the dry-fire interlock).
- **Hold (the CCP):** `HoldTimer` runs while `AtTemp AND Cooking`. It resets if the
  temperature drops, so the milk must be held continuously. `BatchSafe := HoldTimer.Q`.
- **Release:** `Discharge := Emptying`; `Divert := NOT BatchSafe` (fail-safe, defaults ON).
- **Alarms:** `AlmLowLevel` (Level < 20), `AlmHighLevel` (Level > 90),
  `AlmHighTemp` (Temperature > TempHiThr), `AlmPastTemp` (Cooking AND BelowSP).

---

## Baseline: who writes what (the fingerprint)

Over Modbus, external clients only ever do this:
- The **plant** writes only `%QW0` (Temperature) and `%QW1` (Level).
- The **operator/HMI** writes only `%QW2` (TempSetpoint) and `%QW3` (LevelSetpoint).
- Nobody writes any coil, and nobody writes `%QW4`/`%QW5` (the PLC computes those).

Any write that breaks those rules is anomalous by definition: a coil write, a setpoint
write from a source that is not the HMI, or a write to a read-only register. That is
what makes the attack detectable. See `docs/baseline.md`.
