"""Read chip identity and compare the installed camera test image using ST-LINK."""
import json
from datetime import datetime
from pathlib import Path
import sys

TOOLS_DIRECTORY = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIRECTORY / "pyocd"))

from intelhex import IntelHex
from pyocd.core.helpers import ConnectHelper
from pyocd.core.exceptions import TransferError
from pyocd.coresight.ap import APv1Address

project = TOOLS_DIRECTORY.parent / "camera-pulse-test"
session = ConnectHelper.session_with_chosen_probe(
    unique_id="37FF71064E5734361EFA1A43",
    target_override="cortex_m",
    options={
        "connect_mode": "attach",
        "auto_unlock": False,
        "resume_on_disconnect": False,
        "frequency": 1000000,
        "cache.read_memory": False,
        "cache.read_registers": False,
    },
)
if session is None:
    raise RuntimeError("Requested ST-LINK not found")

report = {"time": datetime.now().astimezone().isoformat(), "read_errors": {}}

def read_value(name, operation):
    try:
        value = operation()
        report[name] = value
        return value
    except TransferError as error:
        report["read_errors"][name] = str(error)
        print(f"READ FAILED {name}: {error}")
        return None

try:
    session.open(init_board=False)
    probe = session.probe
    probe.connect()
    probe.write_dp(0x04, 0x50000000)  # Request debug/system power for AP reads.
    report["dp_idcode"] = hex(probe.read_dp(0x00))
    report["dp_ctrlstat"] = hex(probe.read_dp(0x04))
    target = probe.get_memory_interface_for_ap(APv1Address(0))
    rom_base = probe.read_ap(0xF8) & ~3
    report["rom_table_base"] = hex(rom_base)
    for name, address in {
        "cpuid": 0xE000ED00,
        "dbgmcu_idcode": 0xE0042000,
        "dbgmcu_cr": 0xE0042004,
        "dhcsr": 0xE000EDF0,
        "pidr1": rom_base + 0xFE4,
        "pidr2": rom_base + 0xFE8,
        "completed_pulses_address": 0x20000000,
        "test_complete_address": 0x20000004,
        "gpioa_crl": 0x40010800,
        "gpioa_idr": 0x40010808,
        "gpioa_odr": 0x4001080C,
        "tim2_cr1": 0x40000000,
        "tim2_cnt": 0x40000024,
        "scb_vtor": 0xE000ED08,
        "rcc_cfgr": 0x40021004,
    }.items():
        read_value(name, lambda address=address: target.read32(address))
    read_value("flash_size_kib_register", lambda: target.read16(0x1FFFF7E0))
    if "pidr1" in report and "pidr2" in report:
        report["manufacturer_check_value"] = hex(((report["pidr2"] & 7) << 4) |
                                                  ((report["pidr1"] >> 4) & 15))
        report["expected_st_manufacturer_value"] = "0x20"
    image = IntelHex(str(project / "build-keil" / "camera-pulse-test.hex"))
    start, end = image.minaddr(), image.maxaddr()
    if start != 0x08000000 or end >= 0x08010000:
        raise RuntimeError("Unexpected firmware address range")
    expected = bytes(image.tobinarray(start=start, end=end))
    read_value("firmware_matches_keil_hex",
               lambda: bytes(target.read_memory_block8(start, len(expected))) == expected)
    report["firmware_bytes_requested"] = len(expected)
finally:
    session.close()

output = project / ("chip-read-" + datetime.now().strftime("%Y%m%d-%H%M%S") + ".json")
output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2))
print(f"Saved {output}")
