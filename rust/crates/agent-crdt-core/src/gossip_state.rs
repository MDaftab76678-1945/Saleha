use std::collections::HashMap;
use std::time::{SystemTime, UNIX_EPOCH};
use serde::{Deserialize, Serialize};

/// A Conflict-free Replicated Data Type (CRDT) for shared agent state.
/// Ensures eventual consistency without central coordination.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LwwElementSet<T: Clone + Ord + std::hash::Hash + Eq> {
    // Element -> (Timestamp, OriginAgentID)
    pub elements: HashMap<T, (u64, String)>,
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
    pub fn remove(&mut self, element: &T, _agent_id: &str) {
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
        println!("[GOSSIP] Gossip round completed. State size: {}", self.local_state.get_elements().len());
    }

    pub fn local_state(&self) -> &LwwElementSet<String> {
        &self.local_state
    }

    pub fn local_state_mut(&mut self) -> &mut LwwElementSet<String> {
        &mut self.local_state
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_lww_add_and_get() {
        let mut set = LwwElementSet::new();
        set.add("key1".to_string(), "agent_a");
        let elems = set.get_elements();
        assert_eq!(elems.len(), 1);
        assert_eq!(*elems[0], "key1");
    }

    #[test]
    fn test_lww_remove() {
        let mut set = LwwElementSet::new();
        set.add("key1".to_string(), "agent_a");
        set.remove(&"key1".to_string(), "agent_a");
        assert!(set.get_elements().is_empty());
    }

    #[test]
    fn test_lww_merge_conflict_resolution() {
        let mut set_a = LwwElementSet::new();
        let mut set_b = LwwElementSet::new();

        // Older timestamp for A
        set_a.elements.insert("val".to_string(), (100, "agent_a".to_string()));
        // Newer timestamp for B
        set_b.elements.insert("val".to_string(), (200, "agent_b".to_string()));

        set_a.merge(&set_b);
        assert_eq!(set_a.elements.get("val").unwrap().1, "agent_b");
    }

    #[test]
    fn test_gossip_network_simulation() {
        let mut net = GossipNetwork::new(vec!["agent_1".to_string(), "agent_2".to_string()]);
        net.local_state_mut().add("shared_knowledge".to_string(), "agent_0");
        net.simulate_gossip_round();
        assert_eq!(net.local_state().get_elements().len(), 1);
    }
}

