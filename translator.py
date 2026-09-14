import json
import sys
from llm_client import query_llm

def translate_prompt_to_lean(user_prompt: str) -> dict:
    prompt = (
        "SYSTEM: Output ONLY a valid JSON object. No explanations, no prose, no conversational filler.\n\n"
        "You are a Lean 4 formalization assistant using Mathlib.\n"
        "Translate the user request into a formal Lean 4 declaration.\n\n"
        "User Request: \"" + user_prompt + "\"\n\n"
        "Instructions:\n"
        "1. Output ONLY a valid JSON object with keys \"params\" and \"proposition\".\n"
        "2. Do NOT include any text outside the JSON object.\n"
        "3. \"params\": variable binders (e.g., \"(n m : ℕ)\" or \"\").\n"
        "4. \"proposition\": the Lean 4 core statement or target type.\n"
        "5. For infinite set equipollence/bijections, use subtype equivalence notation:\n"
        "   `Equiv {n : ℕ // Even n} {n : ℕ // Odd n}`\n\n"
        "JSON Schema:\n"
        "{\n"
        "  \"params\": \"<binders or empty string>\",\n"
        "  \"proposition\": \"<formal statement>\"\n"
        "}\n"
    )
    
    raw_response = query_llm(prompt)
    
    start_idx = raw_response.find('{')
    end_idx = raw_response.rfind('}')
    
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        json_str = raw_response[start_idx:end_idx+1]
        try:
            parsed = json.loads(json_str)
            if "params" in parsed and "proposition" in parsed:
                return parsed
        except json.JSONDecodeError:
            print("  ├─ [!] Translation AST decode error: " + json_str)

    print("  ├─ [!] Translation failed to output structured AST from model:\n" + raw_response)
    sys.exit(1)
