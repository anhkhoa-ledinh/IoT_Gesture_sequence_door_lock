"""
trich_video.py — bien VIDEO quay san thanh du lieu huan luyen.

Y tuong: KHONG gan nhan tung khung hinh. Moi video chi quay MOT cu chi, dat
video vao thu muc mang ten cu chi do — ten thu muc chinh la nhan:

    data_video\\
        palm\\      khoa_den_sang.mp4   quang_nghieng.mp4   ...
        ok\\        ...
        fist\\      ...
        victory\\  thumb_up\\  point_up\\
        none\\      (tay dang chuyen giua 2 cu chi, tay tha long, ha tay...)

Script lam cho moi video:
  1. Bo 0.7 giay dau va cuoi (luc dang dua tay vao / rut tay ra — de sai nhan).
  2. Lay 1 khung moi 0.2 giay (5 khung/giay). Lay het 30 khung/giay thi cac
     khung gan nhu giong het nhau, chi lam phong to du lieu gia.
  3. Lat ngang khung (giong gesture_lock.py), chay MediaPipe tim ban tay,
     bo khung khong thay tay.
  4. Doi toa do ve dung quy uoc cua camera 640x480 (video dien thoai la 16:9
     hoac doc 9:16 — khong doi thi ban tay bi "meo" so voi luc chay that).
  5. Dua qua dung preprocess_landmarks() nhu luc chay that -> 42 so.
  6. Cho model hien tai doan thu: video nao model doan TRUNG nhan duoi 50%
     thi bao "NGHI SAI NHAN" de ban xem lai (thuong la bo nham thu muc).

Ghi APPEND vao vision/model/keypoint.csv + keypoint_meta.csv, giong collect_data.py.
Moi video la MOT nhom (burst_id = vid_<nhan>_<ten file>), nen notebook chia
train/val theo video — 2 khung cua cung mot video khong bao gio nam o ca hai phia.

Chay:
    .conda\\python.exe scripts\\trich_video.py --chay-thu      # chi xem, KHONG ghi gi
    .conda\\python.exe scripts\\trich_video.py                 # ghi that

Truoc khi ghi, script sao luu keypoint.csv va keypoint_meta.csv. Video da trich
duoc nho trong data_video\\_da_trich.csv nen chay lai khong bi them trung.
"""
from __future__ import annotations

import argparse
import csv
import shutil
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_tasks
from mediapipe.tasks.python import vision as mp_vision

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vision"))
from collect_data import append_sample, check_meta_aligned  # noqa: E402
from common import (  # noqa: E402
    draw_landmarks,
    ensure_hand_landmarker,
    gesture_tables,
    load_config,
    preprocess_landmarks,
    resolve_path,
)

DUOI_VIDEO = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".webm"}


def doi_ve_camera(landmarks, w: int, h: int, cam_w: int, cam_h: int) -> list:
    """Doi toa do chuan hoa 0..1 cua khung video WxH sang toa do chuan hoa cua
    camera cam_w x cam_h, sao cho ty le ban tay giong luc chay gesture_lock.py.

    Toa do pixel that: (x*w, y*h). Camera du an lay x/cam_w, y/cam_h.
    preprocess_landmarks() con chia max_abs nen chi can dung TY LE, khong can
    dung kich thuoc.
    """
    return [SimpleNamespace(x=lm.x * w / cam_w, y=lm.y * h / cam_h) for lm in landmarks]


def danh_sach_video(thu_muc: Path, label_to_id: dict) -> tuple[list, list]:
    """Tra ve [(duong dan, class_id, nhan)] va danh sach thu muc khong hop le."""
    ok, la = [], []
    for d in sorted(p for p in thu_muc.iterdir() if p.is_dir() and not p.name.startswith("_")):
        if d.name not in label_to_id:
            la.append(d.name)
            continue
        for f in sorted(d.iterdir()):
            if f.suffix.lower() in DUOI_VIDEO:
                ok.append((f, label_to_id[d.name], d.name))
    return ok, la


def doc_da_trich(path: Path) -> set:
    if not path.exists():
        return set()
    with open(path, newline="", encoding="utf-8") as f:
        return {(r["video"], r["kich_thuoc"]) for r in csv.DictReader(f)}


def ghi_da_trich(path: Path, video: str, kich_thuoc: int, nhan: str, so_mau: int) -> None:
    moi = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if moi:
            w.writerow(["video", "kich_thuoc", "nhan", "so_mau", "luc"])
        w.writerow([video, kich_thuoc, nhan, so_mau, datetime.now().isoformat(timespec="seconds")])


def trich_mot_video(path: Path, landmarker, args, cam_w: int, cam_h: int, xem_truoc: Path | None):
    """Tra ve (danh sach vector 42 so, so khung da xem, so khung khong thay tay,
    so khung MediaPipe doan nguoc tay trai/phai)."""
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError("OpenCV khong mo duoc video (thu doi sang .mp4)")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    tong = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    dau = int(args.cat_dau * fps)
    cuoi = tong - int(args.cat_cuoi * fps) if tong else None
    buoc = max(1, round(args.buoc_giay * fps))

    diem, tay, da_xem, khong_tay, anh_mau = [], [], 0, 0, []
    i = -1
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        i += 1
        if i < dau or (cuoi is not None and i >= cuoi) or (i - dau) % buoc:
            continue
        if len(diem) >= args.toi_da:
            break
        da_xem += 1
        if not args.khong_lat:
            frame = cv2.flip(frame, 1)               # giong gesture_lock.py
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        res = landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
        if not res.hand_landmarks:
            khong_tay += 1
            continue
        lms = res.hand_landmarks[0]
        diem.append(doi_ve_camera(lms, w, h, cam_w, cam_h))
        tay.append(res.handedness[0][0].category_name)
        if xem_truoc is not None and len(anh_mau) < 12 and len(diem) % 3 == 1:
            nho = frame.copy()
            draw_landmarks(nho, lms)
            s = 240 / max(h, w)
            anh_mau.append(cv2.resize(nho, (int(w * s), int(h * s))))
    cap.release()

    # MediaPipe doi khi doan nham tay trai/phai o vai khung le. preprocess_landmarks
    # lat truc x theo nhan nay, nen 1 khung doan nham = 1 mau bi lat nguoc. Moi
    # video chi dung MOT tay, nen lay nhan chiem da so (hoac --tay neu ban chi dinh)
    # va ap cho moi khung.
    if args.tay:
        tay_chung = {"phai": "Right", "trai": "Left"}[args.tay]
    else:
        tay_chung = Counter(tay).most_common(1)[0][0] if tay else "Right"
    doan_nguoc = sum(1 for t in tay if t != tay_chung)
    vectors = [preprocess_landmarks(d, tay_chung) for d in diem]

    if xem_truoc is not None and anh_mau:
        # Ghep cac khung mau thanh 1 anh de xem nhanh nhan co dung khong.
        H = max(a.shape[0] for a in anh_mau)
        hang = [cv2.copyMakeBorder(a, 0, H - a.shape[0], 0, 4, cv2.BORDER_CONSTANT, value=(255, 255, 255))
                for a in anh_mau]
        cot = 4
        while len(hang) % cot:
            hang.append(np.full_like(hang[0], 255))
        luoi = np.vstack([np.hstack(hang[k:k + cot]) for k in range(0, len(hang), cot)])
        xem_truoc.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(xem_truoc), luoi)
    return vectors, da_xem, khong_tay, doan_nguoc


def nap_model_doan_thu(cfg):
    """Model hien tai, de kiem nhan. Khong co model thi bo qua buoc kiem."""
    try:
        from eval_external import TfliteClassifier
        p = resolve_path(cfg["model"]["classifier_tflite"])
        return TfliteClassifier(p) if p.exists() else None
    except Exception as e:                            # thieu tflite runtime...
        print(f"(Bo qua buoc kiem nhan: {e})")
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Trich du lieu landmark tu video da quay.")
    ap.add_argument("--thu-muc", type=Path, default=ROOT / "data_video")
    ap.add_argument("--chay-thu", action="store_true", help="chi trich va bao cao, KHONG ghi vao keypoint.csv")
    ap.add_argument("--buoc-giay", type=float, default=0.2, help="lay 1 khung moi bao nhieu giay (mac dinh 0.2)")
    ap.add_argument("--cat-dau", type=float, default=0.7, help="bo bao nhieu giay dau video")
    ap.add_argument("--cat-cuoi", type=float, default=0.7, help="bo bao nhieu giay cuoi video")
    ap.add_argument("--toi-da", type=int, default=150, help="toi da so mau moi video")
    ap.add_argument("--khong-lat", action="store_true", help="khong lat ngang khung hinh")
    ap.add_argument("--tay", choices=["phai", "trai"], default=None,
                    help="tay dung trong MOI video (mac dinh: tu lay theo da so khung)")
    ap.add_argument("--khong-xem-truoc", action="store_true", help="khong luu anh xem truoc")
    args = ap.parse_args()

    cfg = load_config()
    id_to_label, _ = gesture_tables(cfg)
    label_to_id = {v: k for k, v in id_to_label.items()}
    cam_w, cam_h = int(cfg["camera"]["frame_width"]), int(cfg["camera"]["frame_height"])
    csv_path = resolve_path(cfg["model"]["keypoint_csv"])
    meta_path = resolve_path(cfg["model"]["keypoint_meta_csv"])

    if not args.thu_muc.exists():
        args.thu_muc.mkdir(parents=True)
        for ten in label_to_id:
            (args.thu_muc / ten).mkdir(exist_ok=True)
        print(f"Da tao {args.thu_muc} voi {len(label_to_id)} thu muc con. Bo video vao roi chay lai.")
        return 0

    videos, la = danh_sach_video(args.thu_muc, label_to_id)
    if la:
        print(f"CANH BAO: bo qua thu muc khong phai ten cu chi: {la}")
        print(f"          ten hop le: {sorted(label_to_id)}")
    so_da = doc_da_trich(args.thu_muc / "_da_trich.csv")
    moi = [(p, c, n) for p, c, n in videos
           if (str(p.relative_to(args.thu_muc)), str(p.stat().st_size)) not in so_da]
    print(f"Tim thay {len(videos)} video, {len(videos) - len(moi)} da trich tu truoc, {len(moi)} video moi.\n")
    if not moi:
        return 0

    if not args.chay_thu:
        check_meta_aligned(csv_path, meta_path)       # lech dong thi dung ngay
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        for p in (csv_path, meta_path):
            if p.exists():
                shutil.copy2(p, p.with_name(f"{p.stem}_truoc_video_{stamp}{p.suffix}"))
        print(f"Da sao luu keypoint.csv va keypoint_meta.csv (duoi _truoc_video_{stamp}).\n")

    task = ensure_hand_landmarker(cfg)
    opts = mp_vision.HandLandmarkerOptions(
        base_options=mp_tasks.BaseOptions(model_asset_path=str(task)),
        running_mode=mp_vision.RunningMode.IMAGE,
        num_hands=1,
    )
    model = nap_model_doan_thu(cfg)
    session_id = datetime.now().strftime("video_%Y%m%d_%H%M%S")

    tong = Counter()
    so_video = Counter()
    nghi_sai = []
    print(f"{'video':<44}{'nhan':<10}{'mau':>5}{'mat tay':>9}{'model dong y':>14}")
    with mp_vision.HandLandmarker.create_from_options(opts) as landmarker:
        for path, cid, nhan in moi:
            ten = str(path.relative_to(args.thu_muc))
            xem = None if args.khong_xem_truoc else args.thu_muc / "_xem_truoc" / f"{nhan}__{path.stem}.jpg"
            try:
                vecs, da_xem, khong_tay, doan_nguoc = trich_mot_video(path, landmarker, args, cam_w, cam_h, xem)
            except Exception as e:
                print(f"{ten:<44}LOI: {e}")
                continue

            dong_y = ""
            if model is not None and vecs:
                pred = model.predict(np.array(vecs, dtype=np.float32))
                ty_le = float((pred == cid).mean())
                dong_y = f"{ty_le:.0%}"
                if ty_le < 0.5 and nhan != "none":
                    hay_doan = id_to_label[Counter(pred.tolist()).most_common(1)[0][0]]
                    nghi_sai.append(f"{ten}: model doan chu yeu la '{hay_doan}'")
                    dong_y += "  <- NGHI SAI NHAN"
            print(f"{ten[:43]:<44}{nhan:<10}{len(vecs):>5}{khong_tay:>6}/{da_xem:<3}{dong_y:>13}")
            if vecs and doan_nguoc > 0.2 * len(vecs):
                print(f"{'':<44}  -> {doan_nguoc}/{len(vecs)} khung MediaPipe doan nguoc tay trai/phai; "
                      "neu video doi tay giua chung thi tach thanh 2 video")

            if len(vecs) < 5:
                print(f"{'':<44}  -> qua it mau (camera khong thay tay?), BO QUA video nay")
                continue
            tong[nhan] += len(vecs)
            so_video[nhan] += 1
            if not args.chay_thu:
                burst_id = f"vid_{nhan}_{path.stem}"
                for v in vecs:
                    append_sample(csv_path, meta_path, cid, v, session_id, burst_id)
                ghi_da_trich(args.thu_muc / "_da_trich.csv", ten, path.stat().st_size, nhan, len(vecs))

    print("\nTONG KET")
    for ten in sorted(label_to_id, key=label_to_id.get):
        if so_video[ten]:
            canh_bao = "  (nen co >= 5 video de chia 5 fold)" if so_video[ten] < 5 else ""
            print(f"  {ten:<10}{so_video[ten]:>3} video {tong[ten]:>6} mau{canh_bao}")
    if nghi_sai:
        print("\nNGHI SAI NHAN — mo anh trong data_video\\_xem_truoc de kiem tra:")
        for s in nghi_sai:
            print("  " + s)
    if args.chay_thu:
        print("\nCHAY THU: chua ghi gi. Bo --chay-thu de ghi that.")
    else:
        print(f"\nDa ghi them {sum(tong.values())} mau vao {csv_path.name}.")
        print("Buoc tiep: mo vision\\train_classifier.ipynb -> Run All.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
