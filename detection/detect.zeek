##! Modbus baseline-violation detection for the pasteurizer lab.
##! Passive. Run on a capture:   zeek -C -r captures/attack.pcap detection/detect.zeek
##! or live:                     sudo zeek -C -i lo detection/detect.zeek
##! Baseline facts come from docs/baseline.md.

module Pasteurizer;

export {
    redef enum Notice::Type += {
        Unsafe_Setpoint,   ## a setpoint driven below the pasteurization minimum
        Coil_Write,        ## any coil write (baseline has NONE)
        Readonly_Write,    ## write to a PLC-owned / read-only register
    };

    const SAFE_TEMP_MIN  = 63 &redef;                       ## pasteurization minimum, deg C
    const TEMP_SETPT_REG = 2  &redef;                       ## reg 2 = TempSetpoint
    const WRITABLE_REGS: set[count] = { 0, 1, 2, 3 } &redef; ## plant=0/1, operator=2/3; 4/5 read-only
}

# FC6 - Write Single Register
event modbus_write_single_register_request(c: connection, headers: ModbusHeaders,
                                            address: count, value: count)
{
    local src = fmt("%s:%d", c$id$orig_h, c$id$orig_p);

    if ( address == TEMP_SETPT_REG && value < SAFE_TEMP_MIN )
        NOTICE([$note=Unsafe_Setpoint, $conn=c,
                $msg=fmt("TempSetpoint (reg %d) set to %d C -- below the %d C pasteurization minimum -- from %s",
                         address, value, SAFE_TEMP_MIN, src)]);
    else if ( address !in WRITABLE_REGS )
        NOTICE([$note=Readonly_Write, $conn=c,
                $msg=fmt("Write to non-writable register %d (value %d) from %s", address, value, src)]);
}

# FC5 - Write Single Coil : nothing legitimate ever writes a coil
event modbus_write_single_coil_request(c: connection, headers: ModbusHeaders,
                                       address: count, value: bool)
{
    NOTICE([$note=Coil_Write, $conn=c,
            $msg=fmt("Coil %d forced to %s from %s:%d -- no legitimate client writes coils",
                     address, value, c$id$orig_h, c$id$orig_p)]);
}
