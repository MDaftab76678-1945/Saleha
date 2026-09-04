---- MODULE HardwareAsync ----
EXTENDS Naturals, Sequences, FiniteSets

CONSTANTS MaxPendingOps, TimeoutMs
VARIABLES pending_ops, completed_ops, mr_registered

Init == 
    /\ pending_ops = {}
    /\ completed_ops = {}
    /\ mr_registered = TRUE

PostOp(op) == 
    /\ mr_registered = TRUE
    /\ Cardinality(pending_ops) < MaxPendingOps
    /\ pending_ops' = pending_ops \union {op}
    /\ UNCHANGED <<completed_ops, mr_registered>>

CompleteOp(op) ==
    /\ op \in pending_ops
    /\ pending_ops' = pending_ops \ {op}
    /\ completed_ops' = completed_ops \union {op}
    /\ UNCHANGED mr_registered

(* SAFETY: Can only deregister when NO ops reference this MR *)
DeregisterMR(mr) ==
    /\ mr_registered = TRUE
    /\ \A op \in pending_ops: op.mr # mr  
    /\ mr_registered' = FALSE
    /\ UNCHANGED <<pending_ops, completed_ops>>

Spec == Init /\ [][PostOp \/ CompleteOp \/ DeregisterMR]_<<pending_ops, completed_ops, mr_registered>>

THEOREM SafeDeregister == 
    Spec => [](DeregisterMR(mr) => \A op \in pending_ops: op.mr # mr)
====
