"""
Benchmark local Ollama inference speed.
Measures tokens/second, time-to-first-token, and response latency.

Usage:
    python scripts/benchmark_ollama_speed.py [model]

Defaults to SALEHA_BENCH_MODEL, else qwen2.5-coder:3b.

History: this script hardcoded `saleha-asi`, a custom fine-tune that was
removed from Ollama after real-testing it scored 0/5 on held-out tasks (its
training data turned out to contain fabricated rows -- see COORDINATION.md
Round 8). Every run therefore failed with a 404 from the daemon. The model is
now a parameter, and a missing model is reported plainly instead of as a
stack trace.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_MODEL = os.environ.get("SALEHA_BENCH_MODEL", "qwen2.5-coder:3b")


def _host() -> str:
    """
    Ollama's own OLLAMA_HOST is conventionally scheme-less (`0.0.0.0:11434`),
    which urllib cannot open. Add the scheme, and treat a wildcard bind
    address as localhost -- 0.0.0.0 says where the daemon listens, not an
    address a client can connect to.
    """
    raw = (os.environ.get("OLLAMA_HOST") or "127.0.0.1:11434").strip()
    if "://" not in raw:
        raw = "http://" + raw
    return raw.replace("://0.0.0.0", "://127.0.0.1").rstrip("/")


OLLAMA_HOST = _host()


def available_models():
    """Model names the local daemon actually has, or None if it is unreachable."""
    try:
        with urllib.request.urlopen(f"{OLLAMA_HOST}/api/tags", timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return [m["name"] for m in data.get("models", [])]
    except (urllib.error.URLError, OSError, ValueError):
        return None


def benchmark(model: str = DEFAULT_MODEL):
    prompt = ("Write a complete Python implementation of an LRU Cache with O(1) "
              "get and put using a Doubly Linked List and a Hash Map.")

    models = available_models()
    if models is None:
        print(f"Ollama is not reachable at {OLLAMA_HOST}. Is `ollama serve` running?")
        return 1
    # Accept both "name" and "name:latest" spellings.
    if model not in models and f"{model}:latest" not in models:
        print(f"Model '{model}' is not installed.")
        print(f"Available: {', '.join(models) if models else '(none)'}")
        print("\nPull it with `ollama pull <model>`, or pass one of the above:")
        print(f"  python {os.path.basename(__file__)} <model>")
        return 1

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_predict": 350,
        },
    }

    print(f"Querying {model} via Ollama...")
    req = urllib.request.Request(
        f"{OLLAMA_HOST}/api/generate",
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
    print("      OLLAMA INFERENCE SPEED BENCHMARK")
    print("=" * 60)
    print(f"Model Name           : {model}")
    print(f"Prompt Tokens        : {prompt_eval_count} tokens ({prompt_speed:.1f} tok/s)")
    print(f"Generated Tokens     : {eval_count} tokens")
    print(f"Generation Duration  : {eval_duration_sec:.2f} seconds")
    print(f"Generation Speed     : {eval_speed:.1f} TOKENS / SECOND")
    print(f"Total Wall Latency   : {total_latency:.2f} seconds")
    print("=" * 60)
    print("\nModel Output Excerpt:")
    print("-" * 60)
    print(res.get("response", "")[:400] + "...")
    print("-" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(benchmark(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_MODEL))
