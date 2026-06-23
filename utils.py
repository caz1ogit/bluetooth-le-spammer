"""Shared utilities for MAC address manipulation, terminal color output, and permission checking."""

import os
import re
import subprocess
import time
from enum import Enum


class BluetoothSpammerError(Exception):
    """Base exception for bluetooth-le-spammer errors."""


MAC_REGEX = re.compile(r'^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$')


class Color(Enum):
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def validate_mac(mac: str) -> bool:
    """Check if a string is a valid MAC address in XX:XX:XX:XX:XX:XX format.

    Args:
        mac: The MAC address string to validate.

    Returns:
        True if the MAC address is valid, False otherwise.
    """
    if not isinstance(mac, str) or not mac:
        return False
    return MAC_REGEX.match(mac.strip()) is not None


def format_mac(mac: str) -> str:
    """Normalize a MAC address to uppercase XX:XX:XX:XX:XX:XX format.

    Args:
        mac: The MAC address string to format.

    Returns:
        The MAC address in uppercase canonical form.

    Raises:
        ValueError: If the input is not a valid MAC address.
    """
    mac = mac.strip().upper()
    if not validate_mac(mac):
        raise ValueError(f"Invalid MAC address: {mac}")
    return mac


def _get_local_mac_via_scapy(interface: int) -> str | None:
    """Try to obtain the local MAC address using Scapy's BluetoothHCISocket.

    Args:
        interface: The HCI interface index.

    Returns:
        The local MAC address string, or None if Scapy is unavailable or fails.
    """
    try:
        from scapy.layers.bluetooth import (
            BluetoothHCISocket, HCI_Hdr, HCI_Command_Hdr,
            HCI_Cmd_Read_BD_Addr, HCI_Event
        )
        sock = BluetoothHCISocket(interface)
        pkt = HCI_Hdr() / HCI_Command_Hdr() / HCI_Cmd_Read_BD_Addr()
        sock.send(pkt)
        time.sleep(0.2)
        resp = sock.recv()
        sock.close()
        if HCI_Event in resp:
            bd_addr = resp[HCI_Event].bd_addr
            if bd_addr and validate_mac(str(bd_addr)):
                return format_mac(str(bd_addr))
    except Exception:
        pass
    return None


def _get_local_mac_via_hcitool() -> str | None:
    """Try to obtain the local MAC address using the hcitool command.

    Returns:
        The local MAC address string, or None if hcitool is unavailable or fails.
    """
    try:
        result = subprocess.run(
            ['hcitool', 'dev'],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.strip().split('\n')[1:]:
            parts = line.split()
            if len(parts) >= 2:
                mac = parts[1].strip()
                if validate_mac(mac):
                    return format_mac(mac)
    except Exception:
        pass
    return None


def get_local_mac(interface: int = 0) -> str | None:
    """Obtain the local Bluetooth MAC address.

    Tries Scapy first, then falls back to hcitool.

    Args:
        interface: The HCI interface index (must be >= 0).

    Returns:
        The local MAC address string, or None if it could not be determined.

    Raises:
        ValueError: If interface is a negative integer or not an int.
    """
    if not isinstance(interface, int) or interface < 0:
        raise ValueError(
            f"interface must be a non-negative integer, got {interface}"
        )

    mac = _get_local_mac_via_scapy(interface)
    if mac:
        return mac
    return _get_local_mac_via_hcitool()


def colorize(text: str, color: Color = Color.RESET) -> str:
    """Wrap text in ANSI escape codes for terminal color output.

    Args:
        text: The text to colorize.
        color: A Color enum value (default: RESET).

    Returns:
        The colorized string with ANSI codes.
    """
    color = color if isinstance(color, Color) else Color.RESET
    return f"{color.value}{text}{Color.RESET.value}"


def require_root() -> None:
    """Check that the script is running as root.

    Raises:
        BluetoothSpammerError: If the effective UID is not 0 (root).
    """
    if os.geteuid() != 0:
        raise BluetoothSpammerError(
            "This script must be run as root (sudo)."
        )
