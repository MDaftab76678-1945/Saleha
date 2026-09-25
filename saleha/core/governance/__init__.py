"""Self-governance: Saleha measuring and improving its own security framework
and keeping its own documents and version in step with the code.

Every improvement here is gated on a measurement Saleha cannot author itself:

- ``exploit_oracle``   -- ground truth. Runs a snippet against real attack
  payloads and checks the side effect from outside the process.
- ``corpus``           -- oracle-labelled vulnerable / not-exploited snippets.
- ``scanner_benchmark`` -- recall and false positives of the SAST scanner on
  that corpus.
- ``learned_rules``    -- scanner rules the evolver added, each with evidence.
- ``security_evolver`` -- red team (generate evasive vulnerable code) and blue
  team (write a rule for what the scanner missed); a rule is kept only if it
  raises measured recall without adding false positives, and only on a branch.
- ``doc_sync``         -- regenerates marked doc regions from code, flags stale
  claims, versions each managed document.
- ``versioning``       -- SemVer bump and changelog from real commits.

Submodules are imported directly; this package imports nothing eagerly.
"""
