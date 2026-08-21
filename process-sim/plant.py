#!/usr/bin/env python3
"""
Process simulator (the physics) for the pasteurizer lab.

The PLC runs the control logic but does not model physics, so on its own the
temperature and level would never move. This script closes the loop. Each tick it
reads the PLC's outputs over Modbus (heater power, pump, discharge valve), updates
the process values (temperature and level), and writes them back to the PLC's input
registers. That feedback makes the vat behave like a real tank instead of static
numbers, and it is what produces the "normal" traffic the detection baselines.

Simplification: temperature is modeled for the vat as a whole and does not reset
when a fresh batch of cold milk is loaded, so a fast cycle can start a little warm.
It is good enough for the traffic and detection work, a mixing model would make it
more realistic.
"""
from pymodbus.client import ModbusTcpClient
import time

HOST, PORT = "127.0.0.1", 502

# Modbus map (matches docs/tag-map.md). "we read"  = the PLC computes it,
# the plant consumes it;  "we write" = the plant is the sensor for it.
REG_TEMP        = 0   # we write : Temperature  (deg C)
REG_LEVEL       = 1   # we write : Level        (percent)
REG_HEATERPOWER = 4   # we read  : PID heater command 0-100 %
COIL_PUMP       = 1   # we read  : fill pump on/off
COIL_DISCHARGE  = 8   # we read  : discharge valve (%QX1.0)

# Physics constants (per-SECOND rates; loss is a fraction/s)
AMBIENT, HEAT_RATE, LOSS = 20, 4, 0.05
FILL_RATE, DRAIN_RATE    = 2, 5          # percent/s: pump fills slow, valve dumps fast
DT = 0.2                                 # plant tick (s): 5x faster than 1s so the
                                         # PID (20 ms scan) sees fresh temperature sooner

def connect():
    c = ModbusTcpClient(HOST, port=PORT)
    c.connect()
    return c

c = connect()
temp  = 20.0
level = 50.0

while True:
      try:
          heater_power = c.read_holding_registers(REG_HEATERPOWER, count=1).registers[0]
          pump         = c.read_coils(COIL_PUMP,      count=1).bits[0]
          discharge    = c.read_coils(COIL_DISCHARGE, count=1).bits[0]
      except Exception as e:
          print("modbus read failed, reconnecting:", e, flush=True)
          try: c.close()
          except Exception: pass
          time.sleep(1); c = connect(); continue

      # temperature: heat in from the jacket, always losing to ambient
      heat_gain = (heater_power / 100) * HEAT_RATE       # deg C / s in
      heat_loss = (temp - AMBIENT) * LOSS                # deg C / s out
      temp = max(AMBIENT, min(100, temp + (heat_gain - heat_loss) * DT))

      # a sealed vat only changes level when the pump fills it or the valve dumps it
      if   discharge: level = level - DRAIN_RATE * DT    # emptying the batch to containers
      elif pump:      level = level + FILL_RATE  * DT    # filling
      else:           level = level                      # holding (cook/hold phase)
      level = max(0, min(100, level))

      try:
          c.write_register(REG_TEMP,  int(temp))
          c.write_register(REG_LEVEL, int(level))
      except Exception as e:
          print("modbus write failed, reconnecting:", e, flush=True)
          try: c.close()
          except Exception: pass
          time.sleep(1); c = connect(); continue

      print(f"power={heater_power:3d}%  temp={temp:6.1f}  level={int(level):3d}  "
            f"pump={pump:d} discharge={discharge:d}", flush=True)
      time.sleep(DT)
