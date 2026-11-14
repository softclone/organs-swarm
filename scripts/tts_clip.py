# tts_clip.py -- Tier-2 standard distilling the _clip* local-voice family (21 one-off copies).
# FAMILY: text -> audio.cpp Kokoro CPU render -> wav -> magic-byte player dispatch, per-clip
#   hand-built wrappers naming a PRUNED scratch path for exe+model (the lane's first pitfall:
#   scratch dies on a ~24h idle clock). Cured at the organ: kit resolves under HOME/tts/
#   (config chain), zero estate literals in code.
# PROVEN at packaging (live fire, CPU backend): render --text-file <text> --out <scratch wav>
#   with the kit under HOME/tts/ RENDERED a 296,444-byte wav (measured; RIFF/WAVE magic
#   verified); refusals print REFUSE rc2 named and BARE-rc-proven (verbless, missing --out,
#   absent text file, kit exe absent). Play dispatch is proven via --dry in suite leg
#   tts-clip-gates; the live player legs (SoundPlayer PlaySync / WPF MediaPlayer) are NOT
#   fired in-suite (no audio, no PowerShell).
# Lane laws carried IN CODE (from the local-voice practice):
#   - CPU backend always (GPU belongs to the inference engine).
#   - NO --speed flag, NO --text-file passthrough to the TTS CLI (unknown-option deaths);
#     our own --text-file arg is shop-side: the organ reads the file, passes --text as one arg.
#   - render verifies wav exists AND size >= 1000 bytes; a 44-byte header file = SILENT-FAIL
#     rc3 named, never played. play gates the same size floor (silent never reaches a player).
#   - player chosen by MAGIC BYTES, never the extension: RIFF....WAVE -> Media.SoundPlayer
#     PlaySync; \xff\xf3 / \xff\xfb (MP3 wearing a .wav name) -> WPF MediaPlayer via generated
#     .ps1; unknown magic -> PLAY-NAMED rc3 (extension lies; magic rules).
#   - PowerShell ONLY on the playback leg, from a generated .ps1 FILE (never inline -Command,
#     never wrapping render); clip stamps report MEASURED bytes (stamp follows the print).
# Verbs:
#   render --text-file PATH --out PATH [--voice af_heart] [--dry]
#   play   --file PATH [--dry]
#   --dry: render plans with chars counted in-call, ZERO exe calls; play names the magic-byte
#     route, ZERO player calls, zero writes. no verb / bad arg shape: REFUSE rc2 BEFORE any exe.
# CURES over the proven skeleton (named; fired in suite leg tts-clip-gates):
#   play --dry cure: the skeleton had no dry play -- dispatch could only be proven by firing
#     real players; --dry now names the route from magic with zero invocations, zero writes.
#   magic-check cure: the skeleton's MP3 branch double-tested magic[0] in two nested ifs;
#     one clean test (0xFF then 0xF3/0xFB) -- same dispatch, no dead span.
#   silent-play gate cure: play refuses sub-1000-byte files SILENT-FAIL rc3 -- a silent header
#     never reaches a player even if render was bypassed (the skeleton played any magic match).
#   ps1-file cure: BOTH player routes run from a generated .ps1 FILE (the skeleton's PCM route
#     used inline -Command; the lane's $-interpolation law says file, never inline).
#   abs-path cure: the player gets the absolute path with single quotes doubled (relative
#     shell paths do not resolve for the native player; the skeleton passed f verbatim).
#   empty-text cure: an empty text file REFUSES rc2 named (the skeleton passed --text "" to
#     the CLI, an unnamed silence/death).
#   render-dead naming cure: TimeoutExpired / FileNotFoundError at the exe fire land as named
#     RENDER-DEAD rc3 (the skeleton let them escape as tracebacks).
#   dispatch-wrap cure: any exception escaping main() prints REFUSE: <Class>: <msg> rc5 --
#     a traceback never escapes the organ (loud-named law).
# DATUMS (deploy lessons kept as prose -- zero estate literals in code):
#   (1) kit locality: exe+model live under HOME/tts/ as a family (CLI, model gguf, espeak
#       pack, assets); a lane whose binaries sit in a pruned dir is weather, not infrastructure.
#   (2) the MP3 route's WPF window is a fixed 30 s hold (skeleton shape): clips longer than
#       the hold may truncate -- the PCM route's PlaySync blocks to end, no such bound.
#   (3) commit-saturation kills the Kokoro CPU lane (ggml wants a ~525 MB contiguous private
#       commit); RENDER-DEAD names the exe's own stderr tail -- pivot to a provider TTS route,
#       re-wrap to pcm_s16le wav, verify RIFF/WAVE magic, play through the PCM route.
# Config chain (portable, zero estate literals, zero secret values):
#   HOME = ORGANS_HOME env > local.json beside > ~/organs.json > ~/shop default
#   kit = HOME/tts/ ; exe = ORGANS_TTS_EXE env > kit/audiocpp_cli.exe
#   model = kit/(ORGANS_TTS_MODEL env > tts_model config > kokoro-82m-q8_0.gguf)
#   voice = --voice arg > af_heart default
import json, os, subprocess, sys

def _cfg_dir(): return os.path.dirname(os.path.abspath(__file__))
def _key(k, dflt=None):
    for p in (os.path.join(_cfg_dir(), "local.json"), os.path.expanduser("~/organs.json")):
        if os.path.exists(p):
            try:
                v = json.load(open(p, encoding="utf-8")).get(k)
                if v: return v
            except Exception: continue
    return dflt
def _home(): return os.environ.get("ORGANS_HOME") or _key("home", os.path.expanduser("~/shop"))

HOME = _home()
KIT = os.path.join(HOME, "tts")
EXE = os.environ.get("ORGANS_TTS_EXE") or os.path.join(KIT, "audiocpp_cli.exe")
MODEL = os.path.join(KIT, os.environ.get("ORGANS_TTS_MODEL") or _key("tts_model", "kokoro-82m-q8_0.gguf"))

def refuse(msg):
    print("REFUSE: " + msg + " (rc2)"); sys.exit(2)

def render(argv):
    tf = out = voice = None
    dry = "--dry" in argv
    for i, a in enumerate(argv):
        if a == "--text-file": tf = argv[i+1] if i+1 < len(argv) else None
        elif a == "--out": out = argv[i+1] if i+1 < len(argv) else None
        elif a == "--voice": voice = argv[i+1] if i+1 < len(argv) else None
    if not tf: refuse("render needs --text-file PATH")
    if not out: refuse("render needs --out PATH (missing --out means playback fires FileNotFoundException)")
    if not os.path.exists(tf): refuse("text file absent: " + tf)
    if not os.path.exists(EXE): refuse("kit exe absent: " + EXE + " (lane binaries must live in HOME/tts/, pruned scratch is weather not infrastructure)")
    if not os.path.exists(MODEL): refuse("model absent: " + MODEL)
    text = open(tf, encoding="utf-8").read().strip()
    if not text: refuse("text file empty: " + tf)
    if dry:
        print("[dry] render chars=%d out=%s voice=%s ZERO render calls" % (len(text), out, voice or "af_heart"))
        return 0
    cmd = [EXE, "--task", "tts", "--family", "kokoro_tts", "--model", MODEL,
           "--backend", "cpu", "--language", "en", "--voice-id", voice or "af_heart",
           "--text", text, "--out", out]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    except subprocess.TimeoutExpired:
        print("RENDER-DEAD timeout=900s: exe never returned"); return 3
    except FileNotFoundError:
        print("RENDER-DEAD: exe vanished before fire: " + EXE); return 3
    if r.returncode != 0:
        print("RENDER-DEAD rc=%d: %s" % (r.returncode, (r.stderr or r.stdout)[-300:])); return 3
    if not os.path.exists(out):
        print("RENDER-NAMED: exe rc0 but no wav landed at " + out); return 3
    size = os.path.getsize(out)
    if size < 1000:
        print("SILENT-FAIL: wav %d bytes (44-byte header class) -- never played" % size); return 3
    print("rendered: %s bytes=%d (measured, stamp-ready)" % (out, size))
    return 0

def play(argv):
    f = None
    dry = "--dry" in argv
    for i, a in enumerate(argv):
        if a == "--file": f = argv[i+1] if i+1 < len(argv) else None
    if not f: refuse("play needs --file PATH")
    if not os.path.exists(f): refuse("file absent: " + f)
    magic = open(f, "rb").read(12)
    size = os.path.getsize(f)
    # magic-byte dispatch: the extension lies; magic rules.
    if magic[:4] == b"RIFF" and magic[8:12] == b"WAVE":
        route = "PCM"
    elif len(magic) >= 2 and magic[0] == 0xFF and magic[1] in (0xF3, 0xFB):
        route = "MP3"
    else:
        print("PLAY-NAMED: unrecognized magic %s -- no player route (extension lies; magic rules)"
              % magic.hex()); return 3
    # silent-play gate cure: a silent header never reaches a player, even if render was bypassed.
    if size < 1000:
        print("SILENT-FAIL: %s %d bytes (44-byte header class) -- never played" % (route, size)); return 3
    if dry:
        print("[dry] play route=%s file=%s bytes=%d ZERO player calls" % (route, f, size))
        return 0
    # live playback: PowerShell ONLY on this leg, from a generated .ps1 FILE ($-interpolation
    # law: never inline -Command). abs-path cure: native players need the absolute Windows
    # path; single quotes doubled for the PowerShell string literal.
    clip = os.path.abspath(f).replace("'", "''")
    script = os.path.join(os.path.dirname(os.path.abspath(f)), "tts-clip-play.ps1")
    if route == "PCM":
        body = ("Add-Type -AssemblyName System.Windows.Forms; "
                "$p=New-Object Media.SoundPlayer '%s'; $p.PlaySync()\n" % clip)
    else:
        body = ("Add-Type -AssemblyName PresentationCore; $p=New-Object System.Windows.Media.MediaPlayer; "
                "[void]$p.Open([Uri]'%s'); Start-Sleep 2; $p.Play(); Start-Sleep 30; $p.Close()\n" % clip)
    open(script, "w", encoding="utf-8").write(body)
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-STA",
                        "-WindowStyle", "Hidden", "-File", script], timeout=1800)
    print("play %s rc=%d" % ("PCM" if route == "PCM" else "MP3-magic", r.returncode))
    return r.returncode

def main(argv):
    if not argv: refuse("verb render|play required")
    verb, rest = argv[0], argv[1:]
    if verb == "render": return render(rest)
    if verb == "play": return play(rest)
    refuse("unknown verb: " + verb)

if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as e:
        # dispatch-wrap cure: a traceback never escapes the organ
        print("REFUSE: %s: %s (rc5)" % (type(e).__name__, str(e)[:200]))
        sys.exit(5)
