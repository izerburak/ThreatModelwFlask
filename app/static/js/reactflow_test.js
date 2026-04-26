(function () {
  const React = window.React;
  const ReactDOM = window.ReactDOM;
  const ReactFlowLib = window.ReactFlow;

  if (!React || !ReactDOM || !ReactFlowLib) {
    const root = document.getElementById("reactflow-test-root");
    if (root) {
      root.innerHTML = '<div class="alert alert-danger">React Flow sandbox assets did not load correctly.</div>';
    }
    return;
  }

  const STORAGE_KEY = "reactflow_test_graph";
  const e = React.createElement;

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

  const palette = [
    { kind: "external_user", label: "External User", notes: "Anonymous public internet user.", color: "#38bdf8" },
    { kind: "authenticated_user", label: "Authenticated User", notes: "Logged-in customer or public user.", color: "#0ea5e9" },
    { kind: "admin", label: "Administrator", notes: "Privileged internal operator.", color: "#f43f5e" },
    { kind: "internal_user", label: "Internal Employee", notes: "Internal business user.", color: "#06b6d4" },
    { kind: "third_party_actor", label: "Third Party System", notes: "External integrated system.", color: "#8b5cf6" },
    { kind: "web_app", label: "Web Application", notes: "Frontend or browser-facing application.", color: "#22c55e" },
    { kind: "mobile_app", label: "Mobile App", notes: "Mobile client application.", color: "#10b981" },
    { kind: "api_service", label: "API Service", notes: "REST / GraphQL / backend API.", color: "#14b8a6" },
    { kind: "backend_service", label: "Backend Service", notes: "Internal business logic service.", color: "#16a34a" },
    { kind: "admin_panel", label: "Admin Panel", notes: "Privileged management interface.", color: "#84cc16" },
    { kind: "auth_service", label: "Auth Service", notes: "Authentication / identity provider.", color: "#f97316" },
    { kind: "waf", label: "WAF", notes: "Web Application Firewall.", color: "#ef4444" },
    { kind: "gateway", label: "API Gateway", notes: "Traffic broker / access control layer.", color: "#fb7185" },
    { kind: "secrets_vault", label: "Secrets Vault", notes: "Credential / secrets manager.", color: "#f59e0b" },
    { kind: "logging", label: "Logging / SIEM", notes: "Audit logging and monitoring.", color: "#eab308" },
    { kind: "llm", label: "LLM", notes: "Hosted or local language model.", color: "#ec4899" },
    { kind: "rag_engine", label: "RAG Engine", notes: "Retrieval orchestration layer.", color: "#ec4899" },
    { kind: "vector_db", label: "Vector Database", notes: "Embedding storage / semantic search.", color: "#c084fc" },
    { kind: "tool_executor", label: "Tool Executor", notes: "LLM tool-calling execution layer.", color: "#f43f5e" },
    { kind: "prompt_store", label: "Prompt Store", notes: "Prompt templates / policies.", color: "#d946ef" },
    { kind: "database", label: "Database", notes: "Structured persistent data.", color: "#f59e0b" },
    { kind: "file_storage", label: "File Storage", notes: "Documents / object storage.", color: "#fbbf24" },
    { kind: "cache", label: "Cache", notes: "Temporary in-memory storage.", color: "#fb923c" },
    { kind: "trust_boundary", label: "Trust Boundary", notes: "Logical security boundary.", color: "#94a3b8" },
    { kind: "internet_zone", label: "Internet Zone", notes: "Public untrusted network.", color: "#38bdf8" },
    { kind: "internal_zone", label: "Internal Zone", notes: "Trusted corporate network.", color: "#22c55e" },
    { kind: "cloud_boundary", label: "Cloud Boundary", notes: "Cloud provider trust zone.", color: "#a855f7" },
    { kind: "text_note", label: "Text Note", notes: "Annotation or analyst note.", color: "#cbd5e1" },
    { kind: "process", label: "Process", notes: "Generic processing component.", color: "#818cf8" },
  ];

  function kindConfig(kind) {
    return palette.find((item) => item.kind === kind) || palette[1];
  }

  function nodeStyle(kind) {
    const config = kindConfig(kind);
    const isBoundary = ["trust_boundary", "internet_zone", "internal_zone", "cloud_boundary"].includes(kind);
    return {
      border: `1px solid ${config.color}`,
      borderRadius: isBoundary ? "18px" : "14px",
      background: "rgba(15, 23, 42, 0.95)",
      color: "#f8fafc",
      minWidth: isBoundary ? 260 : 180,
      boxShadow: "0 12px 24px rgba(2, 6, 23, 0.24)",
    };
  }

  function createNode(kind, position, label, notes, id) {
    const config = kindConfig(kind);
    return {
      id: id || `node_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      type: "default",
      position,
      data: {
        label: label || config.label,
        kind: kind,
        notes: notes || config.notes,
      },
      style: nodeStyle(kind),
      width: ["trust_boundary", "internet_zone", "internal_zone", "cloud_boundary"].includes(kind) ? 860 : undefined,
      height: ["trust_boundary", "internet_zone", "internal_zone", "cloud_boundary"].includes(kind) ? 390 : undefined,
    };
  }

  function createEdge(source, target, label, id) {
    return {
      id: id || `edge_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      source: source,
      target: target,
      label: label || "Data Flow",
      markerEnd: { type: "arrowclosed" },
      style: { stroke: "#60a5fa", strokeWidth: 1.6 },
      labelStyle: { fill: "#cbd5e1", fontSize: 12 },
    };
  }

  function graphForEditor(graph) {
    const safeGraph = graph || {};
    const safeNodes = Array.isArray(safeGraph.nodes) ? safeGraph.nodes : [];
    const safeEdges = Array.isArray(safeGraph.edges) ? safeGraph.edges : [];

    return {
      nodes: safeNodes.map((node) => {
        const data = node.data || {};
        const kind = node.type === "default" ? (data.kind || "process") : (node.type || data.kind || "process");
        return createNode(
          kind,
          node.position || { x: 0, y: 0 },
          data.label || kindConfig(kind).label,
          data.notes || "",
          node.id
        );
      }),
      edges: safeEdges
        .filter((edge) => edge && edge.source && edge.target)
        .map((edge) => createEdge(edge.source, edge.target, edge.label || "Uses", edge.id)),
      viewport: safeGraph.viewport || { x: 0, y: 0, zoom: 0.9 },
    };
  }

  function createSampleGraph() {
    return {
      nodes: [
        createNode("user", { x: 80, y: 180 }, "User", "Human actor", "node_1"),
        createNode("process", { x: 340, y: 180 }, "Web App", "Main application layer", "node_2"),
        createNode("llm", { x: 620, y: 180 }, "LLM", "Future model component", "node_3"),
        createNode("database", { x: 900, y: 180 }, "Database", "Persistent storage", "node_4"),
      ],
      edges: [
        createEdge("node_1", "node_2", "Request", "edge_1"),
        createEdge("node_2", "node_3", "Prompt", "edge_2"),
        createEdge("node_3", "node_4", "Context", "edge_3"),
      ],
      viewport: { x: 0, y: 0, zoom: 0.95 },
    };
  }

  function graphFromStorage() {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return createSampleGraph();
    }

    try {
      const parsed = JSON.parse(raw);
      if (!parsed || !Array.isArray(parsed.nodes) || !Array.isArray(parsed.edges)) {
        return createSampleGraph();
      }
      return graphForEditor(parsed);
    } catch (error) {
      return createSampleGraph();
    }
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
    const initial = React.useMemo(() => graphFromStorage(), []);
    const [nodes, setNodes] = React.useState(initial.nodes);
    const [edges, setEdges] = React.useState(initial.edges);
    const [selectedNodeId, setSelectedNodeId] = React.useState(initial.nodes[0] ? initial.nodes[0].id : null);
    const [status, setStatus] = React.useState("Sample graph loaded.");
    const [extractText, setExtractText] = React.useState("");
    const [extractMessage, setExtractMessage] = React.useState("");
    const [extractMessageType, setExtractMessageType] = React.useState("info");
    const [isGeneratingFromExtract, setIsGeneratingFromExtract] = React.useState(false);
    const flowRef = React.useRef(null);
    const wrapperRef = React.useRef(null);

    const selectedNode = nodes.find((node) => node.id === selectedNodeId) || null;

    const graphPayload = React.useCallback(() => ({
      nodes: nodes,
      edges: edges.map(({ id, source, target, label, markerEnd, style, labelStyle }) => ({
        id,
        source,
        target,
        label,
        markerEnd,
        style,
        labelStyle,
      })),
      viewport: flowRef.current ? flowRef.current.getViewport() : { x: 0, y: 0, zoom: 1 },
    }), [nodes, edges]);

    const addNode = React.useCallback((kind, position) => {
      const node = createNode(kind, position);
      setNodes((current) => current.concat(node));
      setSelectedNodeId(node.id);
      setStatus(`${node.data.label} added.`);
    }, []);

    const addNodeAtCenter = React.useCallback((kind) => {
      const position = flowRef.current
        ? flowRef.current.project({
            x: (wrapperRef.current && wrapperRef.current.clientWidth ? wrapperRef.current.clientWidth : 900) / 2,
            y: (wrapperRef.current && wrapperRef.current.clientHeight ? wrapperRef.current.clientHeight : 600) / 2,
          })
        : { x: 200, y: 200 };
      addNode(kind, position);
    }, [addNode]);

    const onNodesChange = React.useCallback((changes) => {
      setNodes((current) => applyNodeChanges(changes, current));
    }, []);

    const onEdgesChange = React.useCallback((changes) => {
      setEdges((current) => applyEdgeChanges(changes, current));
    }, []);

    const onConnect = React.useCallback((params) => {
      setEdges((current) => addEdge(createEdge(params.source, params.target, "Data Flow"), current));
      setStatus("Edge created.");
    }, []);

    const onSelectionChange = React.useCallback((selection) => {
      setSelectedNodeId(selection && selection.nodes && selection.nodes[0] ? selection.nodes[0].id : null);
    }, []);

    const onDragOver = React.useCallback((event) => {
      event.preventDefault();
      event.dataTransfer.dropEffect = "move";
    }, []);

    const onDrop = React.useCallback((event) => {
      event.preventDefault();
      const kind = event.dataTransfer.getData("application/reactflow");
      if (!kind || !wrapperRef.current) {
        return;
      }

      const bounds = wrapperRef.current.getBoundingClientRect();
      const position = flowRef.current
        ? flowRef.current.project({
            x: event.clientX - bounds.left,
            y: event.clientY - bounds.top,
          })
        : { x: event.clientX - bounds.left, y: event.clientY - bounds.top };

      addNode(kind, position);
    }, [addNode]);

    const updateSelectedNode = React.useCallback((field, value) => {
      if (!selectedNodeId) {
        return;
      }

      setNodes((current) =>
        current.map((node) => {
          if (node.id !== selectedNodeId) {
            return node;
          }

          const nextKind = field === "kind" ? value : node.data.kind;
          const nextData = {
            ...node.data,
            [field === "kind" ? "kind" : field]: value,
          };

          return {
            ...node,
            data: nextData,
            style: nodeStyle(nextKind),
          };
        })
      );

      setStatus("Node updated.");
    }, [selectedNodeId]);

    const addSampleNodes = React.useCallback(() => {
      const sample = createSampleGraph();
      setNodes(sample.nodes);
      setEdges(sample.edges);
      setSelectedNodeId(sample.nodes[0] ? sample.nodes[0].id : null);
      if (flowRef.current) {
        flowRef.current.setViewport(sample.viewport, { duration: 250 });
      }
      setStatus("Sample graph restored.");
    }, []);

    const autoLayout = React.useCallback(() => {
      setNodes((current) =>
        current.map((node, index) => ({
          ...node,
          position: {
            x: 100 + (index % 4) * 240,
            y: 120 + Math.floor(index / 4) * 180,
          },
        }))
      );
      if (flowRef.current) {
        window.setTimeout(() => flowRef.current.fitView({ padding: 0.2, duration: 250 }), 0);
      }
      setStatus("Auto layout applied.");
    }, []);

    const clearCanvas = React.useCallback(() => {
      setNodes([]);
      setEdges([]);
      setSelectedNodeId(null);
      setStatus("Canvas cleared.");
    }, []);

    const saveJson = React.useCallback(() => {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(graphPayload()));
      setStatus(`Saved to ${STORAGE_KEY}.`);
    }, [graphPayload]);

    const loadJson = React.useCallback(() => {
      const loaded = graphFromStorage();
      setNodes(loaded.nodes);
      setEdges(loaded.edges);
      setSelectedNodeId(loaded.nodes[0] ? loaded.nodes[0].id : null);
      if (flowRef.current) {
        flowRef.current.setViewport(loaded.viewport, { duration: 250 });
      }
      setStatus(`Loaded from ${STORAGE_KEY}.`);
    }, []);

    const exportJson = React.useCallback(() => {
      downloadJson("reactflow-test-graph.json", graphPayload());
      setStatus("Exported JSON.");
    }, [graphPayload]);

    const generateFromExtract = React.useCallback(async () => {
      const trimmed = extractText.trim();
      if (!trimmed) {
        setExtractMessage("Paste LLM Extract JSON before generating.");
        setExtractMessageType("error");
        return;
      }

      let payload;
      try {
        payload = JSON.parse(trimmed);
      } catch (error) {
        setExtractMessage("Invalid JSON. Check the pasted extract and try again.");
        setExtractMessageType("error");
        return;
      }

      if (!payload || typeof payload !== "object" || Array.isArray(payload) || Object.keys(payload).length === 0) {
        setExtractMessage("Empty extract. Paste an object with system_summary or architecture data.");
        setExtractMessageType("error");
        return;
      }

      setIsGeneratingFromExtract(true);
      setExtractMessage("Generating graph from extract...");
      setExtractMessageType("info");

      try {
        const response = await fetch("/api/reactflow/from-extract", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        if (!response.ok) {
          throw new Error(`Server returned ${response.status}`);
        }

        const graph = graphForEditor(await response.json());
        setNodes(graph.nodes);
        setEdges(graph.edges);
        setSelectedNodeId(graph.nodes[0] ? graph.nodes[0].id : null);

        if (flowRef.current) {
          flowRef.current.setViewport(graph.viewport, { duration: 250 });
          window.setTimeout(() => flowRef.current.fitView({ padding: 0.18, duration: 250 }), 0);
        }

        setStatus("Graph generated from extract.");
        setExtractMessage(`Generated ${graph.nodes.length} nodes and ${graph.edges.length} edges.`);
        setExtractMessageType("info");
      } catch (error) {
        setExtractMessage("Server error while generating the graph. Please try again.");
        setExtractMessageType("error");
      } finally {
        setIsGeneratingFromExtract(false);
      }
    }, [extractText]);

    return e("div", null, [
      e("div", { className: "lab-toolbar", key: "toolbar" }, [
        e("div", { key: "copy", className: "lab-toolbar-copy" }, "Simple React Flow sandbox for testing nodes, edges, labels, zoom, pan, and local save/load."),
        e("div", { key: "actions", className: "lab-toolbar-actions" }, [
          e("button", { key: "sample", className: "btn btn-primary", onClick: addSampleNodes }, "Add Sample Nodes"),
          e("button", { key: "layout", className: "btn btn-outline-primary", onClick: autoLayout }, "Auto Layout"),
          e("button", { key: "clear", className: "btn btn-outline-primary", onClick: clearCanvas }, "Clear Canvas"),
          e("button", { key: "save", className: "btn btn-outline-primary", onClick: saveJson }, "Save JSON"),
          e("button", { key: "load", className: "btn btn-outline-primary", onClick: loadJson }, "Load JSON"),
          e("button", { key: "export", className: "btn btn-outline-primary", onClick: exportJson }, "Export JSON"),
        ]),
      ]),
      e("div", { className: "lab-grid", key: "grid" }, [
        e("aside", { className: "lab-panel palette-panel", key: "left" }, [
          e("h5", { key: "title" }, "Palette"),
          e("p", { key: "copy", className: "lab-panel-copy" }, "Click or drag a component into the canvas."),
          e("div", { key: "scroll", className: "palette-scroll" },
            palette.map((item) =>
              e("div", {
                key: item.kind,
                className: "palette-item",
                draggable: true,
                onClick: () => addNodeAtCenter(item.kind),
                onDragStart: (event) => {
                  event.dataTransfer.setData("application/reactflow", item.kind);
                  event.dataTransfer.effectAllowed = "move";
                },
              }, [
                e("strong", { key: "label" }, item.label),
                e("small", { key: "notes" }, item.notes),
              ])
            )
          ),
        ]),
        e("section", { className: "lab-canvas", key: "center" },
          e("div", { className: "canvas-wrapper", ref: wrapperRef },
            e(ReactFlow, {
              nodes: nodes,
              edges: edges,
              onInit: (instance) => {
                flowRef.current = instance;
                window.setTimeout(() => instance.fitView({ padding: 0.2 }), 0);
              },
              onNodesChange: onNodesChange,
              onEdgesChange: onEdgesChange,
              onConnect: onConnect,
              onSelectionChange: onSelectionChange,
              onDragOver: onDragOver,
              onDrop: onDrop,
              fitView: true,
              deleteKeyCode: ["Backspace", "Delete"],
              defaultEdgeOptions: {
                markerEnd: { type: "arrowclosed" },
                style: { stroke: "#60a5fa", strokeWidth: 1.6 },
              },
            }, [
              e(Background, { key: "bg", color: "#1e293b", gap: 18 }),
              e(MiniMap, { key: "map", zoomable: true, pannable: true }),
              e(Controls, { key: "controls" }),
              e(Panel, { key: "panel", position: "top-left" },
                e("div", { className: "lab-status" }, `${status} Delete selected nodes with Backspace/Delete.`)
              ),
            ])
          )
        ),
        e("aside", { className: "lab-panel", key: "right" },
          e("div", null, [
            e("div", { key: "extract", className: "extract-panel" }, [
              e("h5", { key: "title" }, "Extract Mapper"),
              e("label", { key: "label", className: "form-label", htmlFor: "extractJson" }, "Paste LLM Extract JSON"),
              e("textarea", {
                key: "textarea",
                id: "extractJson",
                className: "form-control",
                value: extractText,
                onChange: (event) => setExtractText(event.target.value),
              }),
              e("button", {
                key: "button",
                className: "btn btn-primary w-100 mt-3",
                onClick: generateFromExtract,
                disabled: isGeneratingFromExtract,
              }, isGeneratingFromExtract ? "Generating..." : "Generate From Extract"),
              extractMessage
                ? e("div", {
                    key: "message",
                    className: `extract-message ${extractMessageType === "error" ? "error" : ""}`,
                  }, extractMessage)
                : null,
            ]),
            selectedNode
              ? e("div", { key: "editor" }, [
                e("h5", { key: "title" }, "Selected Node"),
                e("label", { key: "labelText", className: "form-label", htmlFor: "nodeLabel" }, "Label"),
                e("input", {
                  key: "labelInput",
                  id: "nodeLabel",
                  className: "form-control mb-3",
                  value: selectedNode.data.label,
                  onChange: (event) => updateSelectedNode("label", event.target.value),
                }),
                e("label", { key: "typeText", className: "form-label", htmlFor: "nodeKind" }, "Type"),
                e("select", {
                  key: "typeInput",
                  id: "nodeKind",
                  className: "form-select mb-3",
                  value: selectedNode.data.kind,
                  onChange: (event) => updateSelectedNode("kind", event.target.value),
                }, palette.map((item) => e("option", { key: item.kind, value: item.kind }, item.label))),
                e("label", { key: "notesText", className: "form-label", htmlFor: "nodeNotes" }, "Notes"),
                e("textarea", {
                  key: "notesInput",
                  id: "nodeNotes",
                  className: "form-control",
                  rows: 8,
                  value: selectedNode.data.notes || "",
                  onChange: (event) => updateSelectedNode("notes", event.target.value),
                }),
              ])
              : e("div", { key: "empty" }, [
                e("h5", { key: "title" }, "Selected Node"),
                e("p", { key: "copy", className: "lab-panel-copy" }, "Select a node to edit its label, type, and notes."),
              ]),
          ])
        ),
      ]),
    ]);
  }

  const rootElement = document.getElementById("reactflow-test-root");
  ReactDOM.createRoot(rootElement).render(e(App));
})();
