"""
============================================================================
 gesture_lock.py — TANG 1a: NODE CAM BIEN (laptop)
----------------------------------------------------------------------------
 Doc webcam -> phan loai cu chi -> ghep thanh chuoi 3 byte -> day len MQTT.
 KHONG dieu khien servo truc tiep. Node-RED moi la nguoi quyet dinh mo hay khong.

 Chay:
   D:\\IoT_Gesture_sequence_door_lock\\.conda\\python.exe vision\\gesture_lock.py

 Ba class doc lap, moi class mot viec:

   GestureClassifier     anh  -> (nhan, do tin cay)
   SequenceStateMachine  (nhan, do tin cay) -> su kien "da nhan 1 cu chi" /
                                               "da du chuoi 3 cu chi"
   MqttPublisher         su kien -> ban tin MQTT

 Ba class nay KHONG biet gi ve nhau. Chung duoc noi lai voi nhau o main().
 Nho vay co the thay GestureClassifier bang mot cach nhan dang khac (vi du
 tinh bitmask hinh hoc thuan tuy, khong can model) ma KHONG phai sua hai
 class con lai — xem lop BaseGestureClassifier ben duoi.
============================================================================
"""

from __future__ import annotations

import json
import sys
import time
import uuid
from abc import ABC, abstractmethod
from typing import Callable

import cv2
import mediapipe as mp
import numpy as np
import paho.mqtt.client as mqtt
from mediapipe.tasks import python as mp_tasks
from mediapipe.tasks.python import vision as mp_vision

from common import (
    cau_hinh_mqtt_client,
    draw_landmarks,
    ensure_hand_landmarker,
    gesture_tables,
    load_config,
    preprocess_landmarks,
    resolve_path,
)


# ============================================================================
#  1. GESTURE CLASSIFIER
# ============================================================================

class BaseGestureClassifier(ABC):
    """Hop dong ma moi bo phan loai cu chi phai tuan theo.

    CHI CO MOT ham bat buoc: classify(frame) -> (label, conf).

    `last_landmarks` la thu tuy chon, chi de ve khung xuong len man hinh.
    Lop con khong can dat no — mac dinh None va phan ve se tu bo qua. Nho vay
    mot ban cai dat khac (vi du tinh bitmask hinh hoc, khong dung model) chi
    can viet dung ham classify() la chay duoc, khong dong den
    SequenceStateMachine hay MqttPublisher.
    """

    def __init__(self) -> None:
        self.last_landmarks = None

    @abstractmethod
    def classify(self, frame) -> tuple[str, float]:
        """Nhan 1 khung hinh BGR, tra ve (ten_lop, do_tin_cay).

        Khong thay tay thi PHAI tra ve ("none", 0.0).
        """

    def close(self) -> None:
        """Don dep tai nguyen. Lop con khong co gi de don thi khong can viet."""


def _load_tflite_interpreter(model_path):
    """Nap model TFLite.

    tf.lite.Interpreter da bi danh dau deprecated tu TensorFlow 2.20, ban thay
    the la goi ai_edge_litert. Thu ban moi truoc, khong co thi dung ban cu —
    van chay binh thuong, chi in canh bao.
    """
    try:
        from ai_edge_litert.interpreter import Interpreter  # type: ignore
        return Interpreter(model_path=str(model_path)), "ai_edge_litert"
    except ImportError:
        import tensorflow as tf
        return tf.lite.Interpreter(model_path=str(model_path)), "tf.lite"


class GestureClassifier(BaseGestureClassifier):
    """Ban cai dat chinh: MediaPipe HandLandmarker + MLP da huan luyen (TFLite).

    Khau tien xu ly dung lai preprocess_landmarks() trong common.py — KHONG
    copy code. Neu khau nay lech so voi luc thu du lieu thi model se doan sai
    ma khong co dau hieu gi bao ra ngoai.
    """

    def __init__(self, cfg: dict) -> None:
        super().__init__()
        self.cfg = cfg
        self.id_to_label, _ = gesture_tables(cfg)

        # --- MediaPipe Tasks HandLandmarker (khong dung mp.solutions.hands) ---
        model_task = ensure_hand_landmarker(cfg)
        options = mp_vision.HandLandmarkerOptions(
            base_options=mp_tasks.BaseOptions(model_asset_path=str(model_task)),
            running_mode=mp_vision.RunningMode.VIDEO,
            num_hands=cfg["model"]["num_hands"],
        )
        self._landmarker = mp_vision.HandLandmarker.create_from_options(options)

        # --- Model phan loai TFLite ---
        tflite_path = resolve_path(cfg["model"]["classifier_tflite"])
        if not tflite_path.exists():
            raise FileNotFoundError(
                f"Chua co {tflite_path}.\n"
                f"Hay chay vision/train_classifier.ipynb de huan luyen truoc."
            )
        self._interp, backend = _load_tflite_interpreter(tflite_path)
        self._interp.allocate_tensors()
        self._in = self._interp.get_input_details()[0]
        self._out = self._interp.get_output_details()[0]
        print(f"[classifier] TFLite nap qua '{backend}': {tflite_path.name}")

        self._t0 = time.monotonic()
        self._last_ts = -1

    def classify(self, frame) -> tuple[str, float]:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        # RunningMode.VIDEO doi moc thoi gian tang dan tuyet doi.
        ts = int((time.monotonic() - self._t0) * 1000)
        if ts <= self._last_ts:
            ts = self._last_ts + 1
        self._last_ts = ts

        result = self._landmarker.detect_for_video(mp_image, ts)
        if not result.hand_landmarks:
            self.last_landmarks = None
            return "none", 0.0

        lms = result.hand_landmarks[0]
        self.last_landmarks = lms
        handed = result.handedness[0][0].category_name

        features = preprocess_landmarks(lms, handed)
        self._interp.set_tensor(self._in["index"],
                                features.reshape(1, -1).astype(np.float32))
        self._interp.invoke()
        probs = self._interp.get_tensor(self._out["index"])[0]

        class_id = int(np.argmax(probs))
        return self.id_to_label[class_id], float(probs[class_id])

    def close(self) -> None:
        self._landmarker.close()


# ============================================================================
#  2. SEQUENCE STATE MACHINE
# ============================================================================

class SequenceStateMachine:
    """Bien chuoi (nhan, do_tin_cay) tung khung thanh mat ma 3 byte hex.

    Luat, lay tu config.json:

      * Chap nhan 1 cu chi khi do tin cay >= min_confidence VA cung mot nhan
        lien tuc du stable_frames khung. Mot khung tut do tin cay la dem lai
        tu dau — nguoi dung phai GIU YEN tay, khong phai luot qua.

      * Sau khi chap nhan, bat buoc qua trang thai 'none' du none_gap_frames
        khung moi nhan cu chi tiep theo. Khong co luat nay thi giu nguyen tay
        se bi dem thanh 3 cu chi giong nhau lien tiep.

      * Qua sequence_timeout_sec giay ma khong chap nhan them cu chi nao thi
        xoa het lam lai. Tinh tu luc chap nhan cu chi dau tien.

      * Du code_length cu chi thi phat su kien on_sequence(code_hex) roi tu reset.

    Class nay THUAN LOGIC: khong dung camera, khong dung mang, khong goi
    time.time() truc tiep (moc thoi gian lay qua tham so `now`). Nho vay test
    duoc bang du lieu gia, khong can webcam va khong phai ngoi doi 10 giay.
    """

    def __init__(
        self,
        cfg: dict,
        on_gesture: Callable[[str, str, float], None] | None = None,
        on_sequence: Callable[[str], None] | None = None,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        th = cfg["thresholds"]
        self.min_conf = float(th["min_confidence"])
        self.stable_frames = int(th["stable_frames"])
        self.none_gap_frames = int(th["none_gap_frames"])
        self.timeout_sec = float(th["sequence_timeout_sec"])
        self.code_length = int(th["code_length"])

        _, self.label_to_hex = gesture_tables(cfg)

        self.on_gesture = on_gesture
        self.on_sequence = on_sequence
        self._now = now

        self.reset()

    # ---------------------------------------------------------------- trang thai
    def reset(self) -> None:
        """Xoa het, quay ve trang thai cho cu chi dau tien."""
        self.accepted: list[str] = []          # danh sach hex da chap nhan
        self.accepted_labels: list[str] = []   # ten lop tuong ung, de hien thi
        self.candidate: str | None = None      # nhan dang duoc tich luy
        self.stable_count = 0                  # da giu duoc bao nhieu khung
        self.waiting_none = False              # dang cho du khoang 'none' chua
        self.none_count = 0
        self.started_at: float | None = None   # luc chap nhan cu chi dau tien
        self.last_progress: float | None = None

    @property
    def progress(self) -> float:
        """Ty le 0..1 cua thanh tien trinh giu cu chi."""
        return min(1.0, self.stable_count / self.stable_frames)

    @property
    def seconds_left(self) -> float | None:
        """So giay con lai truoc khi bi reset. None neu chua bat dau chuoi."""
        if self.last_progress is None:
            return None
        return max(0.0, self.timeout_sec - (self._now() - self.last_progress))

    def code_display(self) -> str:
        """Chuoi hex dang nhap, dang 'E1 7C __'."""
        o = [self.accepted[i] if i < len(self.accepted) else "__"
             for i in range(self.code_length)]
        return " ".join(o)

    # ---------------------------------------------------------------- cap nhat
    def update(self, label: str, conf: float) -> None:
        """Nap 1 khung. Goi ham nay dung 1 lan cho moi khung hinh."""
        now = self._now()

        # --- Timeout: qua lau khong tien trien thi xoa lam lai ---
        if (self.last_progress is not None
                and now - self.last_progress >= self.timeout_sec):
            self.reset()
            return

        # --- Dang cho khoang 'none' giua hai cu chi ---
        if self.waiting_none:
            if label == "none":
                self.none_count += 1
                if self.none_count >= self.none_gap_frames:
                    self.waiting_none = False
                    self.none_count = 0
            else:
                # Van con thay cu chi -> dem lai tu dau, chua duoc nhan cai moi.
                self.none_count = 0
            self.candidate = None
            self.stable_count = 0
            return

        # --- Khung khong dung de tich luy: khong co tay, la 'none',
        #     hoac do tin cay khong dat nguong ---
        if label == "none" or conf < self.min_conf or label not in self.label_to_hex:
            self.candidate = None
            self.stable_count = 0
            return

        # --- Tich luy so khung giu cung mot nhan ---
        if label == self.candidate:
            self.stable_count += 1
        else:
            self.candidate = label
            self.stable_count = 1

        if self.stable_count >= self.stable_frames:
            self._accept(label, conf, now)

    def _accept(self, label: str, conf: float, now: float) -> None:
        """Chot 1 cu chi vao mat ma."""
        hex_code = self.label_to_hex[label]
        self.accepted.append(hex_code)
        self.accepted_labels.append(label)

        if self.started_at is None:
            self.started_at = now
        self.last_progress = now

        self.candidate = None
        self.stable_count = 0

        if self.on_gesture:
            self.on_gesture(label, hex_code, conf)

        if len(self.accepted) >= self.code_length:
            code = "".join(self.accepted)
            if self.on_sequence:
                self.on_sequence(code)
            self.reset()
        else:
            # Bat buoc qua khoang 'none' truoc khi nhan cu chi ke tiep.
            self.waiting_none = True
            self.none_count = 0


# ============================================================================
#  3. MQTT PUBLISHER
# ============================================================================

class MqttPublisher:
    """Day su kien len broker MQTT.

    Dung connect_async() + loop_start(): paho chay mang tren MOT LUONG RIENG,
    nen vong lap camera khong bao gio bi treo cho ket noi. Mat mang thi paho tu
    ket noi lai, ham publish() chi don gian tra ve that bai chu khong chan.
    """

    def __init__(self, cfg: dict) -> None:
        m = cfg["mqtt"]
        self.keepalive = int(m["keepalive"])

        prefix = m["topic_prefix"]
        self.topic_gesture = prefix + m["topics"]["gesture"]
        self.topic_sequence = prefix + m["topics"]["sequence"]

        # Client ID ngau nhien: broker.hivemq.com la broker cong cong, trung ID
        # voi nguoi khac se lam hai ben lien tuc da nhau va bi ngat.
        client_id = m["client_id_prefix"] + uuid.uuid4().hex[:8]
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                                  client_id=client_id)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.reconnect_delay_set(min_delay=1, max_delay=16)

        # Broker cong cong hay broker rieng (TLS + tai khoan 'laptop') do
        # config.json quyet dinh — xem common.cau_hinh_mqtt_client().
        self.host, self.port = cau_hinh_mqtt_client(self.client, cfg, "laptop")
        self.tls = bool(cfg["mqtt"].get("dung_broker_rieng", False))

        self.connected = False
        self.sent_count = 0
        self._client_id = client_id

    # ------------------------------------------------------------- vong doi
    def start(self) -> None:
        """Bat dau ket noi. Tra ve ngay, khong doi ket noi xong."""
        print(f"[mqtt] client_id={self._client_id} -> {self.host}:{self.port}"
              f"{'  (TLS, tai khoan laptop)' if self.tls else ''}")
        self.client.connect_async(self.host, self.port, self.keepalive)
        self.client.loop_start()

    def stop(self) -> None:
        self.client.loop_stop()
        self.client.disconnect()

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        self.connected = (reason_code == 0)
        print(f"[mqtt] {'da ket noi' if self.connected else f'that bai: {reason_code}'}")

    def _on_disconnect(self, client, userdata, flags, reason_code, properties=None):
        self.connected = False
        print(f"[mqtt] mat ket noi ({reason_code}), dang tu ket noi lai...")

    # ------------------------------------------------------------- gui tin
    def _publish(self, topic: str, payload: dict) -> None:
        body = json.dumps(payload, separators=(",", ":"))
        info = self.client.publish(topic, body, qos=0, retain=False)
        ok = info.rc == mqtt.MQTT_ERR_SUCCESS
        if ok:
            self.sent_count += 1
        print(f"[mqtt] {'->' if ok else 'XX'} {topic}  {body}")

    def publish_gesture(self, label: str, hex_code: str, conf: float) -> None:
        """Uplink: bao vua chap nhan 1 cu chi."""
        self._publish(self.topic_gesture, {
            "gesture": label,
            "hex": hex_code,
            "conf": round(float(conf), 2),
            "ts": int(time.time()),
        })

    def publish_sequence(self, code: str) -> None:
        """Uplink: bao da nhap du chuoi 3 cu chi."""
        self._publish(self.topic_sequence, {
            "code": code,
            "ts": int(time.time()),
        })


# ============================================================================
#  4. OVERLAY — ve thong tin len khung hinh (dung de quay video demo)
# ============================================================================

def draw_overlay(frame, classifier, sm, publisher, label, conf):
    """Ve toan bo thong tin trang thai len khung hinh."""
    h, w = frame.shape[:2]

    # --- Khung xuong ban tay (neu bo phan loai co cung cap) ---
    if classifier.last_landmarks is not None:
        draw_landmarks(frame, classifier.last_landmarks)

    # --- Dai mo phia tren cho de doc chu ---
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 96), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)

    # --- Ten lop + do tin cay ---
    dat_nguong = conf >= sm.min_conf and label != "none"
    mau = (0, 255, 0) if dat_nguong else (160, 160, 160)
    cv2.putText(frame, f"{label.upper()}  {conf:.2f}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.85, mau, 2)

    # --- Thanh tien trinh giu du 15 khung ---
    bar_x, bar_y, bar_w, bar_h = 10, 42, 240, 14
    cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h),
                  (90, 90, 90), 1)
    if sm.waiting_none:
        # Dang cho khoang 'none' -> ve tien trinh cua khoang cho, mau khac han.
        ty_le = min(1.0, sm.none_count / sm.none_gap_frames)
        cv2.rectangle(frame, (bar_x + 1, bar_y + 1),
                      (bar_x + int(bar_w * ty_le), bar_y + bar_h - 1),
                      (0, 165, 255), -1)
        cv2.putText(frame, "HA TAY XUONG", (bar_x + bar_w + 12, bar_y + 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 1)
    else:
        cv2.rectangle(frame, (bar_x + 1, bar_y + 1),
                      (bar_x + int(bar_w * sm.progress), bar_y + bar_h - 1),
                      (0, 255, 0), -1)
        cv2.putText(frame, f"{sm.stable_count}/{sm.stable_frames}",
                    (bar_x + bar_w + 12, bar_y + 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    # --- Chuoi hex dang nhap ---
    cv2.putText(frame, f"MA: {sm.code_display()}", (10, 84),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)

    # --- Dem nguoc timeout ---
    con_lai = sm.seconds_left
    if con_lai is not None:
        mau_tg = (0, 0, 255) if con_lai < 3 else (255, 255, 255)
        cv2.putText(frame, f"con {con_lai:4.1f}s", (w - 150, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, mau_tg, 2)

    # --- Trang thai MQTT ---
    mqtt_mau = (0, 255, 0) if publisher.connected else (0, 0, 255)
    cv2.putText(frame,
                f"MQTT {'ON' if publisher.connected else 'OFF'} ({publisher.sent_count})",
                (w - 190, 84), cv2.FONT_HERSHEY_SIMPLEX, 0.6, mqtt_mau, 2)

    cv2.putText(frame, "Q de thoat | R de xoa chuoi dang nhap",
                (10, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)


# ============================================================================
#  5. MAIN — noi ba class lai voi nhau
# ============================================================================

def main() -> int:
    cfg = load_config()

    classifier = GestureClassifier(cfg)
    publisher = MqttPublisher(cfg)

    # Day la toan bo phan "noi day" giua ba class. Doi GestureClassifier sang
    # ban cai dat khac chi can sua DUNG MOT dong o tren.
    sm = SequenceStateMachine(
        cfg,
        on_gesture=lambda label, hex_code, conf: (
            print(f"[chuoi] nhan '{label}' = {hex_code} (conf {conf:.2f})"),
            publisher.publish_gesture(label, hex_code, conf),
        ),
        on_sequence=lambda code: (
            print(f"[chuoi] DU 3 CU CHI -> ma {code}"),
            publisher.publish_sequence(code),
        ),
    )

    publisher.start()

    cam = cfg["camera"]
    cap = cv2.VideoCapture(cam["camera_index"], cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, cam["frame_width"])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cam["frame_height"])
    if not cap.isOpened():
        print(f"LOI: khong mo duoc webcam index {cam['camera_index']}.")
        publisher.stop()
        classifier.close()
        return 1

    print("Da mo webcam. Bam Q trong cua so video de thoat.")

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("LOI: mat tin hieu webcam.")
                break

            # Lat ngang cho giong anh guong. PHAI giong het collect_data.py,
            # neu khong thi du lieu train va luc chay that se lat nguoc nhau.
            frame = cv2.flip(frame, 1)

            label, conf = classifier.classify(frame)
            sm.update(label, conf)
            draw_overlay(frame, classifier, sm, publisher, label, conf)

            cv2.imshow("Gesture door lock - Q de thoat", frame)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), ord("Q"), 27):
                break
            if key in (ord("r"), ord("R")):
                sm.reset()
                print("[chuoi] da xoa, nhap lai tu dau")
    except KeyboardInterrupt:
        print("\nDung boi nguoi dung.")
    finally:
        cap.release()
        cv2.destroyAllWindows()
        publisher.stop()
        classifier.close()
        print(f"Da gui {publisher.sent_count} ban tin MQTT.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
