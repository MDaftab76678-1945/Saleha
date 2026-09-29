"""
Saleha Core: Polyglot DPO (Direct Preference Optimization) & SFT Dataset Engine

Exports hand-written (chosen, rejected) preference pairs across Python,
TypeScript/React, Go, Rust and SQL, plus the matching SFT samples.

Only the curated pairs in POLYGLOT_DPO_TEMPLATES are emitted. An earlier
version padded the output to `target_count` by pasting 17 topic names into one
stub per language -- 994 of the 1000 shipped rows were a class whose
"implementation" of, say, a zero-copy stream parser returned
{"status": "SUCCESS", ...}, with a hardcoded 0.95 margin. That taught a model
to write fake-success stubs. Growing this dataset means writing more real
pairs, not repeating these.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

# Below this many pairs a DPO pass is more noise than signal.
MIN_DPO_PAIRS = 20


@dataclass
class DPOPreferencePair:
    """`margin_score` is a hand-assigned preference label for curated pairs,
    not a measured reward difference."""
    pair_id: str
    prompt: str
    chosen: str
    rejected: str
    language: str
    category: str
    margin_score: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        """HuggingFace TRL DPOTrainer compatible dictionary."""
        return {
            "id": self.pair_id,
            "prompt": self.prompt,
            "chosen": self.chosen,
            "rejected": self.rejected,
            "language": self.language,
            "category": self.category,
            "margin_score": self.margin_score,
        }


@dataclass
class SFTInstructionSample:
    sample_id: str
    instruction: str
    input: str
    output: str
    language: str
    category: str

    def to_sharegpt(self) -> Dict[str, Any]:
        return {
            "id": self.sample_id,
            "language": self.language,
            "category": self.category,
            "conversations": [
                {"from": "human", "value": self.instruction + (f"\n\nInput:\n{self.input}" if self.input else "")},
                {"from": "gpt", "value": self.output}
            ]
        }

    def to_alpaca(self) -> Dict[str, str]:
        return {
            "instruction": self.instruction,
            "input": self.input,
            "output": self.output,
        }


POLYGLOT_DPO_TEMPLATES: List[Tuple[str, str, str, str, str]] = [
    # 1. Python - Security / SQL Injection
    (
        "Write a Python database query function to fetch active users filtered by username and role.",
        "python",
        "security",
        # Chosen: Parameterized query, strict type hints, exception handling
        """import sqlite3
from typing import List, Dict, Any, Optional

def get_active_users(db_path: str, username: str, role: str) -> List[Dict[str, Any]]:
    \"\"\"Fetches active users securely using parameterized SQL queries (OWASP Compliant).\"\"\"
    query = \"\"\"
        SELECT id, username, email, role, created_at
        FROM users
        WHERE username = :username AND role = :role AND is_active = 1;
    \"\"\"
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, {"username": username, "role": role})
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        return []
""",
        # Rejected: Vulnerable string formatting, no error handling
        """import sqlite3

def get_active_users(db_path, username, role):
    # WARNING: Vulnerable to SQL Injection
    query = f"SELECT * FROM users WHERE username = '{username}' AND role = '{role}' AND is_active = 1;"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(query)
    return cursor.fetchall()
"""
    ),
    # 2. Python - Concurrency & Async
    (
        "Implement an async Python HTTP client fetcher with rate limiting and exponential backoff retry.",
        "python",
        "concurrency",
        # Chosen: Non-blocking asyncio, exponential backoff, semaphore
        """import asyncio
import urllib.error
import urllib.request
from typing import Optional


class ResilientAsyncFetcher:
    \"\"\"Async HTTP fetcher: bounded concurrency, exponential backoff on transient errors.\"\"\"

    def __init__(self, max_concurrency: int = 5, max_retries: int = 3, timeout: float = 10.0):
        self.semaphore = asyncio.Semaphore(max(1, max_concurrency))
        self.max_retries = max(0, max_retries)
        self.timeout = timeout

    def _get(self, url: str) -> bytes:
        with urllib.request.urlopen(url, timeout=self.timeout) as resp:
            return resp.read()

    async def fetch(self, url: str) -> Optional[bytes]:
        async with self.semaphore:
            for attempt in range(self.max_retries + 1):
                try:
                    # Blocking I/O runs in a worker thread so the event loop stays free.
                    return await asyncio.to_thread(self._get, url)
                except urllib.error.HTTPError as e:
                    if e.code < 500 and e.code != 429:
                        raise  # a client error will not improve on retry
                except (urllib.error.URLError, TimeoutError):
                    pass
                if attempt < self.max_retries:
                    await asyncio.sleep(0.5 * (2 ** attempt))
            return None
""",
        # Rejected: Blocking time.sleep in async loop, recursion without limit
        """import time
import asyncio

async def fetch_with_retry(url):
    # BAD: Blocking sleep in async function freezes event loop
    time.sleep(1)
    return {"url": url}
"""
    ),
    # 3. TypeScript / React - State Management & Memory Leaks
    (
        "Create a React TypeScript hook for window resize event listener with clean unmount and debounce.",
        "typescript",
        "frontend",
        # Chosen: Type-safe, cleanup function in useEffect, debounced callback
        """import { useState, useEffect } from 'react';

interface WindowSize {
  width: number;
  height: number;
}

export function useWindowSize(delayMs: number = 100): WindowSize {
  const [size, setSize] = useState<WindowSize>({
    width: typeof window !== 'undefined' ? window.innerWidth : 1200,
    height: typeof window !== 'undefined' ? window.innerHeight : 800,
  });

  useEffect(() => {
    let timeoutId: NodeJS.Timeout;
    const handleResize = () => {
      clearTimeout(timeoutId);
      timeoutId = setTimeout(() => {
        setSize({ width: window.innerWidth, height: window.innerHeight });
      }, delayMs);
    };

    window.addEventListener('resize', handleResize, { passive: true });
    return () => {
      clearTimeout(timeoutId);
      window.removeEventListener('resize', handleResize);
    };
  }, [delayMs]);

  return size;
}
""",
        # Rejected: Memory leak (no removeEventListener), no types, no SSR check
        """import { useState, useEffect } from 'react';

export function useWindowSize() {
  const [size, setSize] = useState({ width: window.innerWidth, height: window.innerHeight });
  useEffect(() => {
    // BAD: No cleanup returns, causes severe memory leak on unmount
    window.addEventListener('resize', () => {
      setSize({ width: window.innerWidth, height: window.innerHeight });
    });
  }, []);
  return size;
}
"""
    ),
    # 4. Go - Goroutine Pool & Channel Safety
    (
        "Write a thread-safe worker pool in Go with bounded channels and sync.WaitGroup.",
        "go",
        "systems",
        # Chosen: sync.WaitGroup, context cancellation, closed channels
        """package main

import (
	\"context\"
	\"sync\"
)

type Job func(ctx context.Context) error

type WorkerPool struct {
	maxWorkers int
	jobs       chan Job
	wg         sync.WaitGroup
}

func NewWorkerPool(maxWorkers int, queueCap int) *WorkerPool {
	return &WorkerPool{
		maxWorkers: maxWorkers,
		jobs:       make(chan Job, queueCap),
	}
}

func (p *WorkerPool) Start(ctx context.Context) {
	for i := 0; i < p.maxWorkers; i++ {
		p.wg.Add(1)
		go func() {
			defer p.wg.Done()
			for {
				select {
				case <-ctx.Done():
					return
				case job, ok := <-p.jobs:
					if !ok {
						return
					}
					_ = job(ctx)
				}
			}
		}()
	}
}

func (p *WorkerPool) Submit(job Job) {
	p.jobs <- job
}

func (p *WorkerPool) Stop() {
	close(p.jobs)
	p.wg.Wait()
}
""",
        # Rejected: Unbounded goroutines, race condition, no WaitGroup
        """package main

// BAD: Spawns unbounded goroutines causing OOM, no channel closing
func ProcessJobs(jobs []func()) {
	for _, j := range jobs {
		go j()
	}
}
"""
    ),
    # 5. Rust - Safe Memory & Error Handling
    (
        "Implement a thread-safe in-memory key-value cache with TTL in Rust using Arc and RwLock.",
        "rust",
        "systems",
        # Chosen: RwLock, Instant TTL, clean Result handling
        """use std::collections::HashMap;
use std::sync::{Arc, RwLock};
use std::time::{Duration, Instant};

#[derive(Clone)]
struct CacheEntry<V> {
    value: V,
    expires_at: Instant,
}

#[derive(Clone)]
pub struct TtlCache<K, V> {
    store: Arc<RwLock<HashMap<K, CacheEntry<V>>>>,
}

impl<K: std::hash::Hash + Eq + Clone, V: Clone> TtlCache<K, V> {
    pub fn new() -> Self {
        Self {
            store: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    pub fn set(&self, key: K, value: V, ttl: Duration) {
        let entry = CacheEntry {
            value,
            expires_at: Instant::now() + ttl,
        };
        if let Ok(mut lock) = self.store.write() {
            lock.insert(key, entry);
        }
    }

    pub fn get(&self, key: &K) -> Option<V> {
        let lock = self.store.read().ok()?;
        let entry = lock.get(key)?;
        if Instant::now() > entry.expires_at {
            None
        } else {
            Some(entry.value.clone())
        }
    }
}
""",
        # Rejected: Unsafe pointer usage, unwrap panics, no lock
        """use std::collections::HashMap;

// BAD: Non-thread-safe raw mutable static with unsafe block
static mut CACHE: Option<HashMap<String, String>> = None;

pub fn get_unsafe(key: &str) -> Option<String> {
    unsafe { CACHE.as_ref().unwrap().get(key).cloned() }
}
"""
    ),
    # 6. SQL - Invariant Schema & Index Optimization
    (
        "Design an optimized PostgreSQL schema for high-throughput transactional ledger with composite indexing and check constraints.",
        "sql",
        "database",
        # Chosen: Strict constraints, composite index, immutable audit timestamps
        """CREATE TABLE IF NOT EXISTS transaction_ledger (
    ledger_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL,
    counterparty_id UUID NOT NULL,
    amount_cents BIGINT NOT NULL CHECK (amount_cents > 0),
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    direction VARCHAR(6) NOT NULL CHECK (direction IN ('DEBIT', 'CREDIT')),
    status VARCHAR(12) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'SETTLED', 'FAILED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Performance Index for account statement filtering
CREATE INDEX IF NOT EXISTS idx_ledger_account_created 
ON transaction_ledger (account_id, created_at DESC)
INCLUDE (amount_cents, direction, status);
""",
        # Rejected: Missing primary keys, floats for currency, no indexes
        """-- BAD: Uses FLOAT for currency causing rounding errors, no indexes
CREATE TABLE transactions (
    id INT,
    amount FLOAT,
    account_id INT,
    status TEXT
);
"""
    ),
]


class SalehaDPODatasetEngine:
    """Polyglot DPO Preference Pair & SFT Dataset Synthesizer."""

    def __init__(self, output_dir: str = "datasets"):
        self.output_dir = output_dir
        # No mkdir here: `output_dir` is relative to the caller's cwd and the
        # module-level singleton below is built at import time, so this
        # created a stray `datasets/` directory on import. Every write path
        # already creates its own parent directory before writing.
        self.dpo_pairs: List[DPOPreferencePair] = []
        self.sft_samples: List[SFTInstructionSample] = []

    def build_dataset(self, target_count: Optional[int] = None) -> Tuple[int, int]:
        """Loads the curated pairs (and their SFT samples); returns their counts.

        `target_count` caps the output; it never pads it. Asking for more
        pairs than exist returns fewer, not repeats.
        """
        self.dpo_pairs.clear()
        self.sft_samples.clear()
        templates = POLYGLOT_DPO_TEMPLATES
        if target_count is not None:
            templates = templates[:max(0, target_count)]

        for idx, (prompt, lang, cat, chosen, rejected) in enumerate(templates):
            self.dpo_pairs.append(DPOPreferencePair(
                pair_id=f"dpo_seed_{idx+1:04d}",
                prompt=prompt,
                chosen=chosen.strip(),
                rejected=rejected.strip(),
                language=lang,
                category=cat,
                margin_score=1.0,
            ))
            self.sft_samples.append(SFTInstructionSample(
                sample_id=f"sft_seed_{idx+1:04d}",
                instruction=prompt,
                input="",
                output=chosen.strip(),
                language=lang,
                category=cat,
            ))
        return len(self.dpo_pairs), len(self.sft_samples)

    def export_dpo_jsonl(self, output_path: Optional[str] = None) -> str:
        """Exports DPO dataset in HuggingFace TRL DPOTrainer JSONL format."""
        path = output_path or os.path.join(self.output_dir, "saleha_dpo_pairs.jsonl")
        parent_dir = os.path.dirname(os.path.abspath(path))
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for p in self.dpo_pairs:
                f.write(json.dumps(p.to_dict(), ensure_ascii=False) + "\n")
        return path

    def export_sft_jsonl(self, output_path: Optional[str] = None) -> str:
        """Exports SFT dataset in ShareGPT JSONL format."""
        path = output_path or os.path.join(self.output_dir, "saleha_sft_10k.jsonl")
        parent_dir = os.path.dirname(os.path.abspath(path))
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for s in self.sft_samples:
                f.write(json.dumps(s.to_sharegpt(), ensure_ascii=False) + "\n")
        return path

    def export_alpaca_json(self, output_path: Optional[str] = None) -> str:
        """Exports SFT dataset in Alpaca JSON format."""
        path = output_path or os.path.join(self.output_dir, "saleha_sft_10k_alpaca.json")
        parent_dir = os.path.dirname(os.path.abspath(path))
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        data = [s.to_alpaca() for s in self.sft_samples]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return path


dpo_dataset_engine = SalehaDPODatasetEngine()
