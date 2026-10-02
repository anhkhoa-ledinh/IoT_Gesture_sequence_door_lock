"""
============================================================================
 eval_external.py — Danh gia model tren tap ngoai (HaGRID)
----------------------------------------------------------------------------
 Chay:
   D:\\IoT_Gesture_sequence_door_lock\\.conda\\python.exe vision\\eval_external.py

 MUC DICH
 --------
 Model duoc huan luyen tren du lieu TU THU bang webcam cua chinh nguoi dung.
 Tap validation tu thu chi tra loi duoc cau hoi "model co hoc thuoc du lieu cua
 minh khong". No KHONG tra loi duoc cau hoi quan trong hon: "model co nhan duoc
 ban tay cua NGUOI KHAC, trong dieu kien chup khac, hay khong".

 HaGRID tra loi cau hoi thu hai. Script nay in CANH NHAU hai con so de thay
 khoang cach generalization.

 *** Do chinh xac tren HaGRID SE THAP HON tap validation tu thu. Do la ket qua
 mong doi va trung thuc, khong phai loi can sua. *** Chinh khoang cach giua hai
 con so moi la thu dang bao cao — no do muc do model phu thuoc vao nguoi, nen va
 anh sang luc thu du lieu.
============================================================================
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

from common import FEATURE_DIM, gesture_tables, load_config, resolve_path


# ============================================================================
#  1. NAP MODEL TFLITE
# ============================================================================

def load_interpreter(model_path: Path):
    """Nap model TFLite.

    tf.lite.Interpreter da bi danh dau deprecated tu TensorFlow 2.20, ban thay
    the la goi ai_edge_litert. Thu ban moi truoc, khong co thi dung ban cu.
    Giong het cach gesture_lock.py lam, de hai ben chay tren cung mot backend.
    """
    try:
        from ai_edge_litert.interpreter import Interpreter  # type: ignore
        return Interpreter(model_path=str(model_path)), "ai_edge_litert"
    except ImportError:
        import tensorflow as tf
        return tf.lite.Interpreter(model_path=str(model_path)), "tf.lite"


class TfliteClassifier:
    """Boc model TFLite lai cho gon: du lieu 42 chieu -> class_id du doan."""

    def __init__(self, model_path: Path) -> None:
        self.interp, self.backend = load_interpreter(model_path)
        self.interp.allocate_tensors()
        self._in = self.interp.get_input_details()[0]
        self._out = self.interp.get_output_details()[0]

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Du doan tung dong. Model duoc export voi batch = 1 nen phai chay vong lap."""
        out = np.empty(len(X), dtype=np.int32)
        for i, row in enumerate(X):
            self.interp.set_tensor(self._in["index"],
                                   row.reshape(1, -1).astype(np.float32))
            self.interp.invoke()
            out[i] = int(np.argmax(self.interp.get_tensor(self._out["index"])[0]))
        return out


# ============================================================================
#  2. NAP DU LIEU
# ============================================================================

def load_keypoint_csv(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Doc file keypoint dang: cot 1 class_id, 42 cot dac trung."""
    data = np.loadtxt(path, delimiter=",", dtype=np.float32)
    if data.ndim == 1:
        data = data.reshape(1, -1)
    if data.shape[1] != FEATURE_DIM + 1:
        raise ValueError(
            f"{path.name}: moi dong phai co {FEATURE_DIM + 1} cot "
            f"(1 nhan + {FEATURE_DIM} dac trung), dang co {data.shape[1]}"
        )
    return data[:, 1:], data[:, 0].astype(np.int32)


# ============================================================================
#  3. IN BAO CAO
# ============================================================================

def in_phan_bo(y: np.ndarray, id_to_label: dict[int, str], tieu_de: str) -> None:
    print(f"\n{tieu_de}")
    print("-" * 46)
    print(f"{'id':<4}{'lop':<12}{'so mau':>8}{'ty le':>9}")
    print("-" * 46)
    for cid in sorted(id_to_label):
        n = int((y == cid).sum())
        thieu = "  <-- khong co mau" if n == 0 else ""
        print(f"{cid:<4}{id_to_label[cid]:<12}{n:>8}{n / max(1, len(y)):>8.1%}{thieu}")
    print("-" * 46)
    print(f"{'':<16}{len(y):>8}  tong cong")


def ve_ma_tran_nham_lan(y_true, y_pred, class_names, out_png: Path, tieu_de: str):
    """Ve va luu ma tran nham lan. Tra ve ma tran de dung tiep."""
    import matplotlib
    matplotlib.use("Agg")          # khong can cua so do hoa
    import matplotlib.pyplot as plt
    import seaborn as sns
    from sklearn.metrics import confusion_matrix

    cm = confusion_matrix(y_true, y_pred, labels=list(range(len(class_names))))

    plt.figure(figsize=(7.5, 6))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Oranges", cbar=False,
                xticklabels=class_names, yticklabels=class_names)
    plt.xlabel("Model doan")
    plt.ylabel("Nhan that")
    plt.title(tieu_de)
    plt.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_png, dpi=150)
    plt.close()
    return cm


# ============================================================================
#  4. MAIN
# ============================================================================

def main() -> int:
    from sklearn.metrics import accuracy_score, classification_report
    from sklearn.model_selection import train_test_split

    cfg = load_config()
    id_to_label, _ = gesture_tables(cfg)
    class_names = [id_to_label[i] for i in sorted(id_to_label)]

    tflite_path = resolve_path(cfg["model"]["classifier_tflite"])
    local_csv = resolve_path(cfg["model"]["keypoint_csv"])
    hagrid_csv = local_csv.parent / "keypoint_hagrid.csv"
    report_json = local_csv.parent / "extract_report.json"
    out_png = (Path(__file__).resolve().parent.parent
               / "docs" / "confusion_matrix_hagrid.png")

    # ---------------------------------------------------------- kiem tra dau vao
    if not tflite_path.exists():
        print(f"LOI: chua co {tflite_path}")
        print("Hay chay vision/train_classifier.ipynb de huan luyen truoc.")
        return 1
    if not hagrid_csv.exists():
        print(f"LOI: chua co {hagrid_csv}")
        print("Hay chay kaggle/extract_hagrid_landmarks.ipynb tren Kaggle, roi tai")
        print("keypoint_hagrid.csv ve thu muc vision/model/.")
        return 1

    clf = TfliteClassifier(tflite_path)
    print("=" * 74)
    print("DANH GIA TREN TAP NGOAI — HaGRID")
    print("=" * 74)
    print(f"model   : {tflite_path.name}  (backend {clf.backend})")

    # ------------------------------------------------- bao cao trich xuat, neu co
    if report_json.exists():
        rp = json.loads(report_json.read_text(encoding="utf-8"))
        hd = rp.get("handedness", {})
        ty_le = hd.get("ty_le_khop")
        print(f"trich xuat: {rp.get('tong_so_mau')} mau | "
              f"MAX_PER_CLASS={rp['tham_so'].get('MAX_PER_CLASS')} | "
              f"BBOX_EXPAND={rp['tham_so'].get('BBOX_EXPAND')} | "
              f"mediapipe {rp['tham_so'].get('mediapipe_version')}")
        if ty_le is not None:
            # Con so nay KHONG phai thuoc do chat luong du lieu, va KHONG co nguong.
            # MediaPipe xac dinh handedness voi gia dinh anh dau vao la anh guong;
            # anh HaGRID la anh chup binh thuong nen nhan tra ve nguoc tay that.
            # Vector dac trung khong bi anh huong: lat anh doi dau truc x VA doi nhan,
            # buoc 2 cua preprocess_landmarks doi dau x lan nua, hai phep triet tieu.
            print(f"khop handedness voi leading_hand: {ty_le:.1%}  "
                  f"(thap la dung mong doi, khong anh huong vector - xem README muc 7.2)")
    else:
        print(f"(khong thay {report_json.name} — bo qua phan tham so trich xuat)")

    # ---------------------------------------------------------- do tren HaGRID
    X_h, y_h = load_keypoint_csv(hagrid_csv)
    in_phan_bo(y_h, id_to_label, "PHAN BO LOP TRONG TAP HaGRID")

    y_h_pred = clf.predict(X_h)
    acc_hagrid = float(accuracy_score(y_h, y_h_pred))

    print("\n" + "=" * 74)
    print("CLASSIFICATION REPORT — HaGRID (tap ngoai)")
    print("=" * 74)
    print(classification_report(y_h, y_h_pred,
                                labels=list(range(len(class_names))),
                                target_names=class_names,
                                digits=3, zero_division=0))

    cm = ve_ma_tran_nham_lan(y_h, y_h_pred, class_names, out_png,
                             "Ma tran nham lan — HaGRID (tap ngoai)")
    print(f"Da luu ma tran nham lan: {out_png}")

    # ------------------------------------- do lai tren validation tu thu de so
    acc_val = None
    if local_csv.exists():
        X_l, y_l = load_keypoint_csv(local_csv)
        # Dung DUNG cach chia cua train_classifier.ipynb (80/20, stratified,
        # random_state=42) de lay lai chinh tap validation da dung luc train.
        try:
            _, X_val, _, y_val = train_test_split(
                X_l, y_l, test_size=0.20, stratify=y_l, random_state=42)
            acc_val = float(accuracy_score(y_val, clf.predict(X_val)))
        except ValueError as e:
            print(f"\n(khong chia lai duoc tap validation: {e})")
    else:
        print(f"\n(khong thay {local_csv.name} — khong so sanh duoc voi tap tu thu)")

    # ------------------------------------------------------ HAI CON SO CANH NHAU
    print()
    print("=" * 74)
    print("KHOANG CACH GENERALIZATION")
    print("=" * 74)
    print(f"{'Tap du lieu':<40}{'So mau':>9}{'Do chinh xac':>16}")
    print("-" * 74)
    if acc_val is not None:
        print(f"{'Validation tu thu (webcam nguoi dung)':<40}{len(y_val):>9}{acc_val:>15.1%}")
    else:
        print(f"{'Validation tu thu (webcam nguoi dung)':<40}{'N/A':>9}{'N/A':>16}"
              f"   <- thieu keypoint.csv")
    print(f"{'HaGRID (tap ngoai, nguoi khac)':<40}{len(y_h):>9}{acc_hagrid:>15.1%}")
    print("-" * 74)
    if acc_val is not None:
        chenh = acc_val - acc_hagrid
        print(f"{'Chenh lech':<40}{'':>9}{chenh:>+15.1%}")
        print()
        if chenh < 0.10:
            print("   Chenh lech nho — model tong quat hoa tot ngoai mong doi.")
        elif chenh < 0.30:
            print("   Chenh lech vua — BINH THUONG va dang mong doi cho bai nay.")
            print("   Model hoc duoc hinh dang ban tay, nhung van con phu thuoc vao")
            print("   nguoi va dieu kien chup luc thu du lieu.")
        else:
            print("   Chenh lech LON — model phu thuoc nang vao du lieu tu thu.")
            print("   Neu can cai thien: thu them du lieu o nhieu nguoi, nhieu goc tay,")
            print("   nhieu nen va nhieu muc anh sang khac nhau.")
        print()
        print("   Nhac lai: con so HaGRID thap hon la KET QUA MONG DOI, khong phai loi.")
        print("   Ghi ca hai con so vao bao cao, dung chi ghi con so cao hon.")

    # ------------------------------------------ lop nao te nhat tren tap ngoai
    print()
    print("=" * 74)
    print("DO CHINH XAC TUNG LOP TREN HaGRID")
    print("=" * 74)
    print(f"{'lop':<12}{'so mau':>8}{'dung':>7}{'do chinh xac':>15}")
    print("-" * 74)
    yeu = []
    for i, ten in enumerate(class_names):
        tong = int(cm[i].sum())
        if tong == 0:
            print(f"{ten:<12}{0:>8}{'-':>7}{'khong co mau':>15}")
            continue
        acc_i = cm[i, i] / tong
        dau = "" if acc_i >= 0.70 else ("  <-- yeu" if acc_i >= 0.40 else "  <-- RAT YEU")
        if acc_i < 0.70:
            yeu.append((ten, acc_i))
        print(f"{ten:<12}{tong:>8}{int(cm[i, i]):>7}{acc_i:>14.1%}{dau}")
    print("-" * 74)

    # Nhac rieng ve cac cu chi nam trong mat ma
    ma = cfg["secret"]["default_code"]
    hex_to_label = {g["hex"]: g["label"] for g in cfg["gestures"] if g["hex"]}
    trong_ma = [hex_to_label.get(ma[k:k + 2]) for k in range(0, len(ma), 2)]
    print(f"\nMat ma hien tai '{ma}' dung cac cu chi: {trong_ma}")
    lien_quan = [t for t in yeu if t[0] in trong_ma]
    if lien_quan:
        print("NGHIEM TRONG tren tap ngoai: " +
              ", ".join(f"'{t}' chi {a:.1%}" for t, a in lien_quan))
        print("Nguoi khac se rat kho mo duoc khoa nay. Can doi mat ma hoac thu them du lieu.")
    else:
        print("Cac cu chi trong mat ma deu dat tren 70% o tap ngoai.")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    sys.exit(main())
