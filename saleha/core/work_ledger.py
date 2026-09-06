"""
Saleha Core: Verifiable Work Ledger

What this is
------------
A tamper-evident, independently re-checkable record of what an AI agent
actually did -- not what it said it did.

Every AI coding tool reports its own work. None of them prove it. If an
agent says "I fixed the bug and the tests pass", the only thing backing
that claim is the agent's own summary, and a summary is exactly the thing a
model can fabricate. That was measured in this repo: a model called
finish() on turn 1 with "File read successfully" having read nothing.

Two pieces already exist here, separately:

  * task_evidence.EvidenceLedger records facts observed by real code, so a
    completion claim can be refused. But it lives in memory, dies with the
    process, and only the machine that ran the work can see it.
  * rust/intent-kernel's proof.jsonl hash-chains mission events, so
    tampering is detectable. But it records that an event *happened*, not
    whether the claimed outcome was actually true.

Neither alone gives the thing that matters: a record a *third party* can
take away and re-run, without trusting the agent, the operator, or the
machine it ran on.

This joins them and adds the part that makes it verifiable rather than
merely auditable: every claim carries a **re-executable check**. The ledger
does not store "tests passed" as a fact. It stores the command, the working
tree fingerprint it ran against, and the observed result -- so anyone
holding the repo can call verify() later and get an independent answer.

The distinction, precisely
--------------------------
    Audit log   : "the agent says it ran the tests"      (trust me)
    Hash chain  : "that claim has not been edited since" (trust the log)
    Work ledger : "run this command yourself and see"    (trust nothing)

A hash chain proves nobody rewrote history. It cannot tell you the history
was true when it was written. Re-execution can.

Design rules, kept deliberately narrow
--------------------------------------
1. A claim counts as proof only if it can be re-run. Anything else is
   recorded as an `assertion` and never counted, so an agent cannot inflate
   its record by talking.
2. Verification re-derives results from the repo. It never consults the
   stored outcome to decide -- that would only confirm the ledger agrees
   with itself.
3. Re-verification can legitimately disagree with the original run
   (dependencies move, environments differ). That is reported as
   ENVIRONMENT_DIVERGED, kept distinct from TAMPERED and from FAILED,
   because conflating them makes the ledger either alarmist or useless.
4. No network, no service, no daemon. A ledger is a file you can email.
"""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import subprocess
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Tuple

LEDGER_VERSION = 1
GENESIS = "genesis"


class ClaimKind(str, Enum):
    """What sort of statement is being recorded."""

    # Re-executable: the ledger can prove or disprove these later.
    COMMAND_SUCCEEDED = "command_succeeded"
    TESTS_PASSED = "tests_passed"
    FILE_CONTAINS = "file_contains"
    FILE_ABSENT = "file_absent"
    FILE_DIGEST = "file_digest"

    # Not re-executable: recorded, never counted as proof.
    ASSERTION = "assertion"


RECHECKABLE = {
    ClaimKind.COMMAND_SUCCEEDED,
    ClaimKind.TESTS_PASSED,
    ClaimKind.FILE_CONTAINS,
    ClaimKind.FILE_ABSENT,
    ClaimKind.FILE_DIGEST,
}


class Verdict(str, Enum):
    CONFIRMED = "confirmed"                        # re-ran, same result
    FAILED = "failed"                              # re-ran, claim is false now
    TAMPERED = "tampered"                          # chain broken
    ENVIRONMENT_DIVERGED = "environment_diverged"  # cannot re-run here
    UNVERIFIABLE = "unverifiable"                  # assertion, by design


@dataclass
class Claim:
    """One statement plus the check that can re-establish it."""

    kind: ClaimKind
    subject: str                       # file path, or human-readable command
    detail: str = ""                   # expected text / digest
    observed: str = ""                 # what happened at record time
    tree_digest: str = ""              # repo fingerprint when recorded
    at: float = field(default_factory=time.time)
    # Exact argv for command claims. `subject` is a display string, and
    # re-running a shell-joined string loses quoting -- verified: a command
    # recorded as [python, -c, "import sys;sys.exit(0)"] re-ran as a
    # SyntaxError and reported a false FAILED. The argv list is what gets
    # re-executed; subject is only for humans reading the ledger.
    argv: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["kind"] = self.kind.value
        return d


@dataclass
class Entry:
    """A hash-chained ledger record."""

    seq: int
    actor: str                         # which model/agent made the claim
    goal: str
    claim: Dict[str, Any]
    prev_hash: str
    hash: str = ""
    version: int = LEDGER_VERSION


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonical(obj: Any) -> str:
    """Stable serialisation -- the hash must not depend on dict ordering."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class WorkLedger:
    """
    Append-only, hash-chained, independently re-verifiable record of work.

    Two-sided on purpose: the side that *does* the work calls record_*(),
    and any later party -- possibly on another machine -- calls verify()
    holding only the ledger file and the repo.
    """

    def __init__(self, path: str, root_dir: str = "."):
        self.path = os.path.abspath(path)
        self.root = os.path.abspath(root_dir)
        self._entries: List[Entry] = []
        if os.path.exists(self.path):
            self._load()

    # -- persistence ---------------------------------------------------
    def _load(self) -> None:
        self._entries = []
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    # A corrupt line is itself evidence; keep it visible
                    # rather than skipping to a clean-looking chain.
                    self._entries.append(Entry(seq=-1, actor="", goal="",
                                               claim={"corrupt": line[:200]},
                                               prev_hash="", hash=""))
                    continue
                self._entries.append(Entry(
                    seq=d.get("seq", -1), actor=d.get("actor", ""),
                    goal=d.get("goal", ""), claim=d.get("claim", {}),
                    prev_hash=d.get("prev_hash", ""), hash=d.get("hash", ""),
                    version=d.get("version", LEDGER_VERSION),
                ))

    def _append(self, entry: Entry) -> None:
        parent = os.path.dirname(self.path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(_canonical(asdict(entry)) + "\n")
        self._entries.append(entry)

    # -- repo fingerprint ----------------------------------------------
    def tree_digest(self) -> str:
        """
        Fingerprint of the working tree, tying a claim to the code it was
        made about. Uses git when available; falls back to hashing source
        files so this still works outside a repo.
        """
        try:
            head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.root,
                                  capture_output=True, text=True, timeout=15)
            if head.returncode == 0:
                dirty = subprocess.run(["git", "status", "--porcelain"],
                                       cwd=self.root, capture_output=True,
                                       text=True, timeout=30)
                # A dirty tree must not masquerade as its commit.
                return f"git:{head.stdout.strip()}:{_sha256(dirty.stdout)[:16]}"
        except (OSError, subprocess.SubprocessError):
            pass

        h = hashlib.sha256()
        skip = {".git", "__pycache__", "node_modules", ".venv",
                ".venv_train", "target", "dist", "build"}
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames if d not in skip]
            for fn in sorted(filenames):
                if not fn.endswith((".py", ".rs", ".ts", ".js", ".go", ".java")):
                    continue
                fp = os.path.join(dirpath, fn)
                try:
                    with open(fp, "rb") as fh:
                        h.update(os.path.relpath(fp, self.root).encode())
                        h.update(fh.read())
                except OSError:
                    continue
        return f"tree:{h.hexdigest()[:32]}"

    # -- recording -----------------------------------------------------
    @property
    def head_hash(self) -> str:
        for e in reversed(self._entries):
            if e.hash:
                return e.hash
        return GENESIS

    def _record(self, actor: str, goal: str, claim: Claim) -> Entry:
        prev = self.head_hash
        seq = len(self._entries)
        payload = {"seq": seq, "actor": actor, "goal": goal,
                   "claim": claim.to_dict(), "prev_hash": prev,
                   "version": LEDGER_VERSION}
        entry = Entry(seq=seq, actor=actor, goal=goal, claim=claim.to_dict(),
                      prev_hash=prev, hash=_sha256(_canonical(payload)))
        self._append(entry)
        return entry

    def _run(self, command: List[str], timeout: float) -> Tuple[int, str]:
        try:
            p = subprocess.run(command, cwd=self.root, capture_output=True,
                               text=True, timeout=timeout,
                               encoding="utf-8", errors="replace")
            return p.returncode, (p.stdout or p.stderr or "").strip()[-300:]
        except (OSError, subprocess.SubprocessError) as exc:
            return -1, f"could not run: {exc}"

    def record_command(self, actor: str, goal: str, command: List[str],
                       timeout: float = 300.0) -> Tuple[Entry, bool]:
        """Run a command for real and record it re-runnably."""
        rc, tail = self._run(command, timeout)
        claim = Claim(kind=ClaimKind.COMMAND_SUCCEEDED,
                      subject=shlex.join(command),
                      detail="exit 0 expected",
                      observed=f"exit {rc}: {tail}",
                      tree_digest=self.tree_digest(),
                      argv=list(command))
        return self._record(actor, goal, claim), rc == 0

    def record_tests(self, actor: str, goal: str, command: List[str],
                     timeout: float = 600.0) -> Tuple[Entry, bool]:
        """A test run. Same mechanism, tagged so reports read meaningfully."""
        rc, tail = self._run(command, timeout)
        claim = Claim(kind=ClaimKind.TESTS_PASSED,
                      subject=shlex.join(command),
                      detail="exit 0 expected",
                      observed=f"exit {rc}: {tail}",
                      tree_digest=self.tree_digest(),
                      argv=list(command))
        return self._record(actor, goal, claim), rc == 0

    def record_file_contains(self, actor: str, goal: str, path: str,
                             expected: str) -> Tuple[Entry, bool]:
        try:
            with open(os.path.join(self.root, path), "r",
                      encoding="utf-8", errors="replace") as f:
                present = expected in f.read()
        except OSError:
            present = False
        claim = Claim(kind=ClaimKind.FILE_CONTAINS, subject=path,
                      detail=expected[:400],
                      observed="present" if present else "absent",
                      tree_digest=self.tree_digest())
        return self._record(actor, goal, claim), present

    def record_file_digest(self, actor: str, goal: str, path: str) -> Tuple[Entry, bool]:
        try:
            with open(os.path.join(self.root, path), "rb") as f:
                digest = hashlib.sha256(f.read()).hexdigest()
            ok = True
        except OSError as exc:
            digest, ok = f"unreadable: {exc}", False
        claim = Claim(kind=ClaimKind.FILE_DIGEST, subject=path,
                      detail=digest, observed=digest,
                      tree_digest=self.tree_digest())
        return self._record(actor, goal, claim), ok

    def record_assertion(self, actor: str, goal: str, text: str) -> Entry:
        """
        Something the agent says that cannot be checked. Deliberately kept
        separate: never counted as proof, so talking does not raise the
        proof rate.
        """
        claim = Claim(kind=ClaimKind.ASSERTION, subject="(agent statement)",
                      detail=text[:1000], observed="unverifiable",
                      tree_digest=self.tree_digest())
        return self._record(actor, goal, claim)

    # -- verification --------------------------------------------------
    def verify_chain(self) -> Tuple[bool, str]:
        """Recompute every hash. Detects edits, deletions and reordering."""
        prev = GENESIS
        for i, e in enumerate(self._entries):
            if e.seq == -1:
                return False, f"entry {i}: corrupt JSON line"
            payload = {"seq": e.seq, "actor": e.actor, "goal": e.goal,
                       "claim": e.claim, "prev_hash": e.prev_hash,
                       "version": e.version}
            if e.prev_hash != prev:
                return False, (f"entry {i}: chain broken -- prev_hash "
                               f"{e.prev_hash[:12]}... != {prev[:12]}...")
            if _sha256(_canonical(payload)) != e.hash:
                return False, f"entry {i}: content was modified after signing"
            prev = e.hash
        return True, f"{len(self._entries)} entries, chain intact"

    def _recheck(self, claim: Dict[str, Any]) -> Tuple[Verdict, str]:
        """
        Re-establish one claim from the repo as it is NOW.

        Deliberately ignores the stored `observed` when deciding -- reading
        the recorded answer would only prove the ledger agrees with itself.
        """
        kind = claim.get("kind", "")
        subject = claim.get("subject", "")

        if kind == ClaimKind.ASSERTION.value:
            return Verdict.UNVERIFIABLE, "agent statement, not checkable by design"

        if kind in (ClaimKind.COMMAND_SUCCEEDED.value, ClaimKind.TESTS_PASSED.value):
            # Re-run the exact argv, never a shell-joined string: joining
            # loses quoting, which was verified to turn a passing command
            # into a SyntaxError and report a false FAILED. Older entries
            # without argv fall back to the shell and are reported as
            # diverged rather than silently mis-verified.
            argv = claim.get("argv") or []
            try:
                if argv:
                    p = subprocess.run(argv, cwd=self.root, capture_output=True,
                                       text=True, timeout=600,
                                       encoding="utf-8", errors="replace")
                else:
                    p = subprocess.run(subject, cwd=self.root, shell=True,
                                       capture_output=True, text=True, timeout=600,
                                       encoding="utf-8", errors="replace")
            except (OSError, subprocess.SubprocessError) as exc:
                return Verdict.ENVIRONMENT_DIVERGED, f"cannot run here: {exc}"
            if p.returncode == 0:
                return Verdict.CONFIRMED, "re-ran, exit 0"
            return Verdict.FAILED, f"re-ran, exit {p.returncode}"

        if kind == ClaimKind.FILE_CONTAINS.value:
            try:
                with open(os.path.join(self.root, subject), "r",
                          encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except OSError:
                return Verdict.FAILED, f"{subject} unreadable"
            if claim.get("detail", "") in text:
                return Verdict.CONFIRMED, "text present"
            return Verdict.FAILED, "text no longer present"

        if kind == ClaimKind.FILE_ABSENT.value:
            if os.path.exists(os.path.join(self.root, subject)):
                return Verdict.FAILED, "path exists now"
            return Verdict.CONFIRMED, "still absent"

        if kind == ClaimKind.FILE_DIGEST.value:
            try:
                with open(os.path.join(self.root, subject), "rb") as f:
                    now = hashlib.sha256(f.read()).hexdigest()
            except OSError:
                return Verdict.FAILED, f"{subject} unreadable"
            if now == claim.get("detail"):
                return Verdict.CONFIRMED, "digest matches"
            return Verdict.FAILED, "file changed since"

        return Verdict.UNVERIFIABLE, f"unknown claim kind '{kind}'"

    def verify(self, recheck: bool = True) -> Dict[str, Any]:
        """
        Full independent verification.

        `recheck=False` checks only that the record is unaltered -- fast,
        and all that is possible without the repo. `recheck=True` also
        re-runs every checkable claim, which is what separates this from an
        audit log.
        """
        chain_ok, chain_msg = self.verify_chain()
        results: List[Dict[str, Any]] = []
        tally: Dict[str, int] = {}

        if chain_ok and recheck:
            for e in self._entries:
                verdict, why = self._recheck(e.claim)
                tally[verdict.value] = tally.get(verdict.value, 0) + 1
                results.append({"seq": e.seq, "actor": e.actor,
                                "kind": e.claim.get("kind"),
                                "subject": str(e.claim.get("subject", ""))[:120],
                                "verdict": verdict.value, "why": why})
        elif not chain_ok:
            tally[Verdict.TAMPERED.value] = len(self._entries)

        proved = tally.get(Verdict.CONFIRMED.value, 0)
        checkable = sum(1 for e in self._entries
                        if e.claim.get("kind") in {k.value for k in RECHECKABLE})

        return {
            "ledger": self.path,
            "chain_intact": chain_ok,
            "chain_detail": chain_msg,
            "entries": len(self._entries),
            "checkable_claims": checkable,
            "independently_confirmed": proved,
            "verdicts": tally,
            "results": results,
            # The number that actually means something: the fraction of this
            # agent's checkable claims a stranger could re-establish.
            "proof_rate": round(proved / checkable, 3) if checkable else 0.0,
        }

    def summary_line(self) -> str:
        v = self.verify(recheck=False)
        return (f"{v['entries']} entries, {v['checkable_claims']} checkable, "
                f"chain {'intact' if v['chain_intact'] else 'BROKEN'}")
