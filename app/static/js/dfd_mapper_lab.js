(function () {
  const React = window.React;
  const ReactDOM = window.ReactDOM;
  const ReactFlowLib = window.ReactFlow;
  const e = React.createElement;

  const ANSWERS_KEY = "dfd_mapper_lab_answers";
  const EXTRACT_KEY = "dfd_mapper_lab_extract";
  const GRAPH_KEY = "dfd_mapper_lab_graph";
  const ROLES = ["actor", "interface", "process", "llm", "data_store", "tool", "external", "output", "action"];

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

  function parseJson(text, label) {
    try {
      const parsed = JSON.parse(text || "{}");
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        return { value: null, error: `${label} must be a JSON object.` };
      }
      return { value: parsed, error: null };
    } catch (error) {
      return { value: null, error: `${label} contains invalid JSON: ${error.message}` };
    }
  }

  function graphForFlow(graph) {
    const nodes = Array.isArray(graph?.nodes) ? graph.nodes : [];
    const edges = Array.isArray(graph?.edges) ? graph.edges : [];
    return {
      nodes: nodes.map((node) => ({ ...node, type: "dfdNode" })),
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
    // Legacy static fixtures are intentionally retained for console/manual debugging.
    const legacySamples = window.mockDfdInputs || [];
    const initialGraph = React.useMemo(storageGraph, []);
    const responseFiles = window.dfdMapperLabResponseFiles || [];
    const [selectedResponse, setSelectedResponse] = React.useState("");
    const [extractFiles, setExtractFiles] = React.useState([]);
    const [selectedExtract, setSelectedExtract] = React.useState("");
    const [answersText, setAnswersText] = React.useState(window.localStorage.getItem(ANSWERS_KEY) || pretty(legacySamples[0]?.answersByFlowId));
    const [extractText, setExtractText] = React.useState(window.localStorage.getItem(EXTRACT_KEY) || pretty(legacySamples[0]?.qwenExtract));
    const [nodes, setNodes] = React.useState(initialGraph.nodes);
    const [edges, setEdges] = React.useState(initialGraph.edges);
    const [selectedNodeId, setSelectedNodeId] = React.useState(initialGraph.nodes[0]?.id || null);
    const [status, setStatus] = React.useState("Ready.");
    const [statusType, setStatusType] = React.useState("info");
    const flowRef = React.useRef(null);

    React.useEffect(() => {
      fetch("/api/llm-extracts")
        .then((response) => response.ok ? response.json() : { files: [] })
        .then((payload) => setExtractFiles(Array.isArray(payload.files) ? payload.files : []))
        .catch(() => setExtractFiles([]));
    }, []);

    React.useEffect(() => {
      window.localStorage.setItem(ANSWERS_KEY, answersText);
    }, [answersText]);

    React.useEffect(() => {
      window.localStorage.setItem(EXTRACT_KEY, extractText);
    }, [extractText]);

    const selectedNode = nodes.find((node) => node.id === selectedNodeId) || null;

    const graphPayload = React.useCallback(() => ({
      nodes,
      edges: edges.map(({ id, source, target, label, type, animated, data }) => ({ id, source, target, label, type, animated, data })),
      viewport: flowRef.current ? flowRef.current.getViewport() : { x: 0, y: 0, zoom: 1 },
    }), [nodes, edges]);

    const loadExtract = React.useCallback(async () => {
      if (!selectedExtract) {
        setStatus("Select an LLM extract file first.");
        setStatusType("warning");
        return;
      }
      try {
        const response = await fetch(`/api/llm-extracts/${encodeURIComponent(selectedExtract)}`);
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.description || "Unable to load extract.");
        setExtractText(payload.parsed ? pretty(payload.parsed) : payload.raw || "");
        setStatus(payload.parse_error || `Loaded ${payload.filename}.`);
        setStatusType(payload.parse_error ? "warning" : "info");
      } catch (error) {
        setStatus(error.message || "Unable to load extract.");
        setStatusType("error");
      }
    }, [selectedExtract]);

    const loadResponse = React.useCallback(async () => {
      if (!selectedResponse) {
        setStatus("Select a response file first.");
        setStatusType("warning");
        return;
      }
      try {
        const response = await fetch(`/api/responses/${encodeURIComponent(selectedResponse)}`);
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.description || "Unable to load response.");
        setAnswersText(pretty(payload.answers_by_flow_id));
        setStatus(`Loaded response: ${payload.filename}.`);
        setStatusType("info");
      } catch (error) {
        setStatus(error.message || "Unable to load response.");
        setStatusType("error");
      }
    }, [selectedResponse]);

    const generateDfd = React.useCallback(() => {
      const answers = parseJson(answersText, "answers_by_flow_id");
      if (answers.error) {
        setStatus(answers.error);
        setStatusType("error");
        return;
      }

      const extract = parseJson(extractText, "LLM extract");
      const qwenExtract = extract.error ? null : extract.value;
      const graph = window.DfdMapper.buildDfdGraph({
        answersByFlowId: answers.value,
        qwenExtract,
        mode: "compact",
      });
      const flowGraph = graphForFlow(graph);
      setNodes(flowGraph.nodes);
      setEdges(flowGraph.edges);
      setSelectedNodeId(flowGraph.nodes[0]?.id || null);
      window.localStorage.setItem(GRAPH_KEY, JSON.stringify(graph));
      window.setTimeout(() => flowRef.current?.fitView({ padding: 0.18, duration: 250 }), 0);
      if (extract.error) {
        setStatus("No valid LLM extract loaded. Generated DFD from questionnaire answers only.");
        setStatusType("warning");
      } else {
        setStatus(`Generated ${flowGraph.nodes.length} nodes and ${flowGraph.edges.length} edges.`);
        setStatusType("info");
      }
    }, [answersText, extractText]);

    const clear = React.useCallback(() => {
      setAnswersText("{}");
      setExtractText("{}");
      setNodes([]);
      setEdges([]);
      setSelectedNodeId(null);
      window.localStorage.removeItem(ANSWERS_KEY);
      window.localStorage.removeItem(EXTRACT_KEY);
      window.localStorage.removeItem(GRAPH_KEY);
      setStatus("Cleared lab inputs and graph.");
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
      setStatus("Loaded graph from localStorage.");
      setStatusType("info");
      window.setTimeout(() => flowRef.current?.fitView({ padding: 0.18, duration: 250 }), 0);
    }, []);

    const updateSelectedNode = React.useCallback((field, value) => {
      if (!selectedNodeId) return;
      setNodes((current) => current.map((node) => {
        if (node.id !== selectedNodeId) return node;
        return { ...node, data: { ...node.data, [field]: value } };
      }));
    }, [selectedNodeId]);

    return e("div", { className: "mapper-shell" }, [
      e("aside", { key: "left", className: "mapper-panel" }, [
        e("h5", { key: "extract-title" }, "Inputs"),
        e("label", { key: "response-label", className: "form-label", htmlFor: "responseFile" }, "Select response"),
        e("div", { key: "response-row", className: "d-flex gap-2 mb-3" }, [
          e("select", {
            key: "select",
            id: "responseFile",
            className: "form-select",
            value: selectedResponse,
            onChange: (event) => setSelectedResponse(event.target.value),
          }, [
            e("option", { key: "empty", value: "" }, responseFiles.length ? "Select response from /responses" : "No response files found"),
            ...responseFiles.map((file) => e("option", { key: file, value: file }, file)),
          ]),
          e("button", { key: "button", className: "btn btn-outline-primary", onClick: loadResponse }, "Load Response"),
        ]),
        e("label", { key: "file-label", className: "form-label", htmlFor: "extractFile" }, "Select LLM extract"),
        e("div", { key: "file-row", className: "d-flex gap-2 mb-3" }, [
          e("select", {
            key: "select",
            id: "extractFile",
            className: "form-select",
            value: selectedExtract,
            onChange: (event) => setSelectedExtract(event.target.value),
          }, [
            e("option", { key: "empty", value: "" }, extractFiles.length ? "Select extract" : "No extract files found"),
            ...extractFiles.map((file) => e("option", { key: file, value: file }, file)),
          ]),
          e("button", { key: "button", className: "btn btn-outline-primary", onClick: loadExtract }, "Load Extract"),
        ]),
        e("label", { key: "answers-label", className: "form-label", htmlFor: "answersJson" }, "answers_by_flow_id JSON"),
        e("textarea", {
          key: "answers",
          id: "answersJson",
          className: "form-control mb-3",
          value: answersText,
          onChange: (event) => setAnswersText(event.target.value),
        }),
        e("label", { key: "extract-label", className: "form-label", htmlFor: "extractJson" }, "Optional Qwen/LLM extract JSON"),
        e("textarea", {
          key: "extract",
          id: "extractJson",
          className: "form-control mb-3",
          value: extractText,
          onChange: (event) => setExtractText(event.target.value),
        }),
        e("div", { key: "actions", className: "mapper-actions" }, [
          e("button", { key: "generate", className: "btn btn-primary", onClick: generateDfd }, "Generate DFD"),
          e("button", { key: "clear", className: "btn btn-outline-primary", onClick: clear }, "Clear"),
          e("button", { key: "export", className: "btn btn-outline-primary", onClick: () => downloadJson("dfd-mapper-lab-graph.json", graphPayload()) }, "Export React Flow JSON"),
          e("button", { key: "save", className: "btn btn-outline-primary", onClick: saveGraph }, "Save"),
          e("button", { key: "load", className: "btn btn-outline-primary", onClick: loadGraph }, "Load"),
        ]),
        e("div", { key: "status", className: `mapper-status mt-3 ${statusType}` }, status),
      ]),
      e("section", { key: "canvas", className: "mapper-canvas" },
        e("div", { className: "mapper-canvas-inner" },
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
            onConnect: (params) => setEdges((current) => addEdge({
              ...params,
              id: `edge_${Date.now()}`,
              label: "Data Flow",
              type: "smoothstep",
              animated: false,
              markerEnd: { type: "arrowclosed" },
              style: { stroke: "#60a5fa", strokeWidth: 1.6 },
              labelStyle: { fill: "#f8fafc", fontSize: 12, fontWeight: 700 },
              labelBgStyle: { fill: "rgba(15, 23, 42, 0.94)", stroke: "rgba(96, 165, 250, 0.45)", strokeWidth: 1 },
              labelBgPadding: [8, 5],
              labelBgBorderRadius: 6,
            }, current)),
            onSelectionChange: (selection) => setSelectedNodeId(selection?.nodes?.[0]?.id || null),
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
        e("h5", { key: "title" }, "Selected Node"),
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
                  value: selectedNode.data.role,
                  onChange: (event) => updateSelectedNode("role", event.target.value),
                }, ROLES.map((role) => e("option", { key: role, value: role }, role.replace(/_/g, " ")))),
              ]),
              e("div", { key: "desc", className: "mapper-status" }, selectedNode.data.description || selectedNode.data.source || ""),
            ])
          : e("p", { key: "empty", className: "mapper-status" }, "Select a node to edit its label and role."),
      ]),
    ]);
  }

  ReactDOM.createRoot(document.getElementById("dfd-mapper-lab-root")).render(e(App));
})();
