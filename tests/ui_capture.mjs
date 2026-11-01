// Steuert ein echtes Chrome über das DevTools-Protokoll (ohne Zusatzpakete),
// bedient die Echo-Agent-Oberfläche wie ein Mensch und zeichnet alles auf.
// Aufruf: node ui_capture.mjs <agent-url> <ausgabe-ordner>
import { spawn } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";

const URL_ = process.argv[2] || "http://127.0.0.1:18091/";
const OUT = process.argv[3] || "out/ui";
mkdirSync(`${OUT}/frames`, { recursive: true });

const chrome = spawn("google-chrome", ["--headless=new", "--no-sandbox", "--disable-gpu",
  "--remote-debugging-port=9333", "--window-size=1280,900", "--hide-scrollbars", "about:blank"],
  { stdio: "ignore" });
const sleep = ms => new Promise(r => setTimeout(r, ms));

let ws, id = 0;
const pending = new Map();
let frameNo = 0;
async function connect() {
  for (let i = 0; i < 50; i++) {
    try {
      const list = await (await fetch("http://127.0.0.1:9333/json/list")).json();
      const page = list.find(t => t.type === "page");
      if (page) { ws = new WebSocket(page.webSocketDebuggerUrl); break; }
    } catch { }
    await sleep(200);
  }
  await new Promise(r => ws.addEventListener("open", r));
  ws.addEventListener("message", ev => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) { pending.get(m.id)(m.result || m.error); pending.delete(m.id); }
    if (m.method === "Page.screencastFrame") {
      writeFileSync(`${OUT}/frames/f${String(frameNo++).padStart(5, "0")}.jpg`,
        Buffer.from(m.params.data, "base64"));
      send("Page.screencastFrameAck", { sessionId: m.params.sessionId });
    }
  });
}
function send(method, params = {}) {
  return new Promise(r => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
}
const js = expr => send("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true });
async function shot(name, full = false) {
  const r = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: full });
  writeFileSync(`${OUT}/${name}.png`, Buffer.from(r.data, "base64"));
  console.log("Screenshot:", name);
}
async function typeAndSend(text) {
  await js(`document.querySelector('#q').focus()`);
  for (const ch of text) { await send("Input.insertText", { text: ch }); await sleep(35); }
  await sleep(300);
  await js(`document.querySelector('#f').requestSubmit()`);
}
async function waitReplies(n, timeout = 20000) {
  const end = Date.now() + timeout;
  while (Date.now() < end) {
    const r = await js(`document.querySelectorAll('#log .ai').length`);
    if (r.result.value >= n) return;
    await sleep(200);
  }
}

await connect();
await send("Page.enable");
await send("Runtime.enable");
await send("Emulation.setDeviceMetricsOverride", { width: 1280, height: 900, deviceScaleFactor: 1, mobile: false });
await send("Page.startScreencast", { format: "jpeg", quality: 85, everyNthFrame: 1 });

// 1) Ohne Code: Anmeldedialog
await send("Page.navigate", { url: URL_ });
await sleep(2500);
await shot("01_anmeldung");
// 2) Code eingeben
await js(`document.querySelector('#code').focus()`);
for (const ch of "testcode") { await send("Input.insertText", { text: ch }); await sleep(60); }
await sleep(400);
await js(`document.querySelector('#lf').requestSubmit()`);
await sleep(2500);
await shot("02_uebersicht");
// 3) Chat: Serie abspielen
await typeAndSend("Spiel die nächste Folge von Dark");
await waitReplies(2);
await sleep(1500);
await js(`refresh()`); await sleep(1500);
await shot("03_chat_dark");
// 4) Chat: Updates
await typeAndSend("Gibt es Updates?");
await waitReplies(3);
await sleep(1500);
await shot("04_chat_updates");
// 5) Sicherheits-Button
await js(`document.querySelector('[data-a=security]').click()`);
await waitReplies(4); await sleep(1500);
await shot("05_sicherheit");
// 6) Streaming-Kachel
await js(`document.querySelector('[data-s=netflix]').click()`);
await waitReplies(5); await sleep(1500);
await shot("06_streaming", true);
await send("Page.stopScreencast");
// 7) Handy-Ansicht
await send("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 2, mobile: true });
await sleep(1500);
await shot("07_handy");

ws.close();
chrome.kill();
console.log("Frames:", frameNo);
process.exit(0);
