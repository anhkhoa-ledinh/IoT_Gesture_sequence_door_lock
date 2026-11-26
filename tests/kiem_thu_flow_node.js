// ============================================================================
//  kiem_thu_flow_node.js — kiem thu logic tang 3 (Node-RED) KHONG can broker,
//  KHONG can ESP32, KHONG can camera.
// ----------------------------------------------------------------------------
//  Cach chay (tu thu muc goc repo):
//      node tests/kiem_thu_flow_node.js
//
//  Y tuong: doc THANG middleware/flows.json, lay ma nguon cua cac node
//  function (dung ban dang deploy, khong chep lai), roi chay chung voi mot
//  "flow context" gia va mot dong ho gia. Nho dong ho gia nen kiem duoc
//  lockout 30 giay ma khong phai doi 30 giay that.
//
//  Kiem duoc phan LOGIC cua TC-01..05, TC-13, TC-15..17 o phia Node-RED.
//  KHONG kiem duoc: servo/LED/OLED (tang 1), ket noi MQTT that (tang 2),
//  giao dien dashboard. Nhung phan do van phai test bang tay.
// ============================================================================
const fs = require("fs");
const path = require("path");

const FLOWS = path.join(__dirname, "..", "middleware", "flows.json");
const nodes = JSON.parse(fs.readFileSync(FLOWS, "utf8"));

function layHam(ten) {
    const n = nodes.find((x) => x.type === "function" && x.name === ten);
    if (!n) throw new Error("Khong tim thay node function: " + ten);
    return n.func;
}

// ---------------------------------------------------------------- moi truong gia
let gioGia = Date.UTC(2026, 9, 31, 2, 0, 0);       // dong ho gia, don vi ms
let henGio = [];                                     // cac setTimeout dang cho
const flowCtx = {};

const flow = {
    get: (k) => flowCtx[k],
    set: (k, v) => { flowCtx[k] = v; },
};

class DateGia extends Date {
    constructor(...a) { super(...(a.length ? a : [gioGia])); }
    static now() { return gioGia; }
}

function setTimeoutGia(fn, ms) { henGio.push({ luc: gioGia + ms, fn }); }

function troiQua(giay) {
    gioGia += giay * 1000;
    const den = henGio.filter((h) => h.luc <= gioGia);
    henGio = henGio.filter((h) => h.luc > gioGia);
    den.forEach((h) => h.fn());
}

function chay(ten, msg) {
    const daGui = [];
    const node = { status: () => {}, send: (m) => daGui.push(m) };
    const f = new Function("msg", "flow", "node", "setTimeout", "Date", layHam(ten));
    const ra = f(msg, flow, node, setTimeoutGia, DateGia);
    return { ra, daGui };
}

const kiemMa = (code) => chay("Kiem ma + dem so lan sai + lockout", { payload: { code, ts: 1 } }).ra;
const csv = (banGhi) => chay("Chuan bi dong CSV", { payload: banGhi }).ra.payload;

// ---------------------------------------------------------------- tien ich kiem
let dat = 0, khong = 0;
const ketQua = [];
function kiem(ma, moTa, dieuKien, chiTiet) {
    if (dieuKien) dat++; else khong++;
    ketQua.push({ ma, moTa, ok: !!dieuKien, chiTiet: chiTiet || "" });
    console.log(`${dieuKien ? "DAT  " : "KHONG"}  ${ma.padEnd(6)} ${moTa}${chiTiet ? "  -> " + chiTiet : ""}`);
}

// Ma dung doc thang tu hang MA_MAC_DINH trong flow — doi ma thi test tu theo.
const MA_DUNG = layHam("Kiem ma + dem so lan sai + lockout").match(/MA_MAC_DINH\s*=\s*"([0-9A-F]+)"/)[1];
console.log("Ma dung trong flow: " + MA_DUNG + "\n");
const MA_SAI = "B9B9B9";

// ---------------------------------------------------------------- TC-01
let r = kiemMa(MA_DUNG);
kiem("TC-01", "Ma dung -> lenh unlock ttl 5",
    r[0] && r[0].payload.action === "unlock" && r[0].payload.ttl === 5,
    JSON.stringify(r[0] && r[0].payload));
kiem("TC-01", "Ma dung -> ghi log 'DUNG — MO KHOA'", r[1].payload.ket_qua === "DUNG — MO KHOA");

// ---------------------------------------------------------------- TC-02
r = kiemMa(MA_SAI);
kiem("TC-02", "Ma sai lan 1 -> lenh deny", r[0] && r[0].payload.action === "deny");
kiem("TC-02", "Ma sai lan 1 -> log 'SAI (lan 1/3)'", r[1].payload.ket_qua === "SAI (lan 1/3)", r[1].payload.ket_qua);
const dongCsv = [csv(r[1].payload)];

// ---------------------------------------------------------------- TC-03
r = kiemMa(MA_SAI); dongCsv.push(csv(r[1].payload));
kiem("TC-03", "Ma sai lan 2 -> deny", r[0].payload.action === "deny");
r = kiemMa(MA_SAI); dongCsv.push(csv(r[1].payload));
kiem("TC-03", "Ma sai lan 3 -> lockout 30 giay",
    r[0].payload.action === "lockout" && r[0].payload.sec === 30, JSON.stringify(r[0].payload));

// ---------------------------------------------------------------- TC-04
troiQua(5);
r = kiemMa(MA_DUNG); dongCsv.push(csv(r[1].payload));
kiem("TC-04", "Dang lockout, nhap MA DUNG -> KHONG gui lenh nao", r[0] === null);
kiem("TC-04", "Dang lockout -> van ghi log 'BI CHAN'", r[1].payload.ket_qua === "BI CHAN (dang lockout)");

// ---------------------------------------------------------------- TC-05
troiQua(26);                                   // tong 31 giay ke tu lockout
r = kiemMa(MA_DUNG); dongCsv.push(csv(r[1].payload));
kiem("TC-05", "Het 30 giay -> ma dung mo duoc", r[0] && r[0].payload.action === "unlock");
kiem("TC-05", "Sau khi mo -> bo dem sai ve 0", flowCtx.so_lan_sai === 0);

// ---------------------------------------------------------------- TC-17
const cot = Object.keys(dongCsv[0]).join(",");
kiem("TC-17", "Dong CSV dung 4 cot", cot === "timestamp,ma_nhap,ket_qua,so_lan_sai_lien_tiep", cot);
const chuoiSai = dongCsv.map((d) => d.so_lan_sai_lien_tiep).join("->");
kiem("TC-17", "Cot so_lan_sai_lien_tiep tang 1->2->3, ve 0 sau lan mo", chuoiSai === "1->2->3->3->0", chuoiSai);
kiem("TC-17", "timestamp dang ISO 8601", /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$/.test(dongCsv[0].timestamp), dongCsv[0].timestamp);

// ---------------------------------------------------------------- TC-13
r = chay("Lenh mo khan cap", {}).ra;
kiem("TC-13", "Mo khan cap -> unlock ttl 5 khong qua kiem ma",
    r[0].payload.action === "unlock" && r[0].payload.ttl === 5);
kiem("TC-13", "Mo khan cap -> log 'MO TU DASHBOARD'", r[1].payload.ket_qua === "MO TU DASHBOARD");

// ---------------------------------------------------------------- TC-15
kiemMa(MA_SAI); kiemMa(MA_SAI); r = kiemMa(MA_SAI);
kiem("TC-15", "(chuan bi) gay lockout lan nua", r[0].payload.action === "lockout");
r = chay("Xoa lockout hai noi", {}).ra;
kiem("TC-15", "Reset -> gui lockout sec 0 xuong ESP32",
    r[0].payload.action === "lockout" && r[0].payload.sec === 0);
kiem("TC-15", "Reset -> Node-RED xoa co lockout va bo dem",
    flowCtx.lockout_den_khi === 0 && flowCtx.so_lan_sai === 0);
r = kiemMa(MA_DUNG);
kiem("TC-15", "Ngay sau reset, ma dung mo duoc (khong phai doi 30 giay)", r[0] && r[0].payload.action === "unlock");

// ---------------------------------------------------------------- TC-16
flowCtx.lich_su = [];
let bang;
for (let i = 1; i <= 12; i++) {
    bang = chay("Giu 10 ban ghi gan nhat", { payload: { ma: "LAN" + i } }).ra.payload;
}
kiem("TC-16", "Bang lich su giu toi da 10 dong", bang.length === 10, "co " + bang.length);
kiem("TC-16", "Dong moi nhat nam tren cung", bang[0].ma === "LAN12" && bang[9].ma === "LAN3");
const bd = chay("Dem thanh cong / that bai", {}).daGui;
const tc = bd.find((m) => m.topic === "Thanh cong").payload;
const tb = bd.find((m) => m.topic === "That bai").payload;
kiem("TC-16", "Bieu do dem dung so lan thanh cong / that bai", tc === 3 && tb === 6, `thanh cong ${tc}, that bai ${tb}`);

// ---------------------------------------------------------------- them: dau vao la
r = kiemMa(MA_DUNG.toLowerCase());
kiem("THEM", "Ma viet thuong van duoc chap nhan", r[0] && r[0].payload.action === "unlock");
r = kiemMa("");
kiem("THEM", "Ban tin rong -> tinh la sai, khong mo", r[0] && r[0].payload.action === "deny");

// ---------------------------------------------------------------- tong ket
console.log(`\nTONG: ${dat} dat, ${khong} khong dat`);
if (process.argv.includes("--json")) {
    fs.writeFileSync(process.argv[process.argv.indexOf("--json") + 1],
        JSON.stringify({ dat, khong, ketQua }, null, 2));
}
process.exit(khong ? 1 : 0);
