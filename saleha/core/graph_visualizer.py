"""
Saleha Core: Live Interactive Architecture Graph Visualizer

Converts AST symbol definitions, cross-file imports, and call graphs into
interactive, self-contained HTML5/SVG/D3 force-directed visual network diagrams.
"""

from __future__ import annotations

import os
import json
from typing import Dict, List, Optional, Any

from saleha.core.dependency_graph import dependency_graph


class ArchitectureGraphVisualizer:
    """Generates standalone interactive HTML visualizers for codebase architecture graphs."""

    def __init__(self, root_dir: str = "."):
        self.root_dir = os.path.abspath(root_dir)

    def generate_graph_data(self) -> Dict[str, Any]:
        """Serializes AST dependency graph into D3-compatible nodes and links."""
        if not dependency_graph.files_indexed:
            dependency_graph.build_graph(root_dir=self.root_dir)

        nodes: List[Dict[str, Any]] = []
        links: List[Dict[str, Any]] = []
        node_ids = set()

        # 1. Add file nodes
        for f in dependency_graph.files_indexed:
            node_ids.add(f)
            nodes.append({
                "id": f,
                "label": os.path.basename(f),
                "type": "file",
                "size": 18,
                "color": "#3b82f6"
            })

        # 2. Add symbol definition nodes
        for sym_name, locs in dependency_graph.definitions.items():
            sym_id = f"sym:{sym_name}"
            if sym_id not in node_ids:
                node_ids.add(sym_id)
                kind = getattr(locs[0], "kind", "function") if locs else "function"
                color = "#10b981" if kind == "class" else "#f59e0b"
                nodes.append({
                    "id": sym_id,
                    "label": f"{sym_name}()",
                    "type": kind,
                    "size": 12,
                    "color": color
                })

            for loc in locs:
                if loc.file_path in node_ids:
                    links.append({
                        "source": loc.file_path,
                        "target": sym_id,
                        "type": "defines"
                    })

        # 3. Add cross-file call links
        for sym_name, callers in dependency_graph.references.items():
            sym_id = f"sym:{sym_name}"
            if sym_id in node_ids:
                for c in callers:
                    if c.caller_file in node_ids:
                        links.append({
                            "source": c.caller_file,
                            "target": sym_id,
                            "type": "calls"
                        })

        return {
            "title": f"Architecture Graph - {os.path.basename(self.root_dir)}",
            "nodes": nodes,
            "links": links
        }

    def render_html(self, output_path: str = "docs/architecture_graph.html") -> str:
        """Generates a complete standalone HTML interactive visualizer."""
        graph_data = self.generate_graph_data()
        data_json = json.dumps(graph_data, indent=2)

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{graph_data['title']}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; overflow: hidden; }}
    #header {{ position: absolute; top: 16px; left: 16px; z-index: 10; background: rgba(30, 41, 59, 0.9); padding: 12px 20px; border-radius: 8px; border: 1px solid #334155; backdrop-filter: blur(8px); }}
    #header h1 {{ font-size: 16px; font-weight: 700; color: #38bdf8; }}
    #header p {{ font-size: 12px; color: #94a3b8; margin-top: 4px; }}
    #search-box {{ position: absolute; top: 16px; right: 16px; z-index: 10; background: rgba(30, 41, 59, 0.9); padding: 8px 12px; border-radius: 6px; border: 1px solid #334155; }}
    #search-box input {{ background: #0f172a; border: 1px solid #475569; color: #fff; padding: 6px 10px; border-radius: 4px; outline: none; }}
    #canvas {{ width: 100vw; height: 100vh; }}
    .node text {{ font-size: 10px; fill: #cbd5e1; pointer-events: none; }}
    .link {{ stroke: #475569; stroke-opacity: 0.6; stroke-width: 1.5px; }}
  </style>
  <script src="https://d3js.org/d3.v7.min.js"></script>
</head>
<body>
  <div id="header">
    <h1>⚡ Saleha Architecture Graph</h1>
    <p>{len(graph_data['nodes'])} Nodes | {len(graph_data['links'])} Cross-File Links</p>
  </div>
  <div id="search-box">
    <input type="text" id="filterInput" placeholder="Filter symbols...">
  </div>
  <svg id="canvas"></svg>

  <script>
    const data = {data_json};
    const width = window.innerWidth;
    const height = window.innerHeight;

    const svg = d3.select("#canvas")
      .attr("viewBox", [0, 0, width, height]);

    const g = svg.append("g");

    svg.call(d3.zoom().extent([[0, 0], [width, height]]).scaleExtent([0.1, 8]).on("zoom", (event) => {{
      g.attr("transform", event.transform);
    }}));

    const simulation = d3.forceSimulation(data.nodes)
      .force("link", d3.forceLink(data.links).id(d => d.id).distance(80))
      .force("charge", d3.forceManyBody().strength(-120))
      .force("center", d3.forceCenter(width / 2, height / 2));

    const link = g.append("g")
      .attr("class", "links")
      .selectAll("line")
      .data(data.links)
      .join("line")
      .attr("class", "link");

    const node = g.append("g")
      .attr("class", "nodes")
      .selectAll("g")
      .data(data.nodes)
      .join("g")
      .attr("class", "node")
      .call(d3.drag()
        .on("start", dragstarted)
        .on("drag", dragged)
        .on("end", dragended));

    node.append("circle")
      .attr("r", d => d.size || 10)
      .attr("fill", d => d.color || "#3b82f6");

    node.append("text")
      .attr("x", 12)
      .attr("y", 4)
      .text(d => d.label);

    simulation.on("tick", () => {{
      link
        .attr("x1", d => d.source.x)
        .attr("y1", d => d.source.y)
        .attr("x2", d => d.target.x)
        .attr("y2", d => d.target.y);

      node.attr("transform", d => `translate(${{d.x}},${{d.y}})`);
    }});

    function dragstarted(event, d) {{
      if (!event.active) simulation.alphaTarget(0.3).restart();
      d.fx = d.x; d.fy = d.y;
    }}
    function dragged(event, d) {{ d.fx = event.x; d.fy = event.y; }}
    function dragended(event, d) {{
      if (!event.active) simulation.alphaTarget(0);
      d.fx = null; d.fy = null;
    }}
  </script>
</body>
</html>"""

        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        tmp_p = f"{output_path}.tmp.{os.getpid()}"
        with open(tmp_p, "w", encoding="utf-8") as f:
            f.write(html_content)
        os.replace(tmp_p, output_path)

        return os.path.abspath(output_path)


# Global instance
graph_visualizer = ArchitectureGraphVisualizer()
