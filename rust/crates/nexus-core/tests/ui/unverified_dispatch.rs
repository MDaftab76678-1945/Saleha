//! COMPILE-FAIL TEST: Task<Pending> must NOT have dispatch() method.
//! If this file compiles, the type-state safety invariant is BROKEN.

use nexus_core::orchestrator::{Task, Pending};
use nexus_core::types::{Priority, AgentId};
use uuid::Uuid;

fn main() {
    let task = Task::<Pending>::new(Priority::Normal, vec![1, 2, 3], None);

    // ERROR EXPECTED: no method named `dispatch` found for struct `Task<Pending>`
    // Only Task<Verified> has dispatch(). This is enforced at compile time.
    let _result = task.dispatch(AgentId(Uuid::now_v7()));
}
