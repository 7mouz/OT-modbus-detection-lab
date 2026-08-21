# Running Zeek (the passive OT sensor)

How to reproduce the results. Zeek reads a pcap (offline) or a live
interface, parses Modbus into structured logs, and raises a Notice when
`detection/detect.zeek` sees a baseline violation.

## Two gotchas
- **Zeek is not on PATH.** It lives in `/opt/zeek/bin/`. Add it once per shell:
  ```
  export PATH=/opt/zeek/bin:$PATH
  ```
- **Zeek writes logs into the current directory.** `cd` into an empty working
  folder before each run, or the logs scatter.

## Core pattern
```
zeek -C -r <pcap> [detection/detect.zeek]
```
- `-r <pcap>`  read from a capture (offline / replay)
- `-C`         ignore bad checksums (REQUIRED for loopback captures, or Zeek
               drops every packet and the logs come out empty)
- add the script to load the detection logic

## 1. Parse traffic into logs
```
mkdir -p ~/zeek-run && cd ~/zeek-run
zeek -C -r <repo>/captures/normal-clean.pcap
ls                 # -> conn.log  modbus.log  packet_filter.log
```

## 2. Read the logs (zeek-cut pulls named columns from the TSV)
```
zeek-cut ts id.orig_p id.resp_p func < modbus.log | head
zeek-cut func < modbus.log | sort | uniq -c      # function-code counts
```

## 3. Validate the detector on CLEAN traffic (tune) -> expect no notice.log
```
mkdir -p ~/zeek-clean && cd ~/zeek-clean
zeek -C -r <repo>/captures/normal-clean.pcap <repo>/detection/detect.zeek
ls notice.log 2>/dev/null || echo "no alerts on clean traffic (good)"
```

## 4. Run the detector on the ATTACK (test) -> expect exactly one alert
```
mkdir -p ~/zeek-attack && cd ~/zeek-attack
zeek -C -r <repo>/captures/attack.pcap <repo>/detection/detect.zeek
zeek-cut note msg < notice.log
# -> Pasteurizer::Unsafe_Setpoint  TempSetpoint (reg 2) set to 30 C ... from 127.0.0.1:<port>
```

## Live mode (real-time instead of a pcap) -- needs root, like tcpdump
```
sudo /opt/zeek/bin/zeek -C -i lo <repo>/detection/detect.zeek
```
Sits watching `lo`; fire the attack in another terminal and the notice appears
live. Ctrl-C to stop.

## Capturing a pcap in the first place (tcpdump)
```
sudo tcpdump -Z root -i lo -w <repo>/captures/<name>.pcap 'tcp port 502'
```
- `-Z root` keeps tcpdump as root so it does not try to chown the savefile
- run ~2 min, Ctrl-C to stop

> Replace `<repo>` with the repo path (e.g. the folder that holds `captures/`
> and `detection/`).

## ICSNPP-Modbus (richer parsing, optional)

Zeek's built-in `modbus.log` gives the function code but not the register or value.
The ICSNPP-Modbus parser (Idaho National Lab / CISA) adds `modbus_detailed.log`, which
logs the register address and value on every request. Our `detect.zeek` does not need
it (it reads the register/value straight off the built-in events), but the detailed log
is a much better forensic view.

Install with Zeek's package manager:
```
zkg install icsnpp-modbus
```
(user-local install needs no sudo; a system-wide install for all users needs sudo.)

Load it in a run, before or alongside the detection script:
```
zeek -C -r captures/attack.pcap icsnpp-modbus detection/detect.zeek
```
Then the detailed log shows every write with its register and value:
```
zeek-cut id.orig_p func address request_values < modbus_detailed.log \
  | awk '$2=="WRITE_SINGLE_REGISTER" && $3==2'
# 39470  WRITE_SINGLE_REGISTER  2  30     <- the attacker's setpoint write
```
