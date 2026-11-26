"""
kiem_tra_phan_quyen.py — CHUNG MINH broker rieng chan dung nhung gi can chan.

    .conda\\python.exe scripts\\kiem_tra_phan_quyen.py

Can: vision/mqtt_tai_khoan.json (do scripts/tao_tai_khoan_mqtt.py tao) va da
nhap tai khoan + luat phan quyen vao EMQX. KHONG can bat dung_broker_rieng.

Cach kiem: tai khoan giam_sat nghe toan bo .../#, roi tung tai khoan thu GUI
vao cac topic. Ban tin toi duoc giam_sat nghia la broker CHO PHEP.

An toan khi chay luc he thong dang hoat dong:
  - Lenh gui vao .../cmd la {"action":"kiem_tra_acl"} — firmware bo qua action la.
  - Cu chi gui vao .../gesture co hex rong — firmware bo qua.
  - KHONG gui gi vao .../sequence (se lam Node-RED dem 1 lan sai).

Ket qua ghi them vao docs/ket_qua_phan_quyen.md.
"""
from __future__ import annotations

import json
import socket
import ssl
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

import paho.mqtt.client as mqtt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vision"))
from common import load_config, resolve_path  # noqa: E402

CHO_GIAY = 6          # cho ket noi / cho ban tin toi
RA_FILE = ROOT / "docs" / "ket_qua_phan_quyen.md"


class Client:
    """Boc paho cho gon: noi, cho ket qua, gui, nghe."""

    def __init__(self, host, port, ca_file, username=None, password=None, tls=True):
        self.c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                             client_id="kiemacl-" + uuid.uuid4().hex[:8])
        if tls:
            self.c.tls_set(ca_certs=ca_file, cert_reqs=ssl.CERT_REQUIRED,
                           tls_version=ssl.PROTOCOL_TLS_CLIENT)
        if username is not None:
            self.c.username_pw_set(username, password)
        self.host, self.port = host, port
        self.ket_noi = threading.Event()
        self.ma_ket_noi = None
        self.suback = threading.Event()
        self.ma_suback = None
        self.nhan: list[tuple[str, str]] = []
        self.c.on_connect = self._on_connect
        self.c.on_subscribe = self._on_subscribe
        self.c.on_message = lambda c, u, m: self.nhan.append((m.topic, m.payload.decode(errors="replace")))

    def _on_connect(self, c, u, flags, rc, props=None):
        self.ma_ket_noi = rc
        self.ket_noi.set()

    def _on_subscribe(self, c, u, mid, rcs, props=None):
        self.ma_suback = rcs[0]
        self.suback.set()

    def noi(self) -> bool:
        """True neu broker chap nhan ket noi."""
        try:
            self.c.connect(self.host, self.port, 30)
        except (OSError, ssl.SSLError):
            return False
        self.c.loop_start()
        if not self.ket_noi.wait(CHO_GIAY):
            return False
        return self.ma_ket_noi == 0

    def dang_ky(self, topic) -> bool:
        """True neu broker chap nhan subscribe (SUBACK khong phai loi)."""
        self.suback.clear()
        self.c.subscribe(topic, qos=0)
        if not self.suback.wait(CHO_GIAY):
            return False
        return not self.ma_suback.is_failure

    def gui(self, topic, payload: dict) -> None:
        self.c.publish(topic, json.dumps(payload), qos=0)

    def dong(self) -> None:
        self.c.loop_stop()
        self.c.disconnect()


def main() -> int:
    cfg = load_config()
    m = cfg["mqtt"]
    r = m["broker_rieng"]
    host, port = r["host"], int(r["port"])
    ca = str(resolve_path(r["ca_file"]))
    tk_path = resolve_path(r["tai_khoan_file"])
    if "THAY_BANG" in host or not tk_path.exists():
        print("Chua chuan bi broker rieng. Chay scripts/tao_tai_khoan_mqtt.py --host ... truoc.")
        return 2
    tk = json.loads(tk_path.read_text(encoding="utf-8"))
    p = m["topic_prefix"]
    ket_qua: list[tuple[str, str, bool]] = []   # (phep thu, mong doi, dat?)

    def ghi(ten, mong_doi, dat):
        ket_qua.append((ten, mong_doi, dat))
        print(f"{'DAT  ' if dat else 'KHONG'}  {ten:<62} mong doi: {mong_doi}")

    print(f"Broker: {host}:{port}\n")

    # ---- 1. Ket noi: khong TLS, khong tai khoan, sai mat khau ----
    try:
        s = socket.create_connection((host, 1883), timeout=CHO_GIAY)
        s.close()
        cong_1883_mo = True
    except OSError:
        cong_1883_mo = False
    ghi("Cong 1883 (MQTT khong ma hoa)", "khong mo", not cong_1883_mo)

    c = Client(host, port, ca)
    ghi("Ket noi TLS khong tai khoan", "bi tu choi", not c.noi())
    c.dong()
    c = Client(host, port, ca, tk["laptop"]["username"], "sai-mat-khau")
    ghi("Ket noi TLS sai mat khau", "bi tu choi", not c.noi())
    c.dong()

    # ---- 2. Moi tai khoan noi duoc qua TLS ----
    cl = {}
    for v in ("laptop", "nodered", "esp32", "giam_sat"):
        cl[v] = Client(host, port, ca, tk[v]["username"], tk[v]["password"])
        ghi(f"Tai khoan {v} ket noi TLS", "duoc", cl[v].noi())

    # ---- 3. Nghe len: ai duoc nghe topic nao ----
    gs = cl["giam_sat"]
    ghi("giam_sat nghe .../#", "duoc", gs.dang_ky(p + "#"))
    ghi("esp32 nghe .../sequence (nghe trom ma)", "bi chan", not cl["esp32"].dang_ky(p + "sequence"))
    ghi("laptop nghe .../# (nghe trom moi thu)", "bi chan", not cl["laptop"].dang_ky(p + "#"))
    time.sleep(1)

    # ---- 4. Gui: ban tin co toi duoc giam_sat khong ----
    def thu_gui(ai, topic, payload, mong_cho_phep, ten):
        dau = uuid.uuid4().hex[:6]
        payload = dict(payload, kiem_tra_acl=dau)
        cl[ai].gui(p + topic, payload)
        time.sleep(CHO_GIAY / 2)
        toi = any(dau in body for t, body in gs.nhan if t == p + topic)
        ghi(ten, "duoc" if mong_cho_phep else "bi chan", toi == mong_cho_phep)

    lenh_vo_hai = {"action": "kiem_tra_acl"}
    thu_gui("nodered", "cmd", lenh_vo_hai, True, "nodered gui .../cmd (doi chung)")
    thu_gui("laptop", "cmd", lenh_vo_hai, False, "laptop gui lenh mo cua .../cmd")
    thu_gui("esp32", "cmd", lenh_vo_hai, False, "esp32 gui lenh mo cua .../cmd")
    thu_gui("giam_sat", "cmd", lenh_vo_hai, False, "giam_sat gui lenh mo cua .../cmd")
    thu_gui("laptop", "gesture", {"gesture": "kiem_tra", "hex": ""}, True, "laptop gui .../gesture (doi chung)")
    thu_gui("laptop", "state", {"lock": "open"}, False, "laptop gia trang thai ESP32 .../state")

    for v in cl.values():
        v.dong()

    dat = sum(1 for _, _, d in ket_qua if d)
    print(f"\nTONG: {dat}/{len(ket_qua)} dat")

    dong = [f"\n## {datetime.now():%Y-%m-%d %H:%M} — broker `{host}:{port}`\n",
            "| Phép thử | Mong đợi | Kết quả |", "|---|---|---|"]
    dong += [f"| {t} | {md} | {'Đạt' if d else '**KHÔNG ĐẠT**'} |" for t, md, d in ket_qua]
    dong.append(f"\n**Tổng: {dat}/{len(ket_qua)} đạt.**\n")
    moi = not RA_FILE.exists()
    with open(RA_FILE, "a", encoding="utf-8") as f:
        if moi:
            f.write("# Kết quả kiểm tra phân quyền broker riêng\n\n"
                    "Sinh bởi `scripts/kiem_tra_phan_quyen.py`. Mỗi lần chạy thêm một mục.\n")
        f.write("\n".join(dong))
    print(f"Da ghi them vao {RA_FILE}")
    return 0 if dat == len(ket_qua) else 1


if __name__ == "__main__":
    sys.exit(main())
