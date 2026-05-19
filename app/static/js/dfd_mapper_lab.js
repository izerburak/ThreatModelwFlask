(function () {
  const React = window.React;
  const ReactDOM = window.ReactDOM;
  const ReactFlowLib = window.ReactFlow;
  const e = React.createElement;

  const GRAPH_KEY = "dfd_mapper_lab_graph";
  const ROLES = ["actor", "interface", "process", "llm", "data_store", "tool", "external", "output", "action"];
  const PALETTE = [
    { role: "actor", label: "Actor", description: "Person, user group, or initiating system." },
    { role: "external", label: "External Entity", description: "Third-party service, vendor, or untrusted source." },
    { role: "tool", label: "Tool", description: "Tool call, API action, or agent capability." },
    { role: "data_store", label: "Data Store", description: "Database, vector store, bucket, or knowledge source." },
    { role: "interface", label: "Interface", description: "Web UI, API endpoint, CLI, or integration boundary." },
    { role: "process", label: "Process", description: "Backend service, orchestration, or application logic." },
    { role: "llm", label: "LLM", description: "Model service or hosted language model." },
    { role: "output", label: "Output", description: "Response, notification, report, or downstream result." },
  ];

  const {
    default: ReactFlow,
    addEdge,
    applyEdgeChanges,
    applyNodeChanges,
    Background,
    Controls,
    MiniMap,
    Panel,
  } = ReactFlowLib;

  const nodeTypes = { dfdNode: window.DfdNode };

  function pretty(value) {
    return JSON.stringify(value || {}, null, 2);
  }

  function graphForFlow(graph) {
    const nodes = Array.isArray(graph?.nodes) ? graph.nodes : [];
    const edges = Array.isArray(graph?.edges) ? graph.edges : [];
    return {
      nodes: nodes.map((node) => ({
        ...node,
        type: "dfdNode",
        data: normalizeNodeData(node),
      })),
      edges: edges.map((edge) => ({
        ...edge,
        markerEnd: { type: "arrowclosed" },
        style: { stroke: "#60a5fa", strokeWidth: 1.6 },
        labelStyle: { fill: "#f8fafc", fontSize: 12, fontWeight: 700 },
        labelBgStyle: { fill: "rgba(15, 23, 42, 0.94)", stroke: "rgba(96, 165, 250, 0.45)", strokeWidth: 1 },
        labelBgPadding: [8, 5],
        labelBgBorderRadius: 6,
      })),
    };
  }

  function normalizeNodeData(node) {
    const data = node?.data && typeof node.data === "object" ? node.data : {};
    const role = data.role || roleFromNodeType(node?.type, data.label);
    return {
      ...data,
      label: data.label || node?.id || "Unnamed Node",
      role,
      source: data.source || data.notes || node?.type || "saved DFD",
      description: data.description || data.notes || "",
    };
  }

  function roleFromNodeType(type, label) {
    const value = String(type || "").toLowerCase();
    const text = `${value} ${String(label || "").toLowerCase()}`;
    if (value.includes("user") || value.includes("actor") || value === "admin") return "actor";
    if (value.includes("web") || value.includes("mobile") || value.includes("api") || value.includes("panel")) return "interface";
    if (value.includes("llm") || text.includes("model")) return "llm";
    if (value.includes("database") || value.includes("storage") || value.includes("vector")) return "data_store";
    if (value.includes("tool")) return "tool";
    if (value.includes("third_party") || value.includes("external")) return "external";
    if (value.includes("output")) return "output";
    return "process";
  }

  function decorateEdge(edge) {
    return {
      ...edge,
      markerEnd: { type: "arrowclosed" },
      style: { stroke: "#60a5fa", strokeWidth: 1.6 },
      labelStyle: { fill: "#f8fafc", fontSize: 12, fontWeight: 700 },
      labelBgStyle: { fill: "rgba(15, 23, 42, 0.94)", stroke: "rgba(96, 165, 250, 0.45)", strokeWidth: 1 },
      labelBgPadding: [8, 5],
      labelBgBorderRadius: 6,
    };
  }

  function createManualNode(role, label, position) {
    return {
      id: `node_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      type: "dfdNode",
      position,
      selected: true,
      data: {
        label,
        role,
        source: "manual",
        description: "",
      },
    };
  }

  function storageGraph() {
    try {
      const parsed = JSON.parse(window.localStorage.getItem(GRAPH_KEY) || "{}");
      if (Array.isArray(parsed.nodes) && Array.isArray(parsed.edges)) return graphForFlow(parsed);
    } catch (error) {
      return { nodes: [], edges: [] };
    }
    return { nodes: [], edges: [] };
  }

  function downloadJson(filename, payload) {
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  }

  function App() {
    const initialGraph = React.useMemo(storageGraph, []);
    const initialDfdFiles = window.dfdMapperLabDfdFiles || [];
    const [dfdFiles, setDfdFiles] = React.useState(initialDfdFiles);
    const [selectedDfd, setSelectedDfd] = React.useState(window.dfdMapperLabSelectedDfd || "");
    const [nodes, setNodes] = React.useState(initialGraph.nodes);
    const [edges, setEdges] = React.useState(initialGraph.edges);
    const [selectedNodeId, setSelectedNodeId] = React.useState(initialGraph.nodes[0]?.id || null);
    const [selectedEdgeId, setSelectedEdgeId] = React.useState(null);
    const [status, setStatus] = React.useState("Ready.");
    const [statusType, setStatusType] = React.useState("info");
    const flowRef = React.useRef(null);
    const canvasRef = React.useRef(null);

    React.useEffect(() => {
      fetch("/api/dfd-graphs")
        .then((response) => response.ok ? response.json() : { files: [] })
        .then((payload) => setDfdFiles(Array.isArray(payload.files) ? payload.files : []))
        .catch(() => setDfdFiles(initialDfdFiles));
    }, []);

    const selectedNode = nodes.find((node) => node.id === selectedNodeId) || null;
    const selectedEdge = edges.find((edge) => edge.id === selectedEdgeId) || null;

    const graphPayload = React.useCallback(() => ({
      nodes,
      edges: edges.map(({ id, source, target, label, type, animated, data }) => ({ id, source, target, label, type, animated, data })),
      viewport: flowRef.current ? flowRef.current.getViewport() : { x: 0, y: 0, zoom: 1 },
    }), [nodes, edges]);

    const loadDfd = React.useCallback(async (filename = selectedDfd) => {
      if (!filename) {
        setStatus("Select a saved DFD first.");
        setStatusType("warning");
        return;
      }
      try {
        const response = await fetch(`/api/dfd-graphs/${encodeURIComponent(filename)}`);
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.description || "Unable to load DFD.");
        const flowGraph = graphForFlow(payload.graph);
        setNodes(flowGraph.nodes);
        setEdges(flowGraph.edges);
        setSelectedNodeId(flowGraph.nodes[0]?.id || null);
        setSelectedEdgeId(null);
        window.localStorage.setItem(GRAPH_KEY, JSON.stringify(payload.graph));
        const metadata = payload.graph?.metadata || {};
        setStatus(`Loaded DFD: ${metadata.display_name || metadata.pipeline_id || payload.filename}.`);
        setStatusType("info");
        window.setTimeout(() => flowRef.current?.fitView({ padding: 0.18, duration: 250 }), 0);
      } catch (error) {
        setStatus(error.message || "Unable to load DFD.");
        setStatusType("error");
      }
    }, [selectedDfd]);

    React.useEffect(() => {
      if (!selectedDfd) return;
      loadDfd(selectedDfd);
    }, []);

    const clear = React.useCallback(() => {
      setNodes([]);
      setEdges([]);
      setSelectedNodeId(null);
      window.localStorage.removeItem(GRAPH_KEY);
      setStatus("Cleared graph.");
      setStatusType("info");
    }, []);

    const saveGraph = React.useCallback(() => {
      window.localStorage.setItem(GRAPH_KEY, JSON.stringify(graphPayload()));
      setStatus("Saved graph to localStorage.");
      setStatusType("info");
    }, [graphPayload]);

    const loadGraph = React.useCallback(() => {
      const graph = storageGraph();
      setNodes(graph.nodes);
      setEdges(graph.edges);
      setSelectedNodeId(graph.nodes[0]?.id || null);
      setSelectedEdgeId(null);
      setStatus("Loaded graph from localStorage.");
      setStatusType("info");
      window.setTimeout(() => flowRef.current?.fitView({ padding: 0.18, duration: 250 }), 0);
    }, []);

    const addNodeFromPalette = React.useCallback((item) => {
      const viewport = flowRef.current?.getViewport?.() || { x: 0, y: 0, zoom: 1 };
      const bounds = canvasRef.current?.getBoundingClientRect?.();
      const index = nodes.length;
      const fallback = { x: 100 + (index % 4) * 40, y: 100 + Math.floor(index / 4) * 40 };
      const position = bounds
        ? {
            x: Math.round((bounds.width / 2 - viewport.x) / viewport.zoom - 110),
            y: Math.round((bounds.height / 2 - viewport.y) / viewport.zoom - 45),
          }
        : fallback;
      const node = createManualNode(item.role, item.label, position);
      setNodes((current) => current.map((existing) => ({ ...existing, selected: false })).concat(node));
      setEdges((current) => current.map((edge) => ({ ...edge, selected: false })));
      setSelectedNodeId(node.id);
      setSelectedEdgeId(null);
      setStatus(`${item.label} added to the graph.`);
      setStatusType("info");
    }, [nodes.length]);

    const deleteSelected = React.useCallback(() => {
      if (!selectedNodeId && !selectedEdgeId) {
        setStatus("Select a node or edge to remove.");
        setStatusType("warning");
        return;
      }
      const removedNodeId = selectedNodeId;
      setNodes((current) => current.filter((node) => node.id !== removedNodeId));
      setEdges((current) => current.filter((edge) => {
        if (selectedEdgeId && edge.id === selectedEdgeId) return false;
        if (removedNodeId && (edge.source === removedNodeId || edge.target === removedNodeId)) return false;
        return true;
      }));
      setSelectedNodeId(null);
      setSelectedEdgeId(null);
      setStatus(removedNodeId ? "Selected node and connected flows removed." : "Selected flow removed.");
      setStatusType("info");
    }, [selectedEdgeId, selectedNodeId]);

    const updateSelectedNode = React.useCallback((field, value) => {
      if (!selectedNodeId) return;
      setNodes((current) => current.map((node) => {
        if (node.id !== selectedNodeId) return node;
        return { ...node, data: { ...node.data, [field]: value } };
      }));
    }, [selectedNodeId]);

    const updateSelectedEdge = React.useCallback((field, value) => {
      if (!selectedEdgeId) return;
      setEdges((current) => current.map((edge) => (
        edge.id === selectedEdgeId ? { ...edge, [field]: value } : edge
      )));
    }, [selectedEdgeId]);

    return e("div", { className: "mapper-shell" }, [
      e("aside", { key: "left", className: "mapper-panel" }, [
        e("h5", { key: "extract-title" }, "Inputs"),
        e("label", { key: "dfd-label", className: "form-label", htmlFor: "dfdFile" }, "Saved DFD"),
        e("div", { key: "dfd-row", className: "d-flex gap-2 mb-3" }, [
          e("select", {
            key: "select",
            id: "dfdFile",
            className: "form-select",
            value: selectedDfd,
            onChange: (event) => setSelectedDfd(event.target.value),
          }, [
            e("option", { key: "empty", value: "" }, dfdFiles.length ? "Select generated DFD" : "No generated DFDs found"),
            ...dfdFiles.map((file) => e("option", { key: file.filename, value: file.filename },
              `${file.label || file.filename} (${file.node_count || 0} nodes)`
            )),
          ]),
          e("button", { key: "button", className: "btn btn-outline-primary", onClick: () => loadDfd() }, "Load DFD"),
        ]),
        e("div", { key: "palette", className: "mapper-toolbox mb-3" }, [
          e("div", { key: "title", className: "mapper-toolbox-title" }, "Graph Tools"),
          e("div", { key: "grid", className: "mapper-palette" },
            PALETTE.map((item) =>
              e("button", {
                key: item.role,
                type: "button",
                className: "mapper-palette-item",
                onClick: () => addNodeFromPalette(item),
                title: item.description,
              }, [
                e("span", { key: "role", className: `mapper-role-dot ${item.role}` }),
                e("span", { key: "label" }, item.label),
              ])
            )
          ),
          e("button", {
            key: "delete",
            type: "button",
            className: "btn btn-outline-danger btn-sm mt-2",
            onClick: deleteSelected,
            disabled: !selectedNode && !selectedEdge,
          }, "Remove Selected"),
        ]),
        e("div", { key: "actions", className: "mapper-actions" }, [
          e("button", { key: "clear", className: "btn btn-outline-primary", onClick: clear }, "Clear"),
          e("button", { key: "export", className: "btn btn-outline-primary", onClick: () => downloadJson("dfd-mapper-lab-graph.json", graphPayload()) }, "Export React Flow JSON"),
          e("button", { key: "save", className: "btn btn-outline-primary", onClick: saveGraph }, "Save"),
          e("button", { key: "load", className: "btn btn-outline-primary", onClick: loadGraph }, "Load"),
        ]),
        e("div", { key: "status", className: `mapper-status mt-3 ${statusType}` }, status),
      ]),
      e("section", { key: "canvas", className: "mapper-canvas" },
        e("div", { className: "mapper-canvas-inner", ref: canvasRef },
          e(ReactFlow, {
            nodes,
            edges,
            nodeTypes,
            onInit: (instance) => {
              flowRef.current = instance;
              window.setTimeout(() => instance.fitView({ padding: 0.18 }), 0);
            },
            onNodesChange: (changes) => setNodes((current) => applyNodeChanges(changes, current)),
            onEdgesChange: (changes) => setEdges((current) => applyEdgeChanges(changes, current)),
            onConnect: (params) => setEdges((current) => addEdge(decorateEdge({
              ...params,
              id: `edge_${Date.now()}`,
              label: "Data Flow",
              type: "smoothstep",
              animated: false,
            }), current)),
            onSelectionChange: (selection) => {
              setSelectedNodeId(selection?.nodes?.[0]?.id || null);
              setSelectedEdgeId(selection?.edges?.[0]?.id || null);
            },
            fitView: true,
            deleteKeyCode: ["Backspace", "Delete"],
            defaultEdgeOptions: {
              type: "smoothstep",
              markerEnd: { type: "arrowclosed" },
              style: { stroke: "#60a5fa", strokeWidth: 1.6 },
              labelStyle: { fill: "#f8fafc", fontSize: 12, fontWeight: 700 },
              labelBgStyle: { fill: "rgba(15, 23, 42, 0.94)", stroke: "rgba(96, 165, 250, 0.45)", strokeWidth: 1 },
              labelBgPadding: [8, 5],
              labelBgBorderRadius: 6,
            },
          }, [
            e(Background, { key: "background", color: "#1e293b", gap: 18 }),
            e(MiniMap, { key: "minimap", zoomable: true, pannable: true }),
            e(Controls, { key: "controls" }),
            e(Panel, { key: "panel", position: "top-left" }, e("div", { className: "mapper-status" }, "Drag, connect, edit, or delete selected graph elements.")),
          ])
        )
      ),
      e("aside", { key: "right", className: "mapper-panel" }, [
        e("h5", { key: "title" }, selectedEdge && !selectedNode ? "Selected Flow" : "Selected Node"),
        selectedNode
          ? e("div", { key: "fields" }, [
              e("div", { key: "label-field", className: "selected-field" }, [
                e("label", { key: "label", className: "form-label", htmlFor: "nodeLabel" }, "Label"),
                e("input", {
                  key: "input",
                  id: "nodeLabel",
                  className: "form-control",
                  value: selectedNode.data.label,
                  onChange: (event) => updateSelectedNode("label", event.target.value),
                }),
              ]),
              e("div", { key: "role-field", className: "selected-field" }, [
                e("label", { key: "label", className: "form-label", htmlFor: "nodeRole" }, "Role"),
                e("select", {
                  key: "select",
                  id: "nodeRole",
                  className: "form-select",
                  value: selectedNode.data.role || "process",
                  onChange: (event) => updateSelectedNode("role", event.target.value),
                }, ROLES.map((role) => e("option", { key: role, value: role }, role.replace(/_/g, " ")))),
              ]),
              e("div", { key: "desc", className: "mapper-status" }, selectedNode.data.description || selectedNode.data.source || ""),
              e("button", {
                key: "delete-node",
                type: "button",
                className: "btn btn-outline-danger btn-sm",
                onClick: deleteSelected,
              }, "Remove Node"),
            ])
          : selectedEdge
            ? e("div", { key: "edge-fields" }, [
                e("div", { key: "label-field", className: "selected-field" }, [
                  e("label", { key: "label", className: "form-label", htmlFor: "edgeLabel" }, "Label"),
                  e("input", {
                    key: "input",
                    id: "edgeLabel",
                    className: "form-control",
                    value: selectedEdge.label || "",
                    onChange: (event) => updateSelectedEdge("label", event.target.value),
                  }),
                ]),
                e("button", {
                  key: "delete-edge",
                  type: "button",
                  className: "btn btn-outline-danger btn-sm",
                  onClick: deleteSelected,
                }, "Remove Flow"),
              ])
            : e("p", { key: "empty", className: "mapper-status" }, "Select a node or flow to edit it."),
      ]),
    ]);
  }

  ReactDOM.createRoot(document.getElementById("dfd-mapper-lab-root")).render(e(App));
})();
