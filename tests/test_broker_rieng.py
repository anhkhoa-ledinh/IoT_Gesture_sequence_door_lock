"""Test che do broker rieng (TLS + tai khoan) — khong can mang, khong can broker."""
from __future__ import annotations

import copy
import importlib.util
import json
import ssl
import sys
from pathlib import Path

import pytest

GOC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GOC / "vision"))
import common  # noqa: E402

CFG = json.loads((GOC / "vision" / "config.json").read_text(encoding="utf-8"))


def _nap_script(ten):
    spec = importlib.util.spec_from_file_location(ten, GOC / "scripts" / f"{ten}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ClientGia:
    """Ghi lai nhung gi duoc goi, thay cho paho.mqtt.client.Client."""

    def __init__(self):
        self.tls = None
        self.tai_khoan = None

    def tls_set(self, **kw):
        self.tls = kw

    def username_pw_set(self, u, p):
        self.tai_khoan = (u, p)


def _cfg_rieng(tmp_path, co_file_tk=True):
    cfg = copy.deepcopy(CFG)
    cfg["mqtt"]["dung_broker_rieng"] = True
    cfg["mqtt"]["broker_rieng"]["host"] = "vidu.emqxsl.com"
    tk = tmp_path / "tk.json"
    if co_file_tk:
        tk.write_text(json.dumps({"laptop": {"username": "gate_laptop", "password": "mk1"},
                                  "giam_sat": {"username": "gate_giam_sat", "password": "mk2"}}))
    cfg["mqtt"]["broker_rieng"]["tai_khoan_file"] = str(tk)        # duong dan tuyet doi van dung
    return cfg


def test_mac_dinh_van_la_broker_cong_cong():
    """Chua bat thi giu nguyen hanh vi cu: khong TLS, khong tai khoan."""
    assert CFG["mqtt"]["dung_broker_rieng"] is False
    c = ClientGia()
    host, port = common.cau_hinh_mqtt_client(c, CFG, "laptop")
    assert (host, port) == (CFG["mqtt"]["broker"], CFG["mqtt"]["port"])
    assert c.tls is None and c.tai_khoan is None


def test_broker_rieng_bat_tls_kiem_chung_chi_va_dang_nhap(tmp_path):
    c = ClientGia()
    host, port = common.cau_hinh_mqtt_client(c, _cfg_rieng(tmp_path), "laptop")
    assert (host, port) == ("vidu.emqxsl.com", 8883)
    assert c.tls["cert_reqs"] == ssl.CERT_REQUIRED                 # bat buoc kiem chung chi
    assert Path(c.tls["ca_certs"]).exists()
    assert c.tai_khoan == ("gate_laptop", "mk1")


def test_moi_vai_tro_dung_tai_khoan_rieng(tmp_path):
    c = ClientGia()
    common.cau_hinh_mqtt_client(c, _cfg_rieng(tmp_path), "giam_sat")
    assert c.tai_khoan == ("gate_giam_sat", "mk2")


def test_thieu_file_tai_khoan_bao_loi_ro_rang(tmp_path):
    with pytest.raises(FileNotFoundError, match="tao_tai_khoan_mqtt.py"):
        common.thong_so_mqtt(_cfg_rieng(tmp_path, co_file_tk=False), "laptop")


def test_vai_tro_khong_co_thi_bao_loi(tmp_path):
    with pytest.raises(KeyError):
        common.thong_so_mqtt(_cfg_rieng(tmp_path), "nodered")


def test_goi_ca_co_du_hai_chung_chi_digicert():
    pem = (GOC / "middleware" / "certs" / "emqx_ca_bundle.pem").read_text()
    assert pem.count("BEGIN CERTIFICATE") == 2
    ctx = ssl.create_default_context(cafile=str(GOC / "middleware" / "certs" / "emqx_ca_bundle.pem"))
    ten = sorted(dict(x[0] for x in c["subject"])["commonName"] for c in ctx.get_ca_certs())
    assert ten == ["DigiCert Global Root CA", "DigiCert Global Root G2"]


def test_ca_cert_h_khop_goi_ca():
    """firmware/ca_cert.h phai chua dung noi dung goi CA ma Python dung."""
    h = (GOC / "firmware" / "ca_cert.h").read_text()
    pem = (GOC / "middleware" / "certs" / "emqx_ca_bundle.pem").read_text().strip()
    assert pem in h


def test_bang_phan_quyen_chi_nodered_duoc_gui_lenh():
    t = _nap_script("tao_tai_khoan_mqtt")
    p = CFG["mqtt"]["topic_prefix"]
    luat = t.bang_phan_quyen(p)
    gui_cmd = [u for u, topic, a, q in luat if topic == p + "cmd" and "Publish" in a and q == "Allow"]
    assert gui_cmd == ["gate_nodered"]
    nghe_seq = [u for u, topic, a, q in luat if topic == p + "sequence" and a == "Subscribe" and q == "Allow"]
    assert nghe_seq == ["gate_nodered"]
    assert luat[-1] == ("(All Users)", "#", "Publish & Subscribe", "Deny")   # che do whitelist


def test_tao_tai_khoan_khong_ghi_de_mat_khau_cu(tmp_path, monkeypatch):
    t = _nap_script("tao_tai_khoan_mqtt")
    monkeypatch.setattr(t, "TAI_KHOAN", tmp_path / "tk.json")
    a = t.doc_hoac_tao_tai_khoan(tao_lai=False)
    b = t.doc_hoac_tao_tai_khoan(tao_lai=False)
    assert a == b and set(a) == {"laptop", "nodered", "esp32", "giam_sat"}
    assert len({v["password"] for v in a.values()}) == 4                 # 4 mat khau khac nhau
    c = t.doc_hoac_tao_tai_khoan(tao_lai=True)
    assert c["laptop"]["password"] != a["laptop"]["password"]


def test_ghi_host_config_giu_nguyen_dinh_dang(tmp_path, monkeypatch):
    t = _nap_script("tao_tai_khoan_mqtt")
    goc = (GOC / "vision" / "config.json").read_bytes()
    f = tmp_path / "config.json"
    f.write_bytes(goc)
    monkeypatch.setattr(t, "CONFIG", f)
    t.ghi_host_config("abc.emqxsl.com", 8883)
    moi = f.read_bytes()
    assert json.loads(moi)["mqtt"]["broker_rieng"]["host"] == "abc.emqxsl.com"
    assert json.loads(moi)["mqtt"]["dung_broker_rieng"] is False        # khong tu bat
    assert moi.count(b"\r\n") == goc.count(b"\r\n")                      # giu kieu xuong dong


def test_flow_broker_rieng_dung_tls_va_tai_khoan_nodered(tmp_path, monkeypatch):
    t = _nap_script("tao_tai_khoan_mqtt")
    monkeypatch.setattr(t, "FLOWS_RIENG", tmp_path / "f.json")
    tk = {v: {"username": "gate_" + v, "password": "mk_" + v} for v in t.VAI_TRO}
    t.ghi_flows_rieng("abc.emqxsl.com", 8883, tk)
    nodes = json.loads((tmp_path / "f.json").read_text(encoding="utf-8"))
    b = [n for n in nodes if n["type"] == "mqtt-broker"][0]
    tls = [n for n in nodes if n["type"] == "tls-config"][0]
    assert b["usetls"] is True and b["port"] == "8883" and b["tls"] == tls["id"]
    assert b["credentials"] == {"user": "gate_nodered", "password": "mk_nodered"}
    assert tls["verifyservercert"] is True and tls["ca"].endswith("emqx_ca_bundle.pem")
    # flows.json goc khong bi dong vao
    goc = json.loads((GOC / "middleware" / "flows.json").read_text(encoding="utf-8"))
    assert [n for n in goc if n["type"] == "mqtt-broker"][0]["usetls"] is False
