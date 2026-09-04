//! COMPILE-PASS TEST: Task<Verified> MUST have dispatch() method.
//! If this file fails to compile, the type-state API is broken.

use nexus_core::orchestrator::{Task, Verified, Pending};
use nexus_core::types::{Priority, AgentId};
use nexus_core::safety::{SafetyRail, Constitution, SafetyVerdict};
use uuid::Uuid;

#[tokio::main]
async fn main() {
    // Step 1: Create pending task
    let pending = Task::<Pending>::new(Priority::High, vec![42], None);

    // Step 2: Constitutional check produces Verified task
    let constitution = Constitution {
        hash: [0u8; 32],
        clauses: vec!["no_harm".to_string()],
    };
    let safety_rail = SafetyRail::new_for_testing();

    let verified: Task<Verified> = pending
        .constitutional_check(&constitution, &safety_rail)
        .await
        .expect("Should pass constitutional check in test");

    // Step 3: Only Verified tasks can be dispatched — this MUST compile
    let agent_id = AgentId(Uuid::now_v7());
    let (_inflight_task, _assigned_agent) = verified.dispatch(agent_id);
}
