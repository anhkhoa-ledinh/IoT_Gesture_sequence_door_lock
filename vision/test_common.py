"""
============================================================================
 test_common.py — Unit test cho preprocess_landmarks()
----------------------------------------------------------------------------
 Chay:
   D:\\IoT_Gesture_sequence_door_lock\\.conda\\python.exe -m unittest -v vision.test_common
   (hoac tu trong thu muc vision: ...\\python.exe -m unittest -v test_common)

 Khong can webcam, khong can MediaPipe — dung landmark GIA nen chay o dau cung
 duoc. Muc dich: chot cung 3 tinh chat cua khau tien xu ly, vi neu khau nay sai
 thi model se hoc nham ma nhin ben ngoai khong biet duoc.
============================================================================
"""

from __future__ import annotations

import unittest
from collections import namedtuple

import numpy as np

from common import FEATURE_DIM, NUM_LANDMARKS, preprocess_landmarks

# Gia lap doi tuong landmark cua MediaPipe (chi can co .x .y .z).
FakeLandmark = namedtuple("FakeLandmark", "x y z")


def make_right_hand(seed: int = 42) -> list[FakeLandmark]:
    """Sinh 21 diem moc gia, toa do chuan hoa 0..1 giong MediaPipe tra ve."""
    rng = np.random.default_rng(seed)
    xy = rng.uniform(0.25, 0.75, size=(NUM_LANDMARKS, 2))
    xy[0] = (0.50, 0.70)  # co tay dat o giua duoi khung, cho giong that
    return [FakeLandmark(float(x), float(y), 0.0) for x, y in xy]


def mirror_hand(hand, axis: float = 0.5) -> list[FakeLandmark]:
    """Lat guong ban tay qua truc doc x = axis.

    Mot ban tay phai soi guong thi thanh hinh dang cua ban tay trai.
    """
    return [FakeLandmark(2 * axis - lm.x, lm.y, lm.z) for lm in hand]


class TestPreprocessLandmarks(unittest.TestCase):

    def test_shape_va_kieu_du_lieu(self):
        """Dau ra phai la vector 42 chieu, float32 — dung bang so cot CSV."""
        out = preprocess_landmarks(make_right_hand(), "Right")
        self.assertEqual(out.shape, (FEATURE_DIM,))
        self.assertEqual(out.shape, (42,))
        self.assertEqual(out.dtype, np.float32)
        self.assertFalse(np.isnan(out).any(), "khong duoc co NaN")

    def test_co_tay_ve_goc_toa_do(self):
        """Buoc 1: sau khi doi goc, diem 0 (co tay) phai dung bang (0, 0)."""
        out = preprocess_landmarks(make_right_hand(), "Right")
        self.assertAlmostEqual(float(out[0]), 0.0, places=6)
        self.assertAlmostEqual(float(out[1]), 0.0, places=6)

    def test_bat_bien_khi_scale_gap_doi(self):
        """Buoc 3: phong to toan bo toa do len 2 lan phai cho ra CUNG vector.

        Y nghia that: dua tay lai gan camera hay lui ra xa deu phai nhan dien
        nhu nhau.
        """
        hand = make_right_hand()
        hand_x2 = [FakeLandmark(lm.x * 2, lm.y * 2, lm.z) for lm in hand]

        goc = preprocess_landmarks(hand, "Right")
        to_gap_doi = preprocess_landmarks(hand_x2, "Right")

        np.testing.assert_allclose(goc, to_gap_doi, rtol=1e-5, atol=1e-6)

    def test_bat_bien_khi_doi_cho(self):
        """Buoc 1: doi tay sang goc khac khung hinh phai cho ra CUNG vector."""
        hand = make_right_hand()
        dich = [FakeLandmark(lm.x + 0.13, lm.y - 0.09, lm.z) for lm in hand]

        np.testing.assert_allclose(
            preprocess_landmarks(hand, "Right"),
            preprocess_landmarks(dich, "Right"),
            rtol=1e-5, atol=1e-6,
        )

    def test_lat_tay_trai_ve_tay_phai(self):
        """Buoc 2: anh guong cua tay phai, gan nhan "Left", phai cho ra CUNG
        vector voi tay phai goc.

        Y nghia that: nguoi thuan tay trai khong phai thu lai du lieu rieng.
        """
        phai = make_right_hand()
        trai = mirror_hand(phai)

        np.testing.assert_allclose(
            preprocess_landmarks(phai, "Right"),
            preprocess_landmarks(trai, "Left"),
            rtol=1e-5, atol=1e-6,
        )

    def test_tay_trai_khong_lat_thi_khac(self):
        """Kiem tra nguoc lai: neu QUEN lat tay trai thi ket qua phai KHAC.

        Test nay de bat truong hop ai do lo xoa buoc lat ma cac test tren van
        xanh — no chung minh buoc 2 that su co tac dung.
        """
        phai = make_right_hand()
        trai = mirror_hand(phai)

        dung_nhan_sai = preprocess_landmarks(trai, "Right")  # khong lat
        chuan = preprocess_landmarks(phai, "Right")

        self.assertFalse(
            np.allclose(chuan, dung_nhan_sai, rtol=1e-5, atol=1e-6),
            "lat tay trai phai lam thay doi ket qua",
        )

    def test_nhan_dau_vao_dang_tuple(self):
        """Ham phai nhan duoc ca list cac cap (x, y) — de viet test va de tai
        su dung, khong bat buoc phai co doi tuong cua MediaPipe."""
        hand = make_right_hand()
        dang_tuple = [(lm.x, lm.y) for lm in hand]

        np.testing.assert_allclose(
            preprocess_landmarks(hand, "Right"),
            preprocess_landmarks(dang_tuple, "Right"),
            rtol=1e-6, atol=1e-7,
        )

    def test_ban_tay_suy_bien_khong_sinh_nan(self):
        """21 diem trung nhau -> max_abs = 0. Phai tra ve vector 0, KHONG
        duoc chia cho 0 sinh ra NaN lam hong ca file CSV."""
        suy_bien = [FakeLandmark(0.5, 0.5, 0.0)] * NUM_LANDMARKS
        out = preprocess_landmarks(suy_bien, "Right")

        self.assertFalse(np.isnan(out).any())
        np.testing.assert_allclose(out, np.zeros(FEATURE_DIM, dtype=np.float32))

    def test_bao_loi_khi_sai_so_diem(self):
        """Dua thieu diem phai bao loi ro rang chu khong am tham ghi rac."""
        with self.assertRaises(ValueError):
            preprocess_landmarks(make_right_hand()[:10], "Right")


if __name__ == "__main__":
    unittest.main(verbosity=2)
