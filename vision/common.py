"""
============================================================================
 common.py — Tien xu ly landmark va cac tien ich dung chung
----------------------------------------------------------------------------
 File nay duoc DUNG LAI boi ca collect_data.py (thu du lieu) va
 gesture_lock.py (nhan dien that). Quan trong: khau tien xu ly khi THU du lieu
 va khi NHAN DIEN phai giong nhau tuyet doi, neu khong model se doan sai.
 Vi vay chi co DUNG MOT ban preprocess_landmarks() o day, khong copy di dau.
============================================================================
"""

from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

import numpy as np

# Thu muc vision/ — moi duong dan tuong doi trong config.json tinh tu day.
VISION_DIR = Path(__file__).resolve().parent

# Cac doan noi giua 21 diem moc ban tay, dung de ve khung xuong len anh.
# Day la bo noi chuan cua MediaPipe Hand (21 diem, 21 doan).
HAND_CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 4),            # ngon cai
    (0, 5), (5, 6), (6, 7), (7, 8),            # ngon tro
    (5, 9), (9, 10), (10, 11), (11, 12),       # ngon giua
    (9, 13), (13, 14), (14, 15), (15, 16),     # ngon ap ut
    (13, 17), (17, 18), (18, 19), (19, 20),    # ngon ut
    (0, 17),                                   # canh long ban tay
)

NUM_LANDMARKS = 21
FEATURE_DIM = NUM_LANDMARKS * 2  # 42


# ============================================================================
#  1. CAU HINH
# ============================================================================

def load_config(path: str | os.PathLike | None = None) -> dict:
    """Doc vision/config.json. Moi tham so cua he thong nam o day, khong
    hardcode trong code Python."""
    cfg_path = Path(path) if path else VISION_DIR / "config.json"
    with open(cfg_path, "r", encoding="utf-8") as f:
        return json.load(f)


def resolve_path(cfg_relative: str) -> Path:
    """Doi duong dan tuong doi trong config.json thanh duong dan tuyet doi."""
    return (VISION_DIR / cfg_relative).resolve()


def gesture_tables(cfg: dict) -> tuple[dict[int, str], dict[str, str]]:
    """Tra ve (class_id -> label, label -> hex) lay tu config.json.

    Lop 'none' co hex = null nen khong nam trong bang hex.
    """
    id_to_label = {g["class_id"]: g["label"] for g in cfg["gestures"]}
    label_to_hex = {g["label"]: g["hex"] for g in cfg["gestures"] if g["hex"]}
    return id_to_label, label_to_hex


# ============================================================================
#  2. TIEN XU LY LANDMARK  — TRAI TIM CUA HE THONG
# ============================================================================

def _to_xy_array(hand_landmarks) -> np.ndarray:
    """Gom 21 diem moc thanh mang (21, 2).

    Chap nhan 2 dang dau vao:
      - list cac object co thuoc tinh .x .y  (dang MediaPipe Tasks tra ve)
      - list cac cap (x, y) hoac (x, y, z)   (dung cho unit test, khong can
        phai dung toi MediaPipe)
    """
    pts = []
    for lm in hand_landmarks:
        if hasattr(lm, "x") and hasattr(lm, "y"):
            pts.append((float(lm.x), float(lm.y)))
        else:
            pts.append((float(lm[0]), float(lm[1])))

    arr = np.asarray(pts, dtype=np.float32)
    if arr.shape != (NUM_LANDMARKS, 2):
        raise ValueError(
            f"Can dung {NUM_LANDMARKS} diem moc, nhan duoc {arr.shape[0]}"
        )
    return arr


def preprocess_landmarks(hand_landmarks, handedness: str) -> np.ndarray:
    """Bien 21 diem moc ban tay thanh vector dac trung 42 chieu.

    Ba buoc chuan hoa, lam dung thu tu nay:

      1. DOI GOC ve co tay (diem 0). Nho vay tay o goc trai hay goc phai
         khung hinh deu cho ra cung mot vector — bo di anh huong vi tri.

      2. LAT DAU TRUC X neu la tay trai. Moi thu duoc quy ve "tay phai", nen
         model chi phai hoc mot nua so truong hop, va nguoi dung tay trai hay
         tay phai deu dung duoc.

      3. CHIA CHO GIA TRI TUYET DOI LON NHAT (tinh chung ca x lan y). Nho vay
         tay gan camera (to) hay xa camera (nho) deu cho ra cung mot vector —
         bo di anh huong khoang cach.

    Tham so:
      hand_landmarks : 21 diem moc, toa do chuan hoa 0..1 cua MediaPipe
      handedness     : "Left" hoac "Right" (result.handedness[0][0].category_name)

    Tra ve:
      np.ndarray shape (42,) dtype float32, duoi phang theo thu tu
      x0, y0, x1, y1, ..., x20, y20
    """
    arr = _to_xy_array(hand_landmarks)

    # Buoc 1 — doi goc toa do ve co tay.
    arr = arr - arr[0]

    # Buoc 2 — quy tay trai ve tay phai bang cach lat dau truc x.
    if handedness == "Left":
        arr[:, 0] = -arr[:, 0]

    # Buoc 3 — chuan hoa ty le. Lay max tren CA x va y de giu dung ty le
    # ngang/doc cua ban tay (neu chia rieng tung truc se lam meo hinh dang).
    max_abs = float(np.max(np.abs(arr)))
    if max_abs > 0.0:
        arr = arr / max_abs

    return arr.flatten().astype(np.float32)


# ============================================================================
#  3. TAI MODEL HAND LANDMARKER
# ============================================================================

def ensure_hand_landmarker(cfg: dict, verbose: bool = True) -> Path:
    """Tra ve duong dan toi hand_landmarker.task, tu tai ve neu chua co.

    Nguon: xem model.hand_landmarker_url trong config.json (ghi ca trong README).
    """
    dest = resolve_path(cfg["model"]["hand_landmarker_task"])
    if dest.exists() and dest.stat().st_size > 0:
        return dest

    url = cfg["model"]["hand_landmarker_url"]
    dest.parent.mkdir(parents=True, exist_ok=True)
    if verbose:
        print(f"[common] Chua co model, dang tai ve: {dest.name}")
        print(f"[common] Nguon: {url}")

    # Tai ra file tam roi doi ten, tranh de lai file hong neu mang dut giua chung.
    tmp = dest.with_suffix(dest.suffix + ".part")
    urllib.request.urlretrieve(url, tmp)
    tmp.replace(dest)

    if verbose:
        print(f"[common] Tai xong ({dest.stat().st_size / 1024:.0f} KB)")
    return dest


# ============================================================================
#  3b. KET NOI MQTT — broker cong cong HOAC broker rieng (TLS + tai khoan)
# ----------------------------------------------------------------------------
#  Moi chuong trinh Python noi MQTT (gesture_lock.py, dem_10_lan.py,
#  kiem_truoc_khi_demo.py) deu goi ham nay, nen doi broker chi can sua
#  config.json -> mqtt.dung_broker_rieng, khong sua code.
#
#  Moi chuong trinh dung mot TAI KHOAN rieng ("vai tro"), broker phan quyen
#  theo tung tai khoan (xem docs/BROKER_RIENG_TLS.md):
#    laptop   : chi duoc GUI .../gesture va .../sequence
#    giam_sat : chi duoc NGHE .../#  (dung cho cac script do va kiem tra)
#  Mat khau KHONG nam trong config.json: nam trong file tai_khoan_file
#  (mac dinh vision/mqtt_tai_khoan.json, da dua vao .gitignore).
# ============================================================================

def thong_so_mqtt(cfg: dict, vai_tro: str) -> dict:
    """Tra ve thong so ket noi: host, port, tls, va neu dung broker rieng thi
    them ca_file, username, password cua vai_tro."""
    m = cfg["mqtt"]
    if not m.get("dung_broker_rieng", False):
        return {"host": m["broker"], "port": int(m["port"]), "tls": False}

    r = m["broker_rieng"]
    tk_path = resolve_path(r["tai_khoan_file"])
    if not tk_path.exists():
        raise FileNotFoundError(
            f"Dang bat dung_broker_rieng nhung chua co {tk_path}.\n"
            "Chay: .conda\\python.exe scripts\\tao_tai_khoan_mqtt.py --host <dia chi broker>"
        )
    with open(tk_path, "r", encoding="utf-8") as f:
        tat_ca = json.load(f)
    if vai_tro not in tat_ca:
        raise KeyError(f"{tk_path.name} khong co tai khoan cho vai tro '{vai_tro}'")

    ca_file = resolve_path(r["ca_file"])
    if not ca_file.exists():
        raise FileNotFoundError(f"Khong thay chung chi CA: {ca_file}")
    return {
        "host": r["host"],
        "port": int(r["port"]),
        "tls": True,
        "ca_file": str(ca_file),
        "username": tat_ca[vai_tro]["username"],
        "password": tat_ca[vai_tro]["password"],
    }


def cau_hinh_mqtt_client(client, cfg: dict, vai_tro: str) -> tuple[str, int]:
    """Gan TLS + tai khoan vao client paho neu dang dung broker rieng.

    Tra ve (host, port) de goi client.connect_async(host, port, keepalive).
    Voi broker cong cong thi khong gan gi, giu nguyen hanh vi cu.
    """
    ts = thong_so_mqtt(cfg, vai_tro)
    if ts["tls"]:
        import ssl
        # CERT_REQUIRED + kiem ten may chu: chong gia mao broker (man-in-the-middle).
        client.tls_set(ca_certs=ts["ca_file"], cert_reqs=ssl.CERT_REQUIRED,
                       tls_version=ssl.PROTOCOL_TLS_CLIENT)
        client.username_pw_set(ts["username"], ts["password"])
    return ts["host"], ts["port"]


# ============================================================================
#  4. VE KHUNG XUONG BAN TAY
# ============================================================================

def draw_landmarks(image, hand_landmarks, color=(0, 255, 0)) -> None:
    """Ve khung xuong ban tay len anh (sua truc tiep tren `image`).

    Tu ve bang cv2 chu khong dung mediapipe.solutions.drawing_utils, de toan bo
    du an chi phu thuoc vao Tasks API.
    """
    import cv2  # import tai cho de common.py van test duoc khi khong co cv2

    h, w = image.shape[:2]
    pts = [(int(lm.x * w), int(lm.y * h)) for lm in hand_landmarks]

    for a, b in HAND_CONNECTIONS:
        cv2.line(image, pts[a], pts[b], color, 2)
    for i, p in enumerate(pts):
        # Dau ngon tay ve to hon cho de nhin.
        r = 5 if i in (4, 8, 12, 16, 20) else 3
        cv2.circle(image, p, r, (255, 255, 255), -1)
        cv2.circle(image, p, r, color, 1)
