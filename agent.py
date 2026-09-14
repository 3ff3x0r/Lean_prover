# agent.py
import json
import sys
import config
from translator import translate_prompt_to_lean
from repl_bridge import create_theorem_file, spawn_repl, read_json_frame
from tactic_generator import propose_full_proof

def run_agent(user_prompt: str):
    print("\n[Prompt Received] \"" + user_prompt + "\"")
    print(" ├─ [Pass 1] Formalizing request via LLM...")
    
    spec = translate_prompt_to_lean(user_prompt)
    params = spec["params"]
    prop = spec["proposition"]
    
    print(" │  └─ Formal Signature: def user_theorem " + params + " : " + prop)
    print(" ├─ [Pass 2] Initializing Lean 4 Kernel Engine...")
    
    # Verify declaration signature syntax with sorry first
    create_theorem_file(params, prop, "sorry")
    proc = spawn_repl()
    
    proc.stdin.write(json.dumps({"path": config.LEAN_FILE}) + "\n\n")
    proc.stdin.flush()
    res = read_json_frame(proc)
    proc.terminate()
    
    has_init_error = "messages" in res and any(m.get("severity") == "error" for m in res["messages"])
    if has_init_error or "sorries" not in res or not res["sorries"]:
        print(" │  └─ [!] AST Parse Error: Lean kernel rejected the declaration signature.")
        return

    sorry_obj = res["sorries"][0]
    goal_state = sorry_obj["goal"]
    
    print(" ├─ [Pass 3] Executing Whole-Proof Search & Kernel Verification...")
    attempt_history = []
    
    max_attempts = 5
    for attempt in range(1, max_attempts + 1):
        print(f" │  ├─ Whole-Proof Generation Attempt {attempt}/{max_attempts}...")
        
        proof_candidate = propose_full_proof(goal_state, attempt_history)
        
        # Write complete proof candidate to file and check kernel
        create_theorem_file(params, prop, proof_candidate)
        proc = spawn_repl()
        
        proc.stdin.write(json.dumps({"path": config.LEAN_FILE}) + "\n\n")
        proc.stdin.flush()
        verify_res = read_json_frame(proc)
        proc.terminate()
        
        messages = verify_res.get("messages", [])
        sorries = verify_res.get("sorries", [])
        
        errors = [m["data"] for m in messages if m.get("severity") == "error"]
        has_sorry = len(sorries) > 0 or any("sorry" in m.get("data", "") for m in messages)
        
        if not errors and not has_sorry:
            print(" │  └─ [Kernel Certified] Proof verified with 0 errors!")
            print("\n └─ [COMPLETE] Certified Proof:\n")
            print("```lean")
            print("import Mathlib\n")
            print(f"def user_theorem {params} : {prop} := by")
            print("  " + proof_candidate.replace("\n", "\n  "))
            print("```\n")
            return
        else:
            err_msg = "\n".join(errors) if errors else "Proof contains unclosed goals / sorries."
            config.debug_print("KERNEL REJECTION REASON", err_msg)
            print(f" │  └─ [!] Attempt {attempt} Rejected by Kernel.")
            attempt_history.append((proof_candidate, err_msg))
            
    print(" └─ [!] Proof Search Exhausted: Could not verify complete proof script.")

if __name__ == "__main__":
    args = sys.argv[1:]
    if "--debug" in args:
        config.DEBUG = True
        args.remove("--debug")
    prompt_input = " ".join(args) if args else "Prove that there is the same number of even and odd numbers"
    run_agent(prompt_input)
