"""
============================================================================
 doc_access_log.py — Thong ke middleware/access_log.csv do Node-RED ghi ra
----------------------------------------------------------------------------
 Chay:
   D:\\IoT_Gesture_sequence_door_lock\\.conda\\python.exe scripts\\doc_access_log.py
   ... --tu "2026-10-24 14:00" --den "2026-10-24 15:00"   (chi tinh trong khoang, gio may)
   ... --ra docs\\thong_ke_access_log.md                   (file markdown xuat ra)

 In thong ke ra man hinh va GHI LAI (ghi de) file markdown — file do luon sinh
 lai duoc tu access_log.csv nen ghi de khong mat gi.

 Dinh dang log (function "Chuan bi dong CSV" trong flows.json):
   timestamp,ma_nhap,ket_qua,so_lan_sai_lien_tiep
 timestamp la ISO 8601 gio UTC (Date.toISOString). Node csv ghi dong tieu de
 MOT LAN SAU MOI LAN DEPLOY, nen giua file co the lap lai dong tieu de — bo qua.
============================================================================
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "vision"))
from common import load_config  # noqa: E402

LOG_MAC_DINH = ROOT / "middleware" / "access_log.csv"
TIEU_DE = ["timestamp", "ma_nhap", "ket_qua", "so_lan_sai_lien_tiep"]

# Loai ket qua, suy tu chuoi ket_qua ma function "Kiem ma" / "Lenh mo khan cap" ghi.
MO_BANG_MA, SAI, SAI_GAY_LOCKOUT = "MO BANG MA", "SAI", "SAI -> LOCKOUT"
BI_CHAN, MO_KHAN_CAP, KHAC = "BI CHAN (lockout)", "MO KHAN CAP", "KHAC"
CO_DAU = {MO_BANG_MA: "Mở bằng mã", SAI: "Sai mã", SAI_GAY_LOCKOUT: "Sai mã → kích hoạt lockout",
          BI_CHAN: "Bị chặn do đang lockout", MO_KHAN_CAP: "Mở khẩn cấp từ Dashboard",
          KHAC: "Không nhận ra"}


@dataclass
class DongLog:
    thoi_diem: datetime | None          # gio may (da doi tu UTC)
    ma: str
    ket_qua: str
    loai: str


def phan_loai(ket_qua: str) -> str:
    k = ket_qua.strip().upper()
    if k.startswith("DUNG"):
        return MO_BANG_MA
    if k.startswith("MO TU DASHBOARD"):
        return MO_KHAN_CAP
    if k.startswith("BI CHAN"):
        return BI_CHAN
    if k.startswith("SAI"):
        return SAI_GAY_LOCKOUT if "LOCKOUT" in k else SAI
    return KHAC


def doc_log(path: Path) -> tuple[list[DongLog], int, int]:
    """Tra ve (cac dong, so dong tieu de gap, so dong hong)."""
    dong, so_tieu_de, hong = [], 0, 0
    with open(path, "r", newline="", encoding="utf-8-sig", errors="replace") as f:
        for row in csv.reader(f):
            if not row or not any(c.strip() for c in row):
                continue
            if [c.strip() for c in row] == TIEU_DE:
                so_tieu_de += 1
                continue
            if len(row) < 3:
                hong += 1
                continue
            try:
                t = datetime.fromisoformat(row[0].strip()).astimezone()
            except ValueError:
                t = None
            dong.append(DongLog(t, row[1].strip(), row[2].strip(), phan_loai(row[2])))
    return dong, so_tieu_de, hong


def loc_thoi_gian(dong: list[DongLog], tu: datetime | None, den: datetime | None) -> list[DongLog]:
    """tu / den la gio may (naive). Dong khong doc duoc thoi diem bi loai khi co loc."""
    if tu is None and den is None:
        return dong
    tu = tu.astimezone() if tu else None
    den = den.astimezone() if den else None
    return [d for d in dong if d.thoi_diem is not None
            and (tu is None or d.thoi_diem >= tu) and (den is None or d.thoi_diem <= den)]


def thong_ke(dong: list[DongLog]) -> dict:
    loai = Counter(d.loai for d in dong)
    nhap_ma = [d for d in dong if d.loai != MO_KHAN_CAP]
    theo_ma: dict[str, Counter] = {}
    for d in nhap_ma:
        theo_ma.setdefault(d.ma, Counter())[d.loai] += 1
    tg = [d.thoi_diem for d in dong if d.thoi_diem]
    return {
        "tong_dong": len(dong),
        "lan_nhap_ma": len(nhap_ma),
        "loai": loai,
        "theo_ma": dict(sorted(theo_ma.items(), key=lambda kv: -sum(kv[1].values()))),
        "tu": min(tg) if tg else None,
        "den": max(tg) if tg else None,
    }


def _ti_le(a: int, b: int) -> str:
    return f"{a / b:.1%}" if b else "N/A"


def in_man_hinh(tk: dict, ma_dung: str, so_tieu_de: int, hong: int) -> None:
    L = tk["loai"]
    print("=" * 66)
    print("THONG KE access_log.csv")
    print("=" * 66)
    if tk["tu"]:
        print(f"Khoang thoi gian : {tk['tu']:%Y-%m-%d %H:%M:%S} -> {tk['den']:%Y-%m-%d %H:%M:%S}")
    print(f"Dong tieu de gap : {so_tieu_de} (moi lan deploy Node-RED ghi lai 1 lan)")
    if hong:
        print(f"Dong hong bo qua : {hong}")
    print(f"Tong so lan nhap ma             : {tk['lan_nhap_ma']}")
    print(f"  mo khoa thanh cong            : {L[MO_BANG_MA]}  "
          f"({_ti_le(L[MO_BANG_MA], tk['lan_nhap_ma'])})")
    print(f"  sai ma                        : {L[SAI] + L[SAI_GAY_LOCKOUT]}"
          f"  (trong do {L[SAI_GAY_LOCKOUT]} lan kich hoat lockout)")
    print(f"  bi chan do dang lockout       : {L[BI_CHAN]}")
    if L[KHAC]:
        print(f"  khong nhan ra ket qua         : {L[KHAC]}")
    print(f"Mo khan cap tu Dashboard        : {L[MO_KHAN_CAP]}")
    print("-" * 66)
    print(f"{'ma nhap':<16}{'so lan':>7}{'mo':>5}{'sai':>5}{'bi chan':>9}")
    for ma, c in tk["theo_ma"].items():
        nhan = ma + (" (dung)" if ma.upper() == ma_dung else "")
        print(f"{nhan:<16}{sum(c.values()):>7}{c[MO_BANG_MA]:>5}"
              f"{c[SAI] + c[SAI_GAY_LOCKOUT]:>5}{c[BI_CHAN]:>9}")
    print("=" * 66)


def tao_markdown(tk: dict, ma_dung: str, nguon: Path, so_tieu_de: int, hong: int,
                 loc: str) -> str:
    L = tk["loai"]
    o = ["# Thống kê `access_log.csv`", "",
         f"Sinh tự động bởi `scripts/doc_access_log.py` lúc {datetime.now():%Y-%m-%d %H:%M:%S} "
         f"từ `{nguon.name}`. Chạy lại script để cập nhật — không sửa tay file này.", ""]
    if loc:
        o.append(f"- Bộ lọc thời gian: {loc}")
    if tk["tu"]:
        o.append(f"- Khoảng thời gian có dữ liệu: {tk['tu']:%Y-%m-%d %H:%M:%S} → "
                 f"{tk['den']:%Y-%m-%d %H:%M:%S} (giờ máy)")
    o.append(f"- Dòng tiêu đề gặp trong file: {so_tieu_de} (Node-RED ghi lại sau mỗi lần deploy)")
    if hong:
        o.append(f"- Dòng hỏng bỏ qua: {hong}")
    o += ["", "| Chỉ số | Số lần | Tỉ lệ trên số lần nhập mã |", "|---|---|---|",
          f"| **Tổng số lần nhập mã** | **{tk['lan_nhap_ma']}** | |",
          f"| Mở khóa thành công | {L[MO_BANG_MA]} | {_ti_le(L[MO_BANG_MA], tk['lan_nhap_ma'])} |",
          f"| Sai mã (chưa tới ngưỡng) | {L[SAI]} | {_ti_le(L[SAI], tk['lan_nhap_ma'])} |",
          f"| Sai mã → kích hoạt lockout | {L[SAI_GAY_LOCKOUT]} | "
          f"{_ti_le(L[SAI_GAY_LOCKOUT], tk['lan_nhap_ma'])} |",
          f"| Bị chặn do đang lockout | {L[BI_CHAN]} | {_ti_le(L[BI_CHAN], tk['lan_nhap_ma'])} |"]
    if L[KHAC]:
        o.append(f"| Không nhận ra kết quả | {L[KHAC]} | |")
    o += [f"| Mở khẩn cấp từ Dashboard *(không tính là nhập mã)* | {L[MO_KHAN_CAP]} | |",
          "", "## Phân bố theo mã nhập", "",
          "| Mã nhập | Số lần | Mở | Sai | Bị chặn (lockout) |", "|---|---|---|---|---|"]
    for ma, c in tk["theo_ma"].items():
        nhan = f"`{ma}`" + (" **(mã đúng)**" if ma.upper() == ma_dung else "")
        o.append(f"| {nhan} | {sum(c.values())} | {c[MO_BANG_MA]} | "
                 f"{c[SAI] + c[SAI_GAY_LOCKOUT]} | {c[BI_CHAN]} |")
    return "\n".join(o) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Thong ke access_log.csv cua Node-RED.")
    ap.add_argument("log", nargs="?", default=str(LOG_MAC_DINH), help="duong dan access_log.csv")
    ap.add_argument("--tu", help='chi tinh tu thoi diem nay, vd "2026-10-24 14:00" (gio may)')
    ap.add_argument("--den", help="chi tinh den thoi diem nay (gio may)")
    ap.add_argument("--ra", default=str(ROOT / "docs" / "thong_ke_access_log.md"),
                    help="file markdown xuat ra")
    args = ap.parse_args()

    path = Path(args.log)
    if not path.exists():
        print(f"Chua co {path}")
        print("Node-RED chua ghi lan thu nao. Chay phien do (B2) roi chay lai script nay.")
        return 1
    try:
        tu = datetime.fromisoformat(args.tu) if args.tu else None
        den = datetime.fromisoformat(args.den) if args.den else None
    except ValueError as e:
        print(f"LOI: --tu / --den sai dinh dang ({e}). Vi du: \"2026-10-24 14:00\"")
        return 1

    ma_dung = load_config()["secret"]["default_code"].upper()
    dong, so_tieu_de, hong = doc_log(path)
    dong = loc_thoi_gian(dong, tu, den)
    tk = thong_ke(dong)
    in_man_hinh(tk, ma_dung, so_tieu_de, hong)

    loc = ""
    if tu or den:
        loc = f"từ {args.tu or '(đầu file)'} đến {args.den or '(cuối file)'}"
    ra = Path(args.ra)
    ra.parent.mkdir(parents=True, exist_ok=True)
    ra.write_text(tao_markdown(tk, ma_dung, path, so_tieu_de, hong, loc),
                  encoding="utf-8", newline="\n")
    print(f"Da ghi {ra}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
