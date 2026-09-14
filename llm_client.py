# llm_client.py
import re
import sys
import requests
import config

def query_llm(prompt: str, temperature: float = 0.1, max_tokens: int = 4096) -> str:
    payload = {
        "model": config.MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,  # Explicitly force non-streaming payload
        "options": {
            "num_predict": max_tokens,
            "temperature": temperature
        }
    }
    
    # Disable persistent HTTP connections to prevent queue locking
    headers = {
        "Content-Type": "application/json",
        "Connection": "close"
    }
    
    config.debug_print("LLM PROMPT", prompt)
    
    try:
        # Short connection timeout (5s), 60s read timeout
        with requests.Session() as session:
            session.headers.update(headers)
            response = session.post(config.LLM_URL, json=payload, timeout=(None))
            res = response.json()
        
        config.debug_print("LLM RAW JSON RESPONSE", str(res))
        
        if "error" in res:
            print("[!] Server returned an error payload:")
            print(res["error"])
            sys.exit(1)
            
        if "choices" not in res or not res["choices"]:
            print(f"[!] Invalid API response schema. Full payload: {res}")
            sys.exit(1)
            
        msg = res["choices"][0]["message"]
        content = msg.get("content", "") or ""
        reasoning = msg.get("reasoning", "") or ""

        raw_text = content.strip() if content.strip() else reasoning.strip()
        cleaned = re.sub(r'<think>.*?</think>', '', raw_text, flags=re.DOTALL).strip()
        return cleaned
        
    except Exception as e:
        print(f"[!] LLM HTTP execution error: {e}")
        sys.exit(1)
