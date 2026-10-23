"""
============================================================================
 test_collect_meta.py — Canh giu keypoint_meta.csv khop tung dong voi keypoint.csv
----------------------------------------------------------------------------
 Chay:
   .conda\\python.exe -m pytest tests\\test_collect_meta.py -v

 Notebook chia train/val theo burst_id doc tu keypoint_meta.csv. Lech mot dong
 la moi burst_id phia sau gan nham mau, va diem validation lai bi ro ri ma khong
 co dau hieu gi. Cac test duoi day giu ba dieu:
   1. collect_data.py luon ghi hai file cung nhau, dung mot dong moi mau.
   2. collect_data.py tu choi chay khi hai file da lech.
   3. Du lieu THAT trong repo dang khop, va moi burst chi mang mot nhan.
 Khong can webcam.
============================================================================
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

GOC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GOC / "vision"))
from collect_data import (  # noqa: E402
    META_HEADER,
    CollectSession,
    append_sample,
    check_meta_aligned,
    count_data_rows,
)
from common import FEATURE_DIM, gesture_tables, load_config, resolve_path  # noqa: E402


def _vec(v: float = 0.5) -> np.ndarray:
    return np.full(FEATURE_DIM, v, dtype=np.float32)


# ============================================================================
#  1. Ghi hai file cung nhau
# ============================================================================

def test_ghi_mau_tang_ca_hai_file_mot_dong(tmp_path):
    data, meta = tmp_path / "kp.csv", tmp_path / "kp_meta.csv"
    append_sample(data, meta, 1, _vec(), "s1", "s1_b000")
    append_sample(data, meta, 1, _vec(), "s1", "s1_b000")
    append_sample(data, meta, 6, _vec(), "s1", "s1_b001")

    rows = list(csv.reader(open(data, newline="", encoding="utf-8")))
    mrows = list(csv.reader(open(meta, newline="", encoding="utf-8")))
    assert len(rows) == 3
    assert all(len(r) == FEATURE_DIM + 1 for r in rows), "keypoint.csv phai giu 43 cot"
    assert mrows[0] == META_HEADER, "dong tieu de chi ghi mot lan, o dau file"
    assert mrows[1:] == [["s1", "s1_b000"], ["s1", "s1_b000"], ["s1", "s1_b001"]]
    assert check_meta_aligned(data, meta) == 3


def test_ghi_tiep_vao_meta_da_co_khong_lap_tieu_de(tmp_path):
    data, meta = tmp_path / "kp.csv", tmp_path / "kp_meta.csv"
    append_sample(data, meta, 0, _vec(), "s1", "s1_b000")
    append_sample(data, meta, 0, _vec(), "s2", "s2_b000")   # lan chay sau
    mrows = list(csv.reader(open(meta, newline="", encoding="utf-8")))
    assert [r for r in mrows if r == META_HEADER] == [META_HEADER]


def test_sai_so_chieu_thi_khong_ghi_file_nao(tmp_path):
    data, meta = tmp_path / "kp.csv", tmp_path / "kp_meta.csv"
    with pytest.raises(ValueError):
        append_sample(data, meta, 0, np.zeros(10, dtype=np.float32), "s1", "s1_b000")
    assert not data.exists() and not meta.exists()


# ============================================================================
#  2. Phat hien hai file lech
# ============================================================================

def test_hai_file_chua_ton_tai_la_khop(tmp_path):
    assert check_meta_aligned(tmp_path / "a.csv", tmp_path / "b.csv") == 0


def test_co_du_lieu_ma_thieu_meta_thi_bao_loi(tmp_path):
    data, meta = tmp_path / "kp.csv", tmp_path / "kp_meta.csv"
    append_sample(data, meta, 0, _vec(), "s1", "s1_b000")
    meta.unlink()
    with pytest.raises(RuntimeError):
        check_meta_aligned(data, meta)


def test_them_dong_du_lieu_bang_tay_thi_bao_loi(tmp_path):
    data, meta = tmp_path / "kp.csv", tmp_path / "kp_meta.csv"
    append_sample(data, meta, 0, _vec(), "s1", "s1_b000")
    with open(data, "a", newline="", encoding="utf-8") as f:   # ghi le, khong qua append_sample
        csv.writer(f).writerow([0] + ["0.1"] * FEATURE_DIM)
    with pytest.raises(RuntimeError):
        check_meta_aligned(data, meta)


def test_dem_dong_bo_dong_trong_va_tieu_de(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("session_id,burst_id\r\na,b\r\n\r\nc,d\r\n", encoding="utf-8")
    assert count_data_rows(p, has_header=True) == 2
    assert count_data_rows(p, has_header=False) == 3


# ============================================================================
#  3. Phien va burst
# ============================================================================

def test_session_id_theo_thoi_diem_bat_dau():
    s = CollectSession(datetime(2026, 10, 24, 15, 30, 12))
    assert s.session_id == "s20261024_153012"


def test_moi_lan_bam_la_burst_moi_khong_trung():
    s = CollectSession(datetime(2026, 10, 24, 15, 30, 12))
    ids = [s.new_burst() for _ in range(5)]
    assert len(set(ids)) == 5
    assert ids[0] == "s20261024_153012_b000" and ids[4] == "s20261024_153012_b004"


def test_dem_burst_moi_lop_chi_tinh_burst_da_co_mau():
    s = CollectSession(datetime(2026, 10, 24, 15, 30, 12))
    b1, b2 = s.new_burst(), s.new_burst()
    s.new_burst()                       # bam R roi mat tay ngay: khong co mau nao
    s.mark_written(1, b1)
    s.mark_written(1, b1)               # nhieu mau cung burst chi tinh 1
    s.mark_written(2, b2)
    assert s.burst_count(1) == 1
    assert s.burst_count(2) == 1
    assert s.burst_count(0) == 0


# ============================================================================
#  4. Du lieu that trong repo
# ============================================================================

def test_du_lieu_that_khop_va_moi_burst_mot_nhan():
    cfg = load_config()
    data = resolve_path(cfg["model"]["keypoint_csv"])
    meta = resolve_path(cfg["model"]["keypoint_meta_csv"])
    if not data.exists():
        pytest.skip("chua co keypoint.csv")
    n = check_meta_aligned(data, meta)
    assert n > 0

    ten, _ = gesture_tables(cfg)
    nhan = [int(r[0]) for r in csv.reader(open(data, newline="", encoding="utf-8")) if r]
    mrows = list(csv.DictReader(open(meta, newline="", encoding="utf-8")))
    lop_cua_burst = defaultdict(set)
    for c, r in zip(nhan, mrows):
        lop_cua_burst[r["burst_id"]].add(c)
        if r["session_id"].startswith("legacy_"):
            assert r["session_id"] == f"legacy_{ten[c]}"
    tron = {b: s for b, s in lop_cua_burst.items() if len(s) > 1}
    assert not tron, f"burst mang nhieu nhan: {list(tron)[:5]}"
