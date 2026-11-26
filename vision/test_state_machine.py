"""
============================================================================
 test_state_machine.py — Unit test cho SequenceStateMachine
----------------------------------------------------------------------------
 Chay:
   cd vision
   ..\\.conda\\python.exe -m unittest -v test_state_machine

 Khong can webcam, khong can MQTT, khong can model .tflite. Toan bo dung
 (nhan, do_tin_cay) GIA va mot dong ho GIA, nen test chay trong tich tac
 chu khong phai ngoi doi 10 giay cho timeout.
============================================================================
"""

from __future__ import annotations

import unittest

from common import load_config
from gesture_lock import BaseGestureClassifier, SequenceStateMachine


class FakeClock:
    """Dong ho gia — muon nhay toi giay nao thi nhay, khong can sleep()."""

    def __init__(self, t: float = 1000.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, giay: float) -> None:
        self.t += giay


class SequenceTestBase(unittest.TestCase):
    """Phan dung san dung chung cho moi test."""

    def setUp(self) -> None:
        self.cfg = load_config()
        self.clock = FakeClock()
        self.gestures: list[tuple[str, str, float]] = []
        self.sequences: list[str] = []

        self.sm = SequenceStateMachine(
            self.cfg,
            on_gesture=lambda l, h, c: self.gestures.append((l, h, c)),
            on_sequence=lambda code: self.sequences.append(code),
            now=self.clock,
        )

        th = self.cfg["thresholds"]
        self.N_STABLE = th["stable_frames"]      # 15
        self.N_NONE = th["none_gap_frames"]      # 10
        self.TIMEOUT = th["sequence_timeout_sec"]  # 10
        self.CONF_OK = th["min_confidence"] + 0.20   # 0.90 - dat nguong
        self.CONF_LOW = th["min_confidence"] - 0.20  # 0.50 - khong dat

    # ---- tien ich nap nhieu khung lien tiep ----
    def feed(self, label: str, conf: float, n: int) -> None:
        for _ in range(n):
            self.sm.update(label, conf)

    def feed_none(self, n: int) -> None:
        for _ in range(n):
            self.sm.update("none", 0.0)


class TestChuoiDung(SequenceTestBase):

    def test_kich_ban_1_chuoi_dung_ra_dung_ma(self):
        """KICH BAN 1 — palm, ok, fist lam dung luat -> ma 7C4D3A (ma tu 31/10)."""
        for label in ("palm", "ok", "fist"):
            self.feed(label, self.CONF_OK, self.N_STABLE)
            self.feed_none(self.N_NONE)

        self.assertEqual(len(self.gestures), 3, "phai chap nhan dung 3 cu chi")
        self.assertEqual([g[0] for g in self.gestures], ["palm", "ok", "fist"])
        self.assertEqual([g[1] for g in self.gestures], ["7C", "4D", "3A"])
        self.assertEqual(self.sequences, ["7C4D3A"])
        self.assertEqual(self.sequences[0], self.cfg["secret"]["default_code"])

    def test_tu_reset_sau_khi_du_chuoi(self):
        """Du 3 cu chi thi phai tu xoa, san sang cho lan nhap tiep theo."""
        for label in ("palm", "victory", "fist"):
            self.feed(label, self.CONF_OK, self.N_STABLE)
            self.feed_none(self.N_NONE)

        self.assertEqual(self.sm.accepted, [])
        self.assertEqual(self.sm.code_display(), "__ __ __")
        self.assertIsNone(self.sm.seconds_left)

    def test_dung_14_khung_thi_chua_nhan(self):
        """Giu thieu 1 khung so voi nguong thi KHONG duoc chap nhan."""
        self.feed("victory", self.CONF_OK, self.N_STABLE - 1)
        self.assertEqual(self.gestures, [])
        self.assertEqual(self.sm.stable_count, self.N_STABLE - 1)

        self.sm.update("victory", self.CONF_OK)   # khung thu 15
        self.assertEqual(len(self.gestures), 1)


class TestConfidenceThap(SequenceTestBase):

    def test_kich_ban_2_confidence_thap_bi_loai(self):
        """KICH BAN 2 — giu du 15 khung nhung do tin cay duoi 0.70 -> bo qua."""
        self.feed("victory", self.CONF_LOW, self.N_STABLE * 3)

        self.assertEqual(self.gestures, [], "khong duoc chap nhan cu chi nao")
        self.assertEqual(self.sm.stable_count, 0)
        self.assertEqual(self.sm.code_display(), "__ __ __")

    def test_mot_khung_tut_confidence_lam_dem_lai_tu_dau(self):
        """Do tin cay phai dat o CA 15 khung lien tiep, khong phai trung binh.

        Y nghia that: nguoi dung phai giu yen tay, luot tay qua khong tinh.
        """
        self.feed("victory", self.CONF_OK, self.N_STABLE - 1)
        self.sm.update("victory", self.CONF_LOW)      # 1 khung tut -> dem lai
        self.assertEqual(self.sm.stable_count, 0)

        self.feed("victory", self.CONF_OK, self.N_STABLE - 1)
        self.assertEqual(self.gestures, [], "van chua du 15 khung lien tiep")

        self.sm.update("victory", self.CONF_OK)
        self.assertEqual(len(self.gestures), 1)

    def test_doi_nhan_giua_chung_lam_dem_lai_tu_dau(self):
        """Doi sang nhan khac giua chung cung phai dem lai tu dau."""
        self.feed("victory", self.CONF_OK, self.N_STABLE - 1)
        self.sm.update("palm", self.CONF_OK)
        self.assertEqual(self.sm.candidate, "palm")
        self.assertEqual(self.sm.stable_count, 1)
        self.assertEqual(self.gestures, [])


class TestKhoangNone(SequenceTestBase):

    def test_kich_ban_3_thieu_none_giua_hai_cu_chi(self):
        """KICH BAN 3 — giu nguyen tay sang cu chi thu hai ma khong ha tay
        xuong thi cu chi thu hai KHONG duoc nhan.

        Khong co luat nay, giu yen 1 ban tay 45 khung se bi dem thanh 3 cu chi
        giong nhau va tu dong sinh ra mot mat ma.
        """
        self.feed("victory", self.CONF_OK, self.N_STABLE)
        self.assertEqual(len(self.gestures), 1)

        # Chuyen thang sang palm, KHONG qua trang thai none.
        self.feed("palm", self.CONF_OK, self.N_STABLE * 3)

        self.assertEqual(len(self.gestures), 1, "van chi duoc 1 cu chi")
        self.assertTrue(self.sm.waiting_none, "phai van dang cho khoang none")
        self.assertEqual(self.sm.accepted, ["E1"])

    def test_thieu_1_khung_none_van_chua_du(self):
        """Ha tay 9 khung (thieu 1) thi van chua du dieu kien."""
        self.feed("victory", self.CONF_OK, self.N_STABLE)
        self.feed_none(self.N_NONE - 1)
        self.assertTrue(self.sm.waiting_none)

        self.feed_none(1)                       # du 10 khung
        self.assertFalse(self.sm.waiting_none)

    def test_none_bi_ngat_quang_thi_dem_lai(self):
        """Khoang none phai LIEN TUC. Tho tay ra giua chung la dem lai tu dau."""
        self.feed("victory", self.CONF_OK, self.N_STABLE)
        self.feed_none(self.N_NONE - 2)
        self.sm.update("palm", self.CONF_OK)     # tay lai xuat hien
        self.assertEqual(self.sm.none_count, 0, "phai dem lai tu dau")

        self.feed_none(self.N_NONE - 1)
        self.assertTrue(self.sm.waiting_none)
        self.feed_none(1)
        self.assertFalse(self.sm.waiting_none)

    def test_khong_can_none_truoc_cu_chi_dau_tien(self):
        """Luat 'none' chi ap dung GIUA hai cu chi, khong can truoc cu chi dau."""
        self.feed("victory", self.CONF_OK, self.N_STABLE)
        self.assertEqual(len(self.gestures), 1)


class TestTimeout(SequenceTestBase):

    def test_kich_ban_4_timeout_xoa_chuoi_dang_nhap(self):
        """KICH BAN 4 — nhap 2 cu chi roi bo di, qua 10 giay phai xoa sach."""
        self.feed("victory", self.CONF_OK, self.N_STABLE)
        self.feed_none(self.N_NONE)
        self.feed("palm", self.CONF_OK, self.N_STABLE)
        self.feed_none(self.N_NONE)

        self.assertEqual(self.sm.accepted, ["E1", "7C"])
        self.assertEqual(self.sm.code_display(), "E1 7C __")

        # Bo di qua lau.
        self.clock.advance(self.TIMEOUT + 0.5)
        self.sm.update("none", 0.0)              # 1 khung bat ky sau timeout

        self.assertEqual(self.sm.accepted, [], "phai xoa sach")
        self.assertEqual(self.sm.code_display(), "__ __ __")
        self.assertEqual(self.sequences, [], "khong duoc phat ma nao")

    def test_chua_den_timeout_thi_giu_nguyen(self):
        """Truoc moc 10 giay thi chuoi dang nhap phai con nguyen."""
        self.feed("victory", self.CONF_OK, self.N_STABLE)
        self.feed_none(self.N_NONE)

        self.clock.advance(self.TIMEOUT - 1.0)
        self.sm.update("none", 0.0)

        self.assertEqual(self.sm.accepted, ["E1"])
        self.assertAlmostEqual(self.sm.seconds_left, 1.0, places=3)

    def test_moi_cu_chi_moi_gia_han_dong_ho(self):
        """Chap nhan them 1 cu chi thi dong ho timeout duoc tinh lai tu dau."""
        self.feed("victory", self.CONF_OK, self.N_STABLE)
        self.feed_none(self.N_NONE)

        self.clock.advance(self.TIMEOUT - 1.0)   # sap het gio
        self.feed("palm", self.CONF_OK, self.N_STABLE)
        self.assertEqual(self.sm.accepted, ["E1", "7C"])

        self.clock.advance(self.TIMEOUT - 1.0)   # them gan 10 giay nua
        self.sm.update("none", 0.0)
        self.assertEqual(self.sm.accepted, ["E1", "7C"], "chua duoc reset")

    def test_dong_ho_chua_chay_truoc_cu_chi_dau_tien(self):
        """Chua chap nhan cu chi nao thi khong co timeout nao ca."""
        self.assertIsNone(self.sm.seconds_left)
        self.clock.advance(self.TIMEOUT * 5)
        self.sm.update("none", 0.0)
        self.assertIsNone(self.sm.seconds_left)


class TestMaSai(SequenceTestBase):

    def test_chuoi_sai_van_duoc_phat_de_node_red_tu_cham(self):
        """State machine KHONG tu kiem ma. Chuoi sai van phai day len MQTT.

        Viec kiem ma la cua Node-RED (tang 3). Neu Python tu chan ma sai thi
        Node-RED khong bao gio dem duoc so lan sai va lockout se vo dung.
        """
        for label in ("fist", "fist", "fist"):
            self.feed(label, self.CONF_OK, self.N_STABLE)
            self.feed_none(self.N_NONE)

        self.assertEqual(self.sequences, ["3A3A3A"])
        self.assertNotEqual(self.sequences[0], self.cfg["secret"]["default_code"])


class TestThayTheClassifier(SequenceTestBase):
    """Kiem chung rang buoc thiet ke bat buoc cua spec:

    doi GestureClassifier sang ban cai dat khac ma KHONG phai sua
    SequenceStateMachine hay MqttPublisher.
    """

    def test_classifier_hinh_hoc_gia_van_chay_duoc(self):
        class ClassifierHinhHocGia(BaseGestureClassifier):
            """Ban cai dat thay the: khong dung model, khong dung MediaPipe.

            Chi can viet dung ham classify(). Khong dat last_landmarks —
            phan ve khung xuong tu bo qua.
            """

            def __init__(self, kich_ban):
                super().__init__()
                self.kich_ban = list(kich_ban)

            def classify(self, frame):
                return self.kich_ban.pop(0) if self.kich_ban else ("none", 0.0)

        # Dung chuoi khung y het kich ban 1.
        kich_ban = []
        for label in ("palm", "ok", "fist"):
            kich_ban += [(label, self.CONF_OK)] * self.N_STABLE
            kich_ban += [("none", 0.0)] * self.N_NONE

        clf = ClassifierHinhHocGia(kich_ban)
        self.assertIsInstance(clf, BaseGestureClassifier)
        self.assertIsNone(clf.last_landmarks)

        # SequenceStateMachine khong he biet minh dang duoc nap tu dau.
        for _ in range(len(kich_ban)):
            label, conf = clf.classify(None)
            self.sm.update(label, conf)

        self.assertEqual(self.sequences, ["7C4D3A"])

    def test_khong_the_tao_base_class_thieu_classify(self):
        """Quen viet classify() thi phai bao loi ngay luc tao doi tuong."""
        class ThieuHam(BaseGestureClassifier):
            pass

        with self.assertRaises(TypeError):
            ThieuHam()


if __name__ == "__main__":
    unittest.main(verbosity=2)
