from __future__ import annotations
import os, sys, time, subprocess, asyncio
from typing import List, Tuple, Dict, TypedDict, Optional
from datetime import datetime
import google.generativeai as genai
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END

PER_RUN_SSID_LIMIT = 50
MAX_REQUESTS_PER_RUN = 1
COOLDOWN_SEC = 0.2
DEBUG_SCAN = True
DISCONNECT_FOR_SCAN = False
ENABLE_TTS_PLAYBACK = True
TTS_WAV_PATH = "rap.wav"
TTS_MP3_PATH = "rap.mp3"
ENABLE_TG_TEXT = True

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("❌ Missing GEMINI_API_KEY in .env"); sys.exit(1)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
if ENABLE_TG_TEXT and (not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID):
    print("❌ Telegram is enabled but TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing in .env")
    print("   Disable ENABLE_TG_TEXT or add the creds."); sys.exit(1)

bot = None
if ENABLE_TG_TEXT:
    from telegram import Bot
    bot = Bot(token=TELEGRAM_BOT_TOKEN)

genai.configure(api_key=GEMINI_API_KEY)
MODEL_NAME = "models/gemini-1.5-flash"
model = genai.GenerativeModel(MODEL_NAME)

class State(TypedDict):
    phase: str
    ssids: List[Tuple[str, int]]
    prompt: str
    song: str
    used_requests: int
    errors: List[str]
    message: str

def phase(state: State, msg: str):
    state["phase"] = msg
    print(msg, flush=True)

def _run(cmd: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)

def _detect_wifi_iface() -> Optional[str]:
    out = _run(["iw", "dev"]).stdout
    iface = None
    cur = None
    typ = None
    for line in out.splitlines():
        s = line.strip()
        if s.startswith("Interface "):
            cur = s.split()[1]
            typ = None
        elif s.startswith("type "):
            typ = s.split()[1]
            if cur and typ == "managed":
                iface = cur
                break
    if DEBUG_SCAN:
        print(f"[scan] detected iface: {iface or 'None'}", flush=True)
    return iface

def _nmcli_connected_iface() -> Optional[str]:
    out = _run(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device"]).stdout
    for line in out.splitlines():
        parts = line.split(":")
        if len(parts) >= 3 and parts[1] == "wifi" and parts[2] == "connected":
            return parts[0]
    return None

def _nmcli_current_connection(iface: str) -> Optional[str]:
    out = _run(["nmcli", "-t", "-f", "NAME,DEVICE,TYPE,STATE", "connection", "show", "--active"]).stdout
    for line in out.splitlines():
        parts = line.split(":")
        if len(parts) >= 4 and parts[1] == iface and parts[2] == "802-11-wireless":
            return parts[0]
    return None

def _nmcli_disconnect(iface: str):
    _run(["sudo", "nmcli", "device", "disconnect", iface])

def _nmcli_reconnect(conn_name: str):
    _run(["sudo", "nmcli", "connection", "up", conn_name])

def _bars(p: int) -> str:
    if p >= 90: return "█"
    if p >= 65: return "▅"
    if p >= 35: return "▃"
    if p >= 10: return "▁"
    return "·"

def _tier(p: int) -> str:
    if p >= 70: return "near"
    if p >= 40: return "mid"
    return "far"

def _format_ssid_header(ssids: List[Tuple[str,int]]) -> str:
    parts = []
    for s, p in ssids:
        parts.append(f"{s} [{_bars(p)} {p}% { _tier(p)}]")
    return ", ".join(parts)

def _nmcli_scan() -> Dict[str, int]:
    ssids: Dict[str, int] = {}
    _run(["sudo", "nmcli", "dev", "wifi", "rescan"])
    res = _run(["nmcli", "-t", "-f", "SSID,SIGNAL", "dev", "wifi"])
    for raw in res.stdout.splitlines():
        if not raw.strip():
            continue
        parts = raw.split(":")
        ssid = (parts[0] or "").strip()
        if not ssid:
            continue
        sig = 0
        if len(parts) > 1:
            try: sig = int(parts[1] or "0")
            except: sig = 0
        ssids[ssid] = max(sig, ssids.get(ssid, 0))
    if DEBUG_SCAN:
        print(f"[scan] nmcli found: {len(ssids)}", flush=True)
    return ssids

def _iw_scan(iface: str) -> Dict[str, int]:
    ssids: Dict[str, int] = {}
    res = _run(["sudo", "iw", "dev", iface, "scan"])
    cur = None
    for line in res.stdout.splitlines():
        ln = line.strip()
        if ln.startswith("SSID:"):
            name = ln.split("SSID:", 1)[1].strip()
            cur = name if name else None
            if cur and cur not in ssids:
                ssids[cur] = 0
        elif ln.startswith("signal:") and cur:
            try:
                dbm = float(ln.split("signal:",1)[1].split("dBm")[0])
                score = int(max(0, min(100, (dbm + 90) * (100/60))))
                ssids[cur] = max(score, ssids.get(cur, 0))
            except:
                pass
    if DEBUG_SCAN:
        print(f"[scan] iw found: {len(ssids)}", flush=True)
    return ssids

def _which(cmd: str) -> bool:
    return subprocess.run(["bash", "-lc", f"command -v {cmd} >/dev/null 2>&1"]).returncode == 0

def tts_make_audio(lyrics: str) -> str | None:
    try:
        if not _which("espeak"):
            print("⚠️ espeak not installed; skipping TTS.", flush=True)
            return None
        subprocess.run(["espeak", lyrics, "-w", TTS_WAV_PATH], check=False)
        if _which("ffmpeg"):
            subprocess.run([
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-i", TTS_WAV_PATH, "-codec:a", "libmp3lame", "-q:a", "4", TTS_MP3_PATH
            ], check=False)
            if os.path.exists(TTS_MP3_PATH) and os.path.getsize(TTS_MP3_PATH) > 0:
                return TTS_MP3_PATH
        if os.path.exists(TTS_WAV_PATH) and os.path.getsize(TTS_WAV_PATH) > 0:
            return TTS_WAV_PATH
    except Exception as e:
        print(f"❌ TTS error: {e}", flush=True)
    return None

def tts_play_local(filepath: str):
    try:
        if _which("ffplay"):
            subprocess.run(["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", filepath], check=False)
        elif filepath.lower().endswith(".wav") and _which("aplay"):
            subprocess.run(["aplay", filepath], check=False)
        else:
            print("ℹ️ No local player (ffplay/aplay) found — skipping playback.", flush=True)
    except Exception as e:
        print(f"❌ Local playback error: {e}", flush=True)

def _chunk_telegram(text: str, limit: int = 4000) -> List[str]:
    lines = text.splitlines(keepends=True)
    out, cur = [], ""
    for ln in lines:
        if len(cur) + len(ln) > limit:
            out.append(cur); cur = ""
        cur += ln
    if cur: out.append(cur)
    return out

async def _send_telegram_async(text: str):
    if not (ENABLE_TG_TEXT and bot):
        return
    for part in _chunk_telegram(text):
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=part)
        await asyncio.sleep(0.2)

def send_telegram(text: str):
    if not (ENABLE_TG_TEXT and bot):
        return
    try:
        asyncio.run(_send_telegram_async(text))
    except Exception as e:
        print(f"❌ Telegram send error: {e}", flush=True)

def scan_node(state: State) -> State:
    phase(state, "📡 Scanning SSIDs...")
    iface = _detect_wifi_iface() or _nmcli_connected_iface() or "wlan0"
    if DISCONNECT_FOR_SCAN and iface:
        conn = _nmcli_current_connection(iface)
        if conn:
            if DEBUG_SCAN: print(f"[scan] disconnecting {iface} (conn={conn}) for wide scan...", flush=True)
            _nmcli_disconnect(iface)
            time.sleep(1.0)
    seen: Dict[str, int] = {}
    nm = _nmcli_scan()
    for k, v in nm.items():
        seen[k] = max(v, seen.get(k, 0))
    if iface:
        iw = _iw_scan(iface)
        for k, v in iw.items():
            seen[k] = max(v, seen.get(k, 0))
    if DISCONNECT_FOR_SCAN and iface:
        conn = _nmcli_current_connection(iface)
        if not conn:
            if DEBUG_SCAN: print(f"[scan] attempting reconnect on {iface} (best-effort)", flush=True)
            _run(["sudo", "nmcli", "device", "connect", iface])
    ranked = sorted(seen.items(), key=lambda x: x[1], reverse=True)
    state["ssids"] = ranked[:PER_RUN_SSID_LIMIT]
    if DEBUG_SCAN:
        print(f"[scan] interface={iface} total_unique={len(seen)} using_top={len(state['ssids'])}", flush=True)
    print(f"✅ Found {len(state['ssids'])} networks.", flush=True)
    time.sleep(COOLDOWN_SEC)
    return state

def build_prompt_node(state: State) -> State:
    phase(state, "🧩 Building diss-track prompt...")
    names = [s for s, _ in state.get("ssids", [])]
    if not names:
        state["prompt"] = (
            "Write a short, playful diss-track style verse (10–12 lines) about scanning for Wi-Fi "
            "and finding none. Clean, witty, no profanity. Plain text only."
        )
        return state
    joined = ", ".join(names)
    state["prompt"] = (
        "You are a clever battle-rapper. Write ONE playful, clean diss-track style verse "
        "(10–14 short lines) that name-drops these Wi-Fi network names. Your tone: confident, "
        "witty, a little savage but never profane or mean-spirited.\n\n"
        f"Names to weave in naturally: {joined}\n\n"
        "Rules:\n"
        "- Keep it clean (no profanity), punchy, and rhythmic.\n"
        "- Do NOT use bullet points; return one verse as plain text.\n"
        "- Lines should be short; clever multis and internal rhymes encouraged.\n"
        "- Name-drop as many given names as feels natural; don't invent new ones.\n"
        "- End with a fun mic-drop closer."
    )
    time.sleep(COOLDOWN_SEC)
    return state

def generate_node(state: State) -> State:
    phase(state, "🎛️ Processing with Gemini (composing verse)...")
    if state.get("used_requests", 0) >= MAX_REQUESTS_PER_RUN:
        state["song"] = "🚫 Request cap reached for this run."
        return state
    try:
        resp = model.generate_content(state["prompt"])
        text = (resp.text or "").strip()
        state["song"] = text if text else "(No lyrics returned.)"
        state["used_requests"] = state.get("used_requests", 0) + 1
        print("🎶 Verse composed.", flush=True)
    except Exception as e:
        state["song"] = f"❌ API error: {e}"
        state["errors"].append(f"gemini_error:{e}")
    time.sleep(COOLDOWN_SEC)
    return state

def send_node(state: State) -> State:
    phase(state, "📤 Preparing final message...")
    names = state.get("ssids", [])
    header = " Wi-Fi Rap Star — Diss Track Drop 🔥\n"
    ssid_line = "\nSSIDs:\n" + _format_ssid_header(names) + "\n" if names else ""
    body = state.get("song", "")
    footer = ""
    if state.get("errors"):
        footer = "\n\n— debug —\n" + "\n".join(state["errors"])
    msg = header + ssid_line + "\n" + body + footer
    state["message"] = msg
    if ENABLE_TG_TEXT:
        send_telegram(msg)
    time.sleep(COOLDOWN_SEC)
    return state

def display_node(state: State) -> State:
    phase(state, "📜 Compiling final output & saving...")
    print("\n" + state.get("message", ""), flush=True)
    try:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        with open(f"wifi_rap_output_{ts}.txt", "w", encoding="utf-8") as f:
            f.write(state.get("message", ""))
        print(f"💾 Saved to wifi_rap_output_{ts}.txt", flush=True)
    except Exception as e:
        print(f"❌ Save error: {e}", flush=True)
    try:
        lyrics = state.get("song", "")
        if lyrics and ENABLE_TTS_PLAYBACK:
            print("🎤 Generating audio...", flush=True)
            audio_file = tts_make_audio(lyrics)
            if audio_file:
                print("🔊 Playing on the Pi...", flush=True)
                tts_play_local(audio_file)
            else:
                print(" No audio file created; skipping TTS.", flush=True)
    except Exception as e:
        print(f" TTS/Audio pipeline error: {e}", flush=True)
    phase(state, " Done.")
    return state

def build_graph():
    g = StateGraph(State)
    g.add_node("scan", scan_node)
    g.add_node("prompt", build_prompt_node)
    g.add_node("generate", generate_node)
    g.add_node("send", send_node)
    g.add_node("display", display_node)
    g.set_entry_point("scan")
    g.add_edge("scan", "prompt")
    g.add_edge("prompt", "generate")
    g.add_edge("generate", "send")
    g.add_edge("send", "display")
    g.add_edge("display", END)
    return g.compile()

if __name__ == "__main__":
    graph = build_graph()
    init: State = {
        "phase": "init",
        "ssids": [],
        "prompt": "",
        "song": "",
        "used_requests": 0,
        "errors": [],
        "message": "",
    }
    final_state = graph.invoke(init)
