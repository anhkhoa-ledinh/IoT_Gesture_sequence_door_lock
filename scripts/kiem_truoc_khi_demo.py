"""
============================================================================
 kiem_truoc_khi_demo.py — Tien kiem truoc phien chay that (KHONG can webcam)
----------------------------------------------------------------------------
 Chay SAU KHI da bam chay Wokwi va mo Node-RED:
   D:\\IoT_Gesture_sequence_door_lock\\.conda\\python.exe scripts\\kiem_truoc_khi_demo.py
   ... --node-red http://localhost:1880      (neu Node-RED chay o cong khac)

 In PASS / FAIL / CANH BAO cho tung muc. Co muc FAIL thi tra ve ma thoat 1.

 VE MUC MA_MAC_DINH — QUAN TRONG NHAT
 ------------------------------------
 So MA_MAC_DINH trong FILE middleware/flows.json voi config.json KHONG du:
 file trong repo luon dung, cai can biet la Node-RED DANG CHAY gi. Them nua,
 function "Kiem ma" chi doc MA_MAC_DINH khi flow context 'ma_hop_le' con
 trong — sau lan kiem ma dau tien, ma nam trong context va import flow moi de
 len khong doi duoc no. Vi vay script hoi thang Node-RED qua Admin API:
   GET /flows                 -> flow dang deploy: co bao nhieu node kiem ma, ma gi
   GET /context/flow/<tab>    -> ma_hop_le dang nam trong context
============================================================================
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import urllib.error
import urllib.request
import uuid
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "vision"))
from common import FEATURE_DIM, load_config, resolve_path  # noqa: E402

FLOWS_FILE = ROOT / "middleware" / "flows.json"
KHOA_CONTEXT = "ma_hop_le"
MAU_MA = re.compile(r'const\s+MA_MAC_DINH\s*=\s*"([0-9A-Fa-f]+)"')
THANH_VIEN_TASK = {"hand_detector.tflite", "hand_landmarks_detector.tflite"}
KICH_THUOC_TASK_DA_CHAY = 7_819_105     # ban float16/1 da chay dung tren may nay (02/10)
CHO_BROKER_GIAY = 10
CHO_STATE_GIAY = 15

PASS, FAIL, WARN = "PASS", "FAIL", "CANH BAO"
MAU = {PASS: "\033[92m", FAIL: "\033[91m", WARN: "\033[93m"}
HET_MAU = "\033[0m"


@dataclass
class KetQua:
    trang_thai: str
    ten: str
    chi_tiet: list[str] = field(default_factory=list)


# ============================================================================
#  1. PHAN TICH FLOW VA CONTEXT — thuan logic, test duoc khong can Node-RED
# ============================================================================

def tim_node_kiem_ma(nodes: list[dict]) -> list[dict]:
    """Moi function node co khai bao MA_MAC_DINH -> {id, tab, ten_tab, ten, ma, dang_chay}.

    dang_chay = False neu node hoac ca tab bi disable (Node-RED khong chay no).
    """
    tabs = {n["id"]: n for n in nodes if n.get("type") == "tab"}
    ra = []
    for n in nodes:
        if n.get("type") != "function":
            continue
        m = MAU_MA.search(n.get("func") or "")
        if not m:
            continue
        tab = tabs.get(n.get("z"), {})
        ra.append({
            "id": n.get("id"), "tab": n.get("z"), "ten_tab": tab.get("label", "?"),
            "ten": n.get("name", ""), "ma": m.group(1).upper(),
            "dang_chay": not n.get("d", False) and not tab.get("disabled", False),
        })
    return ra


def doc_ma_tu_context(ctx) -> str | None:
    """Lay 'ma_hop_le' tu ket qua GET /context/flow/<id>.

    Node-RED tra ve {ten_store: {khoa: {"msg": gia_tri, "format": "..."}}}.
    Chap nhan ca gia tri tho va chuoi bi boc them dau ngoac kep.
    Tra ve None neu context chua co khoa nay.
    """
    if not isinstance(ctx, dict):
        return None
    for khoa_store in ctx.values():
        if not isinstance(khoa_store, dict) or KHOA_CONTEXT not in khoa_store:
            continue
        v = khoa_store[KHOA_CONTEXT]
        if isinstance(v, dict):
            v = v.get("msg")
        if v is None:
            return None
        s = str(v).strip()
        if len(s) >= 2 and s[0] == s[-1] == '"':
            try:
                s = str(json.loads(s))
            except json.JSONDecodeError:
                pass
        return s.upper()
    return None


def xac_dinh_kho_context(settings_js: str | None) -> str | None:
    """Doc settings.js cua Node-RED, tra ve module cua kho context MAC DINH.

    flows.json goi flow.get/set("ma_hop_le") KHONG kem ten kho, nen ma nam o kho
    mac dinh. Tra ve "memory" khi contextStorage khong bat (mac dinh cua
    Node-RED), ten module (vd "localfilesystem") neu bat, None neu khong doc duoc.
    """
    if settings_js is None:
        return None
    # Bo chu thich de khong nham khoi 'contextStorage' bi comment trong file mau.
    s = re.sub(r"/\*.*?\*/", "", settings_js, flags=re.S)
    s = re.sub(r"^\s*//.*$", "", s, flags=re.M)
    m = re.search(r"contextStorage\s*:\s*\{", s)
    if not m:
        return "memory"
    # Lay nguyen khoi { ... } bang dem ngoac.
    i, sau = m.end(), 1
    while i < len(s) and sau:
        sau += {"{": 1, "}": -1}.get(s[i], 0)
        i += 1
    khoi = s[m.end():i - 1]
    kho = dict(re.findall(r"([\w$]+)\s*:\s*\{[^{}]*?module\s*:\s*[\"']([\w-]+)[\"']", khoi))
    bi_danh = re.search(r"default\s*:\s*[\"']([\w$]+)[\"']", khoi)
    if "default" in kho:
        return kho["default"]
    if bi_danh and bi_danh.group(1) in kho:
        return kho[bi_danh.group(1)]
    return next(iter(kho.values()), None)      # Node-RED lay kho dau tien lam mac dinh


def huong_dan_dat_lai_context(kho: str | None, user_dir: Path | None, tab: str,
                              ma_flow: str) -> list[str]:
    """Cach dat lai 'ma_hop_le' cu the theo noi Node-RED luu context."""
    settings = user_dir / "settings.js" if user_dir else None
    if kho == "memory":
        return [f"{settings}: contextStorage khong bat -> context nam trong BO NHO.",
                "Cach dat lai: tat Node-RED (Ctrl+C o cua so dang chay node-red) roi chay",
                "lai lenh: node-red. Context bo nho mat khi tat, lan kiem ma dau tien sau",
                f"do se lay MA_MAC_DINH = {ma_flow} tu flow. Chay lai script nay de xac nhan."]
    if kho == "localfilesystem":
        thu_muc = user_dir / "context" / tab if user_dir else Path("<userDir>/context") / tab
        co = " (dang ton tai)" if thu_muc.exists() else " (khong thay - tim trong <userDir>\\context\\)"
        return [f"{settings}: contextStorage dung localfilesystem -> context luu ra FILE,",
                "khoi dong lai Node-RED KHONG xoa duoc ma cu.",
                "Cach dat lai: tat Node-RED, xoa thu muc context cua flow nay:",
                f"  {thu_muc}{co}",
                f"roi chay lai node-red. Lan kiem ma dau tien se lay MA_MAC_DINH = {ma_flow}."]
    if kho:
        return [f"{settings}: kho context mac dinh la module '{kho}' - script khong biet",
                "cach dat lai cho module nay. Xoa khoa ma_hop_le cua flow theo tai lieu module do."]
    return [f"Khong doc duoc settings.js{f' tai {settings}' if settings else ''} nen khong biet",
            "context luu o dau. Mo settings.js, tim 'contextStorage':",
            "  - dang bi comment (//) -> luu bo nho: tat Node-RED roi chay lai node-red.",
            f"  - co module 'localfilesystem' -> luu file: tat Node-RED, xoa <userDir>\\context\\{tab}\\,",
            "    roi chay lai node-red.",
            "Chi ro userDir bang --node-red-dir neu khong phai %USERPROFILE%\\.node-red."]


# ============================================================================
#  2. CAC MUC KIEM
# ============================================================================

def kiem_config() -> tuple[KetQua, dict | None]:
    try:
        cfg = load_config()
        prefix = cfg["mqtt"]["topic_prefix"]
        ma = cfg["secret"]["default_code"]
    except (OSError, json.JSONDecodeError, KeyError) as e:
        return KetQua(FAIL, "vision/config.json", [f"khong doc duoc: {e}"]), None
    return KetQua(PASS, "vision/config.json", [f"prefix topic : {prefix}",
                                               f"default_code : {ma}"]), cfg


def kiem_tflite(cfg: dict) -> KetQua:
    p = resolve_path(cfg["model"]["classifier_tflite"])
    ten = f"model phan loai {p.name}"
    if not p.exists():
        return KetQua(FAIL, ten, [f"khong co file {p}", "chay vision/train_classifier.ipynb"])
    try:
        import numpy as np
        # Dung DUNG ham nap ma gesture_lock.py dung, de kiem cung mot duong di.
        from gesture_lock import _load_tflite_interpreter
        interp, backend = _load_tflite_interpreter(p)
        interp.allocate_tensors()
        inp, out = interp.get_input_details()[0], interp.get_output_details()[0]
        interp.set_tensor(inp["index"], np.zeros((1, FEATURE_DIM), dtype=np.float32))
        interp.invoke()
        so_lop = int(interp.get_tensor(out["index"]).shape[-1])
        so_vao = int(inp["shape"][-1])
    except Exception as e:  # noqa: BLE001 — bat moi loi nap model de bao ro
        return KetQua(FAIL, ten, [f"khong nap duoc: {type(e).__name__}: {e}"])
    sua = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    ct = [f"so lop dau ra: {so_lop}  (can {len(cfg['gestures'])})",
          f"so chieu vao : {so_vao}  (can {FEATURE_DIM})",
          f"sua luc {sua}, nap qua {backend}"]
    ok = so_lop == len(cfg["gestures"]) and so_vao == FEATURE_DIM
    return KetQua(PASS if ok else FAIL, ten, ct)


def kiem_task(cfg: dict) -> KetQua:
    p = resolve_path(cfg["model"]["hand_landmarker_task"])
    ten = f"MediaPipe {p.name}"
    if not p.exists():
        return KetQua(FAIL, ten, ["khong co file - chay gesture_lock.py mot lan de tu tai,",
                                  f"hoac tai tu {cfg['model']['hand_landmarker_url']}"])
    n = p.stat().st_size
    # File .task la mot goi zip chua 2 model. Tai do dang thi zip hong -> bat duoc.
    try:
        with zipfile.ZipFile(p) as z:
            co = {i.filename for i in z.infolist()}
            hong = z.testzip()
    except zipfile.BadZipFile:
        return KetQua(FAIL, ten, [f"{n:,} byte, KHONG phai goi zip hop le - file tai do dang?",
                                  "xoa file roi chay lai de tai lai"])
    thieu = THANH_VIEN_TASK - co
    if thieu or hong:
        return KetQua(FAIL, ten, [f"thieu {sorted(thieu)}" if thieu else f"hong CRC: {hong}"])
    ct = [f"{n:,} byte, du 2 model ben trong, CRC dung"]
    if n != KICH_THUOC_TASK_DA_CHAY:
        ct.append(f"kich thuoc khac ban da chay dung ({KICH_THUOC_TASK_DA_CHAY:,} byte)")
        return KetQua(WARN, ten, ct)
    return KetQua(PASS, ten, ct)


def kiem_mqtt(cfg: dict) -> list[KetQua]:
    """Noi broker trong 10 giay, roi nghe .../state trong 15 giay."""
    import paho.mqtt.client as mqtt

    m = cfg["mqtt"]
    topic_state = m["topic_prefix"] + m["topics"]["state"]
    da_noi, co_state = threading.Event(), threading.Event()
    ban_tin: list[str] = []

    def on_connect(client, userdata, flags, reason_code, properties=None):
        if reason_code == 0:
            client.subscribe(topic_state, qos=0)
            da_noi.set()

    def on_message(client, userdata, msg):
        ban_tin.append(msg.payload.decode("utf-8", errors="replace"))
        co_state.set()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id="tienkiem-" + uuid.uuid4().hex[:8])
    client.on_connect, client.on_message = on_connect, on_message
    ten_broker = f"broker {m['broker']}:{m['port']}"
    try:
        client.connect_async(m["broker"], int(m["port"]), int(m["keepalive"]))
        client.loop_start()
        if not da_noi.wait(CHO_BROKER_GIAY):
            return [KetQua(FAIL, ten_broker, [f"khong noi duoc trong {CHO_BROKER_GIAY} giay",
                                              "kiem tra mang / tuong lua"]),
                    KetQua(FAIL, f"ESP32 tren {topic_state}", ["bo qua vi chua noi duoc broker"])]
        kq = [KetQua(PASS, ten_broker, ["da ket noi"])]
        print(f"   ... dang nghe {topic_state} toi da {CHO_STATE_GIAY} giay")
        if co_state.wait(CHO_STATE_GIAY):
            kq.append(KetQua(PASS, f"ESP32 tren {topic_state}", [f"nghe duoc: {ban_tin[0]}"]))
        else:
            kq.append(KetQua(FAIL, f"ESP32 tren {topic_state}", [
                f"khong nghe thay gi trong {CHO_STATE_GIAY} giay (ESP32 gui moi 5 giay)",
                "Wokwi chua chay hoac chua noi duoc broker",
                "xem OLED tren Wokwi co hien 'WiFi:OK  MQTT:OK' khong"]))
        return kq
    finally:
        client.loop_stop()
        client.disconnect()


def kiem_flows_file(cfg: dict) -> KetQua:
    ten = "MA_MAC_DINH trong file middleware/flows.json"
    try:
        nodes = json.loads(FLOWS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return KetQua(FAIL, ten, [f"khong parse duoc: {e}"])
    tim = tim_node_kiem_ma(nodes)
    ma_dung = cfg["secret"]["default_code"].upper()
    if len(tim) != 1:
        return KetQua(FAIL, ten, [f"tim thay {len(tim)} node co MA_MAC_DINH (can dung 1)"])
    ct = [f"MA_MAC_DINH = {tim[0]['ma']}   secret.default_code = {ma_dung}"]
    if tim[0]["ma"] != ma_dung:
        ct.append("LECH: sua MA_MAC_DINH trong flows.json cho khop config.json")
        return KetQua(FAIL, ten, ct)
    return KetQua(PASS, ten, ct)


def _get_json(url: str):
    req = urllib.request.Request(url, headers={"Node-RED-API-Version": "v1"})
    with urllib.request.urlopen(req, timeout=3) as r:
        return json.loads(r.read().decode("utf-8"))


def kiem_node_red(cfg: dict, base: str, user_dir: Path | None = None) -> list[KetQua]:
    """Hoi Node-RED dang chay: flow nao dang deploy, context dang giu ma gi.

    user_dir = thu muc userDir cua Node-RED (chua settings.js), dung de chi dung
    cach dat lai context. None thi in ca hai cach.
    """
    base = base.rstrip("/")
    ma_dung = cfg["secret"]["default_code"].upper()
    ten = f"flow DANG CHAY trong Node-RED ({base})"
    try:
        flows = _get_json(base + "/flows")
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return [KetQua(WARN, ten, ["Node-RED bat adminAuth, khong doc duoc flow dang chay",
                                       "tu kiem trong editor: mo node 'Kiem ma', xem MA_MAC_DINH"])]
        return [KetQua(FAIL, ten, [f"HTTP {e.code}"])]
    except (urllib.error.URLError, OSError) as e:
        return [KetQua(FAIL, ten, [
            "Node-RED chua chay.",
            f"(khong ket noi duoc {base}: {e})",
            "Cach sua: mo mot cua so lenh, chay: node-red",
            "doi dong 'Server now running at http://127.0.0.1:1880/' roi chay lai script nay."])]
    if isinstance(flows, dict):                     # Node-RED-API-Version v2
        flows = flows.get("flows", [])

    tim = tim_node_kiem_ma(flows)
    chay = [n for n in tim if n["dang_chay"]]
    ct = [f"tab '{n['ten_tab']}' ({n['tab']}): MA_MAC_DINH = {n['ma']}"
          + ("" if n["dang_chay"] else "  [dang disable]") for n in tim]
    if not chay:
        return [KetQua(FAIL, ten, ct + ["KHONG co node kiem ma nao dang chay - chua import flows.json?"])]
    if len(chay) > 1:
        return [KetQua(FAIL, ten, ct + [
            f"CO {len(chay)} NODE KIEM MA CHAY CUNG LUC: moi sequence se nhan {len(chay)} lenh cmd.",
            "Cach sua: Xoa tab flow cu, Deploy, roi Import lai.",
            "  1. Trong editor, nhap phai TUNG tab o tren -> Delete. Bam Deploy.",
            "  2. Menu (3 gach) -> Import -> chon middleware/flows.json -> Import. Bam Deploy.",
            "  3. Chay lai script nay: phai con dung 1 node kiem ma."])]
    n = chay[0]
    kq = []
    if n["ma"] != ma_dung:
        kq.append(KetQua(FAIL, ten, ct + [f"LECH voi secret.default_code = {ma_dung}",
                                          "-> chua import lai flows.json moi"]))
    else:
        kq.append(KetQua(PASS, ten, ct))

    # --- Ma trong flow context: thu ma Kiem ma THUC SU dung ---
    ten_ctx = f"flow context '{KHOA_CONTEXT}' (ma Node-RED THUC SU dung)"
    try:
        ma_ctx = doc_ma_tu_context(_get_json(f"{base}/context/flow/{n['tab']}"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
        kq.append(KetQua(WARN, ten_ctx, [f"khong doc duoc context: {e}"]))
        return kq
    if ma_ctx is None:
        kq.append(KetQua(PASS, ten_ctx, [
            "context chua co ma - lan kiem ma dau tien se lay MA_MAC_DINH = " + n["ma"]]))
    elif ma_ctx != ma_dung:
        settings = user_dir / "settings.js" if user_dir else None
        try:
            noi_dung = settings.read_text(encoding="utf-8") if settings else None
        except OSError:
            noi_dung = None
        kho = xac_dinh_kho_context(noi_dung)
        kq.append(KetQua(FAIL, ten_ctx, [
            f"Node-RED dang giu ma {ma_ctx}, khac secret.default_code = {ma_dung}.",
            "Kiem ma chi doc MA_MAC_DINH khi context con trong, nen import flow moi de",
            "len KHONG doi duoc ma nay - phai xoa context.",
        ] + huong_dan_dat_lai_context(kho, user_dir, n["tab"], n["ma"])))
    else:
        kq.append(KetQua(PASS, ten_ctx, [f"ma_hop_le = {ma_ctx}"]))
    return kq


# ============================================================================
#  3. MAIN
# ============================================================================

def in_ket_qua(kq: KetQua, co_mau: bool) -> None:
    nhan = f"[{kq.trang_thai:^8}]"
    if co_mau:
        nhan = MAU[kq.trang_thai] + nhan + HET_MAU
    print(f"{nhan} {kq.ten}")
    for d in kq.chi_tiet:
        print(f"           {d}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Tien kiem truoc phien chay that.")
    ap.add_argument("--node-red", default="http://localhost:1880", help="dia chi Node-RED")
    ap.add_argument("--node-red-dir", default=str(Path.home() / ".node-red"),
                    help="userDir cua Node-RED (chua settings.js)")
    ap.add_argument("--khong-mau", action="store_true", help="tat mau ANSI")
    args = ap.parse_args()
    co_mau = not args.khong_mau
    if co_mau and os.name == "nt":
        os.system("")                               # bat ma mau ANSI tren console Windows 10

    print("TIEN KIEM TRUOC KHI DEMO\n")
    tat_ca: list[KetQua] = []

    def them(kq):
        for k in (kq if isinstance(kq, list) else [kq]):
            in_ket_qua(k, co_mau)
            tat_ca.append(k)

    kq_cfg, cfg = kiem_config()
    them(kq_cfg)
    if cfg is None:
        return 1
    them(kiem_tflite(cfg))
    them(kiem_task(cfg))
    them(kiem_mqtt(cfg))
    them(kiem_flows_file(cfg))
    them(kiem_node_red(cfg, args.node_red, Path(args.node_red_dir)))

    hong = [k for k in tat_ca if k.trang_thai == FAIL]
    canh_bao = [k for k in tat_ca if k.trang_thai == WARN]
    print()
    print("=" * 70)
    print(f"{len(tat_ca) - len(hong) - len(canh_bao)} PASS, {len(canh_bao)} CANH BAO, "
          f"{len(hong)} FAIL")
    for k in hong:
        dong = f"  FAIL: {k.ten}"
        print(MAU[FAIL] + dong + HET_MAU if co_mau else dong)
    print("=" * 70)
    return 1 if hong else 0


if __name__ == "__main__":
    sys.exit(main())
