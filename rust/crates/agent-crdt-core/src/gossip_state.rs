use std::collections::HashMap;
use std::time::{SystemTime, UNIX_EPOCH};
use serde::{Deserialize, Serialize};

/// A Conflict-free Replicated Data Type (CRDT) for shared agent state.
/// Ensures eventual consistency without central coordination.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LwwElementSet<T: Clone + Ord> {
    // Element -> (Timestamp, OriginAgentID)
    elements: HashMap<T, (u64, String)>,
}

impl<T: Clone + Ord + std::hash::Hash + Eq> LwwElementSet<T> {
    pub fn new() -> Self {
        Self { elements: HashMap::new() }
    }

    /// Adds an element to the set.
    pub fn add(&mut self, element: T, agent_id: &str) {
        let timestamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_millis() as u64;
        
        self.elements.insert(element, (timestamp, agent_id.to_string()));
    }

    /// Removes an element (tombstone).
    pub fn remove(&mut self, element: &T, agent_id: &str) {
        // In a full CRDT, we'd use a separate tombstone set. 
        // Simplified here for architectural demo.
        self.elements.remove(element);
    }

    /// Merges state from another agent (Gossip Protocol).
    /// Resolves conflicts using Last-Write-Wins.
    pub fn merge(&mut self, other: &LwwElementSet<T>) {
        for (element, (ts, origin)) in &other.elements {
            if let Some((my_ts, _)) = self.elements.get(element) {
                if ts > my_ts {
                    self.elements.insert(element.clone(), (*ts, origin.clone()));
                }
            } else {
                self.elements.insert(element.clone(), (*ts, origin.clone()));
            }
        }
    }

    pub fn get_elements(&self) -> Vec<&T> {
        self.elements.keys().collect()
    }
}

/// The Gossip Protocol Runner.
/// Periodically exchanges CRDT state with peer agents.
pub struct GossipNetwork {
    local_state: LwwElementSet<String>, // Shared global context
    peers: Vec<String>, // Peer agent IDs
}

impl GossipNetwork {
    pub fn new(peers: Vec<String>) -> Self {
        Self {
            local_state: LwwElementSet::new(),
            peers,
        }
    }

    pub fn simulate_gossip_round(&mut self) {
        // In production: Send local_state over NATS/UDP to peers
        // Receive their state and call self.local_state.merge(&peer_state)
        println!("🌐 Gossip round completed. State size: {}", self.local_state.get_elements().len());
    }
}
