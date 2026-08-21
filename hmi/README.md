# HMI (Node-RED)

Operator dashboard for the pasteurizer. It polls the PLC over Modbus and renders a P&ID-style mimic of the vat. The mimic shows a shaded vessel, live temperature/level/heat readouts, a BATCH SAFE / DIVERT banner, a pasteurization hold countdown, and an alarm annunciator. Setpoints are written back with two sliders. Built on Dashboard 2.0.

## Import
1. Node-RED menu -> Import -> select `flow.json` -> Import.
2. Deploy.
3. Open the dashboard at `http://localhost:1880/dashboard`.

## Requires
- `node-red-contrib-modbus` 5.60.2
- `@flowfuse/node-red-dashboard` 1.30.2

The mimic is a single `ui-template` fed by all the Modbus reads (each tagged with a
`msg.topic`); it keeps a small reactive store keyed by topic. Setpoint sliders are
commit-only (`outs: end`) so a setpoint change is a single write, not a stream.
