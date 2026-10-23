"""
============================================================================
 test_dem_10_lan.py — Kiem logic phan loai luot cua scripts/dem_10_lan.py
----------------------------------------------------------------------------
 Chay:
   .conda\\python.exe -m pytest tests\\test_dem_10_lan.py -v

 Feed chuoi ban tin MQTT gia, moc thoi gian gia. Khong can broker, khong can
 webcam, khong phai ngoi doi 5 giay.
============================================================================
"""

from __future__ import annotations

import sys
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GOC / "scripts"))
import dem_10_lan as d  # noqa: E402

MA_DUNG = "7CE13A"
PREFIX = "huit/ak_majespecter/gate/"
TOPICS = {"gesture": "gesture", "sequence": "sequence", "cmd": "cmd", "state": "state"}


def bo_moi() -> d.BoDemLuot:
    return d.BoDemLuot(MA_DUNG, timeout_python_giay=10.0)


def nhap(bo: d.BoDemLuot, t0: float, cu_chi: list[str], ma: str) -> list[d.Luot]:
    """Gia lap Python: moi cu chi cach nhau 2 giay, roi gui sequence."""
    xong = []
    for k, g in enumerate(cu_chi):
        xong += bo.nhan("gesture", {"gesture": g}, t0 + 2 * k)
    xong += bo.nhan("sequence", {"code": ma}, t0 + 2 * (len(cu_chi) - 1) + 0.05)
    return xong


# ============================================================================
#  Bon kich ban bat buoc
# ============================================================================

def test_kich_ban_1_chuoi_dung_thanh_cong():
    bo = bo_moi()
    assert nhap(bo, 100.0, ["palm", "victory", "fist"], MA_DUNG) == []   # chua co cmd
    xong = bo.nhan("cmd", {"action": "unlock", "ttl": 5}, 104.3)
    assert len(xong) == 1
    l = xong[0]
    assert l.ket_qua == d.THANH_CONG
    assert l.dung_ma is True
    assert l.cu_chi == ["palm", "victory", "fist"]
    assert abs(l.tre_giay - 0.25) < 1e-9
    assert bo.dem()[d.THANH_CONG] == 1


def test_kich_ban_2_chuoi_sai_tu_choi():
    bo = bo_moi()
    nhap(bo, 100.0, ["thumb_up", "thumb_up", "thumb_up"], "B9B9B9")
    [l] = bo.nhan("cmd", {"action": "deny"}, 104.2)
    assert l.ket_qua == d.TU_CHOI
    assert l.dung_ma is False
    assert l.ghi_chu == ""


def test_kich_ban_3_lockout_roi_chan_ca_ma_dung():
    bo = bo_moi()
    kq = []
    for i, action in enumerate(["deny", "deny", "lockout"]):
        t = 100.0 + 20 * i
        nhap(bo, t, ["fist", "fist", "fist"], "3A3A3A")
        payload = {"action": action, "sec": 30} if action == "lockout" else {"action": action}
        kq += bo.nhan("cmd", payload, t + 4.2)
    assert [l.ket_qua for l in kq] == [d.TU_CHOI, d.TU_CHOI, d.KHOA_TAM]

    # Ngay sau lockout nhap ma DUNG: Node-RED co y khong tra loi (TC-04).
    nhap(bo, 150.0, ["palm", "victory", "fist"], MA_DUNG)
    assert bo.tick(158.0) == []                     # moi 3.95 s ke tu sequence
    [l] = bo.tick(159.2)
    assert l.ket_qua == d.KHONG_PHAN_HOI
    assert l.dung_ma is True
    assert "lockout" in l.ghi_chu


def test_kich_ban_4_sequence_khong_co_cmd():
    bo = bo_moi()
    bo.nhan("sequence", {"code": MA_DUNG}, 100.0)
    assert bo.tick(104.9) == []                     # chua qua 5 giay
    [l] = bo.tick(105.1)
    assert l.ket_qua == d.KHONG_PHAN_HOI
    assert l.ghi_chu == ""                          # khong lockout -> loi that
    assert bo.tick(110.0) == []                     # khong dong lap lai


# ============================================================================
#  Cac truong hop lam sai so dem neu khong xu ly
# ============================================================================

def test_cu_chi_khong_thanh_sequence_van_tinh_la_mot_luot():
    bo = bo_moi()
    bo.nhan("gesture", {"gesture": "palm"}, 100.0)
    bo.nhan("gesture", {"gesture": "victory"}, 102.0)
    assert bo.tick(113.9) == []                     # 10 s timeout Python + 2 s du phong
    [l] = bo.tick(114.1)
    assert l.ket_qua == d.CHUA_DU_MA
    assert l.ma is None and l.cu_chi == ["palm", "victory"]


def test_lan_nhap_moi_sau_timeout_python_chot_phan_do_dang_cu():
    bo = bo_moi()
    bo.nhan("gesture", {"gesture": "palm"}, 100.0)
    # 10.5 s sau Python da reset; cu chi nay la lan nhap MOI.
    [l] = bo.nhan("gesture", {"gesture": "palm"}, 110.5)
    assert l.ket_qua == d.CHUA_DU_MA and l.cu_chi == ["palm"]
    bo.nhan("gesture", {"gesture": "victory"}, 112.5)
    bo.nhan("gesture", {"gesture": "fist"}, 114.5)
    bo.nhan("sequence", {"code": MA_DUNG}, 114.55)
    [l2] = bo.nhan("cmd", {"action": "unlock"}, 114.8)
    assert l2.cu_chi == ["palm", "victory", "fist"]
    assert [x.ket_qua for x in bo.luot] == [d.CHUA_DU_MA, d.THANH_CONG]


def test_ma_dung_ma_bi_tu_choi_canh_bao_node_red_giu_ma_khac():
    bo = bo_moi()
    nhap(bo, 100.0, ["palm", "victory", "fist"], MA_DUNG)
    [l] = bo.nhan("cmd", {"action": "deny"}, 104.2)
    assert l.ket_qua == d.TU_CHOI
    assert "Node-RED" in l.ghi_chu


def test_hai_cmd_cho_mot_sequence_bao_nghi_hai_flow():
    bo = bo_moi()
    nhap(bo, 100.0, ["palm", "victory", "fist"], MA_DUNG)
    [l] = bo.nhan("cmd", {"action": "unlock"}, 104.2)
    assert bo.nhan("cmd", {"action": "deny"}, 104.3) == []
    assert "2 flow" in l.ghi_chu
    assert len(bo.luot) == 1                        # khong sinh luot ao


def test_mo_khan_cap_va_reset_lockout_khong_tao_luot():
    bo = bo_moi()
    assert bo.nhan("cmd", {"action": "unlock", "ttl": 5}, 100.0) == []   # nut dashboard
    nhap(bo, 200.0, ["palm", "victory", "fist"], MA_DUNG)
    # RESET LOCKOUT (sec=0) den giua chung: khong duoc dong luot dang cho.
    assert bo.nhan("cmd", {"action": "lockout", "sec": 0}, 204.1) == []
    [l] = bo.nhan("cmd", {"action": "unlock"}, 204.2)
    assert l.ket_qua == d.THANH_CONG
    assert len(bo.luot) == 1 and len(bo.cmd_ngoai_luot) == 2


def test_ctrl_c_chot_luot_dang_do():
    bo = bo_moi()
    bo.nhan("sequence", {"code": MA_DUNG}, 100.0)
    bo.nhan("gesture", {"gesture": "palm"}, 101.0)
    xong = bo.ket_thuc(101.5)
    assert [l.ket_qua for l in xong] == [d.KHONG_PHAN_HOI, d.CHUA_DU_MA]


# ============================================================================
#  Doc ban tin va xuat markdown
# ============================================================================

def test_phan_tich_ban_tin():
    assert d.phan_tich_ban_tin(PREFIX + "cmd", b'{"action":"deny"}', PREFIX, TOPICS) == \
        ("cmd", {"action": "deny"})
    assert d.phan_tich_ban_tin("nguoi/khac/cmd", b'{"action":"deny"}', PREFIX, TOPICS) is None
    assert d.phan_tich_ban_tin(PREFIX + "cmd", b"khong phai json", PREFIX, TOPICS) is None
    assert d.phan_tich_ban_tin(PREFIX + "cmd", b"[1,2]", PREFIX, TOPICS) is None
    assert d.phan_tich_ban_tin(PREFIX + "la", b"{}", PREFIX, TOPICS) is None


def test_markdown_ghi_them_khong_ghi_de(tmp_path):
    cfg = {"model": {"classifier_tflite": "model/gesture_classifier.tflite"}}
    bo = bo_moi()
    nhap(bo, 100.0, ["palm", "victory", "fist"], MA_DUNG)
    bo.nhan("cmd", {"action": "unlock"}, 104.2)
    out = tmp_path / "kq.md"
    d.ghi_them_markdown(out, d.tao_muc_markdown(bo, cfg, 100.0, 110.0, "truoc"))
    d.ghi_them_markdown(out, d.tao_muc_markdown(bo, cfg, 200.0, 210.0, "sau"))
    s = out.read_text(encoding="utf-8")
    assert s.count("# Kết quả đo nhập mã") == 1
    assert s.count("## Lần đo") == 2 and "— truoc" in s and "— sau" in s
    assert "| 1 |" in s and "THÀNH CÔNG" in s and "`7CE13A`" in s
