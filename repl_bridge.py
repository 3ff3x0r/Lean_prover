# repl_bridge.py
import json
import subprocess
import config

def create_theorem_file(params: str, proposition: str, proof_script: str = "sorry"):
    content = (
        "import Mathlib\n\n"
        "def user_theorem " + params + " : " + proposition + " := by\n"
        "  " + proof_script.replace("\n", "\n  ") + "\n"
    )
    with open(config.LEAN_FILE, "w", encoding="utf-8") as f:
        f.write(content)

def spawn_repl():
    return subprocess.Popen(
        [config.LAKE_BIN, "env", config.REPL_BIN],
        cwd=config.CWD,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1
    )

def read_json_frame(proc) -> dict:
    buffer = ""
    while True:
        line = proc.stdout.readline()
        if not line:
            if proc.poll() is not None:
                raise ConnectionResetError("lean4-repl process terminated unexpectedly.")
            break
        buffer += line
        try:
            parsed = json.loads(buffer)
            config.debug_print("REPL JSON OUTPUT", json.dumps(parsed, indent=2))
            return parsed
        except json.JSONDecodeError:
            continue
    raise RuntimeError("Unparseable JSON frame received from REPL:\n" + buffer)
