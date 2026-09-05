import pytest

from saleha.core.p2p_mesh import P2PMeshNode, MeshNodeHeartbeat, RemoteTaskPacket


def test_p2pmeshnode_start():
    node = P2PMeshNode()
    assert node.is_running is False
    node.start(broadcast_interval_sec=1.0)
    assert node.is_running is True

def test_p2pmeshnode_stop():
    node = P2PMeshNode()
    node.start(broadcast_interval_sec=1.0)
    node.stop()
    assert node.is_running is False

def test_p2pmeshnode_register_peer():
    node = P2PMeshNode()
    peer = MeshNodeHeartbeat(node_id="Peer-Alpha-Laptop", host_ip="192.168.1.1")
    node.register_peer(peer)
    assert "Peer-Alpha-Laptop" in node.discovered_peers

def test_p2pmeshnode_offload_task_to_peer():
    node = P2PMeshNode()
    peer = MeshNodeHeartbeat(node_id="Peer-Beta-Laptop", host_ip="192.168.1.2")
    node.register_peer(peer)
    task_info = node.offload_task_to_peer(10, 5, 3, "Hello, World!")
    assert task_info["status"] == "OFFLOADED_SUCCESS"
    assert task_info["assigned_destination_node"] == "Peer-Beta-Laptop"

def test_p2pmeshnode_get_mesh_status():
    node = P2PMeshNode()
    peer1 = MeshNodeHeartbeat(node_id="Peer-Alpha-Laptop", host_ip="192.168.1.1")
    peer2 = MeshNodeHeartbeat(node_id="Peer-Beta-Laptop", host_ip="192.168.1.2")
    node.register_peer(peer1)
    node.register_peer(peer2)
    status = node.get_mesh_status()
    assert "local_node" in status
    assert "hosted_departments" in status
    assert "total_discovered_peers" in status
    assert len(status["peers"]) == 2