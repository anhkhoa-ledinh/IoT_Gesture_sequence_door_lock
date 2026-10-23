"""
============================================================================
 ve_sinh_du_lieu_20261023.py — Ve sinh keypoint.csv mot lan, ngay 23/10/2026
----------------------------------------------------------------------------
 Chay (MOT LAN DUY NHAT):
   D:\\IoT_Gesture_sequence_door_lock\\.conda\\python.exe scripts\\ve_sinh_du_lieu_20261023.py

 Lam ba viec, theo dung thu tu:
   1. Sao luu keypoint.csv -> keypoint_backup_20261023.csv (giu nguyen tung byte).
   2. Sinh keypoint_meta.csv (session_id, burst_id) cho du lieu cu. Du lieu cu
      khong ghi lai phien va burst, nen suy ra giong scripts/chan_doan_du_lieu.py:
        session_id = "legacy_<ten lop>"   (moi lop duoc thu trong mot phien lien mach)
        burst_id   = "legacy_<ten lop>_bNN" (doan dong lien tiep cung nhan, cat moi 30 mau)
   3. Bo 3 burst lop none o dong 2228-2317 cua file goc. Ly do (Phase 2,
      muc 3c): 3 burst nay duoc ghi ngay sau lop ok va co 81% / 96% / 64% lang
      gieng (ngoai burst) la mau ok — day la ban tay dang lam ok bi dan nhan none,
      nguon goc truc tiep cua cap nham ok <-> none.

 Script tu tu choi chay lan thu hai (neu da co file sao luu), va kiem lai rang
 dong can xoa dung la 3 burst none tron ven truoc khi ghi bat cu thu gi.
============================================================================
"""

from __future__ import annotations

import csv
import shutil
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "vision"))
sys.path.insert(0, str(ROOT / "scripts"))
from common import gesture_tables, load_config, resolve_path  # noqa: E402
from chan_doan_du_lieu import chia_burst                     # noqa: E402

import numpy as np  # noqa: E402

DONG_XOA_TU, DONG_XOA_DEN = 2228, 2317     # so dong trong file goc, tinh tu 1, ca hai dau
LOP_XOA = "none"
SO_BURST_XOA = 3


def main() -> int:
    cfg = load_config()
    ten, _ = gesture_tables(cfg)
    goc = resolve_path(cfg["model"]["keypoint_csv"])
    meta = resolve_path(cfg["model"]["keypoint_meta_csv"])
    sao_luu = goc.with_name("keypoint_backup_20261023.csv")

    if sao_luu.exists() or meta.exists():
        print(f"DUNG: da co {sao_luu.name} hoac {meta.name} -> script nay da chay roi.")
        print("Khong chay lai de tranh xoa them 90 dong nua.")
        return 1

    # --- Doc tung dong NGUYEN BAN (giu \r\n) de dong giu lai khong doi mot byte ---
    dong_tho = goc.read_bytes().splitlines(keepends=True)
    dong_tho = [d for d in dong_tho if d.strip()]
    y = np.array([int(d.split(b",", 1)[0]) for d in dong_tho])

    # --- Suy burst cho du lieu cu, dung dung cach cua Phase 2 ---
    burst = chia_burst(y, cfg["collect"]["burst_samples"])
    stt_trong_lop: dict[int, int] = {}
    nhan_burst: dict[int, str] = {}
    for b in np.unique(burst):
        c = int(y[burst == b][0])
        k = stt_trong_lop.get(c, 0)
        stt_trong_lop[c] = k + 1
        nhan_burst[int(b)] = f"legacy_{ten[c]}_b{k:02d}"

    # --- Kiem tra dong can xoa: dung lop none, dung 3 burst tron ven ---
    xoa = np.zeros(len(y), dtype=bool)
    xoa[DONG_XOA_TU - 1:DONG_XOA_DEN] = True
    ma_none = {v: k for k, v in ten.items()}[LOP_XOA]
    assert (y[xoa] == ma_none).all(), "Co dong khong phai lop none trong khoang xoa"
    burst_xoa = set(burst[xoa].tolist())
    assert len(burst_xoa) == SO_BURST_XOA, f"Khoang xoa trai tren {len(burst_xoa)} burst"
    for b in burst_xoa:
        assert xoa[burst == b].all(), f"Burst {nhan_burst[b]} chi bi xoa mot phan"

    truoc = Counter(y.tolist())

    # --- 1. Sao luu (copy2 giu ca thoi diem sua file) ---
    shutil.copy2(goc, sao_luu)

    # --- 2 + 3. Ghi lai keypoint.csv va keypoint_meta.csv, bo 90 dong ---
    giu = ~xoa
    with open(goc, "wb") as f:
        f.writelines(d for d, g in zip(dong_tho, giu) if g)
    with open(meta, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["session_id", "burst_id"])
        for i in np.where(giu)[0]:
            w.writerow([f"legacy_{ten[int(y[i])]}", nhan_burst[int(burst[i])]])

    sau = Counter(y[giu].tolist())
    print(f"Sao luu   : {sao_luu}")
    print(f"Meta      : {meta}")
    print(f"Da xoa    : dong {DONG_XOA_TU}-{DONG_XOA_DEN} cua file goc "
          f"({int(xoa.sum())} mau, burst {', '.join(sorted(nhan_burst[b] for b in burst_xoa))})")
    print()
    print(f"{'lop':<11}{'truoc':>8}{'sau':>8}{'burst con lai':>15}")
    print("-" * 42)
    for c in sorted(ten):
        so_burst = len({int(b) for b in burst[giu & (y == c)]})
        print(f"{ten[c]:<11}{truoc[c]:>8}{sau[c]:>8}{so_burst:>15}")
    print("-" * 42)
    print(f"{'tong':<11}{len(y):>8}{int(giu.sum()):>8}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
