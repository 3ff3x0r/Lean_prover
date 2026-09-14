# tactic_generator.py
import re
from llm_client import query_llm
import config

def propose_full_proof(goal_state: str, history: list) -> str:
    history_str = ""
    if history:
        history_str = "\nPrevious failed proof candidates and Lean 4 kernel errors:\n"
        for idx, (candidate, err) in enumerate(history, 1):
            history_str += f"\n--- Attempt {idx} ---\nCandidate:\n{candidate}\nKernel Error:\n{err}\n"

    prompt = (
        "SYSTEM: Output ONLY raw Lean 4 code inside a markdown block. Zero explanations. Zero prose.\n\n"
        "You are an expert Lean 4 formal mathematician using Mathlib.\n"
        "Provide a complete, valid Lean 4 proof script (`by ...`) to solve the following target declaration:\n\n"
        "Target Goal State:\n```lean\n" + goal_state + "\n```\n"
        + history_str + "\n"
        "STRICT RULES:\n"
        "1. Output ONLY the ```lean ... ``` code block containing the proof script.\n"
        "2. Do NOT output any explanations, commentary, or text outside the code block.\n"
        "3. Do NOT use `sorry` or `admit`."
    )
    
    raw_response = query_llm(prompt)
    
    match = re.search(r'```(?:lean)?\s*(.*?)\s*```', raw_response, re.DOTALL)
    if match:
        proof_text = match.group(1).strip()
    else:
        proof_text = re.sub(r'`', '', raw_response).strip()
        
    config.debug_print("PARSED WHOLE PROOF CANDIDATE", proof_text)
    return proof_text
