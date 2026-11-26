"""
chuyen_du_lieu_github.py — gom du lieu landmark cong khai tren GitHub thanh
vision/model/keypoint_github.csv (cung dinh dang voi keypoint.csv).

Nguon (ca hai deu giay phep Apache-2.0, cung pipeline MediaPipe Hands -> 21 diem
-> doi goc co tay -> chia max_abs giong het common.preprocess_landmarks):

  1. thatsabhishek/hand-gesture-recognition-using-mediapipe
     = du lieu goc cua Kazuhito00 (Open/Close/Pointer) + OK cua kinivi
       + Peace / Thumbs Up do tac gia thu them
  2. jaeeun/hand-gesture-recognition-using-mediapipe
     = bo thu doc lap (12 lop), lay 6 lop trung voi du an

Hai bo khong trung dong nao voi nhau (da kiem). Cac lop khong co trong du an
(Walking, Gun, Heart, ...) bi bo.

KHAC BIET DUY NHAT CAN SUA: cac repo tren lay toa do theo PIXEL
(x * rong_anh, y * cao_anh) nen giu dung ty le that cua ban tay. Du an nay lay
toa do CHUAN HOA 0..1 cua camera 640x480, tuc truc x bi nen lai 480/640 = 0.75
lan so voi truc y. Vi vay: nhan toa do x voi 0.75 roi chuan hoa max_abs lai.
Phep doi nay CHINH XAC (khong xap xi) vi pixel la hinh vuong.

Cach chay (can mang, chi chay mot lan):
    .conda\\python.exe scripts\\chuyen_du_lieu_github.py
Hoac neu da tai san cac file keypoint.csv ve thu muc:
    .conda\\python.exe scripts\\chuyen_du_lieu_github.py --thu-muc duong\\dan
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
import urllib.request
from pathlib import Path

import numpy as np

GOC = Path(__file__).resolve().parents[1]
RA_CSV = GOC / "vision" / "model" / "keypoint_github.csv"
RA_META = GOC / "vision" / "model" / "keypoint_github_meta.csv"

CAM_W, CAM_H = 640, 480          # phai khop camera.frame_width / frame_height trong config.json

# repo -> {nhan goc: class_id cua du an}
#   class_id du an: 0 fist, 1 palm, 2 victory, 3 thumb_up, 4 point_up, 5 ok
NGUON = {
    "thatsabhishek/hand-gesture-recognition-using-mediapipe": {
        0: 1,   # Open      -> palm
        1: 0,   # Close     -> fist
        2: 4,   # Pointer   -> point_up
        3: 5,   # OK        -> ok
        4: 2,   # Peace     -> victory
        5: 3,   # Thumbs Up -> thumb_up
    },
    "jaeeun/hand-gesture-recognition-using-mediapipe": {
        0: 1,   # Open    -> palm
        1: 0,   # Close   -> fist
        2: 4,   # Pointer -> point_up
        3: 5,   # OK      -> ok
        4: 2,   # V       -> victory
        8: 3,   # Thumb   -> thumb_up
    },
}
DUONG_DAN = "https://raw.githubusercontent.com/{repo}/main/model/keypoint_classifier/keypoint.csv"


def doc_nguon(repo: str, thu_muc: Path | None) -> list[list[str]]:
    """Doc file keypoint.csv cua mot repo: tu thu muc co san, hoac tai tu GitHub."""
    if thu_muc is not None:
        p = thu_muc / repo.split("/")[0] / "keypoint.csv"
        text = p.read_text(encoding="utf-8-sig")
    else:
        with urllib.request.urlopen(DUONG_DAN.format(repo=repo), timeout=60) as r:
            text = r.read().decode("utf-8-sig")
    return [row for row in csv.reader(io.StringIO(text)) if row]


def pixel_sang_camera(vec42: np.ndarray) -> np.ndarray:
    """Doi vector 42 chieu tu quy uoc PIXEL sang quy uoc chuan hoa cua camera du an."""
    p = vec42.reshape(21, 2).astype(np.float64).copy()
    p[:, 0] *= CAM_H / CAM_W
    p -= p[0]
    m = np.abs(p).max()
    if m > 0:
        p /= m
    return p.flatten().astype(np.float32)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--thu-muc", type=Path, default=None,
                    help="thu muc chua <ten_tac_gia>/keypoint.csv da tai san")
    args = ap.parse_args()

    dong_ra, meta_ra = [], []
    for repo, anh_xa in NGUON.items():
        rows = doc_nguon(repo, args.thu_muc)
        doan, dem_doan, nhan_truoc = 0, 0, None
        for row in rows:
            nhan_goc = int(row[0])
            if nhan_goc not in anh_xa:
                continue
            vec = np.array([float(v) for v in row[1:43]], dtype=np.float32)
            # Nhom gia lap "burst": cac dong lien tiep cung nhan, cat moi 30 dong.
            if nhan_goc != nhan_truoc or dem_doan >= 30:
                doan += 1
                dem_doan = 0
            dem_doan += 1
            nhan_truoc = nhan_goc
            dong_ra.append([anh_xa[nhan_goc]] + [f"{v:.6f}" for v in pixel_sang_camera(vec)])
            meta_ra.append([repo.split("/")[0], f"{repo.split('/')[0]}_{doan:04d}", nhan_goc])
        print(f"{repo}: {len(rows)} dong goc")

    RA_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(RA_CSV, "w", newline="") as f:
        csv.writer(f).writerows(dong_ra)
    with open(RA_META, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["nguon", "nhom", "nhan_goc"])
        w.writerows(meta_ra)

    nhan = np.array([r[0] for r in dong_ra])
    ten = ["fist", "palm", "victory", "thumb_up", "point_up", "ok"]
    print(f"\nDa ghi {RA_CSV.name}: {len(dong_ra)} mau")
    for c, t in enumerate(ten):
        print(f"  {t:<10}{int((nhan == c).sum()):>7}")
    print("Lop 'none' KHONG co trong du lieu ngoai - chi lay tu du lieu tu thu.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
