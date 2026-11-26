"""
tao_tai_khoan_mqtt.py — chuan bi moi thu de chuyen sang BROKER RIENG (TLS + tai khoan).

Chay MOT lan, sau khi da tao deployment EMQX Serverless (docs/BROKER_RIENG_TLS.md):

    .conda\\python.exe scripts\\tao_tai_khoan_mqtt.py --host xxxxxxxx.ala.asia-southeast1.emqxsl.com

Script lam 5 viec, KHONG dong gi toi mang:
  1. Sinh 4 tai khoan, mat khau ngau nhien manh (secrets.token_urlsafe):
        laptop   - gesture_lock.py      : chi GUI .../gesture, .../sequence
        nodered  - Node-RED             : NGHE .../sequence, .../state ; GUI .../cmd
        esp32    - firmware ESP32       : NGHE .../cmd, .../gesture    ; GUI .../state
        giam_sat - script do / kiem tra : chi NGHE .../#
  2. Ghi vision/mqtt_tai_khoan.json   (BI MAT, da co trong .gitignore)
  3. Ghi firmware/secrets.h            (BI MAT, da co trong .gitignore)
  4. Ghi middleware/flows_broker_rieng.json — ban sao cua flows.json, doi node
     broker sang TLS cong 8883 kem tai khoan nodered (BI MAT, .gitignore)
  5. Ghi host, port vao vision/config.json -> mqtt.broker_rieng
     (KHONG tu bat dung_broker_rieng — ban tu bat khi da san sang)

Cuoi cung in ra BANG TAI KHOAN va BANG PHAN QUYEN de nhap vao trang quan tri EMQX.
Da co file tai khoan thi giu nguyen mat khau cu (them --tao-lai de sinh moi).
"""
from __future__ import annotations

import argparse
import json
import re
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "vision" / "config.json"
TAI_KHOAN = ROOT / "vision" / "mqtt_tai_khoan.json"
SECRETS_H = ROOT / "firmware" / "secrets.h"
CA_BUNDLE = ROOT / "middleware" / "certs" / "emqx_ca_bundle.pem"
FLOWS = ROOT / "middleware" / "flows.json"
FLOWS_RIENG = ROOT / "middleware" / "flows_broker_rieng.json"

VAI_TRO = ["laptop", "nodered", "esp32", "giam_sat"]


def bang_phan_quyen(prefix: str) -> list[tuple[str, str, str, str]]:
    """(tai khoan, topic, hanh dong, cho phep/cam). Thu tu = thu tu nhap vao EMQX."""
    p = prefix
    return [
        ("gate_laptop",   p + "gesture",  "Publish",   "Allow"),
        ("gate_laptop",   p + "sequence", "Publish",   "Allow"),
        ("gate_nodered",  p + "sequence", "Subscribe", "Allow"),
        ("gate_nodered",  p + "state",    "Subscribe", "Allow"),
        ("gate_nodered",  p + "cmd",      "Publish",   "Allow"),
        ("gate_esp32",    p + "cmd",      "Subscribe", "Allow"),
        ("gate_esp32",    p + "gesture",  "Subscribe", "Allow"),
        ("gate_esp32",    p + "state",    "Publish",   "Allow"),
        ("gate_giam_sat", p + "#",        "Subscribe", "Allow"),
        ("(All Users)",   "#",            "Publish & Subscribe", "Deny"),
    ]


def doc_hoac_tao_tai_khoan(tao_lai: bool) -> dict:
    if TAI_KHOAN.exists() and not tao_lai:
        tk = json.loads(TAI_KHOAN.read_text(encoding="utf-8"))
        if all(v in tk for v in VAI_TRO):
            print(f"Giu nguyen tai khoan da co trong {TAI_KHOAN.name} (them --tao-lai de sinh moi).")
            return tk
    tk = {v: {"username": "gate_" + v, "password": secrets.token_urlsafe(18)} for v in VAI_TRO}
    TAI_KHOAN.write_text(json.dumps(tk, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Da ghi {TAI_KHOAN}")
    return tk


def ghi_secrets_h(host: str, port: int, tk: dict) -> None:
    SECRETS_H.write_text(
        "// secrets.h — SINH TU DONG boi scripts/tao_tai_khoan_mqtt.py. KHONG commit (.gitignore).\n"
        "// Xoa file nay (hoac dat MQTT_DUNG_BROKER_RIENG 0) de quay ve broker cong cong.\n"
        "#pragma once\n"
        "#define MQTT_DUNG_BROKER_RIENG 1\n"
        f'#define MQTT_HOST_RIENG "{host}"\n'
        f"#define MQTT_PORT_RIENG {port}\n"
        f'#define MQTT_USER_RIENG "{tk["esp32"]["username"]}"\n'
        f'#define MQTT_PASS_RIENG "{tk["esp32"]["password"]}"\n',
        encoding="utf-8")
    print(f"Da ghi {SECRETS_H}")


def ghi_flows_rieng(host: str, port: int, tk: dict) -> None:
    """Sao flows.json, doi node mqtt-broker sang TLS + tai khoan nodered."""
    nodes = json.loads(FLOWS.read_text(encoding="utf-8"))
    brokers = [n for n in nodes if n.get("type") == "mqtt-broker"]
    if len(brokers) != 1:
        raise SystemExit(f"flows.json phai co dung 1 node mqtt-broker, dang co {len(brokers)}")
    b = brokers[0]
    b.update({
        "name": "EMQX rieng (TLS)",
        "broker": host,
        "port": str(port),
        "usetls": True,
        "tls": "cfg_tls_emqx",
        "clientid": "",
        # Node-RED nhan credentials kem theo khi import. Neu ban Node-RED cua
        # ban khong nhan, mo node broker -> tab Security de nhap tay.
        "credentials": {"user": tk["nodered"]["username"], "password": tk["nodered"]["password"]},
    })
    nodes.append({
        "id": "cfg_tls_emqx",
        "type": "tls-config",
        "name": "CA cua EMQX",
        "cert": "", "key": "",
        "ca": str(CA_BUNDLE),
        "certname": "", "keyname": "", "caname": "",
        "servername": host,
        "verifyservercert": True,
        "alpnprotocol": "",
    })
    FLOWS_RIENG.write_text(json.dumps(nodes, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Da ghi {FLOWS_RIENG}")


def ghi_host_config(host: str, port: int) -> None:
    """Chi thay host va port trong config.json, giu nguyen dinh dang va chu thich."""
    raw = CONFIG.read_bytes().decode("utf-8")
    moi, n = re.subn(r'("broker_rieng":\s*\{\s*"host":\s*")[^"]*(",\s*"port":\s*)\d+',
                     r"\g<1>" + host + r"\g<2>" + str(port), raw)
    if n != 1:
        raise SystemExit("Khong tim thay mqtt.broker_rieng.host / port trong config.json")
    CONFIG.write_bytes(moi.encode("utf-8"))
    print(f"Da ghi host, port vao {CONFIG.name} (dung_broker_rieng van giu nguyen)")


def main() -> int:
    ap = argparse.ArgumentParser(description="Chuan bi tai khoan cho broker rieng TLS.")
    ap.add_argument("--host", required=True, help="dia chi deployment, vd abc123.ala.asia-southeast1.emqxsl.com")
    ap.add_argument("--port", type=int, default=8883)
    ap.add_argument("--tao-lai", action="store_true", help="sinh mat khau moi (phai nhap lai ca 4 tai khoan tren EMQX)")
    args = ap.parse_args()

    if not re.fullmatch(r"[A-Za-z0-9.-]+", args.host) or "THAY_BANG" in args.host:
        print("--host khong hop le. Lay o trang Overview cua deployment EMQX (muc Address).")
        return 2
    if not CA_BUNDLE.exists():
        print(f"Thieu {CA_BUNDLE}")
        return 2

    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    prefix = cfg["mqtt"]["topic_prefix"]

    tk = doc_hoac_tao_tai_khoan(args.tao_lai)
    ghi_secrets_h(args.host, args.port, tk)
    ghi_flows_rieng(args.host, args.port, tk)
    ghi_host_config(args.host, args.port)

    print("\n" + "=" * 78)
    print("1) NHAP 4 TAI KHOAN NAY VAO EMQX: Access Control -> Authentication -> Add")
    print("=" * 78)
    for v in VAI_TRO:
        print(f"   {tk[v]['username']:<16} {tk[v]['password']}")
    print("\n" + "=" * 78)
    print("2) NHAP CAC LUAT NAY VAO EMQX: Access Control -> Authorization -> Add")
    print("   (luat cuoi cung 'All Users / # / Deny' PHAI co: cam moi thu khong liet ke)")
    print("=" * 78)
    for u, t, a, q in bang_phan_quyen(prefix):
        print(f"   {u:<16} {t:<36} {a:<20} {q}")
    print("\n3) Import middleware/flows_broker_rieng.json vao Node-RED (Replace), Deploy, chay lai node-red")
    print("4) Build lai firmware (PlatformIO Build) roi Start Simulator tren Wokwi")
    print('5) Sua vision/config.json: "dung_broker_rieng": true')
    print("6) Kiem tra: .conda\\python.exe scripts\\kiem_tra_phan_quyen.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
