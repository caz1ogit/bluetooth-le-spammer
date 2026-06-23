#!/usr/bin/env python3
"""
BLE Spammer - Gerador de Advertising BLE
Gera multiplos pacotes de BLE Advertising com MACs e nomes aleatorios.
Projeto educacional para estudo do protocolo Bluetooth.
"""

import argparse
import os
import random
import re
import signal
import subprocess
import sys
import threading
import time

from scapy.packet import Raw
from scapy.layers.bluetooth import (
    BluetoothHCISocket,
    HCI_Hdr,
    HCI_Command_Hdr,
    HCI_Cmd_LE_Set_Random_Address,
    HCI_Cmd_LE_Set_Advertising_Parameters,
    HCI_Cmd_LE_Set_Advertising_Data,
    HCI_Event_Hdr,
)

from utils import colorir, verificar_root

OGF_LE = 0x08
OCF_SET_RANDOM_ADDR = 0x0005
OCF_SET_ADV_PARAMS = 0x0006
OCF_SET_ADV_DATA = 0x0008
OCF_SET_ADV_ENABLE = 0x000A
OCF_RESET = 0x0003
OGF_CONTROLLER = 0x03

ADVERTISING_DATA_MAX = 31
FLAGS_AD = b'\x02\x01\x06'
SUFIXO_PADRAO = "BT-Device-"
INTERVALO_ADV_PADRAO = 0x00A0

NAME_MAX_BYTES = ADVERTISING_DATA_MAX - len(FLAGS_AD) - 2

RE_MAC = re.compile(r'^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$')


def validar_mac(mac: str) -> bool:
    return bool(RE_MAC.match(mac.strip()))


def gerar_mac_aleatorio() -> str:
    mac = [random.randint(0x00, 0xFF) for _ in range(6)]
    mac[0] |= 0xC0
    return ':'.join(f'{b:02X}' for b in mac)


def gerar_nome_aleatorio(prefixo: str) -> str:
    sufixo = ''.join(random.choices('0123456789ABCDEF', k=4))
    nome = f"{prefixo}{sufixo}"
    return nome[:24]


def construir_ad_data(nome: str) -> bytes:
    nome_bytes = nome.encode('utf-8')[:NAME_MAX_BYTES]
    nome_ad = bytes([len(nome_bytes) + 1, 0x09]) + nome_bytes
    ad = FLAGS_AD + nome_ad
    if len(ad) > ADVERTISING_DATA_MAX:
        excesso = len(ad) - ADVERTISING_DATA_MAX
        nome_bytes = nome_bytes[:-excesso]
        nome_ad = bytes([len(nome_bytes) + 1, 0x09]) + nome_bytes
        ad = FLAGS_AD + nome_ad
    return ad


def obter_nome_interface(interface_nome: str) -> int:
    if not interface_nome.startswith('hci'):
        raise ValueError(f"Interface invalida: {interface_nome}")
    try:
        idx = int(interface_nome[3:])
    except ValueError:
        raise ValueError(f"Interface invalida: {interface_nome}")
    caminho = f'/sys/class/bluetooth/{interface_nome}'
    if not os.path.exists(caminho):
        raise ValueError(f"Interface {interface_nome} nao encontrada")
    return idx


def interface_suporta_ble(nome: str) -> bool:
    try:
        result = subprocess.run(
            ['hcitool', 'hci', 'dev', nome],
            capture_output=True, text=True, timeout=5
        )
        if 'not available' in (result.stdout + result.stderr).lower():
            return False
        supported = subprocess.run(
            ['hcitool', '-i', nome, 'features'],
            capture_output=True, text=True, timeout=5
        )
        if 'LE' in supported.stdout:
            return True
    except Exception:
        pass
    try:
        with open(f'/sys/class/bluetooth/{nome}/device/features', 'rb') as f:
            features = f.read()
            if len(features) >= 2 and (features[1] & 0x20):
                return True
    except Exception:
        pass
    return False


def obter_mac_original(nome: str) -> str | None:
    try:
        with open(f'/sys/class/bluetooth/{nome}/address') as f:
            mac = f.read().strip().upper()
            if validar_mac(mac):
                return mac
    except Exception:
        pass
    return None


def liberar_interface(nome: str):
    try:
        subprocess.run(
            ['systemctl', 'stop', 'bluetooth'],
            capture_output=True, timeout=10, check=True
        )
        time.sleep(0.5)
        return
    except Exception:
        pass
    try:
        subprocess.run(
            ['bluetoothctl', 'power', 'off'],
            capture_output=True, timeout=5, check=True
        )
        time.sleep(0.3)
    except Exception:
        try:
            subprocess.run(
                ['hciconfig', nome, 'down'],
                capture_output=True, timeout=5
            )
            subprocess.run(
                ['hciconfig', nome, 'up'],
                capture_output=True, timeout=5
            )
            time.sleep(0.3)
        except Exception:
            pass


def restaurar_interface(nome: str):
    try:
        subprocess.run(
            ['systemctl', 'start', 'bluetooth'],
            capture_output=True, timeout=10, check=True
        )
        time.sleep(1.0)
        return
    except Exception:
        pass
    try:
        subprocess.run(
            ['bluetoothctl', 'power', 'on'],
            capture_output=True, timeout=5
        )
    except Exception:
        pass


def detectar_adaptadores_ble() -> list[str]:
    adaptadores = []
    try:
        result = subprocess.run(
            ['hcitool', 'dev'],
            capture_output=True, text=True, timeout=5
        )
        for linha in result.stdout.strip().split('\n')[1:]:
            partes = linha.split()
            if len(partes) >= 2 and partes[0].startswith('hci'):
                adaptadores.append(partes[0])
    except Exception:
        pass
    return adaptadores


def abrir_socket_raw(interface_idx: int) -> BluetoothHCISocket:
    try:
        sock = BluetoothHCISocket(interface_idx)
        pass
        return sock
    except Exception as e:
        print(colorir(
            f"ERRO: Nao foi possivel abrir socket HCI na interface {interface_idx}.", 'vermelho'))
        print(f"Detalhe: {e}")
        print("Verifique o adaptador Bluetooth e execute com sudo.")
        sys.exit(1)


def enviar_cmd(sock: BluetoothHCISocket | None, pkt, dry_run: bool = False):
    if dry_run or sock is None:
        print(colorir(f"  [DRY-RUN] Enviaria: {bytes(pkt).hex()}", 'amarelo'))
        return
    try:
        sock.send(pkt)
    except Exception as e:
        print(colorir(f"Erro ao enviar comando HCI: {e}", 'vermelho'))


def enviar_cmd_e_aguardar(sock: BluetoothHCISocket | None, pkt, timeout: float = 0.5) -> bool:
    if sock is None:
        return True
    try:
        sock.send(pkt)
        import select as _select
        inicio = time.time()
        while time.time() - inicio < timeout:
            restante = timeout - (time.time() - inicio)
            if restante <= 0:
                break
            ready = _select.select([sock.ins], [], [], min(0.05, restante))
            if ready[0]:
                try:
                    resp = sock.recv(4096)
                    if HCI_Event_Hdr in resp and resp[HCI_Event_Hdr].code == 0x0E:
                        return True
                except Exception:
                    pass
    except Exception as e:
        print(colorir(f"Erro ao enviar comando HCI: {e}", 'vermelho'))
    return False


def resetar_controller(sock: BluetoothHCISocket | None, dry_run: bool = False) -> bool:
    if dry_run or sock is None:
        print(colorir("  [DRY-RUN] HCI_Reset", 'amarelo'))
        return True
    pkt = HCI_Hdr(type=1) / HCI_Command_Hdr(ogf=OGF_CONTROLLER, ocf=OCF_RESET)
    ok = enviar_cmd_e_aguardar(sock, pkt, timeout=1.0)
    time.sleep(0.2)
    return ok


def configurar_advertising_params(sock: BluetoothHCISocket | None,
                                  usar_random_addr: bool = True,
                                  dry_run: bool = False) -> bool:
    pkt = (
        HCI_Hdr(type=1) /
        HCI_Command_Hdr(ogf=OGF_LE, ocf=OCF_SET_ADV_PARAMS) /
        HCI_Cmd_LE_Set_Advertising_Parameters(
            interval_min=INTERVALO_ADV_PADRAO,
            interval_max=INTERVALO_ADV_PADRAO,
            adv_type=0,
            oatype=1 if usar_random_addr else 0,
            datype=0,
            channel_map=7,
            filter_policy=0,
        )
    )
    if dry_run or sock is None:
        print(colorir("  [DRY-RUN] Set Advertising Parameters", 'amarelo'))
        return True
    ok = enviar_cmd_e_aguardar(sock, pkt)
    time.sleep(0.05)
    if not ok:
        print(colorir("  [FALHA] Set Advertising Parameters", 'vermelho'))
    return ok


def configurar_random_address(sock: BluetoothHCISocket | None,
                              mac: str, dry_run: bool = False) -> bool:
    if dry_run or sock is None:
        print(colorir(f"  [DRY-RUN] Set Random Address: {mac}", 'amarelo'))
        return True
    try:
        pkt = (
            HCI_Hdr(type=1) /
            HCI_Command_Hdr(ogf=OGF_LE, ocf=OCF_SET_RANDOM_ADDR) /
            HCI_Cmd_LE_Set_Random_Address(address=mac)
        )
        ok = enviar_cmd_e_aguardar(sock, pkt)
        time.sleep(0.05)
        if not ok:
            print(colorir(f"  AVISO: Random address {mac} rejeitado pelo controller.", 'amarelo'))
        return ok
    except Exception as e:
        print(colorir(f"Erro ao configurar random address: {e}", 'vermelho'))
        return False


def configurar_advertising_data(sock: BluetoothHCISocket | None,
                                ad_bytes: bytes, dry_run: bool = False) -> bool:
    ad_padded = ad_bytes.ljust(ADVERTISING_DATA_MAX, b'\x00')
    pkt = (
        HCI_Hdr(type=1) /
        HCI_Command_Hdr(ogf=OGF_LE, ocf=OCF_SET_ADV_DATA) /
        HCI_Cmd_LE_Set_Advertising_Data(data=ad_padded)
    )
    if dry_run or sock is None:
        print(colorir(f"  [DRY-RUN] AD Data: {ad_padded.hex()}", 'amarelo'))
        return True
    ok = enviar_cmd_e_aguardar(sock, pkt)
    time.sleep(0.05)
    if not ok:
        print(colorir("  [FALHA] Set Advertising Data", 'vermelho'))
    return ok


def configurar_advertising_enable(sock: BluetoothHCISocket | None,
                                  habilitar: bool, dry_run: bool = False) -> bool:
    comando = b'\x01' if habilitar else b'\x00'
    pkt = (
        HCI_Hdr(type=1) /
        HCI_Command_Hdr(ogf=OGF_LE, ocf=OCF_SET_ADV_ENABLE) /
        Raw(comando)
    )
    if dry_run or sock is None:
        print(colorir(f"  [DRY-RUN] Advertising {'ON' if habilitar else 'OFF'}", 'amarelo'))
        return True
    ok = enviar_cmd_e_aguardar(sock, pkt)
    time.sleep(0.05)
    if not ok:
        print(colorir(f"  [FALHA] Advertising {'ON' if habilitar else 'OFF'}", 'vermelho'))
    return ok


def formatar_tempo(segundos: float) -> str:
    segundos = int(segundos)
    h, resto = divmod(segundos, 3600)
    m, s = divmod(resto, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def exibir_banner():
    print()
    print('╔' + '═' * 56 + '╗')
    print(f'║  BLE-SPAMMER v1.0  -  Gerador de Advertising BLE{" " * 15}║')
    print('╚' + '═' * 56 + '╝')
    print()


def exibir_resumo(estatisticas: dict):
    print()
    print('╔' + '═' * 56 + '╗')
    print(f'║  RESUMO DA EXECUCAO{" " * 36}║')
    print('╠' + '═' * 56 + '╣')
    for chave, valor in estatisticas.items():
        print(f'║  {chave:<20}: {str(valor):<30}║')
    print('╚' + '═' * 56 + '╝')
    print()


def executar_modo_single(args, dry_run: bool = False):
    mac = args.mac if args.mac else gerar_mac_aleatorio()
    nome = args.name if args.name else gerar_nome_aleatorio(args.prefix)

    try:
        interface_idx = obter_nome_interface(args.interface)
    except ValueError as e:
        print(colorir(f"ERRO: {e}", 'vermelho'))
        return

    if not validar_mac(mac):
        print(colorir(f"ERRO: MAC invalido: {mac}", 'vermelho'))
        return

    ad_bytes = construir_ad_data(nome)

    print(colorir(f"MAC:     {mac}", 'ciano'))
    print(colorir(f"Nome:    {nome}", 'ciano'))
    print(colorir(f"AD data: {ad_bytes.hex()}", 'amarelo'))
    print(f"Tamanho: {len(ad_bytes)} bytes")
    print()

    if dry_run:
        print(colorir("[DRY-RUN] Simulacao concluida. Nenhum pacote foi enviado.", 'verde'))
        return

    print(colorir("Preparando interface...", 'amarelo'))
    print(colorir("AVISO: O Bluetooth do computador sera desabilitado temporariamente.", 'vermelho'))
    liberar_interface(args.interface)
    sock = abrir_socket_raw(interface_idx)
    mac_original = obter_mac_original(args.interface)

    executando = True
    inicio = time.time()
    contador = 0

    def sinal_encerrar(sig, frame):
        nonlocal executando
        executando = False

    signal.signal(signal.SIGINT, sinal_encerrar)

    try:
        configurar_advertising_params(sock)
        configurar_random_address(sock, mac)
        configurar_advertising_data(sock, ad_bytes)
        configurar_advertising_enable(sock, True)

        print(colorir("Transmitindo... Pressione Ctrl+C para encerrar.", 'verde'))
        print("-" * 60)

        while executando:
            decorrido = time.time() - inicio
            contador += 1
            sys.stdout.write(
                f"\r{colorir('[ATIVO]', 'verde')} MAC: {mac}  "
                f"| Nome: {nome}  "
                f"| Tempo: {formatar_tempo(decorrido)}  "
                f"| Ciclos: {contador}  "
            )
            sys.stdout.flush()
            time.sleep(args.interval)

    finally:
        configurar_advertising_enable(sock, False)
        if mac_original and mac_original != mac:
            configurar_random_address(sock, mac_original)
        print(colorir("Restaurando Bluetooth...", "amarelo"))
        restaurar_interface(args.interface)
        sock.close()

    total = time.time() - inicio
    print()
    print(colorir(f"\nEncerrado. {contador} ciclos em {formatar_tempo(total)}.", 'verde'))


def anunciar_dispositivo(sock, mac, nome, ad_bytes, dwell, usar_random_addr=True):
    if usar_random_addr:
        if not configurar_random_address(sock, mac):
            return False
    if not configurar_advertising_data(sock, ad_bytes):
        return False
    if not configurar_advertising_enable(sock, True):
        return False
    return True


def executar_spam_sequencial(args, parar: threading.Event):
    interface_idx = obter_nome_interface(args.interface)
    print(colorir("AVISO: O Bluetooth do computador sera desabilitado temporariamente.", 'vermelho'))
    print(colorir("Apos o Ctrl+C, o Bluetooth sera restaurado automaticamente.\n", 'amarelo'))
    liberar_interface(args.interface)
    sock = abrir_socket_raw(interface_idx)
    mac_original = obter_mac_original(args.interface)

    print(colorir("Resetando controller...", 'amarelo'))
    resetar_controller(sock)

    usar_random_addr = True
    if not configurar_advertising_params(sock, usar_random_addr=True):
        print(colorir("AVISO: Falha ao configurar advertising parameters.", 'amarelo'))
        usar_random_addr = False

    contador = 0
    inicio = time.time()

    print(colorir(f"Usando adaptador: {args.interface}", 'ciano'))
    if mac_original:
        print(colorir(f"MAC real: {mac_original}", 'amarelo'))
    print()

    while not parar.is_set():
        contador += 1
        mac = gerar_mac_aleatorio()
        nome = gerar_nome_aleatorio(args.prefix)
        ad_bytes = construir_ad_data(nome)

        if usar_random_addr:
            if not configurar_random_address(sock, mac):
                print(colorir(
                    "  Random address rejeitado. Mudando para endereco publico.",
                    'amarelo'))
                usar_random_addr = False
                configurar_advertising_params(sock, usar_random_addr=False)

        if not configurar_advertising_data(sock, ad_bytes):
            print(colorir("  AVISO: Falha ao configurar advertising data.", 'amarelo'))

        if not configurar_advertising_enable(sock, True):
            print(colorir("  AVISO: Falha ao habilitar advertising.", 'amarelo'))

        decorrido = time.time() - inicio
        sys.stdout.write(
            f"\r{colorir(f'[Dispositivo {contador}]', 'verde')} "
            f"MAC: {colorir(mac, 'ciano')} | "
            f"Nome: {colorir(nome, 'amarelo')} | "
            f"Tempo: {formatar_tempo(decorrido)}  "
        )
        sys.stdout.flush()

        step = 0.1
        for _ in range(int(args.dwell / step)):
            if parar.is_set():
                break
            time.sleep(step)
            if _ % 10 == 0:
                decorrido = time.time() - inicio
                sys.stdout.write(
                    f"\r{colorir(f'[Dispositivo {contador}]', 'verde')} "
                    f"MAC: {colorir(mac, 'ciano')} | "
                    f"Nome: {colorir(nome, 'amarelo')} | "
                    f"Tempo: {formatar_tempo(decorrido)}  "
                )
                sys.stdout.flush()

        configurar_advertising_enable(sock, False)

    total = time.time() - inicio
    print()
    print(colorir("\nDesligando advertising e restaurando adaptador...", 'amarelo'))
    configurar_advertising_enable(sock, False)
    if mac_original:
        configurar_random_address(sock, mac_original)
    print(colorir("Restaurando Bluetooth...", 'amarelo'))
    restaurar_interface(args.interface)
    sock.close()

    return contador, total


def anunciar_continuamente(interface: str, mac: str, nome: str,
                           parar: threading.Event):
    ad_bytes = construir_ad_data(nome)
    try:
        interface_idx = obter_nome_interface(interface)
    except ValueError as e:
        print(colorir(f"ERRO ({interface}): {e}", 'vermelho'))
        return

    print(colorir(f"  {interface}: MAC={mac} Nome={nome}", 'ciano'))
    print(colorir(f"  {interface}: Desabilitando Bluetooth temporariamente...", 'vermelho'))
    liberar_interface(interface)
    sock = abrir_socket_raw(interface_idx)
    mac_original = obter_mac_original(interface)

    configurar_advertising_params(sock, usar_random_addr=True)
    configurar_random_address(sock, mac)
    configurar_advertising_data(sock, ad_bytes)
    configurar_advertising_enable(sock, True)

    print(colorir(f"  {interface}: Anunciando continuamente...", 'verde'))

    while not parar.is_set():
        time.sleep(0.5)

    print(colorir(f"  {interface}: Encerrando...", 'amarelo'))
    configurar_advertising_enable(sock, False)
    if mac_original:
        configurar_random_address(sock, mac_original)
    restaurar_interface(interface)
    sock.close()


def executar_spam_multiplo(args, adaptadores: list[str], parar: threading.Event):
    threads = []
    for i, interface in enumerate(adaptadores):
        mac = gerar_mac_aleatorio()
        nome = args.prefix + ''.join(random.choices('0123456789ABCDEF', k=4))
        t = threading.Thread(
            target=anunciar_continuamente,
            args=(interface, mac, nome, parar),
            daemon=True
        )
        threads.append(t)

    print(colorir(f"Iniciando {len(threads)} adaptadores em paralelo...", 'verde'))
    for t in threads:
        t.start()

    print(colorir("Pressione Ctrl+C para encerrar.\n", 'amarelo'))

    while not parar.is_set():
        time.sleep(0.5)

    for t in threads:
        t.join(timeout=3)


def executar_modo_spam(args, dry_run: bool = False):
    adaptadores = detectar_adaptadores_ble()
    if not adaptadores:
        adaptadores = [args.interface]

    if len(adaptadores) > 1:
        print(colorir(f"Detectados {len(adaptadores)} adaptadores BLE.", 'ciano'))
        for a in adaptadores:
            print(colorir(f"  - {a}", 'ciano'))
        print()

    if dry_run:
        num = args.count if args.count > 0 else 5
        print(colorir(f"Simulando {num} dispositivos sequenciais:", 'amarelo'))
        for i in range(num):
            mac = gerar_mac_aleatorio()
            nome = gerar_nome_aleatorio(args.prefix)
            ad_bytes = construir_ad_data(nome)
            print(colorir(
                f"  [{i+1}] MAC: {mac} | Nome: {nome} | "
                f"AD: {len(ad_bytes)} bytes | Payload: {ad_bytes.hex()}",
                'amarelo'
            ))
        print()
        if len(adaptadores) > 1:
            print(colorir(f"Com {len(adaptadores)} adaptadores, cada um manteria um dispositivo fixo.", 'amarelo'))
        print(colorir("[DRY-RUN] Simulacao concluida. Nenhum pacote foi enviado.", 'verde'))
        return

    parar = threading.Event()

    def sinal_encerrar(sig, frame):
        print(colorir("\n\nSinal de encerramento recebido. Finalizando...", 'amarelo'))
        parar.set()

    signal.signal(signal.SIGINT, sinal_encerrar)
    signal.signal(signal.SIGTERM, sinal_encerrar)

    print(colorir(f"Interface: {args.interface}", 'ciano'))
    print(colorir(f"Modo:      spam", 'ciano'))
    print(colorir(f"Dwell:     {args.dwell}s por dispositivo", 'ciano'))
    print(colorir(f"Prefixo:   {args.prefix}", 'amarelo'))
    print()

    if len(adaptadores) > 1:
        print(colorir(
            f"Usando {len(adaptadores)} adaptadores em paralelo. "
            f"Cada um mantem um dispositivo fixo.", 'verde'))
        executar_spam_multiplo(args, adaptadores, parar)
        total_dispositivos = len(adaptadores)
        total_tempo = 0
    else:
        print(colorir(
            "Um adaptador detectado. Modo sequencial: "
            "cria dispositivos um por vez.", 'verde'))
        total_dispositivos, total_tempo = executar_spam_sequencial(args, parar)

    print()
    exibir_resumo({
        'Interface': f"{args.interface}" + (f" +{len(adaptadores)-1} mais" if len(adaptadores) > 1 else ''),
        'Modo': 'spam',
        'Dispositivos': str(total_dispositivos) if len(adaptadores) == 1 else f"{len(adaptadores)} fixos",
        'Tempo total': formatar_tempo(total_tempo) if len(adaptadores) == 1 else 'N/A (paralelo)',
        'Adaptadores': str(len(adaptadores)),
    })


def main():
    verificar_root()

    parser = argparse.ArgumentParser(
        description='BLE Spammer - Gerador de Advertising BLE com MACs e nomes aleatorios',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Exemplos:
  sudo python3 ble_spammer.py --mode spam --dwell 5
  sudo python3 ble_spammer.py --mode single --name "Meu-Device" --mac C0:FF:EE:11:22:33
  sudo python3 ble_spammer.py --mode spam --dwell 10 --prefix "Fake-"
  python3 ble_spammer.py --mode spam --count 5 --dry-run
        '''
    )

    parser.add_argument('--mode', '-m', choices=['single', 'spam'], default='spam',
                        help='Modo de operacao: single ou spam (padrao: spam)')
    parser.add_argument('--count', '-c', type=int, default=10,
                        help='Numero de dispositivos para dry-run (padrao: 10)')
    parser.add_argument('--dwell', '-d', type=float, default=5.0,
                        help='Tempo em segundos que cada dispositivo fica visivel (padrao: 5.0, minimo: 3.0)')
    parser.add_argument('--interval', '-t', type=float, default=5.0,
                        help='Intervalo entre criacao de dispositivos (padrao: 5.0)')
    parser.add_argument('--name', '-n', type=str, default=None,
                        help='Nome fixo para modo single (opcional)')
    parser.add_argument('--mac', '-a', type=str, default=None,
                        help='MAC fixo para modo single (opcional)')
    parser.add_argument('--prefix', '-p', type=str, default=SUFIXO_PADRAO,
                        help=f'Prefixo para nomes aleatorios (padrao: {SUFIXO_PADRAO})')
    parser.add_argument('--interface', '-i', type=str, default='hci0',
                        help='Interface HCI (padrao: hci0)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Simula execucao sem abrir socket HCI')

    args = parser.parse_args()

    if not args.interface.startswith('hci'):
        print(colorir(f"ERRO: Interface deve comecar com 'hci' (ex: hci0)", 'vermelho'))
        sys.exit(1)

    try:
        obter_nome_interface(args.interface)
    except ValueError as e:
        print(colorir(f"ERRO: {e}", 'vermelho'))
        sys.exit(1)

    if args.mac and not validar_mac(args.mac):
        print(colorir(f"ERRO: MAC invalido: {args.mac}. Use formato XX:XX:XX:XX:XX:XX", 'vermelho'))
        sys.exit(1)

    if args.name and len(args.name) > 24:
        print(colorir(f"AVISO: Nome truncado para 24 caracteres.", 'amarelo'))
        args.name = args.name[:24]

    args.dwell = max(args.dwell, 3.0)
    if args.interval < args.dwell:
        args.interval = args.dwell

    if args.count < 0:
        print(colorir("ERRO: --count deve ser >= 0", 'vermelho'))
        sys.exit(1)

    if args.mode == 'single':
        if args.count != 10:
            print(colorir("AVISO: --count ignorado no modo single.", 'amarelo'))
    elif args.mode == 'spam':
        if args.name or args.mac:
            print(colorir("AVISO: --name e --mac ignorados no modo spam.", 'amarelo'))

    exibir_banner()

    if not args.dry_run:
        if not interface_suporta_ble(args.interface):
            print(colorir(
                f"AVISO: Interface {args.interface} pode nao suportar BLE. "
                f"Procedendo mesmo assim.", 'amarelo'
            ))

    try:
        if args.mode == 'single':
            executar_modo_single(args, dry_run=args.dry_run)
        else:
            executar_modo_spam(args, dry_run=args.dry_run)
    except KeyboardInterrupt:
        print(colorir("\n\nInterrompido pelo usuario.", 'amarelo'))
        sys.exit(0)


if __name__ == '__main__':
    main()
