"""
============================================================================
 dem_10_lan.py — Dem ket qua tung luot nhap ma, CHI NGHE MQTT
----------------------------------------------------------------------------
 Chay song song voi phien demo (khong can webcam):
   D:\\IoT_Gesture_sequence_door_lock\\.conda\\python.exe scripts\\dem_10_lan.py
   ... scripts\\dem_10_lan.py --ghi-chu "truoc khi train lai"

 Bam Ctrl+C de dung: in bang tong ket va GHI THEM mot muc vao
 docs/ket_qua_10_lan.md (khong ghi de lan do truoc — giu duoc ca so lieu
 truoc va sau khi train lai).

 Mot "luot" la mot lan nguoi dung nhap ma:
   .../sequence  -> mo luot, ghi ma nhan duoc
   .../cmd       -> dong luot: unlock = THANH CONG, deny = TU CHOI,
                    lockout = KHOA TAM
   qua 5 giay khong co cmd                -> KHONG PHAN HOI
   co .../gesture nhung khong bao gio co
   .../sequence (het gio phia Python)     -> CHUA DU MA

 Luot CHUA DU MA khong co trong de bai goc nhung bat buoc phai dem: lan nhap
 hong o khau nhan dien thi Python khong publish sequence nao ca. Bo qua no thi
 lam 10 lan, hong 2 lan van ra "8/8 = 100%".
============================================================================
"""

from __future__ import annotations

import argparse
import hashlib
import json
import queue
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "vision"))
from common import load_config, resolve_path  # noqa: E402

CHO_CMD_GIAY = 5.0          # sequence -> cmd lau hon muc nay coi la KHONG PHAN HOI
DU_PHONG_GIAY = 2.0         # cho them sau timeout phia Python truoc khi chot CHUA DU MA
CMD_KEP_GIAY = 1.0          # 2 cmd cach nhau duoi muc nay cho 1 sequence -> nghi 2 flow

THANH_CONG, TU_CHOI, KHOA_TAM = "THANH CONG", "TU CHOI", "KHOA TAM"
KHONG_PHAN_HOI, CHUA_DU_MA = "KHONG PHAN HOI", "CHUA DU MA"
THU_TU_KET_QUA = [THANH_CONG, TU_CHOI, KHOA_TAM, KHONG_PHAN_HOI, CHUA_DU_MA]
CO_DAU = {THANH_CONG: "THÀNH CÔNG", TU_CHOI: "TỪ CHỐI", KHOA_TAM: "KHÓA TẠM",
          KHONG_PHAN_HOI: "KHÔNG PHẢN HỒI", CHUA_DU_MA: "CHƯA ĐỦ MÃ"}
ACTION_SANG_KET_QUA = {"unlock": THANH_CONG, "deny": TU_CHOI, "lockout": KHOA_TAM}


# ============================================================================
#  1. LOGIC DEM LUOT — thuan logic, khong mang, moc thoi gian truyen vao
# ============================================================================

@dataclass
class Luot:
    stt: int
    bat_dau: float                      # epoch giay: luc co sequence (hoac cu chi dau)
    ma: str | None                      # None neu chua du ma
    cu_chi: list[str] = field(default_factory=list)
    ket_qua: str = ""
    tre_giay: float | None = None       # sequence -> cmd
    dung_ma: bool | None = None         # ma nhan duoc co trung ma dung khong
    ghi_chu: str = ""


class BoDemLuot:
    """Bien chuoi ban tin MQTT thanh danh sach luot da phan loai.

    Goi nhan() cho moi ban tin va tick() deu dan (vd moi 0.2 giay). Ca hai tra
    ve danh sach luot VUA DONG de in ra man hinh.
    """

    def __init__(self, ma_dung: str, timeout_python_giay: float,
                 cho_cmd_giay: float = CHO_CMD_GIAY) -> None:
        self.ma_dung = ma_dung.upper()
        self.timeout_python = timeout_python_giay
        self.cho_cmd = cho_cmd_giay
        self.luot: list[Luot] = []
        self.cmd_ngoai_luot: list[tuple[float, dict]] = []
        self._mo: Luot | None = None                    # luot dang cho cmd
        self._cu_chi_cho: list[str] = []                # cu chi chua thanh sequence
        self._cu_chi_dau: float | None = None
        self._cu_chi_cuoi: float | None = None
        self._lockout_den = 0.0
        self._dong_cuoi_bang_cmd: tuple[Luot, float] | None = None

    # ------------------------------------------------------------- tien ich
    def _dong(self, l: Luot, ket_qua: str) -> Luot:
        l.stt = len(self.luot) + 1
        l.ket_qua = ket_qua
        self.luot.append(l)
        return l

    def _chot_cu_chi_do_dang(self) -> list[Luot]:
        """Cu chi da nhan ma khong thanh sequence -> mot luot CHUA DU MA."""
        if not self._cu_chi_cho:
            return []
        l = Luot(0, self._cu_chi_dau or 0.0, None, list(self._cu_chi_cho))
        l.ghi_chu = f"{len(l.cu_chi)} cu chi roi het gio phia Python"
        self._cu_chi_cho, self._cu_chi_dau, self._cu_chi_cuoi = [], None, None
        return [self._dong(l, CHUA_DU_MA)]

    # ------------------------------------------------------------- dau vao
    def tick(self, t: float) -> list[Luot]:
        xong: list[Luot] = []
        if self._mo and t - self._mo.bat_dau > self.cho_cmd:
            l, self._mo = self._mo, None
            if l.bat_dau < self._lockout_den:
                l.ghi_chu = "dang lockout - Node-RED co y khong tra loi"
            xong.append(self._dong(l, KHONG_PHAN_HOI))
        if (self._cu_chi_cuoi is not None
                and t - self._cu_chi_cuoi > self.timeout_python + DU_PHONG_GIAY):
            xong += self._chot_cu_chi_do_dang()
        return xong

    def nhan(self, loai: str, payload: dict, t: float) -> list[Luot]:
        """loai = phan duoi topic: 'gesture' / 'sequence' / 'cmd' / 'state'."""
        xong = self.tick(t)

        if loai == "gesture":
            # Python reset chuoi khi qua timeout tinh tu cu chi cuoi. Cu chi moi
            # den sau moc do la bat dau lan nhap moi -> chot phan do dang cu.
            if (self._cu_chi_cuoi is not None
                    and t - self._cu_chi_cuoi >= self.timeout_python):
                xong += self._chot_cu_chi_do_dang()
            if not self._cu_chi_cho:
                self._cu_chi_dau = t
            self._cu_chi_cho.append(str(payload.get("gesture", "?")))
            self._cu_chi_cuoi = t

        elif loai == "sequence":
            if self._mo:                                # sequence truoc chua co cmd
                l, self._mo = self._mo, None
                l.ghi_chu = "co sequence moi truoc khi co cmd"
                xong.append(self._dong(l, KHONG_PHAN_HOI))
            ma = str(payload.get("code", "")).upper()
            self._mo = Luot(0, t, ma, list(self._cu_chi_cho), dung_ma=(ma == self.ma_dung))
            self._cu_chi_cho, self._cu_chi_dau, self._cu_chi_cuoi = [], None, None

        elif loai == "cmd":
            action = str(payload.get("action", ""))
            giay = payload.get("sec", 30)
            # lockout sec=0 la nut RESET LOCKOUT tren dashboard, khong phai tra loi ma.
            if action == "lockout":
                self._lockout_den = t + float(giay) if giay else 0.0
            if action == "lockout" and not giay:
                self.cmd_ngoai_luot.append((t, payload))
            elif self._mo and action in ACTION_SANG_KET_QUA:
                l, self._mo = self._mo, None
                l.tre_giay = t - l.bat_dau
                if action == "deny" and l.dung_ma:
                    l.ghi_chu = "MA DUNG MA BI TU CHOI - Node-RED dang giu ma khac?"
                xong.append(self._dong(l, ACTION_SANG_KET_QUA[action]))
                self._dong_cuoi_bang_cmd = (l, t)
            else:
                # Khong co luot nao dang cho: mo khan cap tu dashboard, hoac
                # cmd thu hai cho cung mot sequence (hai flow kiem ma cung chay).
                self.cmd_ngoai_luot.append((t, payload))
                if self._dong_cuoi_bang_cmd and t - self._dong_cuoi_bang_cmd[1] < CMD_KEP_GIAY:
                    l = self._dong_cuoi_bang_cmd[0]
                    l.ghi_chu = (l.ghi_chu + "; " if l.ghi_chu else "") + \
                        f"nhan 2 cmd cho 1 sequence ({action}) - Node-RED co 2 flow?"
        return xong

    def ket_thuc(self, t: float) -> list[Luot]:
        """Goi khi Ctrl+C: chot luot dang do dang thay vi bo mat no."""
        xong = self.tick(t)
        if self._mo:
            l, self._mo = self._mo, None
            l.ghi_chu = "dung script khi dang cho cmd"
            xong.append(self._dong(l, KHONG_PHAN_HOI))
        xong += self._chot_cu_chi_do_dang()
        return xong

    # ------------------------------------------------------------- tong ket
    def dem(self) -> dict[str, int]:
        d = {k: 0 for k in THU_TU_KET_QUA}
        for l in self.luot:
            d[l.ket_qua] += 1
        return d


# ============================================================================
#  2. DOC BAN TIN MQTT
# ============================================================================

def phan_tich_ban_tin(topic: str, payload: bytes, prefix: str,
                      topics: dict[str, str]) -> tuple[str, dict] | None:
    """Tra ve (loai, payload_dict) hoac None neu khong phai ban tin cua ta."""
    if not topic.startswith(prefix):
        return None
    duoi = topic[len(prefix):]
    loai = {v: k for k, v in topics.items()}.get(duoi)
    if loai is None:
        return None
    try:
        p = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return (loai, p) if isinstance(p, dict) else None


# ============================================================================
#  3. HIEN THI VA XUAT BAO CAO
# ============================================================================

def gio(t: float) -> str:
    return datetime.fromtimestamp(t).strftime("%H:%M:%S")


def dong_ngan(l: Luot) -> str:
    ma = l.ma or "------"
    cc = ">".join(l.cu_chi) or "-"
    tre = f"{l.tre_giay:.2f}s" if l.tre_giay is not None else ""
    dm = "" if l.dung_ma is None else ("ma dung" if l.dung_ma else "ma SAI")
    s = f"[{gio(l.bat_dau)}] #{l.stt:02d}  {ma:<6}  {cc:<26} {l.ket_qua:<15}{tre:>7}  {dm}"
    return s + (f"  ({l.ghi_chu})" if l.ghi_chu else "")


def thong_tin_model(cfg: dict) -> tuple[str, str, str] | None:
    """(ten file, thoi diem sua, md5 rut gon) cua model dang dung, None neu khong co.

    Ghi vao bao cao de phan biet lan do TRUOC va SAU khi train lai.
    """
    p = resolve_path(cfg["model"]["classifier_tflite"])
    if not p.exists():
        return None
    md5 = hashlib.md5(p.read_bytes()).hexdigest()[:8]
    sua = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    return p.name, sua, md5


def mo_ta_model(cfg: dict, co_dau: bool) -> str:
    tt = thong_tin_model(cfg)
    if tt is None:
        return "KHÔNG CÓ file .tflite" if co_dau else "KHONG CO file .tflite"
    ten, sua, md5 = tt
    if co_dau:
        return f"`{ten}` sửa lúc {sua}, md5 `{md5}`"
    return f"{ten} sua luc {sua}, md5 {md5}"       # ban ASCII cho console Windows


def in_tong_ket(bo: BoDemLuot) -> None:
    d = bo.dem()
    n = len(bo.luot)
    print()
    print("=" * 78)
    print(f"TONG KET: {n} luot")
    print("=" * 78)
    for k in THU_TU_KET_QUA:
        print(f"  {k:<16}{d[k]:>4}")
    if n:
        print(f"\nTi le thanh cong: {d[THANH_CONG]}/{n} = {d[THANH_CONG] / n:.1%}")
        co_ma = [l for l in bo.luot if l.ma is not None]
        if co_ma:
            dung = sum(1 for l in co_ma if l.dung_ma)
            print(f"Nhan dien ra dung ma: {dung}/{len(co_ma)} luot co sequence")
    if bo.cmd_ngoai_luot:
        print(f"cmd ngoai luot (mo khan cap / reset lockout / cmd lap): {len(bo.cmd_ngoai_luot)}")
    print("\nNEU ban da lam N lan ma bang co it hon N luot: so lan thieu la lan Python")
    print("khong gui ban tin nao (vd chua giu du 15 khung) - cong vao that bai.")
    print("-" * 78)
    for l in bo.luot:
        print(dong_ngan(l))
    print("=" * 78)


def tao_muc_markdown(bo: BoDemLuot, cfg: dict, bat_dau: float, ket_thuc: float,
                     ghi_chu: str) -> str:
    d = bo.dem()
    n = len(bo.luot)
    tieu_de = (f"## Lần đo {datetime.fromtimestamp(bat_dau):%Y-%m-%d %H:%M:%S} → "
               f"{datetime.fromtimestamp(ket_thuc):%H:%M:%S}")
    if ghi_chu:
        tieu_de += f" — {ghi_chu}"
    o = [tieu_de, "",
         f"- Model: {mo_ta_model(cfg, co_dau=True)}",
         f"- Mã đúng (`config.json` → `secret.default_code`): `{bo.ma_dung}`",
         f"- **Tổng số lượt: {n} — thành công {d[THANH_CONG]}"
         + (f" ({d[THANH_CONG] / n:.1%})**" if n else "**")]
    co_ma = [l for l in bo.luot if l.ma is not None]
    if co_ma:
        o.append(f"- Nhận diện ra đúng mã: {sum(1 for l in co_ma if l.dung_ma)}/{len(co_ma)} "
                 "lượt có gửi `sequence`")
    if bo.cmd_ngoai_luot:
        o.append(f"- `cmd` ngoài lượt (mở khẩn cấp / reset lockout / cmd lặp): "
                 f"{len(bo.cmd_ngoai_luot)}")
    o += ["", "| Kết quả | Số lượt |", "|---|---|"]
    o += [f"| {CO_DAU[k]} | {d[k]} |" for k in THU_TU_KET_QUA]
    o += ["", "| # | Thời điểm | Mã nhận | Cử chỉ | Đúng mã? | Kết quả | Trễ `cmd` | Ghi chú |",
          "|---|---|---|---|---|---|---|---|"]
    for l in bo.luot:
        dm = "—" if l.dung_ma is None else ("có" if l.dung_ma else "**không**")
        tre = f"{l.tre_giay:.2f} s" if l.tre_giay is not None else "—"
        o.append(f"| {l.stt} | {gio(l.bat_dau)} | `{l.ma or '—'}` | "
                 f"{' → '.join(l.cu_chi) or '—'} | {dm} | {CO_DAU[l.ket_qua]} | {tre} | "
                 f"{l.ghi_chu.replace('|', '/')} |")
    return "\n".join(o) + "\n"


def ghi_them_markdown(path: Path, muc: str) -> None:
    """Ghi THEM vao cuoi file, khong bao gio ghi de lan do cu."""
    moi = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        if moi:
            f.write("# Kết quả đo nhập mã trên hệ thống chạy thật\n\n"
                    "Sinh tự động bởi `scripts/dem_10_lan.py` (nghe MQTT, không đếm tay). "
                    "Mỗi lần chạy script thêm một mục mới ở cuối file.\n\n"
                    "Một **lượt** mở khi có `.../sequence` và đóng khi có `.../cmd`. "
                    "`KHÔNG PHẢN HỒI` = quá 5 giây không có `cmd`. `CHƯA ĐỦ MÃ` = Python "
                    "đã nhận cử chỉ nhưng hết giờ trước khi đủ 3 cử chỉ, nên không gửi "
                    "`sequence` nào.\n")
        f.write("\n" + muc)


# ============================================================================
#  4. MAIN — MQTT chay luong rieng, logic chay o luong chinh
# ============================================================================

def main() -> int:
    import paho.mqtt.client as mqtt

    ap = argparse.ArgumentParser(description="Dem ket qua nhap ma bang cach nghe MQTT.")
    ap.add_argument("--ghi-chu", default="", help="nhan cho lan do, vd 'truoc khi train lai'")
    ap.add_argument("--ra", default=str(ROOT / "docs" / "ket_qua_10_lan.md"),
                    help="file markdown ghi them ket qua")
    args = ap.parse_args()

    cfg = load_config()
    m = cfg["mqtt"]
    prefix, topics = m["topic_prefix"], m["topics"]
    bo = BoDemLuot(cfg["secret"]["default_code"], float(cfg["thresholds"]["sequence_timeout_sec"]))
    hang_doi: queue.Queue = queue.Queue()

    def on_connect(client, userdata, flags, reason_code, properties=None):
        if reason_code == 0:
            client.subscribe(prefix + "#", qos=0)          # subscribe lai moi lan noi lai
            print(f"[mqtt] da ket noi, nghe {prefix}#")
        else:
            print(f"[mqtt] ket noi that bai: {reason_code}")

    def on_disconnect(client, userdata, flags, reason_code, properties=None):
        print(f"[mqtt] mat ket noi ({reason_code}), dang tu ket noi lai...")

    def on_message(client, userdata, msg):
        # Luong mang chi day vao hang doi; moi logic chay o luong chinh.
        hang_doi.put((msg.topic, msg.payload, time.time()))

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id="dem10-" + uuid.uuid4().hex[:8])
    client.on_connect, client.on_disconnect, client.on_message = on_connect, on_disconnect, on_message
    client.reconnect_delay_set(min_delay=1, max_delay=16)
    client.connect_async(m["broker"], int(m["port"]), int(m["keepalive"]))
    client.loop_start()

    bat_dau = time.time()
    print(f"Dang nghe {m['broker']}:{m['port']}  ma dung = {bo.ma_dung}")
    print(f"Model: {mo_ta_model(cfg, co_dau=False)}")
    print("Bam Ctrl+C de dung va lay bang tong ket.\n")
    try:
        while True:
            while True:
                try:
                    topic, payload, t = hang_doi.get_nowait()
                except queue.Empty:
                    break
                bt = phan_tich_ban_tin(topic, payload, prefix, topics)
                if bt:
                    for l in bo.nhan(bt[0], bt[1], t):
                        print(dong_ngan(l))
            for l in bo.tick(time.time()):
                print(dong_ngan(l))
            time.sleep(0.2)                                 # sleep ngat duoc bang Ctrl+C
    except KeyboardInterrupt:
        pass
    finally:
        client.loop_stop()
        client.disconnect()

    for l in bo.ket_thuc(time.time()):
        print(dong_ngan(l))
    in_tong_ket(bo)
    if bo.luot:
        ra = Path(args.ra)
        ghi_them_markdown(ra, tao_muc_markdown(bo, cfg, bat_dau, time.time(), args.ghi_chu))
        print(f"Da ghi them vao {ra}")
    else:
        print("Khong co luot nao - khong ghi file.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
