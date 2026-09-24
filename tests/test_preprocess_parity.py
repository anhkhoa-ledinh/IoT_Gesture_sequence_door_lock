"""
============================================================================
 test_preprocess_parity.py — Canh giu khoi tien xu ly chep sang Kaggle
----------------------------------------------------------------------------
 Chay:
   .conda\\python.exe -m pytest tests\\test_preprocess_parity.py -v

 VAN DE NAY GIAI QUYET
 ---------------------
 Notebook Kaggle (kaggle/extract_hagrid_landmarks.ipynb) khong import duoc
 vision/common.py, nen ham preprocess_landmarks bi CHEP sang notebook. Hai ban
 chep co the lech nhau theo thoi gian ma khong ai biet.

 Lech mot buoc tien xu ly thi toan bo du lieu HaGRID thanh nhieu, va con so
 kiem thu se vo nghia MA KHONG CO DAU HIEU GI bao ra ngoai — model van chay,
 van tra ve so, chi la so sai.

 Test nay trich khoi nam giua hai dong danh dau BEGIN/END ra khoi notebook,
 exec no trong mot khong gian ten rieng, roi so tung con so voi ban goc trong
 vision/common.py. SAI SO TUYET DOI TOI DA PHAI BANG 0 — khong phai "gan bang",
 vi hai ben chay dung cung mot phep tinh tren cung mot dau vao.
============================================================================
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

GOC = Path(__file__).resolve().parent.parent
NOTEBOOK = GOC / "kaggle" / "extract_hagrid_landmarks.ipynb"

sys.path.insert(0, str(GOC / "vision"))
from common import preprocess_landmarks as goc_preprocess  # noqa: E402
from common import NUM_LANDMARKS, FEATURE_DIM              # noqa: E402

DAU_BEGIN = "# === BEGIN preprocess_landmarks (COPY NGUYEN VAN tu vision/common.py) ==="
DAU_END = "# === END preprocess_landmarks ==="


# ============================================================================
#  Trich khoi code tu notebook
# ============================================================================

def doc_khoi_tu_notebook() -> str:
    """Tra ve doan code nam giua hai dong danh dau trong notebook Kaggle."""
    assert NOTEBOOK.exists(), f"Khong thay notebook: {NOTEBOOK}"
    nb = json.loads(NOTEBOOK.read_text(encoding="utf-8"))

    tim_thay = []
    for cell in nb["cells"]:
        if cell["cell_type"] != "code":
            continue
        src = "".join(cell["source"])
        if DAU_BEGIN in src and DAU_END in src:
            than = src.split(DAU_BEGIN, 1)[1].split(DAU_END, 1)[0]
            tim_thay.append(than)

    assert len(tim_thay) == 1, (
        f"Phai co DUNG MOT cell chua khoi BEGIN/END, dang co {len(tim_thay)}. "
        "Notebook bi sua tay?"
    )
    return tim_thay[0]


@pytest.fixture(scope="module")
def ban_chep():
    """exec khoi chep ra mot khong gian ten rieng, tra ve ham preprocess_landmarks."""
    ns: dict = {}
    exec(compile(doc_khoi_tu_notebook(), "<khoi_chep_trong_notebook>", "exec"), ns)
    assert "preprocess_landmarks" in ns, (
        "Khoi chep khong dinh nghia preprocess_landmarks. "
        "Co the dong danh dau BEGIN/END dat sai cho."
    )
    return ns["preprocess_landmarks"]


# ============================================================================
#  Du lieu gia
# ============================================================================

def sinh_ban_tay(rng) -> list[tuple[float, float, float]]:
    """21 diem moc gia, toa do chuan hoa 0..1 giong MediaPipe tra ve."""
    xy = rng.uniform(0.05, 0.95, size=(NUM_LANDMARKS, 2))
    return [(float(x), float(y), 0.0) for x, y in xy]


# ============================================================================
#  Test
# ============================================================================

def test_notebook_co_dung_mot_khoi_danh_dau():
    """Notebook phai co dung mot cell mang cap dau BEGIN/END."""
    khoi = doc_khoi_tu_notebook()
    assert "def preprocess_landmarks" in khoi
    assert "def _to_xy_array" in khoi, (
        "Khoi chep phai keo theo ca _to_xy_array, neu khong exec se hong"
    )


def test_ban_chep_chay_duoc(ban_chep):
    """Khoi chep phai tu chay duoc, khong phu thuoc gi ben ngoai."""
    rng = np.random.default_rng(0)
    out = ban_chep(sinh_ban_tay(rng), "Right")
    assert out.shape == (FEATURE_DIM,)
    assert out.dtype == np.float32


@pytest.mark.parametrize("handedness", ["Right", "Left"])
def test_khop_tuyet_doi_tren_40_ban_tay(ban_chep, handedness):
    """40 ban tay ngau nhien moi ben tay — sai so tuyet doi toi da phai BANG 0.

    Yeu cau bang 0 chu khong phai 'gan bang': hai ban chay dung cung mot phep
    tinh tren cung mot dau vao, nen bat ky sai lech nao cung la dau hieu hai
    ban da khac nhau.
    """
    rng = np.random.default_rng(20260925)
    lech_max = 0.0
    for _ in range(40):
        tay = sinh_ban_tay(rng)
        a = goc_preprocess(tay, handedness)
        b = ban_chep(tay, handedness)
        assert a.shape == b.shape == (FEATURE_DIM,)
        assert a.dtype == b.dtype
        lech_max = max(lech_max, float(np.max(np.abs(a - b))))

    assert lech_max == 0.0, (
        f"Ban chep trong notebook da LECH so voi vision/common.py "
        f"(sai so toi da {lech_max:g}). Chep lai khoi tu common.py."
    )


def test_khop_ca_truong_hop_bien(ban_chep):
    """Cac dau vao de lam lo khac biet: suy bien, am, rat lon, rat nho."""
    bien = {
        "moi diem trung nhau": [(0.5, 0.5, 0.0)] * NUM_LANDMARKS,
        "toa do am": [(-0.3 + i * 0.01, -0.2 + i * 0.02, 0.0)
                      for i in range(NUM_LANDMARKS)],
        "gia tri rat lon": [(100.0 + i, 200.0 - i, 0.0)
                            for i in range(NUM_LANDMARKS)],
        "gia tri rat nho": [(1e-6 * i, 1e-6 * (NUM_LANDMARKS - i), 0.0)
                            for i in range(NUM_LANDMARKS)],
    }
    for ten, tay in bien.items():
        for handedness in ("Right", "Left"):
            a = goc_preprocess(tay, handedness)
            b = ban_chep(tay, handedness)
            assert not np.isnan(a).any(), f"ban goc sinh NaN o '{ten}'"
            assert not np.isnan(b).any(), f"ban chep sinh NaN o '{ten}'"
            np.testing.assert_array_equal(
                a, b, err_msg=f"lech o truong hop bien '{ten}' ({handedness})"
            )


def test_khop_ca_khi_dau_vao_dang_tuple(ban_chep):
    """Ca hai ban phai nhan duoc list cac cap (x, y), khong chi doi tuong MediaPipe."""
    rng = np.random.default_rng(5)
    tay = sinh_ban_tay(rng)
    dang_tuple = [(x, y) for x, y, _ in tay]
    np.testing.assert_array_equal(
        goc_preprocess(dang_tuple, "Right"),
        ban_chep(dang_tuple, "Right"),
    )


def test_ca_hai_ban_deu_bao_loi_khi_thieu_diem(ban_chep):
    """Dua thieu diem moc thi ca hai ban phai cung bao ValueError."""
    rng = np.random.default_rng(9)
    thieu = sinh_ban_tay(rng)[:10]
    with pytest.raises(ValueError):
        goc_preprocess(thieu, "Right")
    with pytest.raises(ValueError):
        ban_chep(thieu, "Right")


def test_hang_so_khop(ban_chep):
    """NUM_LANDMARKS va FEATURE_DIM trong khoi chep phai khop ban goc."""
    ns: dict = {}
    exec(compile(doc_khoi_tu_notebook(), "<khoi>", "exec"), ns)
    assert ns["NUM_LANDMARKS"] == NUM_LANDMARKS
    assert ns["FEATURE_DIM"] == FEATURE_DIM
