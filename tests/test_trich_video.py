"""Test scripts/trich_video.py — phan khong can MediaPipe."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np

GOC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GOC / "vision"))
from common import preprocess_landmarks  # noqa: E402

spec = importlib.util.spec_from_file_location("trich_video", GOC / "scripts" / "trich_video.py")
tv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tv)


def _ban_tay(seed=0):
    rng = np.random.default_rng(seed)
    return rng.uniform(100, 300, size=(21, 2))           # toa do PIXEL


def test_doi_ve_camera_cho_cung_vector_moi_kich_thuoc_khung():
    """Cung mot ban tay (cung toa do pixel) trong khung 640x480, 1920x1080 va
    khung doc 1080x1920 phai cho ra CUNG vector dac trung sau khi doi."""
    px = _ban_tay()
    ket_qua = []
    for w, h in [(640, 480), (1920, 1080), (1080, 1920), (1280, 720)]:
        lms = [SimpleNamespace(x=x / w, y=y / h) for x, y in px]   # MediaPipe tra 0..1 theo khung
        ket_qua.append(preprocess_landmarks(tv.doi_ve_camera(lms, w, h, 640, 480), "Right"))
    for v in ket_qua[1:]:
        np.testing.assert_allclose(v, ket_qua[0], atol=1e-5)


def test_khong_doi_thi_khung_16_9_bi_meo():
    """Doi chung: bo buoc doi thi vector khac han -> buoc doi la can thiet."""
    px = _ban_tay()
    a = preprocess_landmarks([SimpleNamespace(x=x / 640, y=y / 480) for x, y in px], "Right")
    b = preprocess_landmarks([SimpleNamespace(x=x / 1920, y=y / 1080) for x, y in px], "Right")
    assert np.abs(a - b).max() > 0.05


def test_danh_sach_video_lay_nhan_tu_ten_thu_muc(tmp_path):
    for d in ["palm", "ok", "khong_phai_nhan", "_xem_truoc"]:
        (tmp_path / d).mkdir()
    (tmp_path / "palm" / "a.mp4").write_bytes(b"x")
    (tmp_path / "palm" / "ghi_chu.txt").write_text("bo qua")
    (tmp_path / "ok" / "b.MOV").write_bytes(b"x")
    (tmp_path / "khong_phai_nhan" / "c.mp4").write_bytes(b"x")
    (tmp_path / "_xem_truoc" / "d.mp4").write_bytes(b"x")
    videos, la = tv.danh_sach_video(tmp_path, {"palm": 1, "ok": 5})
    assert [(p.name, c, n) for p, c, n in videos] == [("b.MOV", 5, "ok"), ("a.mp4", 1, "palm")]
    assert la == ["khong_phai_nhan"]                      # bao canh bao, khong lay


def test_nho_video_da_trich(tmp_path):
    f = tmp_path / "_da_trich.csv"
    assert tv.doc_da_trich(f) == set()
    tv.ghi_da_trich(f, "palm\\a.mp4", 1234, "palm", 40)
    tv.ghi_da_trich(f, "ok\\b.mp4", 99, "ok", 12)
    assert tv.doc_da_trich(f) == {("palm\\a.mp4", "1234"), ("ok\\b.mp4", "99")}
