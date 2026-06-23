import re
import os
import sys
import subprocess
import time


def validar_mac(mac: str) -> bool:
    if not mac or not isinstance(mac, str):
        return False
    mac = mac.strip()
    return bool(re.match(r'^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$', mac))


def formatar_mac(mac: str) -> str:
    mac = mac.strip().upper()
    if not validar_mac(mac):
        raise ValueError(f"MAC invalido: {mac}")
    return mac


def obter_mac_local(interface: int = 0) -> str:
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
            if bd_addr and validar_mac(str(bd_addr)):
                return formatar_mac(str(bd_addr))
    except Exception:
        pass
    try:
        result = subprocess.run(
            ['hcitool', 'dev'],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.strip().split('\n')[1:]:
            parts = line.split()
            if len(parts) >= 2:
                mac = parts[1].strip()
                if validar_mac(mac):
                    return formatar_mac(mac)
    except Exception:
        pass
    return None


def colorir(texto: str, cor: str = 'reset') -> str:
    cores = {
        'vermelho': '\033[91m',
        'verde': '\033[92m',
        'amarelo': '\033[93m',
        'azul': '\033[94m',
        'roxo': '\033[95m',
        'ciano': '\033[96m',
        'branco': '\033[97m',
        'reset': '\033[0m',
        'negrito': '\033[1m',
    }
    inicio = cores.get(cor.lower(), cores['reset'])
    return f"{inicio}{texto}{cores['reset']}"


def verificar_root():
    if os.geteuid() != 0:
        print(colorir("ERRO: Este script deve ser executado como root (sudo).", 'vermelho'))
        print(f"Execute: sudo python3 {sys.argv[0]}")
        sys.exit(1)
