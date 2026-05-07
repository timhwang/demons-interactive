// Demons / Бесы — browser bootloader.
// Loads Pyodide, mounts demons.py, pipes stdout/stdin through xterm.js.

const loading = document.getElementById("loading");
const progressEl = document.getElementById("loading-progress");

function setProgress(msg) {
  if (progressEl) progressEl.textContent = msg;
}

const TERM_FONT = '"JetBrains Mono", "Menlo", "Monaco", "Courier New", monospace';

// The widest line of demons.py's ASCII art (chapter 1's carriage scene) is
// 83 chars. Chapter borders and the chapel diagram sit around 70-75. We size
// the font so at least MIN_COLS chars fit at the current viewport width;
// this lets the same source render cleanly from a wide desktop down to a
// phone in landscape.
const MIN_COLS = 85;
const MIN_FONT = 10;
const MAX_FONT = 18;

const term = new Terminal({
  convertEol: true,
  cursorBlink: true,
  fontFamily: TERM_FONT,
  fontSize: 14,
  lineHeight: 1.0,
  letterSpacing: 0,
  theme: {
    background: "#0c0c0c",
    foreground: "#d4d4d4",
    cursor: "#d4d4d4",
    red: "#c4302b",
    green: "#3aa655",
    yellow: "#d7a13e",
    cyan: "#3a8aa6",
    magenta: "#a64bb0",
    white: "#d4d4d4",
  },
});
const fitAddon = new FitAddon.FitAddon();
term.loadAddon(fitAddon);

function safeFit() {
  try {
    const proposed = fitAddon.proposeDimensions();
    if (proposed && proposed.cols > 0 && proposed.rows > 0) {
      fitAddon.fit();
    }
  } catch (e) {
    /* container not yet sized */
  }
}

// Pick a fontSize so at least MIN_COLS chars fit in the current container,
// then refit. This is iterative because xterm's actual char width depends on
// the rendered font (varies slightly across browsers/zoom levels), so we let
// proposeDimensions tell us the truth and step the size to match.
function applyResponsiveFont() {
  const container = document.getElementById("term");
  if (!container || container.clientWidth <= 0) return;

  // Start at MAX_FONT and step down until proposeDimensions reports >= MIN_COLS,
  // or we hit MIN_FONT (then accept whatever cols we get; mobile fallback).
  let size = MAX_FONT;
  for (; size >= MIN_FONT; size--) {
    if (term.options.fontSize !== size) {
      term.options.fontSize = size;
    }
    let proposed;
    try { proposed = fitAddon.proposeDimensions(); } catch (e) { proposed = null; }
    if (proposed && proposed.cols >= MIN_COLS) break;
  }
  if (size < MIN_FONT) size = MIN_FONT;
  if (term.options.fontSize !== size) term.options.fontSize = size;
  safeFit();
}

// xterm measures char-cell width once, on Terminal.open(). If JetBrains Mono
// hasn't finished downloading at that moment, xterm picks Menlo's narrower
// glyph widths and computes more cols than actually fit — so when the title
// art renders with JetBrains Mono's wider glyphs, lines wrap.
// Wait for the webfont to load BEFORE opening the terminal; then refit after.
async function openTerminal() {
  if (document.fonts && document.fonts.load) {
    try {
      await document.fonts.load('14px "JetBrains Mono"');
      await document.fonts.ready;
    } catch (e) { /* fall back silently */ }
  }
  term.open(document.getElementById("term"));
  await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
  applyResponsiveFont();
}

// Debounce resize events so we don't refit on every pixel during a window drag.
let resizeTimer = null;
function scheduleResponsiveFit() {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(applyResponsiveFont, 100);
}
window.addEventListener("resize", scheduleResponsiveFit);
if (typeof ResizeObserver !== "undefined") {
  new ResizeObserver(scheduleResponsiveFit).observe(document.getElementById("term"));
}

// ─── Async input bridge ──────────────────────────────────────
let resolveLine = null;
let lineBuffer = "";

term.onData((data) => {
  // No active prompt? Drop input.
  if (!resolveLine) return;
  for (const ch of data) {
    if (ch === "\r" || ch === "\n") {
      term.write("\r\n");
      const out = lineBuffer;
      lineBuffer = "";
      const r = resolveLine;
      resolveLine = null;
      r(out);
      return;
    } else if (ch === "\x7f" || ch === "\b") {
      if (lineBuffer.length > 0) {
        lineBuffer = lineBuffer.slice(0, -1);
        term.write("\b \b");
      }
    } else if (ch === "\x03") {
      // Ctrl-C: clear current line
      term.write("^C\r\n");
      lineBuffer = "";
    } else if (ch >= " ") {
      lineBuffer += ch;
      term.write(ch);
    }
  }
});

window.demonsGetLine = function () {
  return new Promise((resolve) => {
    resolveLine = resolve;
  });
};

// ─── Boot Pyodide ────────────────────────────────────────────
async function boot() {
  await openTerminal();
  setProgress("Downloading Pyodide runtime…");
  const pyodide = await loadPyodide({
    indexURL: "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/",
    stdout: (s) => term.write(s + "\r\n"),
    stderr: (s) => term.write(s + "\r\n"),
  });

  // Stream stdout char-by-char (without forced newline) so slow_print's
  // sys.stdout.write/flush per character renders smoothly.
  pyodide.setStdout({
    batched: (s) => term.write(s.replace(/\n/g, "\r\n")),
  });
  pyodide.setStderr({
    batched: (s) => term.write(s.replace(/\n/g, "\r\n")),
  });

  setProgress("Fetching the provincial chronicle…");
  const code = await fetch("./demons.py").then((r) => {
    if (!r.ok) throw new Error("could not fetch demons.py: " + r.status);
    return r.text();
  });
  pyodide.FS.writeFile("/home/pyodide/demons.py", code);

  setProgress("Patching for the browser…");
  await pyodide.runPythonAsync(`
import sys, json, asyncio

# Stub modules that don't exist in WASM CPython.
class _NoOp:
    def __getattr__(self, k):
        return lambda *a, **kw: None
    error = type("error", (Exception,), {})
    TCIFLUSH = 0
    TCSADRAIN = 0

if 'termios' not in sys.modules:
    sys.modules['termios'] = _NoOp()
if 'tty' not in sys.modules:
    sys.modules['tty'] = _NoOp()

# Make the cwd the directory containing demons.py.
sys.path.insert(0, '/home/pyodide')

import demons
from js import localStorage, demonsGetLine

# ─── Save backend → localStorage ───
SAVE_KEY = 'demons_save_v1'

def _load_save_file():
    raw = localStorage.getItem(SAVE_KEY)
    if not raw:
        return {"auto": None, "slot_1": None, "slot_2": None, "slot_3": None}
    try:
        data = json.loads(raw)
        if "chapter_index" in data and "auto" not in data:
            return {"auto": data, "slot_1": None, "slot_2": None, "slot_3": None}
        return data
    except Exception:
        return {"auto": None, "slot_1": None, "slot_2": None, "slot_3": None}

def _write_save_file(data):
    try:
        localStorage.setItem(SAVE_KEY, json.dumps(data))
    except Exception:
        pass

demons._load_save_file = _load_save_file
demons._write_save_file = _write_save_file

# ─── Async input bridge ───
async def web_ainput(prompt=""):
    if prompt:
        sys.stdout.write(prompt)
        sys.stdout.flush()
    line = await demonsGetLine()
    return str(line)

demons.ainput = web_ainput

# ─── Skip non-TTY branches ───
# slow_print/dramatic_pause check _is_interactive() and degrade gracefully
# to time-based pacing when stdin isn't a TTY. In the browser we want
# that degraded path (no select.select on raw stdin), so leave _is_interactive
# as-is — sys.stdin.isatty() returns False under Pyodide, which is what
# we want.
`);

  setProgress("Curtain up.");
  loading.classList.add("hidden");
  setTimeout(() => loading.remove(), 500);

  // Final responsive fit once the loading overlay is on its way out — gives
  // the terminal a definitive size for slow_print's line wrapping.
  await new Promise((r) => setTimeout(r, 50));
  applyResponsiveFont();
  term.focus();

  try {
    await pyodide.runPythonAsync("await demons.main()");
  } catch (err) {
    term.write("\r\n\x1b[31mFatal: " + String(err) + "\x1b[0m\r\n");
    console.error(err);
  }
}

boot().catch((err) => {
  setProgress("Failed to load: " + err.message);
  console.error(err);
});
