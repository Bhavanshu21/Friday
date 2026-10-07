# FRIDAY — offline AI assistant for Kali Linux

A personal command assistant that maps what you type to a **fixed allowlist**
of pre-approved system commands. Nothing else can execute. Ever.

## Layout

```
Friday/
├── friday.py          # entry point: loop, intent matching, dispatch, help
├── common.py          # safe subprocess runner, logging, user detection
├── loader.py          # auto-discovers commands/*.py at startup
├── context.py         # short-term memory: last runs, for "again"/recall
├── commands/
│   ├── system.py      # status, disk, memory, uptime, kernel, date, whoami,
│   │                  # reboot, tail <log>, service <name> <action>
│   ├── network.py     # ip, internet, ports, processes, wifi,
│   │                  # ping <host>, traceroute <host>, lookup <domain>
│   ├── nmap.py        # 14 scan profiles: quick, standard, full, os, udp,
│   │                  # vuln, sweep, syn, connect, aggressive, version,
│   │                  # ports, script, list — all with validated targets
│   ├── metasploit.py  # msf version, msf search <term>, msf info <module>
│   ├── burp.py        # burp start / status / stop (lifecycle)
│   ├── workflows.py   # health check (composite of status+disk+memory+updates)
│   ├── packages.py    # update, packages, usb, install requirements
│   └── fun.py         # greeting, joke, clear
└── README.md
```

## Get it onto the VM

Built for your Kali VM (user `arise`).

1. Clone the repo into the VM: `git clone https://github.com/Bhavanshu21/Friday.git`
2. Run it from inside the folder:
   ```bash
   cd Friday
   python3 friday.py
   ```
   No dependencies beyond Python 3 (standard library only).
   Optional tools it can drive if installed: `nmap`, `msfconsole`, `burpsuite`,
   `traceroute`, `dig`.

Type `help` inside to see all commands. Type `exit` to quit.

## Run it on Windows (native, no VM)

On Windows FRIDAY loads `commands_win/` instead of `commands/` — everyday
commands live there, no Kali tooling involved.

1. Install Python 3 from python.org (tick **Add python.exe to PATH**).
2. Clone the repo: `git clone https://github.com/Bhavanshu21/Friday.git`
3. Install voice dependencies (one time):
   ```powershell
   cd Friday
   pip install -r requirements.txt
   ```
4. Make sure Ollama is running on the PC (it serves on `localhost:11434`
   by default — no `--brain-url` needed for local use).
5. Run it: double-click `friday.bat`, or from a terminal:
   ```powershell
   .\friday.bat
   ```
   Bare run = voice + Ollama brain, same as the Linux launcher.
   `friday.bat --help` etc. override the defaults.

Type `help` inside to see all commands. Type `exit` to quit.

### Windows daily commands

**Excel** — `remember sheet budget C:\Users\you\Documents\budget.xlsx`
registers a nickname; then `update budget cell B5 to 108`,
`add row to budget: 2026-10-07, Metro, 108`, `read excel budget A1:D20`.

**Reminders** — `remind me in 20 minutes to stretch` pops a Windows toast
at the time, even if FRIDAY is closed (uses Task Scheduler).
`my reminders` lists them, `cancel reminder stretch` removes one.

**Ask anything** — `what's the weather in Delhi`, `define serendipity`,
`explain photosynthesis`. FRIDAY searches the web and explains in plain
words (weather/word answers are direct; general questions are simplified
by the local brain — or shown raw with a note if the brain is offline).

**Open things** — `remember folder dreamvirtment C:\path\to\folder`, then
`open folder dreamvirtment` pops it in Explorer. `open excel` launches
Excel; `open excel budget` opens that workbook. Then dictate updates:
`update budget cell B5 to 108`, `add row to budget: 2026-10-07, Metro, 108`.

### Graphical HUD (Tony Stark mode)

`friday_gui.py` — same engine (all 18 commands, same brain, same voice),
new face: a live arc-reactor visualizer (pulses idle, flares while
listening, spins while thinking, equalizer while speaking), a transcript,
a text box, and a mic button. Needs nothing new — tkinter ships with
Python.

```powershell
.\friday_gui.bat
```

Desktop shortcut (run from inside the Friday folder):

```powershell
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$HOME\Desktop\FRIDAY HUD.lnk")
$Shortcut.TargetPath = "$PWD\friday_gui.bat"
$Shortcut.WorkingDirectory = "$PWD"
$Shortcut.Save()
```

**Gmail setup (one time)** — FRIDAY creates drafts only, never sends:
1. `pip install google-api-python-client google-auth-oauthlib`
2. [Google Cloud Console](https://console.cloud.google.com) → new project → enable the **Gmail API**
3. OAuth consent screen → External → add yourself as a test user
4. Credentials → Create Credentials → OAuth client ID → **Desktop app**
5. Download the JSON → save as `%USERPROFILE%\.friday\gmail_credentials.json`
6. Ask FRIDAY to draft a mail — a browser window opens once for consent,
   then the token is cached and never asked again.

### Run it as just `friday` (one time, Linux)

```bash
mkdir -p ~/.local/bin
chmod +x ~/Friday/friday
ln -sf ~/Friday/friday ~/.local/bin/friday
```

Then from anywhere: `friday` — with no flags it starts the full
experience (`--voice --brain ollama`). Pass flags explicitly to override:
`friday --voice`, `friday --help`, etc.
(`~/.local/bin` is on PATH by default on Kali; if your shell says
"command not found", run `export PATH="$HOME/.local/bin:$PATH"` and add
that line to `~/.bashrc`.)

## What's new in Phase 2a

**Parameterized commands.** Commands declare `arg_patterns` (regex per
argument); the dispatcher extracts them and passes a `params` dict to
handlers that ask for it. Old no-arg handlers work unchanged.

```python
TOOLS = [{
    "name": "ping",
    "description": "Ping a host 4 times. Usage: ping <host>.",
    "triggers": ["ping"],
    "arg_patterns": {"host": r"ping\s+([A-Za-z0-9.\-]+)"},
    "parameters": {"type": "OBJECT",
                   "properties": {"host": {"type": "STRING"}}},
    "handler": _ping,          # def _ping(params): ...
}]
```

**Short-term memory.** The last 10 runs are kept in memory: `again` /
`repeat` re-runs the last command, and FRIDAY can recall things like
the last IP address it printed.

**Composite workflows.** `commands/workflows.py` holds commands that call
other registered commands and combine results — `health check` runs
status + disk + memory + pending updates in one report. Handlers that
declare `ctx` receive `{"registry", "context"}`.

**Pentest tools.**
- `nmap <quick|standard|full|os|udp|vuln|syn|connect|aggressive|version|ports|script|list> <target>`, `nmap sweep <subnet>`
  — targets are strictly validated (IPv4/CIDR/hostname); some profiles
  need sudo and warn that they're slow.
- `msf search <term>`, `msf info <module path>`, `msf version` —
  non-interactive via `msfconsole -x`. Interactive exploit sessions stay
  in msfconsole itself; FRIDAY finds the module, you run it.
- `burp start` / `burp status` / `burp stop` — Burp is GUI-driven, so
  FRIDAY manages its lifecycle rather than its scans.

## How it works

**Adding a command = one TOOL dict** (see `friday.py` header for the full
template). Restart FRIDAY — nothing else changes. A file with a syntax
error, a bad regex, or a duplicate name is logged and skipped; it can
never break the other commands.

**Matching:** longest trigger wins, ties break by earliest position, so
`service ssh restart` hits `service` (not reboot) and `nmap ping sweep`
hits the sweep (not `ping`).

**Why both `description` and `triggers`?** Keywords match today
(`triggers`); Phase 3 hands `name` + `description` + `parameters` to a
local LLM for function calling — the same shape every LLM tool API uses.
The registry serves both brains, so the upgrade won't need restructuring.

## Safety design

1. **Allowlist only** — the registry is the entire set of runnable things.
2. **No `shell=True` anywhere** — argument arrays only, no shell to inject into.
3. **Timeouts** on every command (longer for slow scans).
4. **Destructive commands ask first** — `reboot` needs a typed YES.
5. **Arguments are validated** — nmap targets, msf terms, service names
   and log names are pattern-checked before use; raw input never reaches
   a subprocess unfiltered. `tail` can only read 4 named logs.
6. **Audit trail** — every run (and every rejected input) goes to
   `~/.friday/friday.log`.

## Deliberately left out

- **No cloud LLM / API keys** — fully offline by design.
- **No GUI/avatar** — it's a terminal tool for a VM.
- **No undo stack yet** — arrives with the first file-changing command.
- **No wake word** — push-to-talk only, by choice. No always-listening mic.

## Phase 2b — voice (this release)

`python3 friday.py --voice` switches to push-to-talk: **Enter** starts
recording, **Enter** again stops it. Speech is transcribed locally by
faster-whisper, the reply is spoken back by Piper — everything offline.
Long outputs print in full but only the first 600 characters are spoken.

Setup (one time, on the Kali VM):

```bash
# system libraries: PortAudio (mic/speaker) + espeak-ng (Piper phonemes)
sudo apt install libportaudio2 espeak-ng

# python packages (text mode never needs these) — or just tell FRIDAY:
#   "install requirements"
pip install -r requirements.txt

python3 friday.py --voice
```

First run downloads the Whisper base model (~1GB) and the Piper voice
(~60MB) into `~/.friday/models/`. Use `VoiceIO(stt_model="tiny")` in
`friday.py` if you want the smaller/faster model instead.

**Microphone in VirtualBox:** VM Settings → Audio → tick **Enable Audio
Input**. In the guest, `arecord -l` must list a capture device; test it
with `arecord -d 3 test.wav && aplay test.wav`. If the guest sees no
input device, voice mode can't hear you — text mode is unaffected.

## Phase 3 — the brain (this release)

`python3 friday.py --brain ollama` hands command choice to a local LLM
(`qwen3:4b` by default). The model reads the TOOL registry through
Ollama's native tools API and picks one command per turn; unknown tool
names are rejected before execution. The registry is still the allowlist —
the brain never invents commands. If Ollama isn't reachable, FRIDAY falls
back to keyword matching automatically. Combine with voice:
`python3 friday.py --voice --brain ollama`.

Setup (one time, on the Kali VM):

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen3:4b
ollama serve   # or: systemctl start ollama
```

Switch models at runtime with `--model` (e.g. `friday --voice --brain ollama
--model qwen3:1.7b` after `ollama pull qwen3:1.7b`). `qwen3:1.7b` is much
faster on CPU-only machines but dumber at picking commands; `qwen3:8b`
is smarter but wants ~6GB RAM.

### Faster brain: run Ollama on the host PC (or any GPU box)

The VM's CPU is the bottleneck. Run Ollama where the hardware is — your
host PC — and point FRIDAY at it:

1. On the host: install Ollama, set `OLLAMA_HOST=0.0.0.0`, restart it,
   allow port 11434 through the firewall, then `ollama pull qwen3:4b`.
2. On the VM, find the host's address: `ip route | grep default`
   (VirtualBox NAT: usually `10.0.2.2`). Test it:
   `curl http://10.0.2.2:11434/api/tags`
3. Run: `friday --voice --brain ollama --brain-url http://10.0.2.2:11434`

To make the host brain the permanent default so bare `friday` just uses
it, add this to `~/.bashrc` on the VM (explicit `--brain-url` still wins
when given):

```bash
export FRIDAY_BRAIN_URL=http://10.0.2.2:11434
```

Same works for a cloud GPU pod over an SSH tunnel
(`ssh -L 11434:localhost:11434 user@pod`, then `--brain-url
http://localhost:11434` — stop the VM-local Ollama first to avoid a port
clash). Voice audio never leaves the VM; only command text goes to the
brain.

**Design notes:**
- One tool call per user turn. Tool outputs are shown to you, never fed
  back into the model — hostile text in a log or scan result can't steer
  the next decision (prompt-injection mitigation).
- Conversation history keeps intents ("ran nmap_quick"), not outputs.
  The Phase 2a context buffer (`again`, IP recall) still works underneath.
- Every model-chosen argument still passes through each command's own
  validation (nmap target regex, msf term whitelist, ...).

## Roadmap

- **Phase 2b — voice**: faster-whisper (STT) + Piper (TTS), push-to-talk.
  Mic via VirtualBox audio passthrough. The registry doesn't change —
  voice just replaces the keyboard.
- **Phase 3 — smarter brain**: local LLM (Ollama, ~3B fits your 9.7GB VM)
  picks from this same registry via the TOOL dicts instead of keyword
  matching. The allowlist stays; only the matcher gets smarter. That's
  the security boundary — it never moves.
