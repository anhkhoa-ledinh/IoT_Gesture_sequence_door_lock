"""
============================================================================
 test_doc_access_log.py — Kiem scripts/doc_access_log.py bang log gia
----------------------------------------------------------------------------
 Chay:
   .conda\\python.exe -m pytest tests\\test_doc_access_log.py -v

 Log gia dung DUNG chuoi ket_qua ma flows.json ghi ra (ke ca dau gach dai),
 va lap lai dong tieu de giua file nhu khi Node-RED duoc deploy lai.
============================================================================
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GOC / "scripts"))
import doc_access_log as a  # noqa: E402

LOG_GIA = """timestamp,ma_nhap,ket_qua,so_lan_sai_lien_tiep
2026-10-24T07:00:00.000Z,7CE13A,DUNG — MO KHOA,0
2026-10-24T07:01:00.000Z,7CE1B9,SAI (lan 1/3),1
2026-10-24T07:02:00.000Z,B9B9B9,SAI (lan 2/3),2
2026-10-24T07:03:00.000Z,B9B9B9,SAI LAN 3 — LOCKOUT 30s,3
2026-10-24T07:03:10.000Z,7CE13A,BI CHAN (dang lockout),3
timestamp,ma_nhap,ket_qua,so_lan_sai_lien_tiep
2026-10-24T08:00:00.000Z,(khan cap),MO TU DASHBOARD,0
2026-10-24T08:01:00.000Z,7CE13A,DUNG — MO KHOA,0

"""


def ghi_log(tmp_path) -> Path:
    p = tmp_path / "access_log.csv"
    p.write_text(LOG_GIA, encoding="utf-8", newline="\n")
    return p


def test_phan_loai_dung_chuoi_cua_flows_json():
    assert a.phan_loai("DUNG — MO KHOA") == a.MO_BANG_MA
    assert a.phan_loai("SAI (lan 2/3)") == a.SAI
    assert a.phan_loai("SAI LAN 3 — LOCKOUT 30s") == a.SAI_GAY_LOCKOUT
    assert a.phan_loai("BI CHAN (dang lockout)") == a.BI_CHAN
    assert a.phan_loai("MO TU DASHBOARD") == a.MO_KHAN_CAP
    assert a.phan_loai("chuoi la") == a.KHAC


def test_bo_qua_dong_tieu_de_lap_lai(tmp_path):
    dong, so_tieu_de, hong = a.doc_log(ghi_log(tmp_path))
    assert len(dong) == 7 and so_tieu_de == 2 and hong == 0


def test_thong_ke_tach_mo_khan_cap_khoi_lan_nhap_ma(tmp_path):
    dong, _, _ = a.doc_log(ghi_log(tmp_path))
    tk = a.thong_ke(dong)
    L = tk["loai"]
    assert tk["tong_dong"] == 7
    assert tk["lan_nhap_ma"] == 6                   # khong tinh mo khan cap
    assert L[a.MO_BANG_MA] == 2
    assert L[a.SAI] == 2 and L[a.SAI_GAY_LOCKOUT] == 1
    assert L[a.BI_CHAN] == 1 and L[a.MO_KHAN_CAP] == 1
    assert "(khan cap)" not in tk["theo_ma"]
    assert sum(tk["theo_ma"]["7CE13A"].values()) == 3
    assert list(tk["theo_ma"])[0] == "7CE13A"       # nhieu nhat dung dau


def test_loc_theo_thoi_gian_doi_utc_sang_gio_may(tmp_path):
    dong, _, _ = a.doc_log(ghi_log(tmp_path))
    # Moc 07:30 UTC, doi sang gio may de truyen vao nhu nguoi dung go.
    moc = datetime(2026, 10, 24, 7, 30, tzinfo=timezone.utc).astimezone().replace(tzinfo=None)
    assert len(a.loc_thoi_gian(dong, None, moc)) == 5
    assert len(a.loc_thoi_gian(dong, moc, None)) == 2


def test_markdown_co_bang_va_danh_dau_ma_dung(tmp_path):
    p = ghi_log(tmp_path)
    dong, n_td, hong = a.doc_log(p)
    s = a.tao_markdown(a.thong_ke(dong), "7CE13A", p, n_td, hong, "")
    assert "**Tổng số lần nhập mã** | **6**" in s
    assert "`7CE13A` **(mã đúng)** | 3 | 2 | 0 | 1 |" in s
    assert "| Mở khẩn cấp từ Dashboard *(không tính là nhập mã)* | 1 |" in s


def test_log_rong_khong_loi(tmp_path):
    p = tmp_path / "access_log.csv"
    p.write_text("timestamp,ma_nhap,ket_qua,so_lan_sai_lien_tiep\n", encoding="utf-8")
    dong, n_td, _ = a.doc_log(p)
    tk = a.thong_ke(dong)
    assert tk["lan_nhap_ma"] == 0 and n_td == 1
    assert "N/A" in a.tao_markdown(tk, "7CE13A", p, n_td, 0, "")
