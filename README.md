# projeto_redes

Projeto educacional para estudo do protocolo **Bluetooth** (Classic e BLE) usando Python e Scapy.

> **Aviso legal:** Este projeto foi desenvolvido para fins acadêmicos e de pesquisa. O uso indevido dessas ferramentas pode violar leis locais e políticas de rede. Utilize apenas em ambientes controlados e com permissão explícita.

---

## Conteúdo do repositório

- `ble_spammer.py` — Gera pacotes de **Advertising BLE** com MACs e nomes aleatórios.
- `injector.py` — Realiza **spoofing de MAC** e injeta pacotes Bluetooth Classic (L2CAP/HCI).
- `scanner.py` — Realiza **scan contínuo** de dispositivos Bluetooth Classic (BR/EDR) e BLE.
- `utils.py` — Funções auxiliares (validação de MAC, cores no terminal, verificação de root etc.).

---

## Requisitos mínimos

- Sistema **Linux** (testado em distribuições Debian/Ubuntu).
- Adaptador **Bluetooth USB** compatível com HCI e, preferencialmente, com suporte a **BLE**.
- Python **3.8+**
- Permissões de **root** (`sudo`).

---

## 1. Instalação do Python e pip

Verifique se o Python 3 e o pip estão instalados:

```bash
python3 --version
pip3 --version
```

Caso não estejam, instale:

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv
```

---

## 2. Instalar dependências do sistema

O Scapy e os sockets Bluetooth precisam de bibliotecas de sistema.

```bash
sudo apt update
sudo apt install -y \
    libpcap-dev \
    libbluetooth-dev \
    bluez \
    hcitool \
    bluetoothctl \
    libglib2.0-dev
```

---

## 3. Clonar ou acessar o projeto

```bash
cd /home/cassio/Downloads/projeto_redes
```

---

## 4. Instalar a biblioteca Scapy

Recomendado usar um ambiente virtual (opcional, mas limpo):

```bash
python3 -m venv venv
source venv/bin/activate
```

Instale o Scapy:

```bash
pip install scapy
```

Para instalar globalmente (sem venv):

```bash
sudo pip3 install scapy
```

---

## 5. Verificar o adaptador Bluetooth

Liste as interfaces HCI disponíveis:

```bash
hcitool dev
```

Saída esperada:

```
Devices:
	hci0	XX:XX:XX:XX:XX:XX
```

Se nenhum dispositivo aparecer, verifique se o adaptador está conectado e se o serviço Bluetooth está ativo:

```bash
sudo systemctl status bluetooth
sudo systemctl start bluetooth
```

---

## 6. Como usar o `ble_spammer.py`

O script envia anúncios BLE (Advertising) com nomes e endereços MAC aleatórios.

### 6.1 Executar

```bash
sudo python3 ble_spammer.py
```

> **Importante:** todos os scripts deste projeto exigem `sudo` ou execução como `root`, pois utilizam sockets HCI brutos.

### 6.2 Argumentos comuns

```bash
sudo python3 ble_spammer.py -i hci0 -n 5 -t 0.1 -p "BT-Test-"
```

Opções típicas (verifique com `--help`):

| Opção | Descrição |
|-------|-----------|
| `-i`, `--interface` | Interface HCI (ex: `hci0`) |
| `-n`, `--count` | Quantidade de dispositivos simulados |
| `-t`, `--interval` | Intervalo entre trocas de anúncio |
| `-p`, `--prefix` | Prefixo do nome exibido no advertising |

Consulte todas as opções:

```bash
sudo python3 ble_spammer.py --help
```

### 6.3 Parar a execução

Pressione `Ctrl + C` para encerrar de forma segura.

---

## 7. Como usar os outros scripts

### `scanner.py`

```bash
sudo python3 scanner.py
```

Realiza scan contínuo de dispositivos Bluetooth Classic (BR/EDR inquiry) e BLE. Pressione `Ctrl + C` para sair.

### `injector.py`

```bash
sudo python3 injector.py
```

Solicita o MAC do dispositivo alvo e o MAC de origem (ou usa o MAC local) para enviar pacotes L2CAP forjados.

---

## 8. Resolução de problemas

### Erro: `Permission denied` ao abrir socket HCI

Execute o script com `sudo`.

### Erro: `No such device` ou `Device not found`

- Verifique se o adaptador Bluetooth está conectado.
- Execute `hcitool dev` para confirmar a interface.
- Tente reiniciar o serviço Bluetooth:

```bash
sudo systemctl restart bluetooth
```

### Erro ao importar `scapy.layers.bluetooth`

Algumas versões do Scapy não incluem as camadas Bluetooth por padrão. Instale a versão completa:

```bash
pip install --upgrade scapy
```

### Erro: `BluetoothHCISocket` não encontrado

Isso pode ocorrer em kernels ou ambientes sem suporte a sockets Bluetooth. Verifique:

```bash
ls /sys/class/bluetooth/
```

Se o diretório estiver vazio, o sistema não detectou nenhum adaptador Bluetooth.

---

## 9. Estrutura do projeto

```
projeto_redes/
├── README.md
├── ble_spammer.py
├── injector.py
├── scanner.py
└── utils.py
```

---

## 10. Tecnologias utilizadas

- Python 3
- Scapy
- BlueZ (stack Bluetooth do Linux)
- HCI / L2CAP / BLE Advertising

---

## Autor

Projeto acadêmico de estudo de redes sem fio.
