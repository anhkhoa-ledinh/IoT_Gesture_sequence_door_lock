"""
============================================================================
 test_eval_external.py — Phia "validation tu thu" cua vision/eval_external.py
----------------------------------------------------------------------------
 Chay:
   .conda\\python.exe -m pytest tests\\test_eval_external.py -v

 eval_external.py KHONG tu chia lai du lieu nua (model trien khai da hoc het
 keypoint.csv). No doc vision/model/eval_metrics.json do notebook ghi. Test giu:
   - khong co file -> N/A kem ly do "chua chay notebook sau Phase 2.6"
   - file hong     -> N/A kem ly do, khong crash
   - keypoint.csv doi sau lan danh gia -> canh bao so lieu cu
   - script khong con goi train_test_split
============================================================================
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GOC / "vision"))
import eval_external as ev  # noqa: E402


def metrics_mau(md5: str) -> dict:
    return {"phuong_phap": "StratifiedGroupKFold", "n_splits": 5, "nhom": "burst_id",
            "so_mau": 100, "keypoint_csv_md5": md5, "thoi_diem": "2026-10-24T10:00:00",
            "tong_the": {"mean": 0.7, "std": 0.05, "oof": 0.71}}


def test_khong_co_file_thi_na_kem_ly_do(tmp_path):
    m, ly_do, canh_bao = ev.doc_eval_metrics(tmp_path / "eval_metrics.json", tmp_path / "kp.csv")
    assert m is None
    assert ly_do == "chua chay notebook sau Phase 2.6"
    assert canh_bao == ""


def test_doc_dung_file_va_du_lieu_khong_doi(tmp_path):
    kp = tmp_path / "kp.csv"
    kp.write_bytes(b"0,1,2\r\n")
    p = tmp_path / "eval_metrics.json"
    p.write_text(json.dumps(metrics_mau(hashlib.md5(kp.read_bytes()).hexdigest())), encoding="utf-8")
    m, ly_do, canh_bao = ev.doc_eval_metrics(p, kp)
    assert m["tong_the"]["oof"] == 0.71 and ly_do == "" and canh_bao == ""


def test_du_lieu_doi_sau_lan_danh_gia_thi_canh_bao(tmp_path):
    kp = tmp_path / "kp.csv"
    kp.write_bytes(b"0,1,2\r\n")
    p = tmp_path / "eval_metrics.json"
    p.write_text(json.dumps(metrics_mau("md5_cu")), encoding="utf-8")
    m, _, canh_bao = ev.doc_eval_metrics(p, kp)
    assert m is not None and "chay lai notebook" in canh_bao


def test_file_hong_khong_crash(tmp_path):
    p = tmp_path / "eval_metrics.json"
    p.write_text("{khong phai json", encoding="utf-8")
    m, ly_do, _ = ev.doc_eval_metrics(p, tmp_path / "kp.csv")
    assert m is None and "hong" in ly_do
    p.write_text(json.dumps({"so_mau": 1}), encoding="utf-8")     # thieu tong_the
    m, ly_do, _ = ev.doc_eval_metrics(p, tmp_path / "kp.csv")
    assert m is None and "hong" in ly_do


def test_khong_con_tu_chia_lai_du_lieu():
    src = (GOC / "vision" / "eval_external.py").read_text(encoding="utf-8")
    assert "train_test_split" not in src
