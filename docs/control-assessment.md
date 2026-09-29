# Security control assessment

This is a security control assessment of the pasteurizer lab against a small set of NIST
SP 800-53 controls. I did it to learn the assessor side of the work: not "does the attack
get detected", but "does this system meet a written control, and if not, what is the risk
and the fix".

**Honesty about scope.** This is a self-assessment of a lab I built, for learning. It is
not an official authorization and there is no real authorizing official. The method follows
NIST SP 800-53A (assessment objectives; the examine / interview / test methods). The OT
interpretation — why a failed control here can still be defended — follows NIST SP 800-82r3.
Control identifiers are looked up in the SP 800-53r5 catalogue as needed; I do not assess
from memory.

---

## System summary (assessor's view)

**System.** A batch milk pasteurizer control system. It fills a vat, heats milk to 63 C,
holds at temperature for the hold time, and releases the batch only if the hold was met,
otherwise diverts. Under-pasteurized milk must never be released.

**Authorization boundary.** Five components on one host (`127.0.0.1`):

| Component | Role | Interface |
|---|---|---|
| OpenPLC | control logic; Modbus TCP **server** | `:502` |
| `process-sim/plant.py` | process physics (temperature, level) | Modbus client |
| Node-RED HMI | operator; the only legitimate source of setpoint writes | Modbus client |
| `attacker/attack.py` | unauthorized client on the segment (threat) | Modbus client |
| Zeek + ICSNPP + `detect.zeek` | passive monitor (logs + alerts) | port mirror of `:502` |

Full register/coil map: `docs/tag-map.md`. Normal write fingerprint: `docs/baseline.md`.

**Data flows worth noting.** All control traffic is Modbus TCP on `:502`, in plaintext,
with no authentication. The HMI writes only `TempSetpoint` (`%QW2`) and `LevelSetpoint`
(`%QW3`). The plant writes only `Temperature` (`%QW0`) and `Level` (`%QW1`). Anything else
is anomalous by definition.

**Notional impact if the system fails (categorization, for context only).**
- *Integrity — High.* A false "batch safe" release is a food-safety event.
- *Availability — Moderate.* A stopped process spoils product but is not itself a safety event.
- *Confidentiality — Low.* No sensitive data on the wire.

This ordering (integrity/safety and availability over confidentiality) is the OT inversion
of the usual IT priority — SP 800-82 §4.1.

---

## Method

For each control I state:
- **Assessment objective** — the thing I am proving true or false, in plain terms.
- **Method** — examine (read it), interview (ask about it), test (try it). I note which I used.
- **Finding** — *satisfied*, *other than satisfied*, or *not applicable*, with the reason.
- **Evidence** — the file, capture, or config that backs the finding.

Findings then roll up into the POA&M at the bottom.

---

## Controls assessed

### IA-2 — Identification and Authentication (organizational users)  · Finding: OTHER THAN SATISFIED

**Assessment objective.** Determine whether the system identifies and authenticates the
entity issuing control commands before acting on them — i.e. whether a command can be
attributed to a known, authorized source.

**Method.**
- *Examine* — the OpenPLC Modbus server configuration and the Modbus TCP protocol itself.
  Modbus TCP carries no authentication: no user, no credential, no session identity. The
  server acts on any well-formed request that reaches `:502`.
- *Test* — ran `attacker/attack.py`, which opens a Modbus TCP session to `:502` and writes
  `TempSetpoint` (`%QW2`) although it is not the HMI. The PLC accepted and acted on the write.
- *Interview* — N/A; I am the system owner. Noted rather than skipped.

**Finding: OTHER THAN SATISFIED.** The control channel authenticates neither the user nor
the device. Any host that can reach `:502` can issue control commands, and there is no way
to attribute a command to a source.

*(Scoping note, so this is not confused with IA-3. Modbus has no authentication of any kind
on the control channel, so both user identification/authentication [IA-2] and device
identification/authentication [IA-3] fail for the same root reason. I record the finding
under IA-2 and note IA-3 inherits it.)*

**Evidence.**
- `attacker/attack.py` — the unauthorized write, from a client that is not the HMI.
- `captures/attack.pcap` — the write on the wire (Modbus FC6 to `%QW2` from the attacker).
- `detection/detect.zeek` — flags it precisely *because* the protocol cannot, i.e. by source
  and register rather than by identity.

**OT interpretation (SP 800-82).** This is not a defect unique to my lab — it is
characteristic of OT protocols. Modbus predates authentication and you cannot add it without
breaking the protocol. So the remediation is not "fix Modbus"; it is compensating controls:
segment the network so few hosts can reach `:502`, and monitor for writes that violate the
baseline. That is why IA-2 fails and the system is still defensible.

---

### SC-8 — Transmission Confidentiality and Integrity  · Finding: _to assess_

> Template for me to fill next. Objective: does the system protect control traffic from
> disclosure and modification in transit? (Modbus TCP is plaintext, no integrity check —
> mirror the IA-2 reasoning: examine the protocol, test with the capture in
> `captures/attack.pcap`, cite the OT compensating-control interpretation.)

### AC-3 / AC-6 — Access Enforcement / Least Privilege  · Finding: _to assess_

> Objective: does the system restrict what a connected client is allowed to do? (No
> read/write authorization on registers or coils — any client can write any writable point.)

### SI-4 — System Monitoring  · Finding: _to assess (this is the compensating control that PASSES)_

> Objective: does the system detect unauthorized or anomalous activity? This is where the
> Zeek + ICSNPP detection earns a *satisfied (compensating)* finding — detect not prevent.
> Evidence: `detection/detect.zeek`, `docs/baseline.md`, the alert screenshot.

### AU-2 / AU-3 — Event Logging / Content of Records  · Finding: _to assess_

> Objective: are the right events logged, with enough content to reconstruct what happened?
> Evidence: the Zeek Modbus logs (`detection/zeek-attack`, `detection/zeek-baseline`).

### CM-2 — Baseline Configuration  · Finding: _to assess (likely SATISFIED)_

> Objective: is there a documented baseline of the system's normal state? Evidence:
> `docs/baseline.md` (the normal write fingerprint) and `docs/tag-map.md`.

---

## POA&M — plan of action and milestones

Findings that are *other than satisfied* become POA&M items: the weakness, the risk if left
unfixed, the fix, resources, a milestone date, and the residual risk once fixed.

| ID | Weakness | Risk if unfixed | Remediation | Resources | Milestone | Residual risk |
|---|---|---|---|---|---|---|
| POA&M-01 (IA-2) | No authentication on the Modbus control channel | Any host reaching `:502` can issue control commands — e.g. lower `TempSetpoint` so an under-pasteurized batch is released while the operator screen still reads normal | Segment the OT network; restrict `:502` to the HMI host by firewall/ACL; run Zeek/ICSNPP monitoring to detect writes that violate the baseline (SI-4 compensating); long term, front the PLC with an authenticating gateway | Firewall/VLAN config; the Zeek sensor (already built) | _date_ | Reduced, not eliminated — segmentation limits *who* can reach `:502`; monitoring detects but does not prevent. Accepted. |

*(Add a row per other-than-satisfied finding as I assess SC-8, AC-3/AC-6, etc.)*
