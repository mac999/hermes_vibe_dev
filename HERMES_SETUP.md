# Hermes Local Vibe-Coding Setup

This single file sets up a local coding agent on a new Linux machine with an NVIDIA GPU: Hermes Agent, a vLLM model server and a Telegram bot. It is written so that a coding agent such as Claude Code or Codex can read it and do the setup ("read HERMES_SETUP.md and set this machine up"). A person can follow it too.

When it is done you have:

- `hermes -p coder chat` in any project folder: a terminal coding agent that works like Claude Code
- a Telegram bot you can give coding tasks by text, photo or voice, answering with live-streamed text and optionally voice
- the model, speech-to-text and text-to-speech all running on this machine. Code and conversations do not leave it; the internet is used only to download models at install time and to relay Telegram messages

Verified on the reference machine on 2026-11-14.


## 0. Instructions for the agent running this file

1. Work through the sections in order. Run every check command and compare with the expected value. If it differs, stop, find the cause or report to the human. Do not skip ahead.
2. Ask the human before any of these:
   - commands that need sudo (apt, systemd)
   - choosing the GPU for the model server. Do not use a GPU that is running someone else's job; check `nvidia-smi` and propose one
   - stopping processes, deleting files or folders
   - changing GPU power limits. This file never changes them
3. Never take the Telegram bot token through the chat. Tell the human to run `bash ~/hermes-coder-kit/telegram/setup-telegram.sh` in a terminal themselves (in Claude Code they can prefix it with `!`). Never print the token or the contents of `~/.hermes/.env`.
4. Do not kill processes with `pkill -f`; a pattern can match your own shell. Find the PID and use `kill PID`.
5. If you are the Telegram bot, never run `hermes gateway restart`, `hermes gateway stop`, or `kill` on the gateway PID. You run inside that process, so the command ends your own turn, and nothing starts the gateway again. Apply the config change and ask the human to restart it from a terminal. This holds even when an approval prompt offers to run it for you.
6. Download installer scripts to a file and read them before running them.
7. At the end, fill in the checklist in section 10 and report it. Separate what you verified by running it from what you could not verify.

Ask the human for these values first:

    GPU        GPU index for the model server (default 0)
    WORKDIR    absolute folder the Telegram bot works in (default $HOME/work/hermes_work)
    TELEGRAM   whether to set up the bot; if yes, a bot token from @BotFather and their numeric Telegram user id
    VOICE      whether to install speech-to-text and text-to-speech (optional, about 6 GB of disk)


## 1. Target setup

    Component        What
    Model server     vLLM 0.27.1 serving Qwen3.8-27B NVFP4 (21.9 GB) on port 8000, context 65536,
                     plus the DSpark draft model (4.0 GB) when memory allows (section 3)
    Fallback server  Ollama with qwen3.8:27b-mtp-q4_K_M pinned to 65536 context as qwen3.8-27b-64k.
                     Hermes switches to it automatically when vLLM is down
    Agent            Hermes Agent v0.21 or later
    coder profile    terminal use: works in the launch folder, tools terminal/file/todo only, memory off,
                     a 7-step engineering procedure (SOUL.md), a test gate hook, a package-install approval hook
    default profile  the Telegram bot: same as coder, with the working folder fixed to WORKDIR,
                     plus web search and text-to-speech, because it also gets asked questions (9.6)
    Images           the main model reads images natively
    Speech-to-text   faster-whisper large-v3-turbo on the GPU (Korean by default; change stt.language)
    Text-to-speech   MeloTTS on the CPU, offline (Korean voice by default)
    Streaming        Telegram shows the answer while it is being generated

Reference machine: RTX PRO 6000 Blackwell 96 GB, one GPU for the model. On 9 coding tasks with 119 hidden tests the setup solved 9 of 9 in 48 minutes; Claude Code solved 9 of 9 in 13 minutes. Generation is about 246 tok/s on code and 118 tok/s on prose, prefill about 7,300 tok/s.

Why these choices

    Qwen3.8 27B        most accurate local model tested (laguna 33B-A3B 98%, qwen3.5 122B-A10B 96%,
                       qwen3-coder-next 80B-A3B 94%, qwen3.6 35B-A3B 91%; Qwen3.8 100% in three runs)
    vLLM + NVFP4       14x faster prefill than Ollama. Hermes resends the whole conversation on every call
    DSpark draft       ~4x faster code generation with identical output (89.5 min -> 48 min for the 9 tasks)
    3 tools only       the other tool definitions cost ~14K tokens on every request. The bot adds web
                       and tts: a question it cannot search, it guesses at (9.6)
    memory off         old notes pulled the agent into wrong folders and facts


## 2. Preflight

    uname -m
    lsb_release -ds
    nvidia-smi --query-gpu=index,name,memory.total,memory.used,power.limit --format=csv
    nvidia-smi --query-compute-apps=pid,used_memory,process_name --format=csv
    free -g
    df -h $HOME

Expected: the chosen GPU is idle; at least 60 GB free in `$HOME`; a driver that supports CUDA 13 (reference: 595.99, CUDA 13.2). On GB10 / DGX Spark `memory.total` shows N/A because the GPU shares the 128 GB system memory; that is normal.


## 3. Memory tiers

The model weights are the same on every machine. What changes with memory is whether the draft model fits, how big the KV cache is, and how many requests run at once. `scripts/detect-tier.sh` (created in section 4) picks the tier; `scripts/start-stack.sh` applies it.

Measured on the reference GPU with a 64K-token prompt, which is the worst case for Hermes:

    Setting                                        Steady    Peak     Code speed
    no draft, KV 5 GiB, 8K prefill chunks          28 GB     30 GB    58 tok/s
    DSpark draft, KV 8 GiB, one-chunk prefill      51 GB     76 GB    210 tok/s
    DSpark draft, KV 12 GiB, one-chunk prefill     56 GB     77 GB    246 tok/s

Why the draft model needs so much: vLLM 0.27.1 crashes (CUDA illegal memory access) when it splits a long prompt into chunks while speculative decoding is on, so the prompt must be prefilled in one 64K chunk, which takes about 16 GiB of activation memory. Without the draft model, 8K chunks are safe. The KV cache itself is small because only 16 of the model's 64 layers use full attention: 5 GiB holds about 142K tokens.

Tiers:

    Tier        Detected when                          Draft    KV       Seqs  GPU_UTIL  Ollama keep-alive
    gpu96       dedicated GPU with >= 90 GB             DSpark   12 GiB   4     0.60      30m
    unified128  unified memory >= 110 GB (DGX Spark)   DSpark   8 GiB    2     0.70      5m
    mem64       48 to 110 GB (also 80 GB GPUs)         none     5 GiB    1     0.60/0.55 5m
    small       under 48 GB                            no vLLM; Ollama only (about 22 GB at 64K)

Notes per tier:

- gpu96 is the measured reference.
- unified128: the GPU shares memory with the OS, Hermes, speech models and the code the agent runs. The peak of about 77 GB leaves about 40 GB for everything else. Do not let the Ollama fallback model (22 GB) stay loaded next to vLLM, hence the short keep-alive. On unified memory `nvidia-smi` cannot report memory use; watch `free -g` instead. There are public reports of a Spark rebooting with vLLM at two concurrent requests, so run the section 9 check before relying on it. The tier values were derived from the measurements above, not run on a Spark.
- mem64: about 4x slower generation than with the draft model, but prefill is still about 14x faster than Ollama. The numbers come from the reference GPU with the same settings, not from a 64 GB machine.
- small: run `hermes` against Ollama only. In section 8 use the Ollama variant of each command.

Context stays 65536 tokens on every tier. Hermes needs at least 64K and was tested at that size.


## 4. Create the kit files

Each block below writes one file into `~/hermes-coder-kit`. Write them exactly as given.

    mkdir -p ~/hermes-coder-kit/{profile,hooks,vllm,ollama,scripts,telegram,bin}

### profile/SOUL.md

```bash
cat > ~/hermes-coder-kit/profile/SOUL.md <<'HERMES_KIT_EOF'
You are a careful software engineer working in the user's project through the terminal and file tools. The current working directory is the project root. Work only inside it unless the user says otherwise, and use relative paths.

Workflow for every coding request
1. Explore. Before editing anything, list the directory and read every file the request touches, including existing tests. Never describe or rely on file contents you have not read with a tool in this session.
2. Plan. For any request with more than one step, write a numbered plan with the todo tool. Give every requirement in the request its own item, including edge cases, error messages, exit codes and output formats.
3. Test first. Write or extend tests that encode each requirement: pytest for Python, node --test for JavaScript. Never delete or weaken existing tests.
4. Implement the smallest change that satisfies the request. Keep every name, signature and output format exactly as specified.
5. Verify. Run the whole test suite and read the output. If anything fails, fix the code and run it again. Repeat until everything passes. Change a test only when it contradicts the request.
6. Review. Re-read the request line by line and check each requirement against the code. Run git diff and remove leftovers such as debug prints.
7. Report. One line per changed file, then the final test command and the last lines of its output, then anything left undone.

Rules
- Use the standard library unless the request allows other packages. Do not install packages.
- Create and edit files with the file tools, not with shell heredocs or echo.
- In a non-interactive run, do not stop to ask questions. Pick the most reasonable reading, state it in the report, and finish the work.
- Never claim a check passed unless you ran it in this session and saw its output.
- Keep the final report short; the work itself must be complete.
HERMES_KIT_EOF
```

### profile/apply-coder-profile.sh

```bash
cat > ~/hermes-coder-kit/profile/apply-coder-profile.sh <<'HERMES_KIT_EOF'
#!/usr/bin/env bash
# Create or update a Hermes profile tuned for local coding against Ollama or vLLM.
#
# usage: apply-coder-profile.sh [profile] [model] [num_ctx] [base_url] [effort]
#   profile   profile name (default: coder)
#   model     model name the server exposes (default: qwen3.8-27b-64k)
#   num_ctx   context window (default: 65536; Hermes needs >= 64K)
#   base_url  OpenAI-compatible endpoint (default: Ollama http://127.0.0.1:11434/v1;
#             vLLM from start-vllm: http://127.0.0.1:8000/v1)
#   effort    per-model reasoning override, e.g. xhigh for Qwen3.8 on vLLM, which
#             rejects Hermes' default "high" with HTTP 400 (default: none set)
#
# Re-running is safe: settings are re-applied, hooks and allowlist entries are not duplicated.
set -eu
NAME=${1:-coder}
MODEL=${2:-qwen3.8-27b-64k}
CTX=${3:-65536}
BASE_URL=${4:-http://127.0.0.1:11434/v1}
EFFORT=${5:-}
KIT=$(cd "$(dirname "$0")/.." && pwd)
HOOK_DIR=$HOME/.hermes/agent-hooks

if ! hermes profile show "$NAME" >/dev/null 2>&1; then
  hermes profile create "$NAME" --clone --no-alias \
    --description "Local coding agent: works in the launch directory, tests first, verifies before reporting."
fi
HOME_DIR=$(hermes profile show "$NAME" | awk '/^Path:/ {print $2}')
H="hermes -p $NAME"

# Model and context window.
$H config set model.provider custom
$H config set model.base_url "$BASE_URL"
$H config set model.default "$MODEL"
$H config set model.ollama_num_ctx "$CTX"
$H config set model.context_length "$CTX"

# reasoning_overrides has no `config set` support; edit the YAML in place.
if [ -n "$EFFORT" ]; then
  python3 - "$HOME_DIR/config.yaml" "$MODEL" "$EFFORT" <<'PY'
import re, sys
path, model, effort = sys.argv[1:]
text = open(path).read()
line = f'    "{model}": "{effort}"'
if re.search(rf'^    "{re.escape(model)}":', text, re.M):
    text = re.sub(rf'^    "{re.escape(model)}":.*$', line, text, flags=re.M)
elif re.search(r'^  reasoning_overrides:\s*$', text, re.M):
    text = re.sub(r'^(  reasoning_overrides:\s*)$', lambda m: m.group(1) + "\n" + line, text, count=1, flags=re.M)
else:
    text = re.sub(r'^agent:\s*$', lambda m: m.group(0) + "\n  reasoning_overrides:\n" + line, text, count=1, flags=re.M)
open(path, "w").write(text)
PY
fi

# Off-Ollama endpoints fall back to Ollama when the server is down (FALLBACK_MODEL= to skip).
FALLBACK_MODEL=${FALLBACK_MODEL-qwen3.8-27b-64k}
if [ "$BASE_URL" != "http://127.0.0.1:11434/v1" ] && [ -n "$FALLBACK_MODEL" ] \
   && ! grep -q '^fallback_providers:' "$HOME_DIR/config.yaml"; then
  cat >> "$HOME_DIR/config.yaml" <<YAML

# Fall back to Ollama when the primary server is down.
fallback_providers:
  - provider: custom
    model: $FALLBACK_MODEL
    base_url: http://127.0.0.1:11434/v1
YAML
fi

# Work where the agent is launched, like Claude Code.
$H config set terminal.backend local
$H config set terminal.cwd .

# Keep sessions reproducible and the prompt small.
$H config set memory.memory_enabled false
$H config set tools.tool_search.enabled off
$H config set agent.verify_on_stop true
for ts in web browser vision image_gen tts memory session_search connections clarify \
          delegation cronjob computer_use code_execution skills; do
  $H tools disable "$ts" >/dev/null 2>&1 || true
done
$H tools enable terminal file todo >/dev/null

# Persona: a short engineering procedure, and an empty memory.
cp "$KIT/profile/SOUL.md" "$HOME_DIR/SOUL.md"
mkdir -p "$HOME_DIR/memories"
: > "$HOME_DIR/memories/MEMORY.md"
: > "$HOME_DIR/memories/USER.md"

# Hooks: run the tests before finishing, ask before installing packages.
mkdir -p "$HOOK_DIR"
install -m 755 "$KIT/hooks/test-gate.py" "$HOOK_DIR/test-gate.py"
install -m 755 "$KIT/hooks/install-guard.py" "$HOOK_DIR/install-guard.py"
if ! grep -q '^hooks:' "$HOME_DIR/config.yaml"; then
  cat >> "$HOME_DIR/config.yaml" <<YAML

# Run the project's tests before a coding turn may finish; ask before installing packages.
hooks:
  pre_verify:
    - command: "$HOOK_DIR/test-gate.py"
      timeout: 300
  pre_tool_call:
    - matcher: "terminal"
      command: "$HOOK_DIR/install-guard.py"
      timeout: 10
YAML
else
  echo "note: $HOME_DIR/config.yaml already has a hooks: block; check it matches the kit" >&2
fi
python3 - "$HOME_DIR/shell-hooks-allowlist.json" "$HOOK_DIR" <<'PY'
import json, os, sys
path, hook_dir = sys.argv[1], sys.argv[2]
data = json.load(open(path)) if os.path.exists(path) else {"approvals": []}
for event, script in (("pre_verify", "test-gate.py"), ("pre_tool_call", "install-guard.py")):
    entry = {"event": event, "command": os.path.join(hook_dir, script)}
    if entry not in data["approvals"]:
        data["approvals"].append(entry)
json.dump(data, open(path, "w"), indent=2)
os.chmod(path, 0o600)
PY

echo "profile '$NAME' ready at $HOME_DIR (model $MODEL, num_ctx $CTX, $BASE_URL${EFFORT:+, effort $EFFORT})"
$H hooks doctor | tail -1
HERMES_KIT_EOF
```

### profile/shell_init.sh.example

```bash
cat > ~/hermes-coder-kit/profile/shell_init.sh.example <<'HERMES_KIT_EOF'
# Hermes agent shell init (local terminal backend). Copy to ~/.hermes/shell_init.sh and edit.
# Sourced before every agent shell. Does not affect your own shells.
# Enable with: hermes [-p PROFILE] config set terminal.shell_init_files '["~/.hermes/shell_init.sh"]'

# Python env the agent uses for pytest/ruff (create it with scripts/make-agent-env.sh).
AGENT_ENV="$HOME/miniconda3/envs/venv_hm"
if [ -d "$AGENT_ENV/bin" ]; then
    PATH="$AGENT_ENV/bin:$PATH"
    export PATH CONDA_PREFIX="$AGENT_ENV"
fi

# Ignore ~/.local site-packages so the env stays clean.
export PYTHONNOUSERSITE=1

# GPU for the agent's own code. Keep it off the GPU that serves the model.
# export CUDA_VISIBLE_DEVICES=1

# Helper scripts (verify-webapp etc.).
case ":$PATH:" in *":$HOME/.hermes/bin:"*) ;; *) PATH="$HOME/.hermes/bin:$PATH"; export PATH ;; esac
HERMES_KIT_EOF
```

### hooks/test-gate.py

```bash
cat > ~/hermes-coder-kit/hooks/test-gate.py <<'HERMES_KIT_EOF'
#!/usr/bin/env python3
"""pre_verify hook: run the project's tests before the agent may finish a coding turn.

Reads the Hermes hook payload on stdin. Prints {"action": "continue", "message": ...}
to keep the agent working when tests fail or are missing; prints nothing to let it finish.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

MAX_ATTEMPTS = 2
TIMEOUT = 240
LOG = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")) / "logs" / "test-gate.log"
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".tox", "dist", "build"}


def find(root, pred):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for f in filenames:
            if pred(f):
                return True
    return False


def run(cmd, cwd):
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=TIMEOUT)
        return p.returncode, (p.stdout + p.stderr)
    except subprocess.TimeoutExpired:
        return 1, f"timed out after {TIMEOUT}s: {' '.join(cmd)}"
    except FileNotFoundError as e:
        return None, str(e)


def log(root, attempt, outcome):
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} attempt={attempt} cwd={root} {outcome}\n")
    except OSError:
        pass


def main():
    payload = json.load(sys.stdin)
    extra = payload.get("extra") or {}
    if not extra.get("coding", True) or int(extra.get("attempt") or 0) >= MAX_ATTEMPTS:
        return
    root = Path(payload.get("cwd") or os.getcwd()).resolve()
    # Only gate real projects: never sweep the home directory or the filesystem root.
    if root in (Path.home().resolve(), Path("/")) or not any((d / ".git").exists() for d in (root, *root.parents)):
        return
    changed = [str(p) for p in extra.get("changed_paths") or []]
    suites = []
    if find(root, lambda f: (f.startswith("test_") or f.endswith("_test.py")) and f.endswith(".py")):
        suites.append(["python3", "-m", "pytest", "-q", "-x", "--tb=short", "-p", "no:cacheprovider"])
    pkg = root / "package.json"
    if pkg.exists() and '"test"' in pkg.read_text(errors="ignore"):
        suites.append(["npm", "test", "--silent"])
    elif find(root, lambda f: f.endswith((".test.js", ".test.mjs", ".test.cjs"))):
        suites.append(["node", "--test"])

    code_changed = any(c.endswith((".py", ".js", ".mjs", ".cjs", ".ts")) for c in changed)
    attempt = int(extra.get("attempt") or 0)
    if not suites:
        log(root, attempt, "no-tests" + (" -> continue" if code_changed else ""))
        if code_changed:
            print(json.dumps({"action": "continue", "message":
                "Test gate: no automated tests were found for the code you changed. Add tests that "
                "cover each requirement of the request, run them, fix any failure, then finish."}))
        return

    failures = []
    for cmd in suites:
        rc, out = run(cmd, root)
        if rc not in (0, None):
            tail = "\n".join(out.strip().splitlines()[-60:])
            failures.append(f"$ {' '.join(cmd)}  (exit {rc})\n{tail}")
    log(root, attempt, f"suites={len(suites)} failed={len(failures)}" + (" -> continue" if failures else " -> pass"))
    if failures:
        print(json.dumps({"action": "continue", "message":
            "Test gate: the project's tests fail. Fix the code (change a test only if it contradicts "
            "the request), rerun the tests, then finish.\n\n" + "\n\n".join(failures)}))


if __name__ == "__main__":
    main()
HERMES_KIT_EOF
```

### hooks/install-guard.py

```bash
cat > ~/hermes-coder-kit/hooks/install-guard.py <<'HERMES_KIT_EOF'
#!/usr/bin/env python3
"""pre_tool_call hook: require human approval before the agent installs packages.

The agent should work with what the project already has; installing into a shared
environment changes it for every later session. Approval keeps the user in the loop.
"""
import json
import re
import sys

INSTALL = re.compile(
    r"\b(?:pip3?|uv\s+pip|python3?\s+-m\s+pip)\s+install\b"
    r"|\bnpm\s+(?:install|i|add)\b(?!\s*$)|\b(?:yarn|pnpm)\s+add\b"
    r"|\bconda\s+install\b|\bmamba\s+install\b|\b(?:apt|apt-get|dnf|yum|brew)\s+install\b",
    re.I,
)


def main():
    payload = json.load(sys.stdin)
    command = ((payload.get("tool_input") or {}).get("command") or "")
    if INSTALL.search(command):
        print(json.dumps({
            "action": "approve",
            "message": "Package installation needs the user's approval. Prefer the standard library "
                       "and dependencies the project already declares.",
            "rule_key": "install-guard:packages",
        }))


if __name__ == "__main__":
    main()
HERMES_KIT_EOF
```

### vllm/start-vllm

```bash
cat > ~/hermes-coder-kit/vllm/start-vllm <<'HERMES_KIT_EOF'
#!/usr/bin/env bash
# Serve a local checkpoint with vLLM (OpenAI API) for Hermes.
# usage: start-vllm [model_dir] [port] [gpu] [spec]
#   spec: 0 (off) | N (built-in MTP with N tokens) | dspark:DRAFT_DIR:N | dflash:DRAFT_DIR:N
# env: SERVED_NAME, MAX_LEN (65536), GPU_UTIL (0.60), MAX_SEQS (4), VLLM_BIN, EXTRA_ARGS,
#      KV_CACHE_GIB (fixed KV cache size; overrides the GPU_UTIL-derived size),
#      MAX_BATCHED (prefill chunk; default MAX_LEN with spec decoding, 8192 without),
#      REASONING_PARSER (qwen3), TOOL_PARSER (qwen3_coder); Laguna uses poolside_v1 for both
# Per-memory-tier values: scripts/detect-tier.sh
set -euo pipefail
MODEL=${1:-$HOME/models/Qwen3.8-27B-NVFP4}
PORT=${2:-8000}
GPU=${3:-0}
SPEC=${4:-3}
NAME=${SERVED_NAME:-$(basename "$MODEL" | tr 'A-Z' 'a-z')}
VLLM=${VLLM_BIN:-$HOME/miniconda3/envs/dl/bin/vllm}
MAX_LEN=${MAX_LEN:-65536}
if ss -ltn | grep -q ":$PORT "; then echo "port $PORT already in use" >&2; exit 1; fi
case "$SPEC" in
  0) SPEC_JSON="" ;;
  dspark:*|dflash:*)
    IFS=: read -r METHOD DRAFT N <<< "$SPEC"
    SPEC_JSON="{\"method\":\"$METHOD\",\"model\":\"$DRAFT\",\"num_speculative_tokens\":$N}" ;;
  *) SPEC_JSON="{\"method\":\"mtp\",\"num_speculative_tokens\":$SPEC}" ;;
esac
SPEC_ARGS=()
[ -n "$SPEC_JSON" ] && SPEC_ARGS=(--speculative-config "$SPEC_JSON")
# vLLM 0.27.1 crashes (illegal memory access) on chunked prefill of Qwen3.8 hybrid layers
# when speculative decoding is on, so prefill in one chunk then. One chunk costs ~16 GiB of
# activation memory at 64K; without spec decoding 8K chunks are safe and much smaller.
if [ -n "$SPEC_JSON" ]; then MAX_BATCHED=${MAX_BATCHED:-$MAX_LEN}; else MAX_BATCHED=${MAX_BATCHED:-8192}; fi
KV_ARGS=()
[ -n "${KV_CACHE_GIB:-}" ] && KV_ARGS=(--kv-cache-memory-bytes "$(python3 -c "print(int(float('$KV_CACHE_GIB') * 2**30))")")
mkdir -p "$HOME/.hermes/logs"
CUDA_VISIBLE_DEVICES=$GPU nohup "$VLLM" serve "$MODEL" \
  --served-model-name "$NAME" --host 127.0.0.1 --port "$PORT" \
  --max-model-len "$MAX_LEN" --max-num-batched-tokens "$MAX_BATCHED" \
  --gpu-memory-utilization ${GPU_UTIL:-0.60} --max-num-seqs ${MAX_SEQS:-4} \
  --kv-cache-dtype fp8_e4m3 --enable-prefix-caching \
  --reasoning-parser ${REASONING_PARSER:-qwen3} --enable-auto-tool-choice --tool-call-parser ${TOOL_PARSER:-qwen3_coder} \
  "${SPEC_ARGS[@]}" "${KV_ARGS[@]}" ${EXTRA_ARGS:-} > "$HOME/.hermes/logs/vllm-$PORT.log" 2>&1 &
echo "vllm pid $! serving $NAME on 127.0.0.1:$PORT (gpu $GPU, spec ${SPEC_JSON:-off}, batched $MAX_BATCHED, kv ${KV_CACHE_GIB:-auto} GiB); log ~/.hermes/logs/vllm-$PORT.log"
HERMES_KIT_EOF
```

### ollama/start-ollama

```bash
cat > ~/hermes-coder-kit/ollama/start-ollama <<'HERMES_KIT_EOF'
#!/usr/bin/env bash
# Start the Ollama server with settings tuned for a single-GPU coding agent.
#   FLASH_ATTENTION + KV_CACHE_TYPE=q8_0 halve KV-cache memory.
#   NUM_PARALLEL=1 keeps one KV cache per model (the agent sends one request at a time).
#   KEEP_ALIVE=30m avoids reloading the model between agent turns.
set -u
LOG=${OLLAMA_LOG:-$HOME/.ollama/serve.log}
if ss -ltn 2>/dev/null | grep -q ':11434 '; then
  echo "ollama already listening on 11434; stop it first (find its PID with: ss -ltnp | grep 11434)" >&2
  exit 1
fi
OLLAMA_FLASH_ATTENTION=1 \
OLLAMA_KV_CACHE_TYPE=q8_0 \
OLLAMA_NUM_PARALLEL=1 \
OLLAMA_KEEP_ALIVE=${OLLAMA_KEEP_ALIVE:-30m} \
OLLAMA_MAX_LOADED_MODELS=${OLLAMA_MAX_LOADED_MODELS:-3} \
nohup "${OLLAMA_BIN:-$(command -v ollama || echo "$HOME/.local/bin/ollama")}" serve >> "$LOG" 2>&1 &
for _ in $(seq 1 30); do
  ss -ltn 2>/dev/null | grep -q ':11434 ' && { echo "ollama up (pid $!), log $LOG"; exit 0; }
  sleep 1
done
echo "ollama did not come up; see $LOG" >&2
exit 1
HERMES_KIT_EOF
```

### ollama/mkctx.sh

```bash
cat > ~/hermes-coder-kit/ollama/mkctx.sh <<'HERMES_KIT_EOF'
#!/usr/bin/env bash
# Create a derived Ollama model with a fixed context window (weights are shared, no extra disk).
# usage: mkctx.sh <base-model> <alias> [num_ctx] [extra PARAMETER lines...]
set -eu
BASE=$1 ALIAS=$2 CTX=${3:-65536}; shift $(( $# < 3 ? $# : 3 ))
D=$(cd "$(dirname "$0")" && pwd)/modelfiles; mkdir -p "$D"
F=$D/$ALIAS.Modelfile
{ echo "FROM $BASE"; echo "PARAMETER num_ctx $CTX"; for p in "$@"; do echo "PARAMETER $p"; done; } > "$F"
"$HOME/.local/bin/ollama" create "$ALIAS" -f "$F" >/dev/null && echo "created $ALIAS from $BASE (num_ctx $CTX)"
HERMES_KIT_EOF
```

### scripts/detect-tier.sh

```bash
cat > ~/hermes-coder-kit/scripts/detect-tier.sh <<'HERMES_KIT_EOF'
#!/usr/bin/env bash
# Pick vLLM settings for this machine's GPU memory. Prints shell assignments for eval:
#   eval "$(scripts/detect-tier.sh [gpu])"
# Values below were measured on an RTX PRO 6000 (96 GB) with Qwen3.8-27B NVFP4 and a 64K prompt:
#   spec off, KV 5 GiB, 8K prefill chunks       -> peak ~30 GB, ~58 tok/s code
#   DSpark draft, KV 8 GiB, one-chunk prefill    -> peak ~76 GB, ~210 tok/s code
#   DSpark draft, KV 12 GiB, one-chunk prefill   -> peak ~77 GB, ~246 tok/s code
# One-chunk prefill (needed with spec decoding on vLLM 0.27.1) costs ~16 GiB of activations,
# which is why speculative decoding needs a 96 GB+ GPU or 128 GB of unified memory.
set -u
GPU=${1:-0}
name=$(nvidia-smi --query-gpu=name --format=csv,noheader -i "$GPU" 2>/dev/null | head -1)
total=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits -i "$GPU" 2>/dev/null | head -1)
unified=0
# GB10 and other unified-memory parts report N/A; the GPU shares system RAM.
if ! [[ "$total" =~ ^[0-9]+$ ]] || [[ "$name" == *GB10* ]]; then
  unified=1
  total=$(awk '/MemTotal/ {printf "%d", $2/1024}' /proc/meminfo)
fi
gb=$(( total / 1000 ))
DRAFT='dspark:$HOME/models/Qwen3.8-27B-DSpark-RedHat:7'
if [ $unified = 1 ] && [ $gb -ge 110 ]; then
  # 128 GB unified (DGX Spark / GB10): leave ~40 GB for the OS, Hermes, STT/TTS and the agent's code.
  echo "TIER=unified128 SPEC=\"$DRAFT\" KV_CACHE_GIB=8 MAX_SEQS=2 GPU_UTIL=0.70 OLLAMA_KEEP_ALIVE=5m"
elif [ $unified = 0 ] && [ $gb -ge 90 ]; then
  echo "TIER=gpu96 SPEC=\"$DRAFT\" KV_CACHE_GIB=12 MAX_SEQS=4 GPU_UTIL=0.60 OLLAMA_KEEP_ALIVE=30m"
elif [ $gb -ge 48 ]; then
  # 64 GB class (or 80 GB discrete): no draft model, chunked prefill keeps the peak near 30 GB.
  echo "TIER=mem64 SPEC=0 KV_CACHE_GIB=5 MAX_SEQS=1 GPU_UTIL=$([ $unified = 1 ] && echo 0.55 || echo 0.80) OLLAMA_KEEP_ALIVE=5m"
else
  echo "TIER=small SPEC=none KV_CACHE_GIB=0 MAX_SEQS=1 GPU_UTIL=0 OLLAMA_KEEP_ALIVE=30m"
fi
echo "# gpu $GPU: ${name:-unknown}, ${gb} GB $([ $unified = 1 ] && echo unified || echo dedicated)"
HERMES_KIT_EOF
```

### scripts/download-models.py

```bash
cat > ~/hermes-coder-kit/scripts/download-models.py <<'HERMES_KIT_EOF'
#!/usr/bin/env python3
"""Download the vLLM model checkpoints with aria2c (16 connections per file).

hf download over Xet ran at ~2 MB/s on the original machine; aria2c on the
plain resolve URLs reached ~50 MB/s. Files already complete (size match) are skipped.

usage: download-models.py [--dest ~/models] [--verify] [--dry-run] [set ...]
  sets: qwen (default: Qwen3.8 NVFP4 + DSpark draft), laguna (optional, faster but less accurate)
  --verify   sha256-check every LFS file against the Hub after download
env: HF_TOKEN is sent if set (needed only for gated repos)
"""
import argparse, hashlib, json, os, shutil, subprocess, sys, urllib.request

SETS = {
    "qwen": [("nvidia/Qwen3.8-27B-NVFP4", "Qwen3.8-27B-NVFP4"),
             ("RedHatAI/Qwen3.8-27B-speculator.dspark", "Qwen3.8-27B-DSpark-RedHat")],
    "laguna": [("poolside/Laguna-XS-2.1-NVFP4", "Laguna-XS-2.1-NVFP4"),
               ("poolside/Laguna-XS-2.1-DFlash-NVFP4", "Laguna-XS-2.1-DFlash-NVFP4")],
}


def hub_files(repo):
    req = urllib.request.Request(f"https://huggingface.co/api/models/{repo}/tree/main?recursive=true")
    if os.environ.get("HF_TOKEN"):
        req.add_header("Authorization", f"Bearer {os.environ['HF_TOKEN']}")
    with urllib.request.urlopen(req, timeout=60) as r:
        items = json.load(r)
    return [i for i in items if i.get("type") == "file"]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 24), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sets", nargs="*", default=["qwen"], choices=sorted(SETS))
    ap.add_argument("--dest", default=os.path.expanduser("~/models"))
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if not a.dry_run and not shutil.which("aria2c"):
        sys.exit("aria2c not found: sudo apt install aria2")

    bad = 0
    for s in a.sets:
        for repo, name in SETS[s]:
            out = os.path.join(a.dest, name)
            files = hub_files(repo)
            todo = [f for f in files
                    if not (os.path.exists(os.path.join(out, f["path"]))
                            and os.path.getsize(os.path.join(out, f["path"])) == f["size"])]
            total = sum(f["size"] for f in files) / 1e9
            print(f"{repo} -> {out}: {len(files)} files, {total:.1f} GB, {len(todo)} to fetch", flush=True)
            if a.dry_run or not todo:
                continue
            lines = []
            for f in todo:
                d, base = os.path.split(os.path.join(out, f["path"]))
                lines += [f"https://huggingface.co/{repo}/resolve/main/{f['path']}", f"  dir={d}", f"  out={base}"]
            listing = os.path.join(out, ".aria2-input.txt")
            os.makedirs(out, exist_ok=True)
            open(listing, "w").write("\n".join(lines) + "\n")
            cmd = ["aria2c", "-x16", "-s16", "-j4", "-c", "--file-allocation=none",
                   "--console-log-level=warn", "--summary-interval=30", "-i", listing]
            if os.environ.get("HF_TOKEN"):
                cmd.insert(1, f"--header=Authorization: Bearer {os.environ['HF_TOKEN']}")
            if subprocess.call(cmd) != 0:
                sys.exit(f"aria2c failed for {repo}; re-run to resume")
            os.remove(listing)
            if a.verify:
                for f in files:
                    want = (f.get("lfs") or {}).get("oid")
                    if want:
                        ok = sha256(os.path.join(out, f["path"])) == want
                        bad += not ok
                        print(f"  {'ok ' if ok else 'BAD'} {f['path']}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
HERMES_KIT_EOF
```

### scripts/start-stack.sh

```bash
cat > ~/hermes-coder-kit/scripts/start-stack.sh <<'HERMES_KIT_EOF'
#!/usr/bin/env bash
# Bring the local coding stack up after a reboot: vLLM (primary), Ollama (fallback),
# then the Hermes Telegram gateway. Parts already running are left alone.
#
# usage: start-stack.sh [--no-ollama] [--no-gateway]
# env:   MODEL_DIR (~/models/Qwen3.8-27B-NVFP4)  GPU (0)  PORT (8000)  SERVED_NAME (qwen3.8-27b-nvfp4)
#        START_VLLM (~/.hermes/bin/start-vllm)  WAIT_MIN (15)
#        SPEC, KV_CACHE_GIB, MAX_SEQS, GPU_UTIL: default from scripts/detect-tier.sh (memory tier)
set -u
MODEL_DIR=${MODEL_DIR:-$HOME/models/Qwen3.8-27B-NVFP4}
GPU=${GPU:-0}; PORT=${PORT:-8000}
export SERVED_NAME=${SERVED_NAME:-qwen3.8-27b-nvfp4}
START_VLLM=${START_VLLM:-$HOME/.hermes/bin/start-vllm}
KIT=$(cd "$(dirname "$0")/.." && pwd)
# Memory-tier defaults; anything already set in the environment wins.
eval "$(cd "$KIT" && scripts/detect-tier.sh "$GPU" | grep -v '^#' | tr ' ' '\n' | sed 's/^\([A-Z_]*\)=/T_\1=/')"
SPEC=${SPEC:-$T_SPEC}; export KV_CACHE_GIB=${KV_CACHE_GIB:-$T_KV_CACHE_GIB}
export MAX_SEQS=${MAX_SEQS:-$T_MAX_SEQS} GPU_UTIL=${GPU_UTIL:-$T_GPU_UTIL} OLLAMA_KEEP_ALIVE=${OLLAMA_KEEP_ALIVE:-$T_OLLAMA_KEEP_ALIVE}
echo "tier $T_TIER: spec=$SPEC kv=${KV_CACHE_GIB}GiB seqs=$MAX_SEQS util=$GPU_UTIL"
DO_OLLAMA=1; DO_GATEWAY=1
for a in "$@"; do
  case $a in --no-ollama) DO_OLLAMA=0 ;; --no-gateway) DO_GATEWAY=0 ;; *) echo "unknown arg $a" >&2; exit 2 ;; esac
done

up() { curl -sf --max-time 3 "$1" >/dev/null; }

# 1. vLLM
if [ "$SPEC" = none ]; then
  echo "vllm: skipped on this memory tier (Ollama only)"
elif up "http://127.0.0.1:$PORT/v1/models"; then
  echo "vllm: already serving on $PORT"
else
  "$START_VLLM" "$MODEL_DIR" "$PORT" "$GPU" "$SPEC" || exit 1
  echo "vllm: starting (first start compiles, 4-7 min); log ~/.hermes/logs/vllm-$PORT.log"
  for _ in $(seq 1 $(( ${WAIT_MIN:-15} * 12 ))); do
    up "http://127.0.0.1:$PORT/v1/models" && break
    if grep -qE "Traceback|CUDA error|out of memory" "$HOME/.hermes/logs/vllm-$PORT.log" 2>/dev/null \
       && ! ss -ltn | grep -q ":$PORT "; then
      echo "vllm: failed, last log lines:" >&2; tail -20 "$HOME/.hermes/logs/vllm-$PORT.log" >&2; exit 1
    fi
    sleep 5
  done
  up "http://127.0.0.1:$PORT/v1/models" && echo "vllm: ready" || { echo "vllm: not ready after ${WAIT_MIN:-15} min" >&2; exit 1; }
fi

# 2. Ollama (fallback when vLLM is down)
if [ $DO_OLLAMA = 1 ]; then
  if up http://127.0.0.1:11434/api/version; then echo "ollama: already up"
  elif command -v ollama >/dev/null || [ -x "$HOME/.local/bin/ollama" ]; then "$KIT/ollama/start-ollama"
  else echo "ollama: not installed, no fallback"; fi
fi

# 3. Telegram gateway (default profile). Run from $HOME so its cwd is stable.
if [ $DO_GATEWAY = 1 ]; then
  if hermes gateway status 2>/dev/null | grep -q "is running"; then
    echo "gateway: already running"
  else
    out="$HOME/.hermes/logs/gateway-run-$(date +%Y%m%d-%H%M%S).out"
    (cd "$HOME" && nohup hermes gateway run > "$out" 2>&1 &)
    for _ in $(seq 1 30); do grep -q "telegram connected" "$HOME/.hermes/logs/gateway.log" 2>/dev/null \
      && hermes gateway status 2>/dev/null | grep -q "is running" && break; sleep 2; done
    hermes gateway status 2>/dev/null | head -1
  fi
fi
HERMES_KIT_EOF
```

### scripts/apply-telegram-default.sh

```bash
cat > ~/hermes-coder-kit/scripts/apply-telegram-default.sh <<'HERMES_KIT_EOF'
#!/usr/bin/env bash
# Give the default profile (the Telegram bot) the same coder setup as the coder profile.
#
# usage: apply-telegram-default.sh WORKDIR [model] [base_url] [effort]
#   WORKDIR   absolute folder the bot works in (Telegram has no "current directory")
# Backs up config.yaml, SOUL.md and memories first and restores the memory files,
# which apply-coder-profile.sh would otherwise empty. Restart the gateway afterwards.
set -eu
WORKDIR=${1:?usage: apply-telegram-default.sh WORKDIR [model] [base_url] [effort]}
MODEL=${2:-qwen3.8-27b-nvfp4}
BASE_URL=${3:-http://127.0.0.1:8000/v1}
EFFORT=${4-xhigh}   # pass "" for Ollama (no override)
KIT=$(cd "$(dirname "$0")/.." && pwd)
H=$HOME/.hermes
case $WORKDIR in /*) ;; *) echo "WORKDIR must be absolute" >&2; exit 1 ;; esac
mkdir -p "$WORKDIR"
[ -d "$WORKDIR/.git" ] || git -C "$WORKDIR" init -q   # test-gate hook only runs inside git repos

BK=$H/backup-default-$(date +%Y%m%d-%H%M%S)
mkdir -p "$BK"
cp -a "$H/config.yaml" "$BK/" 2>/dev/null || true
cp -a "$H/SOUL.md" "$BK/" 2>/dev/null || true
cp -a "$H/memories" "$BK/" 2>/dev/null || true
echo "backup: $BK"

bash "$KIT/profile/apply-coder-profile.sh" default "$MODEL" 65536 "$BASE_URL" "$EFFORT"

# Keep the bot's own memory files; memory stays switched off for coding turns.
[ -d "$BK/memories" ] && cp -a "$BK/memories/." "$H/memories/"

hermes config set terminal.cwd "$WORKDIR"
# Coding keeps three tools. The bot also answers questions that need current facts,
# so it keeps web (search and extract) and tts; without web it scrapes with curl,
# gets anti-bot pages, and burns its retry budget. See section 9.6.
for ts in browser vision image_gen memory session_search connections clarify \
          delegation cronjob computer_use code_execution skills; do
  hermes tools disable --platform telegram "$ts" >/dev/null 2>&1 || true
done
hermes tools enable --platform telegram terminal file todo tts web >/dev/null
echo "default profile ready: cwd $WORKDIR, model $MODEL at $BASE_URL"
echo "restart the gateway FROM A TERMINAL, not from the bot: hermes gateway status -> kill <PID> -> scripts/start-stack.sh"
HERMES_KIT_EOF
```

### scripts/make-agent-env.sh

```bash
cat > ~/hermes-coder-kit/scripts/make-agent-env.sh <<'HERMES_KIT_EOF'
#!/usr/bin/env bash
# Create the Python env the agent uses to run tests (pytest, ruff, common web/test deps).
# usage: make-agent-env.sh [env_name]   (default venv_hm; needs conda or miniconda)
set -eu
NAME=${1:-venv_hm}
CONDA=${CONDA_EXE:-$(command -v conda || echo "$HOME/miniconda3/bin/conda")}
"$CONDA" create -y -n "$NAME" python=3.12
P=$("$CONDA" run -n "$NAME" python -c 'import sys; print(sys.prefix)')
"$P/bin/pip" install -q pytest ruff flask requests httpx numpy
"$P/bin/python" -m pytest --version && "$P/bin/ruff" --version
echo "agent env: $P  (put it on PATH in ~/.hermes/shell_init.sh)"
HERMES_KIT_EOF
```

### scripts/check-setup.sh

```bash
cat > ~/hermes-coder-kit/scripts/check-setup.sh <<'HERMES_KIT_EOF'
#!/usr/bin/env bash
# Print the versions and live state that the setup guide depends on. Read-only.
# usage: check-setup.sh [profile ...]   (default: coder default)
set -u
PROFILES=("$@"); [ ${#PROFILES[@]} -eq 0 ] && PROFILES=(coder default)
VLLM_PY=${VLLM_PY:-$HOME/miniconda3/envs/dl/bin/python}
ok() { printf '  %-4s %s\n' "$1" "$2"; }

echo "[system]"
ok "" "$(uname -m), $( (lsb_release -ds || grep PRETTY /etc/os-release) 2>/dev/null | head -1)"
nvidia-smi --query-gpu=index,name,memory.total,power.limit --format=csv,noheader 2>/dev/null | sed 's/^/  gpu  /'
ok "" "node $(node --version 2>/dev/null || echo missing), aria2c $(command -v aria2c >/dev/null && echo ok || echo missing)"

echo "[engines]"
ok "" "$("$VLLM_PY" -c 'import vllm, torch; print("vllm", vllm.__version__, "torch", torch.__version__)' 2>/dev/null || echo "vllm env not found at $VLLM_PY")"
ok "" "$(ollama --version 2>/dev/null | tail -1 || echo 'ollama missing')"
curl -sf --max-time 3 http://127.0.0.1:8000/v1/models >/dev/null && ok OK "vllm :8000 serving $(curl -s http://127.0.0.1:8000/v1/models | python3 -c 'import json,sys; print(",".join(m["id"] for m in json.load(sys.stdin)["data"]))')" || ok "--" "vllm :8000 not serving"
curl -sf --max-time 3 http://127.0.0.1:11434/api/version >/dev/null && ok OK "ollama :11434 up, models: $(ollama list 2>/dev/null | awk 'NR>1{sub(/:latest$/,"",$1); print $1}' | grep -E '64k$' | paste -sd' ')" || ok "--" "ollama :11434 down"

echo "[hermes]"
ok "" "$(hermes --version 2>/dev/null | head -1)"
for p in "${PROFILES[@]}"; do
  if [ "$p" = default ]; then H="hermes"; C=$HOME/.hermes/config.yaml; else H="hermes -p $p"; C=$(hermes profile show "$p" 2>/dev/null | awk '/^Path:/ {print $2}')/config.yaml; fi
  [ -f "$C" ] || { ok "--" "profile $p missing"; continue; }
  python3 -c "import yaml" 2>/dev/null || { ok "--" "python3 yaml missing (pip install pyyaml) for profile summary"; continue; }
  python3 - "$p" "$C" <<'PY'
import sys, yaml
p, path = sys.argv[1:]
c = yaml.safe_load(open(path))
m, a, t = c.get("model", {}), c.get("agent", {}), c.get("terminal", {})
fb = ",".join(f.get("model", "?") for f in c.get("fallback_providers") or []) or "none"
print(f"  {p}: {m.get('default')} @ {m.get('base_url')} ctx={m.get('context_length')} "
      f"effort={(a.get('reasoning_overrides') or {}).get(m.get('default'), a.get('reasoning_effort'))} "
      f"verify_on_stop={a.get('verify_on_stop')} memory={c.get('memory', {}).get('memory_enabled')} "
      f"cwd={t.get('cwd')} hooks={','.join((c.get('hooks') or {}).keys()) or 'none'} fallback={fb}")
if p == "default":
    print(f"  default telegram tools: {(c.get('platform_toolsets') or {}).get('telegram')}")
PY
  $H hooks doctor 2>/dev/null | tail -1 | sed 's/^/  /'
done
grep -q '^TELEGRAM_BOT_TOKEN=.\+' "$HOME/.hermes/.env" 2>/dev/null && ok OK "telegram token set in ~/.hermes/.env" || ok "--" "telegram token not set"
hermes gateway status 2>/dev/null | head -1 | sed 's/^/  /'
HERMES_KIT_EOF
```

### telegram/setup-telegram.sh

```bash
cat > ~/hermes-coder-kit/telegram/setup-telegram.sh <<'HERMES_KIT_EOF'
#!/usr/bin/env bash
# Write Telegram credentials into ~/.hermes/.env after verifying them with Telegram.
# The token is read with hidden input and is never echoed or logged.
set -uo pipefail

ENV_FILE="$HOME/.hermes/.env"
[ -f "$ENV_FILE" ] || { echo "missing $ENV_FILE"; exit 1; }

printf 'Bot token (hidden, paste then Enter): '
IFS= read -rs TOKEN
printf '\n'
printf 'Your numeric Telegram user ID: '
IFS= read -r UID_IN
printf '\n'

TOKEN="$(printf '%s' "$TOKEN" | tr -d '[:space:]')"
UID_IN="$(printf '%s' "$UID_IN" | tr -d '[:space:]')"

[[ "$TOKEN" =~ ^[0-9]{6,}:[A-Za-z0-9_-]{30,}$ ]] || {
  echo "FAIL: token shape is wrong (expected digits:letters, ~46 chars). Nothing written."; exit 1; }
[[ "$UID_IN" =~ ^[0-9]{5,}$ ]] || {
  echo "FAIL: user ID must be digits only. Nothing written."; exit 1; }

echo "Verifying token with api.telegram.org ..."
RESP="$(curl -sS --max-time 20 "https://api.telegram.org/bot${TOKEN}/getMe")" || {
  echo "FAIL: could not reach Telegram. Nothing written."; exit 1; }

python3 - "$RESP" <<'PY' || exit 1
import json, sys
try:
    d = json.loads(sys.argv[1])
except Exception:
    print("FAIL: unparseable reply from Telegram. Nothing written."); sys.exit(1)
if not d.get("ok"):
    print("FAIL: Telegram rejected the token ->", d.get("description", "?"))
    print("Nothing written. Re-copy the token from @BotFather.")
    sys.exit(1)
r = d["result"]
print("OK  bot verified: @%s  (%s)" % (r.get("username"), r.get("first_name")))
PY

cp -p "$ENV_FILE" "${ENV_FILE}.bak-$(date +%Y%m%d-%H%M%S)"
sed -i '/^TELEGRAM_BOT_TOKEN=/d;/^TELEGRAM_ALLOWED_USERS=/d' "$ENV_FILE"
{
  echo ""
  echo "# Telegram gateway"
  echo "TELEGRAM_BOT_TOKEN=${TOKEN}"
  echo "TELEGRAM_ALLOWED_USERS=${UID_IN}"
} >> "$ENV_FILE"
chmod 600 "$ENV_FILE"

echo "Wrote TELEGRAM_BOT_TOKEN and TELEGRAM_ALLOWED_USERS to $ENV_FILE (mode 600)."
echo "Allowed user: ${UID_IN}"
unset TOKEN
HERMES_KIT_EOF
```

### bin/stt-whisper

```bash
cat > ~/hermes-coder-kit/bin/stt-whisper <<'HERMES_KIT_EOF'
#!/usr/bin/env bash
# Local speech-to-text for Hermes (HERMES_LOCAL_STT_COMMAND).
# usage: stt-whisper INPUT OUTPUT_DIR LANGUAGE MODEL  -> writes OUTPUT_DIR/<name>.txt
# Runs faster-whisper from the "stt" conda env on GPU (STT_DEVICE, default cuda:0), CPU int8 on failure.
set -u
ENV=${STT_ENV:-$HOME/miniconda3/envs/stt}
SP=$("$ENV/bin/python" -c 'import site; print(site.getsitepackages()[0])')
export LD_LIBRARY_PATH="$SP/nvidia/cublas/lib:$SP/nvidia/cudnn/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "$ENV/bin/python" -I - "$@" <<'PY'
import os, sys
from faster_whisper import WhisperModel
src, out_dir, lang, model = sys.argv[1:5]
model = os.environ.get("STT_MODEL") or ("large-v3-turbo" if model in ("", "base", "tiny") else model)
lang = None if lang in ("", "auto") else lang
dev = os.environ.get("STT_DEVICE", "cuda:0")
try:
    kind, _, idx = dev.partition(":")
    m = WhisperModel(model, device=kind, device_index=int(idx or 0), compute_type="float16")
    segs, info = m.transcribe(src, language=lang, vad_filter=True)
    text = " ".join(s.text.strip() for s in segs)
except Exception as e:
    print(f"gpu stt failed ({e}); using cpu", file=sys.stderr)
    m = WhisperModel(model, device="cpu", compute_type="int8")
    segs, info = m.transcribe(src, language=lang, vad_filter=True)
    text = " ".join(s.text.strip() for s in segs)
name = os.path.splitext(os.path.basename(src))[0]
open(os.path.join(out_dir, name + ".txt"), "w", encoding="utf-8").write(text.strip() + "\n")
PY
HERMES_KIT_EOF
```

### bin/tts-melo

```bash
cat > ~/hermes-coder-kit/bin/tts-melo <<'HERMES_KIT_EOF'
#!/usr/bin/env bash
# Local Korean text-to-speech for Hermes (tts.providers.melo, type: command).
# usage: tts-melo TEXT_FILE OUTPUT_PATH [speed]   -> OUTPUT_PATH as Ogg/Opus (Telegram voice note)
# Runs MeloTTS (KR) on CPU from the "tts" conda env; models come from the local HF cache only.
set -eu
ENV=${TTS_ENV:-$HOME/miniconda3/envs/tts}
IN=$1; OUT=$2; SPEED=${3:-1.1}
case $SPEED in ''|*[!0-9.]*) SPEED=1.1 ;; esac
WAV=$(mktemp --suffix=.wav)
trap 'rm -f "$WAV"' EXIT
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "$ENV/bin/python" -I - "$IN" "$WAV" "$SPEED" <<'PY' 2>/dev/null
import sys
from melo.api import TTS
src, wav, speed = sys.argv[1], sys.argv[2], float(sys.argv[3])
text = open(src, encoding="utf-8").read().strip()
m = TTS(language="KR", device="cpu")
m.tts_to_file(text, m.hps.data.spk2id["KR"], wav, speed=speed, quiet=True)
PY
ffmpeg -loglevel error -y -i "$WAV" -c:a libopus -b:a 32k -ac 1 -ar 48000 "$OUT"
HERMES_KIT_EOF
```

### bin/verify-webapp

```bash
cat > ~/hermes-coder-kit/bin/verify-webapp <<'HERMES_KIT_EOF'
#!/usr/bin/env bash
# verify-webapp: run the standard checks for a local Flask web app and print
# raw evidence. The agent pastes this output verbatim instead of describing it.
#
# Usage: verify-webapp <port> [route ...]
#   Run from the app directory (the one containing app.py). Routes default
#   to "/". If nothing listens on <port>, app.py is started in the background.
#
# Checks: route status codes, external URLs in the served page, browser
# console errors, two screenshots a few seconds apart. Exit 1 on any FAIL.
set -u
PORT="${1:?usage: verify-webapp <port> [route ...]}"; shift
ROUTES=("$@"); [ ${#ROUTES[@]} -eq 0 ] && ROUTES=("/")
BASE="http://127.0.0.1:$PORT"
OUT="/tmp/verify-$PORT"; mkdir -p "$OUT"
PY="${PYTHON:-python}"
CHROME="${CHROME:-google-chrome}"
CHROME_FLAGS=(--headless=new --disable-gpu --no-sandbox --use-gl=angle
              --use-angle=swiftshader --enable-unsafe-swiftshader)
FAIL=0

echo "== verify-webapp  port=$PORT  cwd=$PWD  $(date '+%F %T')"

# 1. server
if ss -ltn | grep -q ":$PORT "; then
  echo "server: already listening on :$PORT"
else
  [ -f app.py ] || { echo "FAIL: nothing on :$PORT and no app.py in $PWD"; exit 1; }
  setsid nohup "$PY" app.py > "$OUT/server.log" 2>&1 < /dev/null &
  for _ in $(seq 1 15); do sleep 1; ss -ltn | grep -q ":$PORT " && break; done
  if ss -ltn | grep -q ":$PORT "; then
    echo "server: started app.py (log: $OUT/server.log)"
  else
    echo "FAIL: app.py did not open :$PORT"; tail -20 "$OUT/server.log"; exit 1
  fi
fi

# 2. routes
echo "-- routes"
for r in "${ROUTES[@]}"; do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$BASE$r")
  printf '%-40s %s\n' "$r" "$code"
  [ "$code" = 200 ] || FAIL=1
done

# 3. external URLs referenced by the page
echo "-- external URLs"
curl -s --max-time 10 "$BASE/" -o "$OUT/index.html"
urls=$(grep -oE 'https?://[^"'"'"' <>)]+' "$OUT/index.html" | sort -u)
[ -z "$urls" ] && echo "(none)"
for u in $urls; do
  code=$(curl -sIL --max-time 15 -o /dev/null -w '%{http_code}' "$u")
  printf '%-90s %s\n' "$u" "$code"
  [ "$code" = 200 ] || FAIL=1
done

# 4. browser console
echo "-- browser console"
"$CHROME" "${CHROME_FLAGS[@]}" --enable-logging=stderr --v=0 \
  --virtual-time-budget=10000 --dump-dom "$BASE/" > /dev/null 2> "$OUT/console.log"
errs=$(grep -a 'CONSOLE' "$OUT/console.log" | grep -aiE 'Uncaught|Error|Failed to load|net::ERR|404' || true)
n=$(printf '%s' "$errs" | grep -c . || true)
echo "console errors: $n"
if [ "$n" -gt 0 ]; then printf '%s\n' "$errs" | cut -c1-300 | head -20; FAIL=1; fi

# 5. screenshots at two points in virtual time
echo "-- screenshots"
for i in 1 2; do
  "$CHROME" "${CHROME_FLAGS[@]}" --window-size=1600,900 \
    --virtual-time-budget=$((8000 + 4000 * i)) --screenshot="$OUT/shot$i.png" "$BASE/" > /dev/null 2>&1
  if [ -s "$OUT/shot$i.png" ]; then
    echo "$OUT/shot$i.png  $(stat -c %s "$OUT/shot$i.png") bytes"
  else
    echo "FAIL: screenshot $i missing"; FAIL=1
  fi
done
echo "next: vision_analyze both screenshots (shot2 is 4 s of animation after shot1) and list what is visible"

if [ "$FAIL" -eq 0 ]; then echo "== RESULT: PASS"; else echo "== RESULT: FAIL"; fi
exit "$FAIL"
HERMES_KIT_EOF
```


Set permissions and check:

```bash
chmod 755 ~/hermes-coder-kit/profile/*.sh ~/hermes-coder-kit/hooks/*.py ~/hermes-coder-kit/vllm/* ~/hermes-coder-kit/ollama/* ~/hermes-coder-kit/scripts/* ~/hermes-coder-kit/telegram/* ~/hermes-coder-kit/bin/*
for f in ~/hermes-coder-kit/profile/*.sh ~/hermes-coder-kit/vllm/* ~/hermes-coder-kit/ollama/* ~/hermes-coder-kit/scripts/*.sh ~/hermes-coder-kit/telegram/* ~/hermes-coder-kit/bin/*; do bash -n "$f" || echo "syntax error: $f"; done
python3 -m py_compile ~/hermes-coder-kit/hooks/*.py ~/hermes-coder-kit/scripts/download-models.py && echo ok
~/hermes-coder-kit/scripts/detect-tier.sh "$GPU"
```

Expected: no `syntax error` lines, `ok`, and a tier line. Tell the human which tier was detected.


## 5. Base tools and vLLM

    sudo apt update
    sudo apt install -y git curl aria2 ffmpeg build-essential python3-yaml nodejs npm

Install Miniconda if conda is missing (download, read, then run):

    curl -fsSL https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-$(uname -m).sh -o ~/miniconda.sh
    bash ~/miniconda.sh -b -p $HOME/miniconda3
    $HOME/miniconda3/bin/conda init bash

Skip the rest of this section on the `small` tier.

vLLM on x86_64:

    ~/miniconda3/bin/conda create -y -n dl python=3.12
    ~/miniconda3/envs/dl/bin/pip install vllm==0.27.1 "huggingface_hub[cli]"
    ~/miniconda3/envs/dl/bin/python -c "import vllm, torch; print(vllm.__version__, torch.__version__, torch.cuda.is_available())"

Expected: `0.27.1 2.13.0+cu130 True` (reference: torch 2.13.0+cu130, flashinfer-python 0.6.16.post3, transformers 5.15.0). If it is not True, fix the driver and CUDA version first.

arm64 (GB10 / DGX Spark): use NVIDIA's vLLM container (the vllm image on nvcr.io) or an official arm64 wheel instead of the PyPI wheel. If the `vllm` binary lives elsewhere, set `VLLM_BIN=path` when starting the server.


## 6. Models and the vLLM server

Skip on the `small` tier. The `mem64` tier does not need the draft model; download only `nvidia/Qwen3.8-27B-NVFP4` there (the script fetches both, the draft is 4 GB).

    ~/miniconda3/envs/dl/bin/python ~/hermes-coder-kit/scripts/download-models.py --verify qwen
    ~/miniconda3/envs/dl/bin/python ~/hermes-coder-kit/scripts/download-models.py --dry-run qwen

Expected: both lines end in `0 to fetch`. The script uses aria2c with 16 connections per file and checks sha256 against the Hub (reference: 45 to 50 MB/s; `hf download` managed 2 MB/s). Re-run it to resume.

Start the server with the tier settings:

    mkdir -p ~/.hermes/bin ~/.hermes/logs
    install -m 755 ~/hermes-coder-kit/vllm/start-vllm ~/.hermes/bin/start-vllm
    GPU=0 ~/hermes-coder-kit/scripts/start-stack.sh --no-ollama --no-gateway

Replace `GPU=0` with the chosen GPU. The first start compiles kernels and takes 4 to 7 minutes; the script waits up to 15. The log is `~/.hermes/logs/vllm-8000.log`. Any of `SPEC`, `KV_CACHE_GIB`, `MAX_SEQS`, `GPU_UTIL` set in the environment overrides the tier.

    curl -s http://127.0.0.1:8000/v1/models
    grep -E "GPU KV cache size|Maximum concurrency" ~/.hermes/logs/vllm-8000.log

Expected: `qwen3.8-27b-nvfp4` is listed; on gpu96 the KV cache is about 170K tokens. Quick request:

    curl -s http://127.0.0.1:8000/v1/chat/completions -H 'Content-Type: application/json' -d '{"model":"qwen3.8-27b-nvfp4","max_tokens":50,"chat_template_kwargs":{"enable_thinking":false},"messages":[{"role":"user","content":"Say OK"}]}'


## 7. Ollama fallback

This is where Hermes goes when vLLM is down, and the only server on the `small` tier.

    curl -fsSL https://ollama.com/install.sh -o ~/ollama-install.sh
    less ~/ollama-install.sh
    sh ~/ollama-install.sh
    curl -sf http://127.0.0.1:11434/api/version || ~/hermes-coder-kit/ollama/start-ollama
    ollama pull qwen3.8:27b-mtp-q4_K_M
    ~/hermes-coder-kit/ollama/mkctx.sh qwen3.8:27b-mtp-q4_K_M qwen3.8-27b-64k 65536
    ollama list | grep qwen3.8-27b-64k

If the installer set Ollama up as a systemd service, put these in the service environment instead (`sudo systemctl edit ollama`, add `Environment=` lines, restart): `OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KV_CACHE_TYPE=q8_0`, `OLLAMA_NUM_PARALLEL=1`, and `OLLAMA_KEEP_ALIVE` from the tier table. Qwen3.8 needs Ollama 0.32.12 or later. `mkctx.sh` pins the context to 65536; otherwise Ollama ignores the context Hermes asks for and grows to 262K tokens.


## 8. Hermes and the profiles

Python env the agent uses to run tests, shell init, and the web-app checker:

    ~/hermes-coder-kit/scripts/make-agent-env.sh venv_hm
    mkdir -p ~/.hermes && cp ~/hermes-coder-kit/profile/shell_init.sh.example ~/.hermes/shell_init.sh
    install -m 755 ~/hermes-coder-kit/bin/verify-webapp ~/.hermes/bin/verify-webapp

To keep the agent's own code off the model GPU, uncomment `CUDA_VISIBLE_DEVICES` in `~/.hermes/shell_init.sh` and point it at another GPU.

Install Hermes:

    curl -fsSL https://hermes-agent.nousresearch.com/install.sh -o ~/hermes-install.sh
    less ~/hermes-install.sh
    bash ~/hermes-install.sh
    hermes --version

The coder profile (terminal) and an Ollama-only spare profile:

    bash ~/hermes-coder-kit/profile/apply-coder-profile.sh coder qwen3.8-27b-nvfp4 65536 http://127.0.0.1:8000/v1 xhigh
    bash ~/hermes-coder-kit/profile/apply-coder-profile.sh coderollama qwen3.8-27b-64k 65536
    for p in coder coderollama; do
      hermes -p $p config set terminal.shell_init_files '["~/.hermes/shell_init.sh"]'
      hermes -p $p config set model.supports_vision true
      hermes -p $p config set agent.image_input_mode native
    done

On the `small` tier make coder use Ollama: `bash ~/hermes-coder-kit/profile/apply-coder-profile.sh coder qwen3.8-27b-64k 65536`.

The last argument `xhigh` matters: the Qwen3.8 chat template accepts reasoning effort low, medium or xhigh, and rejects Hermes' default `high` with HTTP 400. For a non-Ollama endpoint the script also adds the Ollama model as `fallback_providers`. `image_input_mode native` is needed because Hermes cannot tell that a self-hosted model sees images, and an `auxiliary.vision` model, if configured, would otherwise take over.

Check:

    ~/hermes-coder-kit/scripts/check-setup.sh coder
    mkdir -p ~/work/smoke && cd ~/work/smoke && git init -q
    hermes -p coder chat -q "Write add(a, b) in calc.py with pytest tests and run them" --oneshot
    tail -1 ~/.hermes/profiles/coder/logs/test-gate.log

Expected: the coder line reads `qwen3.8-27b-nvfp4 @ http://127.0.0.1:8000/v1 ctx=65536 effort=xhigh verify_on_stop=True memory=False cwd=. hooks=pre_verify,pre_tool_call fallback=qwen3.8-27b-64k`, then `All shell hooks look healthy`, and the last test-gate line ends in `pass`.


## 9. Telegram bot, images, voice, streaming

Skip 9.1 to 9.3 and 9.6 if the human does not want the bot.

9.1 Token. The human runs this themselves; the agent only explains it.

    bash ~/hermes-coder-kit/telegram/setup-telegram.sh

It reads the token without echo, checks it with Telegram, and writes it to `~/.hermes/.env` (mode 600). Only the given user id may talk to the bot.

9.2 Give the default profile (the bot) the coder setup:

    ~/hermes-coder-kit/scripts/apply-telegram-default.sh "$WORKDIR"
    hermes config set terminal.shell_init_files '["~/.hermes/shell_init.sh"]'
    hermes config set model.supports_vision true
    hermes config set agent.image_input_mode native
    hermes config set streaming.enabled true
    hermes config set streaming.transport auto

On the `small` tier: `~/hermes-coder-kit/scripts/apply-telegram-default.sh "$WORKDIR" qwen3.8-27b-64k http://127.0.0.1:11434/v1 ""`.

The script backs up `config.yaml`, `SOUL.md` and `memories` to `~/.hermes/backup-default-<timestamp>`, sets the working folder (running `git init` if needed, because the test gate only runs inside git repositories), limits the Telegram tools to terminal, file, todo, tts and web (9.6), and restores the memory files. Streaming is off by default in Hermes; without it the bot sends nothing until the whole answer is done.

9.3 Gateway:

    ~/hermes-coder-kit/scripts/start-stack.sh
    hermes gateway status
    grep "telegram connected" ~/.hermes/logs/gateway.log | tail -1

9.4 Speech-to-text (optional). faster-whisper in its own env. PyAV 17+ breaks faster-whisper 1.2.1, so pin it below 17.

    ~/miniconda3/bin/conda create -y -n stt python=3.12
    ~/miniconda3/envs/stt/bin/pip install faster-whisper nvidia-cublas-cu12 "nvidia-cudnn-cu12==9.*" "av<17"
    install -m 755 ~/hermes-coder-kit/bin/stt-whisper ~/.hermes/bin/stt-whisper
    grep -q '^HERMES_LOCAL_STT_COMMAND=' ~/.hermes/.env || echo "HERMES_LOCAL_STT_COMMAND=\"$HOME/.hermes/bin/stt-whisper {input_path} {output_dir} {language} {model}\"" >> ~/.hermes/.env
    hermes config set stt.language ko
    hermes config set stt.local.model large-v3-turbo

The value in `.env` must be in double quotes. Use your own language code for `stt.language` (ko, en, ...). `stt-whisper` runs on cuda:0 and falls back to the CPU; set `STT_DEVICE=cuda:1` in `.env` for another GPU. The model (about 1.6 GB) downloads on first use and loads only while transcribing. Check:

    ffmpeg -loglevel error -f lavfi -i "sine=frequency=440:duration=1" -y /tmp/stt-test.wav
    mkdir -p /tmp/stt-out && ~/.hermes/bin/stt-whisper /tmp/stt-test.wav /tmp/stt-out en base && ls /tmp/stt-out

Expected: `stt-test.txt` exists (it may be empty; a real check is a Telegram voice message). Reference: a 10-second Korean voice note transcribed correctly in about 8 seconds.

9.5 Text-to-speech (optional). Hermes' default TTS (edge) sends the answer text to Microsoft, so use MeloTTS locally on the CPU (MIT license). `tts-melo` speaks Korean (`language="KR"`); for another language change `KR` in `bin/tts-melo` and in the warm-up line to one MeloTTS supports (EN, JP, ZH, ES, FR).

    ~/miniconda3/bin/conda create -y -n tts python=3.10
    mkdir -p ~/.hermes/tts && git clone --depth 1 https://github.com/myshell-ai/MeloTTS.git ~/.hermes/tts/MeloTTS
    ~/miniconda3/envs/tts/bin/pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
    ~/miniconda3/envs/tts/bin/pip install -e ~/.hermes/tts/MeloTTS "setuptools<70" python-mecab-ko
    ~/miniconda3/envs/tts/bin/python -m unidic download
    ~/miniconda3/envs/tts/bin/python -c "from melo.api import TTS; m=TTS(language='KR', device='cpu'); m.tts_to_file('설치 확인', m.hps.data.spk2id['KR'], '/tmp/tts-warm.wav')"
    install -m 755 ~/hermes-coder-kit/bin/tts-melo ~/.hermes/bin/tts-melo
    hermes config set tts.provider melo
    hermes config set --force tts.providers.melo.type command
    hermes config set --force tts.providers.melo.command "$HOME/.hermes/bin/tts-melo {input_path} {output_path} {speed}"
    hermes config set --force tts.providers.melo.output_format ogg
    hermes config set --force tts.providers.melo.voice_compatible true
    hermes config set --force tts.providers.melo.timeout 180

The warm-up line downloads the voice and BERT models once; after that `tts-melo` runs offline. Check:

    echo '음성 답장 시험입니다.' > /tmp/tts-in.txt && ~/.hermes/bin/tts-melo /tmp/tts-in.txt /tmp/tts-out.ogg && ffprobe -v error -show_entries stream=codec_name -of csv /tmp/tts-out.ogg

Expected: `stream,opus`. About 8 seconds per sentence and 2.5 GB of RAM while speaking. If 9.4 is installed, transcribe `/tmp/tts-out.ogg` with `stt-whisper` and compare.

9.6 Web search. The bot gets asked questions that need current facts, not only coding tasks. With no search tool it falls back to `curl` against Google or DuckDuckGo, receives an anti-bot or JavaScript page, reads it as an empty result, and retries until the loop guardrail stops it with `identical_cycle_halt`. Give it the `web` toolset and a search backend.

    hermes pm install --extra ddgs
    hermes tools enable --platform telegram web
    hermes tools list --platform telegram

`ddgs` is the keyless backend: DuckDuckGo, no API key, no account, nothing leaves the machine except the query itself. `hermes pm install --extra ddgs` records the extra, so `hermes update` keeps it. `apply-telegram-default.sh` already enables the toolset; the `enable` line above is for an installation made before that change.

Expected from `tools list`: `✓ enabled web`, alongside `terminal`, `file`, `todo` and `tts`. Restart the gateway, then ask the bot something it cannot answer from the model alone, such as a release version from this month, and check that the answer cites pages rather than guessing.

Two notes:

- Do not put `stt` in `platform_toolsets`. It is not a toolset with tools behind it, and the config validator rejects it. Inbound voice is transcribed by the gateway from `stt.enabled` (9.4), with no agent tool involved.
- For better result quality than DuckDuckGo, set `BRAVE_SEARCH_API_KEY`, `TAVILY_API_KEY`, `SERPER_API_KEY` or `EXA_API_KEY` in `~/.hermes/.env`; Hermes prefers a keyed backend over the keyless one. This sends queries to that vendor, so on an air-gapped or NDA-bound machine stay on `ddgs`.

Searching is not the same as judging. Measure the bot's answers the way you would any other source: a query that returns a result count is not evidence that a claim is true.

9.7 Restart the gateway after any config change. Get the PID from `hermes gateway status`, make sure the bot is idle (the last `API call` time in `~/.hermes/logs/agent.log`), `kill PID`, then `~/hermes-coder-kit/scripts/start-stack.sh`.

Run this from a terminal, never from the bot. A restart asked of the bot kills the process the bot is running in: the turn ends mid-answer, nothing starts the gateway again, and Telegram messages sent meanwhile are dropped on the next cold boot. Hermes flags the command, but smart approval can approve it on its own, so the rule has to hold in section 0 rather than at the prompt. `hermes gateway install` creates a user service that comes back by itself; it was not tested on the reference machine.

Telegram usage: send coding requests as text, photos or voice notes. `/voice on` answers voice with voice, `/voice tts` answers everything with voice too, `/voice off` turns it off. `/new` starts a fresh conversation; start each new task with it, because long chats trigger context compression waits.


## 10. Checklist (the agent fills this in and reports)

    Item                     How                                                    Result
    tier                     scripts/detect-tier.sh
    vLLM server              curl http://127.0.0.1:8000/v1/models
    vLLM speed               speed test below
    Ollama fallback          ollama list | grep 64k
    coder profile            scripts/check-setup.sh coder
    coder real task          section 8 smoke test, test-gate.log pass
    image input              hermes chat -q "Describe this image" --image some.png --oneshot
    Telegram connection      "telegram connected" in gateway.log
    speech-to-text           9.4 check
    text-to-speech           9.5 check
    web search               hermes tools list --platform telegram | grep web
    Telegram in practice     the human sends text, a photo and a voice note
    Telegram research        ask the bot a question needing a current fact; the answer cites pages

Speed test (reference gpu96: code about 246 tok/s, prose about 118 tok/s; the numbers below include prefill):

```bash
python3 - <<'PY'
import json, time, urllib.request
def run(prompt, n=400):
    body = {"model": "qwen3.8-27b-nvfp4", "max_tokens": n, "stream": False,
            "chat_template_kwargs": {"enable_thinking": False},
            "messages": [{"role": "user", "content": prompt}]}
    t = time.time()
    r = json.load(urllib.request.urlopen(urllib.request.Request(
        "http://127.0.0.1:8000/v1/chat/completions", json.dumps(body).encode(),
        {"Content-Type": "application/json"}), timeout=300))
    u = r["usage"]; dt = time.time() - t
    print(f"{prompt[:30]:32} out={u['completion_tokens']} {u['completion_tokens']/dt:.0f} tok/s")
run("Write a Python LRU cache class with type hints and pytest tests.")
run("Explain how TCP congestion control works.")
PY
```

Generation speed scales with memory bandwidth: a GB10 / DGX Spark is roughly one sixth of the reference GPU. The full 9-task benchmark is in the `bench/` folder of the repository this file comes from.


## 11. After a reboot

vLLM, Ollama (when started by hand) and the gateway do not start on their own.

    ~/hermes-coder-kit/scripts/start-stack.sh

Prefix `GPU=1` or `MODEL_DIR=...` if they differ. Telegram requests that arrive before vLLM is ready go to the Ollama fallback, just slower. `hermes gateway install` can create a user service for the gateway; that path was not tested on the reference machine.


## 12. Troubleshooting

    vLLM dies with CUDA illegal memory access     spec decoding with chunked prefill. Use start-vllm, which sets
                                                  --max-num-batched-tokens to the context length when a draft is on
    HTTP 400 Unexpected reasoning effort high      agent.reasoning_overrides needs "qwen3.8-27b-nvfp4": "xhigh"
    vLLM out of memory at start                    another process on that GPU, or the tier is too big: set
                                                  SPEC=0 KV_CACHE_GIB=5 (the mem64 settings)
    Spark freezes or reboots                       lower GPU_UTIL, MAX_SEQS=1, or use the mem64 settings
    "Model fallback" on every answer               vLLM is down: start-stack.sh
    the model does not see Telegram photos         agent.image_input_mode must be native; restart the gateway
    voice: No STT provider available               HERMES_LOCAL_STT_COMMAND in .env must be double-quoted; restart
    stt-whisper: metadata_errors                   pip install "av<17" in the stt env
    MeloTTS: No module named pkg_resources         pip install "setuptools<70" in the tts env
    MeloTTS: mecabrc not found                     python -m unidic download in the tts env
    Telegram answer arrives all at once            streaming.enabled true, then restart the gateway
    "Dual-stack api.telegram.org path failed"      the gateway recovers through another route; ignore if "recovered" follows
    hooks do not run                               hermes -p coder hooks doctor; the folder must be a git repo
    the agent stops before installing a package    install-guard is waiting for approval; approve, or preinstall in venv_hm
    "Tool guardrail halted terminal:               the agent retried one command with no progress. Usually a missing
    identical_cycle_halt"                          tool, not a bad model: check the tool it kept reaching for (9.6)
    the bot curls Google and gets nothing          the web toolset is off; section 9.6. Google serves curl an
                                                  anti-bot page, so a 200 response can still carry no results
    the bot went silent after a config change      it restarted the gateway it runs in; see 9.7. Start the gateway
                                                  from a terminal: nothing supervises it unless you installed a service
    "unknown toolset 'stt'"                        remove stt from platform_toolsets; transcription is stt.enabled (9.4)
    web_search returns no results                  hermes pm install --extra ddgs, then restart the gateway

Undo: copy the files from `~/.hermes/backup-default-<timestamp>` back to `~/.hermes` and restart the gateway. For the coder profile, `hermes profile delete coder` and redo section 8.


## 13. References

    Hermes docs          https://hermes-agent.nousresearch.com/docs/user-guide/local-models
    Main model           https://huggingface.co/nvidia/Qwen3.8-27B-NVFP4
    Draft model          https://huggingface.co/RedHatAI/Qwen3.8-27B-speculator.dspark
    vLLM on DGX Spark    https://vllm.ai/blog/2026-06-01-vllm-dgx-spark
    Spark memory notes   https://forums.developer.nvidia.com/t/memory-creep-on-dgx-spark-where-your-128-gb-actually-goes-and-how-to-stop-it/364886
    Spark measurements   https://blog.kubesimplify.com/qwen3-8-27b-on-dgx-spark
    MeloTTS              https://github.com/myshell-ai/MeloTTS
    faster-whisper       https://github.com/SYSTRAN/faster-whisper
