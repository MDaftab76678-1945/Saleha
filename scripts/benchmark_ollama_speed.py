"""
Benchmark Saleha-ASI inference speed in Ollama
Measures tokens/second, time-to-first-token, and response latency.
"""

import json
import os
import sys
import time
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def benchmark():
    prompt = "Write a complete Python implementation of an LRU Cache with O(1) get and put using a Doubly Linked List and a Hash Map."
    url = "http://127.0.0.1:11434/api/generate"
    payload = {
        "model": "saleha-asi",
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_predict": 350,
        },
    }

    print("🚀 Querying Saleha-ASI via Ollama C++ CUDA Engine...")
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    t0 = time.time()
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode("utf-8"))
    total_latency = time.time() - t0

    eval_count = res.get("eval_count", 0)
    eval_duration_ns = res.get("eval_duration", 1)
    prompt_eval_count = res.get("prompt_eval_count", 0)
    prompt_eval_duration_ns = res.get("prompt_eval_duration", 1)

    eval_duration_sec = eval_duration_ns / 1e9
    prompt_eval_sec = prompt_eval_duration_ns / 1e9
    eval_speed = eval_count / max(eval_duration_sec, 0.001)
    prompt_speed = prompt_eval_count / max(prompt_eval_sec, 0.001)

    print("\n" + "=" * 60)
    print("      ⚡ SALEHA-ASI OLLAMA INFERENCE SPEED BENCHMARK ⚡")
    print("=" * 60)
    print(f"Model Name           : saleha-asi:latest")
    print(f"Prompt Tokens        : {prompt_eval_count} tokens ({prompt_speed:.1f} tok/s)")
    print(f"Generated Tokens     : {eval_count} tokens")
    print(f"Generation Duration  : {eval_duration_sec:.2f} seconds")
    print(f"⚡ Generation Speed  : {eval_speed:.1f} TOKENS / SECOND")
    print(f"Total Wall Latency   : {total_latency:.2f} seconds")
    print("=" * 60)
    print("\nModel Output Excerpt:")
    print("-" * 60)
    print(res.get("response", "")[:400] + "...")
    print("-" * 60)


if __name__ == "__main__":
    benchmark()
