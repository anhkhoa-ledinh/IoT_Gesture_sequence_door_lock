"""
============================================================================
 test_chan_doan_du_lieu.py — scripts/chan_doan_du_lieu.py doc burst tu meta
----------------------------------------------------------------------------
 Chay:
   .conda\\python.exe -m pytest tests\\test_chan_doan_du_lieu.py -v

 Script khong con doan burst bang cach cat khuc 30 mau; no doc burst_id va
 session_id tu keypoint_meta.csv. Test giu cho viec ghep dong giua hai file
 dung ca khi co dong trong / dong hong, va script dung han khi hai file lech.
============================================================================
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GOC / "scripts"))
import chan_doan_du_lieu as cd  # noqa: E402


def _dong(c: int) -> list[str]:
    return [str(c)] + ["0.1"] * cd.FEATURE_DIM


def test_doc_csv_bo_dong_trong_va_dong_hong_van_ghep_dung_meta(tmp_path):
    kp = tmp_path / "kp.csv"
    with open(kp, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(_dong(0))
        f.write("\r\n")                       # dong trong: khong tinh
        w.writerow(["1", "0.1"])              # dong hong: tinh vao meta nhung bo qua
        w.writerow(_dong(2))
    meta = tmp_path / "kp_meta.csv"
    meta.write_text("session_id,burst_id\r\ns1,b0\r\ns1,b1\r\ns1,b2\r\n", encoding="utf-8")

    X, y, dong, hong, stt, so_dong = cd.doc_csv(kp)
    burst, phien = cd.doc_meta(meta)
    assert so_dong == 3 and hong == 1 and len(burst) == 3
    assert list(y) == [0, 2]
    assert list(burst[stt]) == ["b0", "b2"]           # mau thu 2 ung dong meta thu 3
    assert list(dong) == [1, 4]


def test_hai_file_lech_thi_dung_han(tmp_path, monkeypatch, capsys):
    kp = tmp_path / "kp.csv"
    with open(kp, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows([_dong(0), _dong(1)])
    meta = tmp_path / "kp_meta.csv"
    meta.write_text("session_id,burst_id\r\ns1,b0\r\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["x", str(kp), "--meta", str(meta)])
    assert cd.main() == 1
    assert "khop tung dong" in capsys.readouterr().out


def test_file_csv_khac_ma_khong_co_meta_thi_bao_loi(tmp_path, monkeypatch, capsys):
    kp = tmp_path / "kp.csv"
    kp.write_text(",".join(_dong(0)) + "\r\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["x", str(kp)])
    assert cd.main() == 1
    assert "--meta" in capsys.readouterr().out


def test_khong_con_ham_cat_khuc():
    assert not hasattr(cd, "chia_burst")
