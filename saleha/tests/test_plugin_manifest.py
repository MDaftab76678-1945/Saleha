import pytest

from saleha.core.plugin_manifest import SalehaPluginManifest, PluginAgentSpec, PluginManifestEngine


def test_plugin_agent_spec():
    spec = PluginAgentSpec(
        name="example-agent",
        role="data_processing",
        description="A sample agent for data processing tasks.",
        entrypoint="/path/to/entrypoint",
        version="2.0.0"
    )
    assert spec.name == "example-agent"
    assert spec.role == "data_processing"
    assert spec.description == "A sample agent for data processing tasks."
    assert spec.entrypoint == "/path/to/entrypoint"
    assert spec.version == "2.0.0"


def test_saleha_plugin_manifest():
    manifest = SalehaPluginManifest(
        plugin_id="example-plugin",
        name="Example Plugin",
        version="1.0.0",
        author="John Doe",
        description="A sample plugin for demonstration purposes.",
        agents=[
            PluginAgentSpec(
                name="agent1",
                role="data_processing",
                description="First agent in the plugin.",
                entrypoint="/path/to/entrypoint1"
            ),
            PluginAgentSpec(
                name="agent2",
                role="machine_learning",
                description="Second agent in the plugin.",
                entrypoint="/path/to/entrypoint2"
            )
        ],
        tools=["tool1", "tool2"],
        enabled=True
    )
    assert manifest.plugin_id == "example-plugin"
    assert manifest.name == "Example Plugin"
    assert manifest.version == "1.0.0"
    assert manifest.author == "John Doe"
    assert manifest.description == "A sample plugin for demonstration purposes."
    assert len(manifest.agents) == 2
    assert manifest.tools == ["tool1", "tool2"]
    assert manifest.enabled is True


def test_plugin_manifest_engine_discover_plugins():
    engine = PluginManifestEngine()
    plugins = engine.discover_plugins()
    assert isinstance(plugins, list)
    for plugin in plugins:
        assert isinstance(plugin, SalehaPluginManifest)


def test_plugin_manifest_engine_register_plugin_manifest():
    engine = PluginManifestEngine()
    manifest = SalehaPluginManifest(
        plugin_id="example-plugin",
        name="Example Plugin",
        version="1.0.0",
        author="John Doe",
        description="A sample plugin for demonstration purposes.",
        agents=[
            PluginAgentSpec(
                name="agent1",
                role="data_processing",
                description="First agent in the plugin.",
                entrypoint="/path/to/entrypoint1"
            ),
            PluginAgentSpec(
                name="agent2",
                role="machine_learning",
                description="Second agent in the plugin.",
                entrypoint="/path/to/entrypoint2"
            )
        ],
        tools=["tool1", "tool2"],
        enabled=True
    )
    engine.register_plugin_manifest(manifest)
    assert manifest.plugin_id in engine._plugins


def test_plugin_manifest_engine_get_plugin():
    engine = PluginManifestEngine()
    manifest = SalehaPluginManifest(
        plugin_id="example-plugin",
        name="Example Plugin",
        version="1.0.0",
        author="John Doe",
        description="A sample plugin for demonstration purposes.",
        agents=[
            PluginAgentSpec(
                name="agent1",
                role="data_processing",
                description="First agent in the plugin.",
                entrypoint="/path/to/entrypoint1"
            ),
            PluginAgentSpec(
                name="agent2",
                role="machine_learning",
                description="Second agent in the plugin.",
                entrypoint="/path/to/entrypoint2"
            )
        ],
        tools=["tool1", "tool2"],
        enabled=True
    )
    engine.register_plugin_manifest(manifest)
    retrieved = engine.get_plugin("example-plugin")
    assert retrieved is manifest


def test_plugin_manifest_engine_get_all_plugins():
    engine = PluginManifestEngine()
    manifest = SalehaPluginManifest(
        plugin_id="example-plugin",
        name="Example Plugin",
        version="1.0.0",
        author="John Doe",
        description="A sample plugin for demonstration purposes.",
        agents=[
            PluginAgentSpec(
                name="agent1",
                role="data_processing",
                description="First agent in the plugin.",
                entrypoint="/path/to/entrypoint1"
            ),
            PluginAgentSpec(
                name="agent2",
                role="machine_learning",
                description="Second agent in the plugin.",
                entrypoint="/path/to/entrypoint2"
            )
        ],
        tools=["tool1", "tool2"],
        enabled=True
    )
    engine.register_plugin_manifest(manifest)
    retrieved = engine.get_all_plugins()
    assert len(retrieved) == 1