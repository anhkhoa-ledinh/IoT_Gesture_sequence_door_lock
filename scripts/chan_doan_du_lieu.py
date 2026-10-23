"""
============================================================================
 chan_doan_du_lieu.py — Chan doan chat luong du lieu keypoint.csv
----------------------------------------------------------------------------
 Chay:
   D:\\IoT_Gesture_sequence_door_lock\\.conda\\python.exe scripts\\chan_doan_du_lieu.py
   ... scripts\\chan_doan_du_lieu.py duong\\dan\\khac.csv     (doc file khac)
   ... scripts\\chan_doan_du_lieu.py --tat-ca                 (liet ke het mau nghi ngo)

 Script CHI DOC va DO. Khong sua du lieu, khong train lai, khong can webcam.

 Nam phep do, tat ca tinh trong khong gian dac trung 42 chieu ma model nhin thay
 (dau ra cua preprocess_landmarks):
   1. So mau moi lop
   2. Do phan tan trong tung lop (khoang cach toi tam lop)
   3. Mau nghi ngo sai nhan (gan tam lop khac hon tam lop minh)
   4. Ma tran khoang cach giua cac tam lop (7x7)
   5. Mau trung lap (cap mau cach nhau duoi 0.01)

 VE "BURST": collect_data.py ghi 30 mau lien tiep moi lan bam R, cach nhau 2
 khung hinh. 30 mau do gan nhu la MOT tu the tay. Neu bo qua dieu nay, moi phep
 do lang gieng se bao "sach" chi vi moi mau dung canh 29 ban sao cua chinh no.
 Vi vay muc 3b/3c loai tru cac mau cung burst khi tim lang gieng.
============================================================================
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

import numpy as np

# Dung chung cau hinh voi vision/ — khong hardcode ten lop hay duong dan.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "vision"))
from common import FEATURE_DIM, gesture_tables, load_config, resolve_path  # noqa: E402

NGUONG_TRUNG_LAP = 0.01     # hai mau cach nhau duoi muc nay coi la trung lap
K_LANG_GIENG = 10           # so lang gieng cho phep kiem cheo k-NN (muc 3b)
SO_MAU_LIET_KE = 10         # so mau nghi ngo in ra moi lop khi khong co --tat-ca
NGUONG_LECH_SO_MAU = 0.20   # danh dau lop co so mau lech > 20% so voi trung vi


# ============================================================================
#  0. DOC DU LIEU VA CHIA BURST
# ============================================================================

def doc_csv(csv_path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, int]:
    """Doc keypoint.csv. Tra ve (X, y, so_dong, so_dong_hong).

    so_dong la so thu tu dong trong file (bat dau tu 1) de nguoi dung tim lai
    dung mau khi can loc tay.
    """
    X, y, dong = [], [], []
    hong = 0
    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        for i, row in enumerate(csv.reader(f), start=1):
            if not row:
                continue
            if len(row) != FEATURE_DIM + 1:
                hong += 1
                continue
            try:
                y.append(int(row[0]))
                X.append([float(v) for v in row[1:]])
                dong.append(i)
            except ValueError:
                hong += 1
    return np.asarray(X, dtype=np.float64), np.asarray(y), np.asarray(dong), hong


def chia_burst(y: np.ndarray, co_burst: int) -> np.ndarray:
    """Gan ma burst cho tung mau.

    File CSV chi ghi them (append) nen thu tu dong = thu tu ghi. Moi doan dong
    lien tiep cung nhan duoc cat thanh tung khuc co_burst mau. Day la UOC LUONG:
    neu nguoi thu bam SPACE le hoac burst bi huy giua chung vi mat tay thi ranh
    gioi khuc se lech, nhung moi khuc van chu yeu gom cac mau ghi sat nhau.
    """
    ma = np.zeros(len(y), dtype=int)
    k, vi_tri = 0, 0
    for i in range(len(y)):
        # sang lop khac, hoac du co_burst mau -> mo burst moi
        if i > 0 and (y[i] != y[i - 1] or vi_tri == co_burst):
            k, vi_tri = k + 1, 0
        ma[i] = k
        vi_tri += 1
    return ma


def ma_tran_khoang_cach(A: np.ndarray, B: np.ndarray) -> np.ndarray:
    """Khoang cach Euclid giua moi hang cua A va moi hang cua B."""
    d2 = (A * A).sum(1)[:, None] + (B * B).sum(1)[None, :] - 2.0 * A @ B.T
    return np.sqrt(np.clip(d2, 0.0, None))


def tieu_de(s: str) -> None:
    print()
    print("=" * 78)
    print(s)
    print("=" * 78)


# ============================================================================
#  1. SO MAU MOI LOP
# ============================================================================

def do_so_mau(y, burst, lop_ids, ten):
    tieu_de("1. SO MAU MOI LOP")
    dem = Counter(y.tolist())
    trung_vi = float(np.median([dem[c] for c in lop_ids]))
    print(f"{'id':<4}{'lop':<11}{'so mau':>8}{'/ trung vi':>12}{'so burst':>10}"
          f"{'so doan ghi':>13}")
    print("-" * 78)
    for c in lop_ids:
        m = (y == c)
        n = int(m.sum())
        ti_le = n / trung_vi if trung_vi else 0.0
        # so doan ghi = so lan nguoi thu quay lai lop nay (cac khuc dong khong lien nhau)
        idx = np.where(m)[0]
        so_doan = 1 + int((np.diff(idx) > 1).sum())
        ghi_chu = ""
        if abs(ti_le - 1.0) > NGUONG_LECH_SO_MAU:
            ghi_chu = "  <-- lech"
        if n < 250:
            ghi_chu += "  <-- duoi 250"
        print(f"{c:<4}{ten[c]:<11}{n:>8}{ti_le:>11.2f}x{len(set(burst[m])):>10}"
              f"{so_doan:>13}{ghi_chu}")
    print("-" * 78)
    lon, nho = max(dem[c] for c in lop_ids), min(dem[c] for c in lop_ids)
    print(f"Tong {len(y)} mau, {len(set(burst))} burst. Trung vi {trung_vi:.0f}. "
          f"Lop nhieu nhat / it nhat = {lon}/{nho} = {lon / nho:.2f}x")
    print("so doan ghi = 1 nghia la ca lop duoc thu trong MOT lan ngoi lien mach")
    print("  (cung anh sang, cung tu the ngoi) - model co the hoc ca boi canh do.")


# ============================================================================
#  2. DO PHAN TAN TRONG TUNG LOP
# ============================================================================

def do_phan_tan(X, y, lop_ids, ten, tam):
    tieu_de("2. DO PHAN TAN TRONG TUNG LOP  (khoang cach Euclid tu mau toi tam lop)")
    D_tam = ma_tran_khoang_cach(tam, tam)
    print(f"{'lop':<11}{'min':>8}{'median':>8}{'max':>8}{'std':>8}"
          f"{'tam gan nhat':>20}{'median/kc':>11}")
    print("-" * 78)
    for k, c in enumerate(lop_ids):
        d = np.linalg.norm(X[y == c] - tam[k], axis=1)
        kc = D_tam[k].copy()
        kc[k] = np.inf
        j = int(np.argmin(kc))
        print(f"{ten[c]:<11}{d.min():>8.3f}{np.median(d):>8.3f}{d.max():>8.3f}"
              f"{d.std():>8.3f}{ten[lop_ids[j]]:>13} {kc[j]:>6.3f}"
              f"{np.median(d) / kc[j]:>11.2f}")
    print("-" * 78)
    print("median/kc = median do phan tan / khoang cach toi tam lop khac gan nhat.")
    print("  Xap xi 1 tro len: nua so mau cua lop nam xa tam minh bang hoac hon")
    print("  khoang cach sang tam lop ben canh -> hai lop chong lan manh.")


# ============================================================================
#  3. MAU NGHI NGO SAI NHAN
# ============================================================================

def do_nghi_sai_nhan(X, y, dong, burst, lop_ids, ten, tam, D_all, tat_ca):
    tieu_de("3. MAU NGHI NGO SAI NHAN  (gan tam lop khac hon tam lop cua minh)")
    vi_tri = {c: k for k, c in enumerate(lop_ids)}
    k_cua = np.array([vi_tri[c] for c in y])
    D = ma_tran_khoang_cach(X, tam)                     # (n, 7)
    d_minh = D[np.arange(len(y)), k_cua]
    D_khac = D.copy()
    D_khac[np.arange(len(y)), k_cua] = np.inf
    k_khac = np.argmin(D_khac, axis=1)
    d_khac = D_khac[np.arange(len(y)), k_khac]
    nghi = d_khac < d_minh

    print(f"{'lop':<11}{'nghi ngo':>10}{'/ tong':>8}{'ti le':>8}   gan tam lop nao hon")
    print("-" * 78)
    for k, c in enumerate(lop_ids):
        m = (y == c)
        n_nghi = int((nghi & m).sum())
        sang = Counter(ten[lop_ids[j]] for j in k_khac[nghi & m])
        chi_tiet = ", ".join(f"{t} {s}" for t, s in sang.most_common())
        print(f"{ten[c]:<11}{n_nghi:>10}{int(m.sum()):>8}{n_nghi / m.sum():>8.1%}   {chi_tiet}")
    print("-" * 78)
    print(f"Tong: {int(nghi.sum())}/{len(y)} = {nghi.mean():.1%}")
    print("Luu y: ti le cao o day KHONG tu no chung minh sai nhan. Neu median/kc o")
    print("  muc 2 lon hon 1, moi lop la nhieu cum tu the roi rac chu khong phai mot")
    print("  khoi tron quanh tam, nen tam lop khong dai dien cho mau nao. Xem 3b/3c.")

    # --- Rieng cap palm / ok: cap gay loi khi chay that ngay 02/10 ---
    ma_nguoc = {v: k for k, v in ten.items()}
    if "palm" in ma_nguoc and "ok" in ma_nguoc:
        p, o = vi_tri[ma_nguoc["palm"]], vi_tri[ma_nguoc["ok"]]
        mp_, mo = (k_cua == p), (k_cua == o)
        p_sang_o = int((mp_ & (D[:, o] < D[:, p])).sum())
        o_sang_p = int((mo & (D[:, p] < D[:, o])).sum())
        print()
        print("Rieng cap palm / ok:")
        print(f"  mau palm gan tam ok hon tam palm : {p_sang_o}/{int(mp_.sum())}"
              f" = {p_sang_o / mp_.sum():.1%}")
        print(f"  mau ok   gan tam palm hon tam ok : {o_sang_p}/{int(mo.sum())}"
              f" = {o_sang_p / mo.sum():.1%}")
        ti = D[mp_, p] / D[mp_, o]
        print(f"  ti so kc(palm->tam palm)/kc(palm->tam ok): "
              f"min {ti.min():.2f}  median {np.median(ti):.2f}  max {ti.max():.2f}"
              "   (<1 la dung phia)")

    # --- 3b. Kiem cheo k-NN: tinh ca burst vs bo burst cua chinh mau do ---
    # Tieu chi "gan tam lop khac" bao dong nham voi lop da hinh nhu 'none'.
    # k-NN nhin lang gieng that su. Nhung lang gieng gan nhat cua mot mau gan nhu
    # luon la 29 mau cung burst, nen phai bo chung di moi biet mau do co duoc
    # CAC LAN GHI KHAC cua cung lop ung ho hay khong.
    def knn(Dm):
        lg = np.argpartition(Dm, K_LANG_GIENG, axis=1)[:, :K_LANG_GIENG]
        return lg, (y[lg] == y[:, None]).mean(axis=1), y[np.argmin(Dm, axis=1)]

    _, cung_co_burst, _ = knn(D_all)
    D_bo = np.where(burst[:, None] == burst[None, :], np.inf, D_all)
    lg_bo, cung_bo, nn1_bo = knn(D_bo)

    print()
    print(f"3b. Kiem cheo k-NN (k={K_LANG_GIENG}): ti le mau co DUOI MOT NUA lang gieng "
          "cung nhan")
    print(f"{'lop':<11}{'tinh ca burst':>15}{'BO burst':>10}{'1-NN bo burst dung':>20}"
          "   1-NN bo burst doan thanh")
    print("-" * 78)
    for c in lop_ids:
        m = (y == c)
        sai = Counter(ten[v] for v in nn1_bo[m] if v != c)
        chi_tiet = ", ".join(f"{t} {s}" for t, s in sai.most_common(3))
        print(f"{ten[c]:<11}{np.mean(cung_co_burst[m] < 0.5):>15.1%}"
              f"{np.mean(cung_bo[m] < 0.5):>10.1%}{np.mean(nn1_bo[m] == c):>20.1%}   {chi_tiet}")
    print("-" * 78)
    print(f"Tong: tinh ca burst {np.mean(cung_co_burst < 0.5):.1%}  |  bo burst "
          f"{np.mean(cung_bo < 0.5):.1%}  |  1-NN bo burst dung {np.mean(nn1_bo == y):.1%}")
    print("1-NN bo burst dung = mau co lang gieng gan nhat (ngoai burst cua no) cung nhan.")
    print("  Day KHONG phai do chinh xac cua model, chi la phep do tho xem moi lan ghi")
    print("  co duoc cac lan ghi khac cua cung lop 'ho tro' hay khong.")

    # --- 3c. Burst ma da so lang gieng ngoai burst thuoc lop khac ---
    print()
    print("3c. Burst ma DA SO lang gieng ngoai burst thuoc lop KHAC (ung vien loc / thu lai):")
    co = False
    for b in np.unique(burst):
        m = np.where(burst == b)[0]
        c = y[m[0]]
        dem = Counter(y[lg_bo[m]].ravel().tolist())
        top = dem.most_common(1)[0][0]
        if top != c:
            co = True
            tong = len(m) * K_LANG_GIENG
            print(f"  dong {dong[m[0]]:>5}-{dong[m[-1]]:<5} ({len(m):>2} mau) nhan {ten[c]:<9}"
                  f"-> lang gieng: "
                  + ", ".join(f"{ten[a]} {s / tong:.0%}" for a, s in dem.most_common(3)))
    if not co:
        print("  (khong co)")

    # --- Liet ke mau nghi ngo theo tieu chi tam lop, xep theo muc do ---
    print()
    so = "tat ca" if tat_ca else f"toi da {SO_MAU_LIET_KE} mau/lop"
    print(f"Danh sach mau gan tam lop khac ({so}), xep theo kc(tam minh) - kc(tam khac):")
    print(f"{'dong':>6}  {'nhan':<10}{'gan hon':<10}{'kc minh':>8}{'kc khac':>8}"
          f"{'knn cung nhan (bo burst)':>26}")
    for c in lop_ids:
        idx = np.where(nghi & (y == c))[0]
        idx = idx[np.argsort(-(d_minh[idx] - d_khac[idx]))]
        if not tat_ca:
            idx = idx[:SO_MAU_LIET_KE]
        for i in idx:
            print(f"{dong[i]:>6}  {ten[c]:<10}{ten[lop_ids[k_khac[i]]]:<10}"
                  f"{d_minh[i]:>8.3f}{d_khac[i]:>8.3f}{cung_bo[i]:>26.0%}")


# ============================================================================
#  4. MA TRAN KHOANG CACH GIUA CAC TAM LOP
# ============================================================================

def do_khoang_cach_tam(lop_ids, ten, tam):
    tieu_de("4. MA TRAN KHOANG CACH GIUA CAC TAM LOP (7x7)")
    D = ma_tran_khoang_cach(tam, tam)
    print(" " * 10 + "".join(f"{ten[c]:>10}" for c in lop_ids))
    for a, ca in enumerate(lop_ids):
        print(f"{ten[ca]:<10}" + "".join(
            f"{'-':>10}" if a == b else f"{D[a, b]:>10.3f}" for b in range(len(lop_ids))))
    cap = sorted((D[a, b], ten[lop_ids[a]], ten[lop_ids[b]])
                 for a in range(len(lop_ids)) for b in range(a + 1, len(lop_ids)))
    print()
    print("Cac cap tam gan nhau nhat:")
    for d, a, b in cap[:6]:
        print(f"  {a:<10} - {b:<10} {d:.3f}")


# ============================================================================
#  5. MAU TRUNG LAP VA DO BIEN THIEN TRONG BURST
# ============================================================================

def do_trung_lap(X, y, burst, lop_ids, ten, tam, D_all):
    tieu_de(f"5. MAU TRUNG LAP  (cap mau cach nhau duoi {NGUONG_TRUNG_LAP})")
    iu = np.triu_indices(len(y), k=1)
    d = D_all[iu]
    gan = d < NGUONG_TRUNG_LAP
    a, b = iu[0][gan], iu[1][gan]
    cung = (y[a] == y[b])
    print(f"Tong so cap duoi nguong: {int(gan.sum())} "
          f"(tren {len(d)} cap) - cung nhan {int(cung.sum())}, KHAC nhan {int((~cung).sum())}")
    print(f"Trong do trung tuyet doi (kc < 1e-6): {int((d < 1e-6).sum())}")
    print()

    # Nguong 0.01 thap hon ca do rung landmark cua MediaPipe, nen mot ban tay
    # dung yen hoan toan van cho cap mau cach nhau > 0.01. Do bien thien that su
    # cua mot lan bam R thi phai so do phan tan TRONG burst voi do phan tan
    # cua ca lop.
    nn = D_all.min(axis=1)                      # kc toi lang gieng gan nhat
    print(f"{'lop':<11}{'cap trung':>10}{'kc lg gan nhat p10/median':>28}"
          f"{'trong burst':>13}{'ca lop':>9}{'ti so':>8}")
    print("-" * 79)
    for k, c in enumerate(lop_ids):
        m = (y == c)
        cap_c = int((cung & (y[a] == c)).sum())
        d_trong = []
        for bb in np.unique(burst[m]):
            mb = (burst == bb)
            d_trong.append(np.linalg.norm(X[mb] - X[mb].mean(axis=0), axis=1))
        trong = float(np.median(np.concatenate(d_trong)))
        ca_lop = float(np.median(np.linalg.norm(X[m] - tam[k], axis=1)))
        print(f"{ten[c]:<11}{cap_c:>10}{np.percentile(nn[m], 10):>17.4f} / "
              f"{np.median(nn[m]):.4f}{trong:>13.3f}{ca_lop:>9.3f}{trong / ca_lop:>8.2f}")
    print("-" * 79)
    print("trong burst = median kc tu mau toi tam burst cua no; ca lop = median kc toi")
    print("  tam lop (nhu muc 2). Ti so nho: moi lan bam R gan nhu chi ghi MOT tu the,")
    print("  da dang cua lop chu yeu den tu so burst chu khong phai so mau.")
    if (~cung).any():
        print()
        print("CANH BAO: cap gan nhu trung nhau nhung KHAC nhan (gan nhu chac chan sai nhan):")
        for i, j in list(zip(a[~cung], b[~cung]))[:20]:
            print(f"  {ten[y[i]]} vs {ten[y[j]]}  kc {D_all[i, j]:.4f}")


# ============================================================================
#  CHAY
# ============================================================================

def main() -> int:
    ap = argparse.ArgumentParser(description="Chan doan chat luong keypoint.csv (chi doc).")
    ap.add_argument("csv", nargs="?", help="duong dan CSV (mac dinh: model.keypoint_csv)")
    ap.add_argument("--tat-ca", action="store_true", help="liet ke het mau nghi ngo")
    args = ap.parse_args()

    cfg = load_config()
    ten, _ = gesture_tables(cfg)
    lop_ids = sorted(ten)
    csv_path = Path(args.csv) if args.csv else resolve_path(cfg["model"]["keypoint_csv"])
    if not csv_path.exists():
        print(f"LOI: khong tim thay {csv_path}")
        return 1

    X, y, dong, hong = doc_csv(csv_path)
    print(f"File: {csv_path}")
    print(f"Doc duoc {len(y)} mau, {FEATURE_DIM} chieu. Dong hong bo qua: {hong}")

    # Chi giu cac lop co trong config de moi phep do dung cung mot bang lop.
    la = sorted(set(y.tolist()) - set(lop_ids))
    if la:
        print(f"CANH BAO: class_id khong co trong config.json, bo qua: {la}")
    giu = np.isin(y, lop_ids)
    X, y, dong = X[giu], y[giu], dong[giu]
    lop_ids = [c for c in lop_ids if (y == c).any()]
    tam = np.stack([X[y == c].mean(axis=0) for c in lop_ids])

    co_burst = cfg["collect"]["burst_samples"]
    burst = chia_burst(y, co_burst)
    print(f"Chia burst: moi doan dong lien tiep cung nhan cat thanh khuc {co_burst} mau "
          "(collect.burst_samples).")

    D_all = ma_tran_khoang_cach(X, X)
    np.fill_diagonal(D_all, np.inf)

    do_so_mau(y, burst, lop_ids, ten)
    do_phan_tan(X, y, lop_ids, ten, tam)
    do_nghi_sai_nhan(X, y, dong, burst, lop_ids, ten, tam, D_all, args.tat_ca)
    do_khoang_cach_tam(lop_ids, ten, tam)
    do_trung_lap(X, y, burst, lop_ids, ten, tam, D_all)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
