# MUKTI Chaos Engineering

## Quick Start

```bash
# 1. Install LitmusChaos
kubectl apply -f https://litmuschaos.github.io/litmus/litmus-operator-v3.14.1.yaml
kubectl apply -f k8s/chaos/litmus/namespace.yaml

# 2. Run a single experiment manually
kubectl apply -f k8s/chaos/litmus/experiments/api-pod-delete.yaml
kubectl get chaosengine -n mukti -w

# 3. Run all experiments via orchestrator (staging only!)
cd k8s/chaos/orchestrator
python chaos_runner.py

# 4. Dry run (no actual chaos)
python -c "
import asyncio
from chaos_runner import ChaosRunner
runner = ChaosRunner(dry_run=True)
asyncio.run(runner.run_all())
runner.print_report()
"
