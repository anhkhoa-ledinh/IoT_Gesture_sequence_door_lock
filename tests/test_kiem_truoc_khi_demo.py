"""
============================================================================
 test_kiem_truoc_khi_demo.py — Kiem scripts/kiem_truoc_khi_demo.py
----------------------------------------------------------------------------
 Chay:
   .conda\\python.exe -m pytest tests\\test_kiem_truoc_khi_demo.py -v

 Phan Node-RED duoc kiem bang mot HTTP server gia chay tren 127.0.0.1, dong
 vai Admin API (/flows, /context/flow/<tab>). Khong can Node-RED, Wokwi,
 broker hay webcam. Phan MQTT khong test o day (can broker that).
============================================================================
"""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

GOC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GOC / "scripts"))
import kiem_truoc_khi_demo as k  # noqa: E402

CFG = json.loads((GOC / "vision" / "config.json").read_text(encoding="utf-8"))
FLOWS_THAT = json.loads((GOC / "middleware" / "flows.json").read_text(encoding="utf-8"))


def flow_voi_ma(ma: str, tab: str = "tab_gate", node_id: str = "a_kiem_ma") -> list[dict]:
    return [{"id": tab, "type": "tab", "label": "Khoa cua cu chi"},
            {"id": node_id, "type": "function", "z": tab, "name": "Kiem ma",
             "func": f'const MA_MAC_DINH       = "{ma}";\nreturn msg;'}]


# ============================================================================
#  1. Phan tich flow va context
# ============================================================================

def test_flows_that_trong_repo_co_dung_mot_node_kiem_ma():
    tim = k.tim_node_kiem_ma(FLOWS_THAT)
    assert len(tim) == 1
    assert tim[0]["ma"] == CFG["secret"]["default_code"]
    assert tim[0]["dang_chay"] and tim[0]["tab"] == "tab_gate"


def test_tab_bi_disable_thi_khong_tinh_la_dang_chay():
    nodes = flow_voi_ma("7CE13A")
    nodes[0]["disabled"] = True
    assert k.tim_node_kiem_ma(nodes)[0]["dang_chay"] is False


@pytest.mark.parametrize("ctx, mong_doi", [
    ({"memory": {"ma_hop_le": {"msg": "7CE13A", "format": "string[6]"}}}, "7CE13A"),
    ({"default": {"ma_hop_le": {"msg": '"e17c4d"', "format": "string[6]"}}}, "E17C4D"),
    ({"memory": {"ma_hop_le": "7ce13a"}}, "7CE13A"),
    ({"memory": {"so_lan_sai": {"msg": 1, "format": "number"}}}, None),
    ({}, None),
    ([], None),
])
def test_doc_ma_tu_context(ctx, mong_doi):
    assert k.doc_ma_tu_context(ctx) == mong_doi


def test_file_flows_khop_config():
    assert k.kiem_flows_file(CFG).trang_thai == k.PASS


# ============================================================================
#  2. Node-RED Admin API gia
# ============================================================================

class _NodeRedGia(BaseHTTPRequestHandler):
    flows: list | dict = []
    context: dict = {}
    ma_loi: int | None = None

    def do_GET(self):  # noqa: N802
        if self.ma_loi:
            self.send_response(self.ma_loi)
            self.end_headers()
            return
        if self.path == "/flows":
            body = self.flows
        elif self.path.startswith("/context/flow/"):
            body = self.context
        else:
            self.send_response(404)
            self.end_headers()
            return
        data = json.dumps(body).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):  # tat log ra console
        pass


@pytest.fixture
def node_red():
    srv = HTTPServer(("127.0.0.1", 0), _NodeRedGia)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    def dat(flows, context=None, ma_loi=None):
        _NodeRedGia.flows, _NodeRedGia.context, _NodeRedGia.ma_loi = flows, context or {}, ma_loi
        return f"http://127.0.0.1:{srv.server_address[1]}"
    yield dat
    srv.shutdown()
    srv.server_close()


def trang_thai(kq):
    return [x.trang_thai for x in kq]


def test_flow_dung_context_trong(node_red):
    kq = k.kiem_node_red(CFG, node_red(FLOWS_THAT))
    assert trang_thai(kq) == [k.PASS, k.PASS]


def test_flow_moi_nhung_context_con_giu_ma_cu(node_red):
    # Dung loi am tham: da import flow moi, nhung context van giu ma cu E17C4D.
    url = node_red(flow_voi_ma("7CE13A"), {"memory": {"ma_hop_le": {"msg": "E17C4D"}}})
    kq = k.kiem_node_red(CFG, url)
    assert trang_thai(kq) == [k.PASS, k.FAIL]
    assert "E17C4D" in " ".join(kq[1].chi_tiet)


SETTINGS_MAU = """module.exports = {
    /** contextStorage: ...  (chu thich khoi) */
    //contextStorage: {
    //    default: {
    //        module:"localfilesystem"
    //    },
    //},
    flowFile: 'flows.json',
}"""
SETTINGS_FILE = """module.exports = {
    contextStorage: {
        default: { module: "localfilesystem" },
    },
}"""
SETTINGS_HAI_KHO = """module.exports = {
    contextStorage: {
        default: { module: "memory" },
        file: { module: "localfilesystem" }
    },
}"""
SETTINGS_BI_DANH = """module.exports = {
    contextStorage: {
        default: "file",
        mem: { module: "memory" },
        file: { module: "localfilesystem" }
    },
}"""


@pytest.mark.parametrize("noi_dung, mong_doi", [
    (SETTINGS_MAU, "memory"),             # file mau: contextStorage bi comment -> bo nho
    (SETTINGS_FILE, "localfilesystem"),
    (SETTINGS_HAI_KHO, "memory"),         # flows.json khong ghi ten kho -> kho default
    (SETTINGS_BI_DANH, "localfilesystem"),
    (None, None),
])
def test_xac_dinh_kho_context(noi_dung, mong_doi):
    assert k.xac_dinh_kho_context(noi_dung) == mong_doi


def _user_dir(tmp_path, noi_dung):
    (tmp_path / "settings.js").write_text(noi_dung, encoding="utf-8")
    return tmp_path


CTX_MA_CU = {"memory": {"ma_hop_le": {"msg": "E17C4D"}}}


def test_context_lech_kho_bo_nho_chi_khoi_dong_lai(node_red, tmp_path):
    url = node_red(flow_voi_ma("7CE13A"), CTX_MA_CU)
    kq = k.kiem_node_red(CFG, url, _user_dir(tmp_path, SETTINGS_MAU))
    s = " ".join(kq[1].chi_tiet)
    assert kq[1].trang_thai == k.FAIL
    assert "BO NHO" in s and "node-red" in s and "FILE" not in s


def test_context_lech_kho_file_chi_thu_muc_can_xoa(node_red, tmp_path):
    ud = _user_dir(tmp_path, SETTINGS_FILE)
    (ud / "context" / "tab_gate").mkdir(parents=True)
    url = node_red(flow_voi_ma("7CE13A"), CTX_MA_CU)
    s = " ".join(k.kiem_node_red(CFG, url, ud)[1].chi_tiet)
    assert "FILE" in s and "KHONG xoa duoc" in s
    assert str(ud / "context" / "tab_gate") in s and "dang ton tai" in s


def test_context_lech_khong_doc_duoc_settings_in_ca_hai_cach(node_red, tmp_path):
    url = node_red(flow_voi_ma("7CE13A"), CTX_MA_CU)
    s = " ".join(k.kiem_node_red(CFG, url, tmp_path / "khong_co")[1].chi_tiet)
    assert "bo nho" in s and "luu file" in s


def test_thong_bao_sua_khi_node_red_chua_chay():
    s = " ".join(k.kiem_node_red(CFG, "http://127.0.0.1:9")[0].chi_tiet)
    assert "Node-RED chua chay" in s and "node-red" in s


def test_thong_bao_sua_khi_co_hai_node_kiem_ma(node_red):
    nodes = flow_voi_ma("7CE13A") + flow_voi_ma("7CE13A", tab="tab_cu", node_id="cu")
    s = " ".join(k.kiem_node_red(CFG, node_red(nodes))[0].chi_tiet)
    assert "Xoa tab flow cu, Deploy, roi Import lai" in s


def test_flow_cu_chua_import_lai(node_red):
    kq = k.kiem_node_red(CFG, node_red(flow_voi_ma("E17C4D")))
    assert kq[0].trang_thai == k.FAIL


def test_hai_flow_kiem_ma_cung_chay(node_red):
    nodes = flow_voi_ma("7CE13A") + flow_voi_ma("E17C4D", tab="tab_cu", node_id="cu")
    kq = k.kiem_node_red(CFG, node_red(nodes))
    assert trang_thai(kq) == [k.FAIL]
    assert "2 NODE KIEM MA" in " ".join(kq[0].chi_tiet)


def test_api_v2_tra_ve_dict(node_red):
    kq = k.kiem_node_red(CFG, node_red({"rev": "abc", "flows": FLOWS_THAT}))
    assert trang_thai(kq) == [k.PASS, k.PASS]


def test_admin_auth_chi_canh_bao(node_red):
    kq = k.kiem_node_red(CFG, node_red([], ma_loi=401))
    assert trang_thai(kq) == [k.WARN]


def test_node_red_chua_chay():
    kq = k.kiem_node_red(CFG, "http://127.0.0.1:9")    # cong 9: khong ai nghe
    assert trang_thai(kq) == [k.FAIL]


# ============================================================================
#  3. File model
# ============================================================================

def test_hand_landmarker_that_hop_le():
    assert k.kiem_task(CFG).trang_thai == k.PASS


def test_hand_landmarker_tai_do_dang_bi_bat(tmp_path):
    goc = (GOC / "vision" / CFG["model"]["hand_landmarker_task"]).resolve()
    hong = tmp_path / "hand_landmarker.task"
    hong.write_bytes(goc.read_bytes()[:3_000_000])          # gia lap tai dut giua chung
    cfg = json.loads(json.dumps(CFG))
    cfg["model"]["hand_landmarker_task"] = str(hong)
    assert k.kiem_task(cfg).trang_thai == k.FAIL


def test_tflite_that_co_7_lop():
    kq = k.kiem_tflite(CFG)
    assert kq.trang_thai == k.PASS, kq.chi_tiet
