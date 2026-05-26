(function () {
  const React = window.React;
  const ReactDOM = window.ReactDOM;
  const ReactFlowLib = window.ReactFlow;
  const e = React.createElement;

  const GRAPH_KEY = "dfd_mapper_lab_graph";
  const ROLES = ["actor", "interface", "process", "llm", "data_store", "tool", "external", "output", "action"];
  const EDGE_TYPE_OPTIONS = [
    { value: "data", label: "Data flow", defaultLabel: "Data Flow" },
    { value: "request", label: "Request", defaultLabel: "User prompt / request" },
    { value: "prompt", label: "Prompt / LLM", defaultLabel: "LLM request" },
    { value: "rag", label: "RAG / retrieval", defaultLabel: "Retrieval query" },
    { value: "tool", label: "Tool call", defaultLabel: "Tool request" },
    { value: "api", label: "API / DB operation", defaultLabel: "API call request" },
    { value: "response", label: "Response", defaultLabel: "Response" },
    { value: "logging", label: "Logging / audit", defaultLabel: "Telemetry / audit event" },
  ];
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
  const STATIC_SAMPLE = {
    schema_version: "llmsec.adaptive.v1",
    project_id: "demo",
    system_id: "customer-support-ai",
    answers_by_flow_id: {
      Q1: "Customer support assistant",
      Q2: ["Anonymous public internet users", "Authenticated public users"],
      Q3: ["Web-based chat interface", "REST API endpoint"],
      Q7: ["Input filtering", "Prompt templating", "RAG augmentation"],
      Q8: ["Internal knowledge base", "Documentation"],
      Q13: ["Vector DB"],
      Q17: "Third-party cloud API",
      Q23: ["Public internet to web application", "Internal API to model service"],
      Q31: "Rule-based or schema validation",
      Q33: "Prompt/response logging with monitoring",
      Q47: "Logs contain full prompts and responses",
    },
  };

  const {
    default: ReactFlow,
    addEdge,
    applyEdgeChanges,
    applyNodeChanges,
    Background,
    BaseEdge,
    Controls,
    EdgeLabelRenderer,
    MiniMap,
  } = ReactFlowLib;

  const nodeTypes = {
    dfdNode: window.DfdNode,
    custom: window.StaticDfdNode || window.DfdNode,
  };
  const edgeTypes = {
    staticDfdEdge: StaticDfdEdge,
  };

  function pretty(value) {
    return JSON.stringify(value || {}, null, 2);
  }

  function asObject(value) {
    return value && typeof value === "object" && !Array.isArray(value) ? value : {};
  }

  function asArray(value) {
    if (Array.isArray(value)) return value;
    if (value === undefined || value === null || value === "") return [];
    return [value];
  }

  function displayValue(value) {
    if (Array.isArray(value)) return value.length ? value.join(", ") : "";
    if (value && typeof value === "object") return JSON.stringify(value);
    return value === undefined || value === null ? "" : String(value);
  }

  function nodeTypeFromData(data, fallbackRole) {
    const nodeType = String(data.nodeType || "").toLowerCase();
    if (nodeType) return nodeType;
    if (fallbackRole === "data_store") return "database";
    if (fallbackRole === "external") return "external_api";
    return fallbackRole || "process";
  }

  function graphForFlow(graph) {
    const nodes = Array.isArray(graph?.nodes) ? graph.nodes : [];
    const edges = Array.isArray(graph?.edges) ? graph.edges : [];
    const normalizedNodes = nodes.map((node, index) => {
      const data = normalizeNodeData(node);
      const isBoundary = data.nodeType === "trust_boundary";
      const width = Number(data.width || data.w) || (isBoundary ? 560 : undefined);
      const height = Number(data.height || data.h) || (isBoundary ? 320 : undefined);
      return {
        ...node,
        id: String(node?.id || `node_${index + 1}`),
        type: node?.type === "custom" || data.nodeType ? "custom" : "dfdNode",
        position: normalizePosition(node?.position, index),
        data: isBoundary ? { ...data, width, height } : data,
        draggable: node?.draggable !== false,
        selectable: node?.selectable !== false,
        zIndex: isBoundary ? -10 : (Number.isFinite(node?.zIndex) ? node.zIndex : 1),
        style: isBoundary
          ? { ...(asObject(node?.style)), width, height }
          : node?.style,
      };
    });

    return {
      nodes: applyTrustBoundaryContainment(normalizedNodes),
      edges: edges.map((edge, index) => decorateEdge({
        ...edge,
        id: String(edge?.id || `edge_${index + 1}`),
        source: String(edge?.source || ""),
        target: String(edge?.target || ""),
      })),
    };
  }

  function applyTrustBoundaryContainment(nodes) {
    const byId = new Map(nodes.map((node) => [node.id, node]));
    const boundaries = nodes.filter((node) => node.data?.nodeType === "trust_boundary");
    const memberships = new Map();

    boundaries.forEach((boundary) => {
      asArray(boundary.data?.contains).forEach((childId) => {
        if (!byId.has(childId) || childId === boundary.id) return;
        memberships.set(childId, (memberships.get(childId) || []).concat(boundary.id));
      });
    });

    const containedNodes = nodes.map((node) => {
      const boundaryIds = memberships.get(node.id) || [];
      if (boundaryIds.length !== 1 || node.data?.nodeType === "trust_boundary") return node;

      const boundary = byId.get(boundaryIds[0]);
      if (!boundary || !isNodeInsideBoundary(node, boundary)) return node;

      return applyParentBoundary(node, boundary);
    });

    return containedNodes.map((node) => {
      if (node.parentNode || node.data?.nodeType === "trust_boundary") return node;
      if ((memberships.get(node.id) || []).length > 0) return node;

      const boundary = bestVisualBoundary(node, boundaries);
      return boundary ? applyParentBoundary(node, boundary) : node;
    }).sort((left, right) => {
      const leftBoundary = left.data?.nodeType === "trust_boundary" ? 0 : 1;
      const rightBoundary = right.data?.nodeType === "trust_boundary" ? 0 : 1;
      return leftBoundary - rightBoundary;
    });
  }

  function applyParentBoundary(node, boundary) {
      const boundarySize = nodeSize(boundary, 560, 320);
      const childSize = nodeSize(node, 238, 110);
      return {
        ...node,
        parentNode: boundary.id,
        extent: "parent",
        expandParent: false,
        position: {
          x: clamp(node.position.x - boundary.position.x, 12, Math.max(12, boundarySize.width - childSize.width - 12)),
          y: clamp(node.position.y - boundary.position.y, 42, Math.max(42, boundarySize.height - childSize.height - 12)),
        },
        data: {
          ...node.data,
          containedBy: boundary.id,
        },
      };
  }

  function isNodeInsideBoundary(node, boundary) {
    const boundarySize = nodeSize(boundary, 560, 320);
    const childSize = nodeSize(node, 238, 110);
    const childCenter = {
      x: node.position.x + childSize.width / 2,
      y: node.position.y + childSize.height / 2,
    };

    return (
      childCenter.x >= boundary.position.x &&
      childCenter.x <= boundary.position.x + boundarySize.width &&
      childCenter.y >= boundary.position.y &&
      childCenter.y <= boundary.position.y + boundarySize.height
    );
  }

  function bestVisualBoundary(node, boundaries) {
    const candidates = boundaries
      .filter((boundary) => isNodeInsideBoundary(node, boundary))
      .map((boundary) => {
        const size = nodeSize(boundary, 560, 320);
        const dx = node.position.x - boundary.position.x;
        const dy = node.position.y - boundary.position.y;
        return {
          boundary,
          area: size.width * size.height,
          distanceFromOrigin: Math.sqrt(dx * dx + dy * dy),
        };
      })
      .sort((left, right) => {
        if (left.area !== right.area) return left.area - right.area;
        return left.distanceFromOrigin - right.distanceFromOrigin;
      });

    return candidates[0]?.boundary || null;
  }

  function nodeSize(node, fallbackWidth, fallbackHeight) {
    const data = asObject(node?.data);
    const style = asObject(node?.style);
    const width = Number(data.width || data.w || style.width);
    const height = Number(data.height || data.h || style.height || style.minHeight);
    return {
      width: Number.isFinite(width) ? width : fallbackWidth,
      height: Number.isFinite(height) ? height : fallbackHeight,
    };
  }

  function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
  }

  function normalizePosition(position, index) {
    const value = asObject(position);
    const x = Number(value.x);
    const y = Number(value.y);
    return {
      x: Number.isFinite(x) ? x : 120 + (index % 4) * 280,
      y: Number.isFinite(y) ? y : 120 + Math.floor(index / 4) * 160,
    };
  }

  function normalizeNodeData(node) {
    const data = asObject(node?.data);
    const role = data.role || roleFromNodeType(node?.type, data.label);
    const nodeType = nodeTypeFromData(data, role);
    return {
      ...data,
      label: data.label || node?.id || "Unnamed Node",
      role,
      nodeType,
      evidence: asArray(data.evidence),
      controls: asArray(data.controls),
      contains: asArray(data.contains),
      metadata: asObject(data.metadata),
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
    const data = asObject(edge?.data);
    const edgeType = data.edgeType || inferEdgeType(edge?.label, data);
    const palette = edgeStyle(edgeType);
    return {
      ...edge,
      type: "staticDfdEdge",
      data: {
        ...data,
        edgeType,
        evidence: asArray(data.evidence),
        metadata: asObject(data.metadata),
      },
      markerEnd: { type: "arrowclosed" },
      style: { stroke: palette.stroke, strokeWidth: palette.width, strokeDasharray: palette.dash },
      labelStyle: { fill: "#f8fafc", fontSize: 12, fontWeight: 700 },
      labelBgStyle: { fill: "rgba(15, 23, 42, 0.94)", stroke: palette.stroke, strokeWidth: 1 },
      labelBgPadding: [8, 5],
      labelBgBorderRadius: 6,
      animated: edge?.animated || edgeType === "prompt" || edgeType === "tool",
    };
  }

  function StaticDfdEdge(props) {
    const {
      id,
      sourceX,
      sourceY,
      targetX,
      targetY,
      sourcePosition,
      targetPosition,
      markerEnd,
      style,
      selected,
    } = props;
    const data = asObject(props.data);
    const edgeType = data.edgeType || inferEdgeType(props.label, data);
    const label = props.label || data.label || "";
    const palette = edgeStyle(edgeType);
    const geometry = edgeGeometry({
      sourceX,
      sourceY,
      targetX,
      targetY,
      sourcePosition,
      targetPosition,
      offset: edgeLaneOffset(edgeType, label),
      labelYOffset: edgeLabelYOffset(edgeType, label),
    });
    const edgeStyleValue = {
      ...(style || {}),
      stroke: selected ? "#f8fafc" : palette.stroke,
      strokeWidth: selected ? Math.max((palette.width || 1.8) + 0.7, 2.4) : palette.width,
      strokeDasharray: palette.dash,
    };

    return e(React.Fragment, null, [
      BaseEdge
        ? e(BaseEdge, {
            key: "edge",
            id,
            path: geometry.path,
            markerEnd,
            style: edgeStyleValue,
            interactionWidth: 18,
          })
        : e("path", {
            key: "edge",
            id,
            className: "react-flow__edge-path",
            d: geometry.path,
            markerEnd,
            style: edgeStyleValue,
          }),
      label && EdgeLabelRenderer
        ? e(EdgeLabelRenderer, { key: "label" },
            e("div", {
              className: `static-edge-label static-edge-label-${edgeType}`,
              style: {
                transform: `translate(-50%, -50%) translate(${geometry.labelX}px, ${geometry.labelY}px)`,
                borderColor: selected ? "#f8fafc" : palette.stroke,
              },
            }, label)
          )
        : null,
    ]);
  }

  function edgeLaneOffset(edgeType, label) {
    const text = String(label || "").toLowerCase();
    if (edgeType === "response" || /response|result|output/.test(text)) return 26;
    if (edgeType === "request" || /request|authenticated|user prompt/.test(text)) return -26;
    if (edgeType === "prompt") return -18;
    if (edgeType === "rag") return 20;
    if (edgeType === "tool") return -22;
    if (edgeType === "logging") return 30;
    return 0;
  }

  function edgeLabelYOffset(edgeType, label) {
    const text = String(label || "").toLowerCase();
    if (edgeType === "response" || /response|result|output/.test(text)) return 18;
    if (edgeType === "request" || /request|authenticated|user prompt/.test(text)) return -18;
    if (edgeType === "prompt") return -14;
    if (edgeType === "rag") return 14;
    if (edgeType === "tool") return -16;
    if (edgeType === "logging") return 22;
    return 0;
  }

  function edgeGeometry({ sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, offset, labelYOffset }) {
    const dx = targetX - sourceX;
    const dy = targetY - sourceY;
    const length = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
    const normalX = -dy / length;
    const normalY = dx / length;
    const controlDistance = Math.max(Math.min(Math.abs(dx) * 0.5, 180), 80);
    const c1 = controlPoint(sourceX, sourceY, sourcePosition, controlDistance);
    const c2 = controlPoint(targetX, targetY, targetPosition, controlDistance);
    const controlOffset = offset * 0.85;
    const c1x = c1.x + normalX * controlOffset;
    const c1y = c1.y + normalY * controlOffset;
    const c2x = c2.x + normalX * controlOffset;
    const c2y = c2.y + normalY * controlOffset;
    const mid = cubicPoint(0.5, sourceX, sourceY, c1x, c1y, c2x, c2y, targetX, targetY);

    return {
      path: `M ${sourceX},${sourceY} C ${c1x},${c1y} ${c2x},${c2y} ${targetX},${targetY}`,
      labelX: mid.x + normalX * Math.abs(offset) * 0.25,
      labelY: mid.y + labelYOffset,
    };
  }

  function controlPoint(x, y, position, distance) {
    if (position === "left") return { x: x - distance, y };
    if (position === "right") return { x: x + distance, y };
    if (position === "top") return { x, y: y - distance };
    if (position === "bottom") return { x, y: y + distance };
    return { x: x + distance, y };
  }

  function cubicPoint(t, x0, y0, x1, y1, x2, y2, x3, y3) {
    const mt = 1 - t;
    const a = mt * mt * mt;
    const b = 3 * mt * mt * t;
    const c = 3 * mt * t * t;
    const d = t * t * t;
    return {
      x: a * x0 + b * x1 + c * x2 + d * x3,
      y: a * y0 + b * y1 + c * y2 + d * y3,
    };
  }

  function inferEdgeType(label, data) {
    const text = `${label || ""} ${data?.source || ""}`.toLowerCase();
    if (/telemetry|audit|log|monitor/.test(text)) return "logging";
    if (/tool result|tool response|invoke tool|tool request|function/.test(text)) return "tool";
    if (/retrieval|retrieved context|rag|vector|search query|knowledge/.test(text)) return "rag";
    if (/prompt|model request|llm request|context/.test(text)) return "prompt";
    if (/validated response|model response|response|result|answer/.test(text)) return "response";
    if (/api|database|db|store|query|operation|outbound|integration/.test(text)) return "api";
    if (/request|authenticated|admin|user/.test(text)) return "request";
    return "data";
  }

  function edgeStyle(edgeType) {
    const styles = {
      request: { stroke: "#38bdf8", width: 1.9 },
      prompt: { stroke: "#f472b6", width: 2.1 },
      rag: { stroke: "#22c55e", width: 1.9, dash: "7 5" },
      tool: { stroke: "#a78bfa", width: 2 },
      api: { stroke: "#60a5fa", width: 1.8 },
      response: { stroke: "#2dd4bf", width: 1.9 },
      logging: { stroke: "#f59e0b", width: 1.7, dash: "4 4" },
      data: { stroke: "#94a3b8", width: 1.6 },
    };
    return styles[edgeType] || styles.data;
  }

  function edgeTypeOption(edgeType) {
    return EDGE_TYPE_OPTIONS.find((option) => option.value === edgeType) || EDGE_TYPE_OPTIONS[0];
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

  function renderMetadataSummary(metadata) {
    const data = asObject(metadata);
    const signals = asObject(data.signals_summary);
    const unresolved = asArray(data.unresolved_control_targets);
    const orphanNodes = asArray(data.orphan_nodes);
    const warnings = asArray(data.warnings);
    const assumptions = asArray(data.assumptions);
    const rows = [
      ["Graph mode", data.graph_mode],
      ["Mapper version", data.mapper_version],
      ["Answer count", data.normalized_answer_count],
      ["Signals", Object.keys(signals).length ? signals : null],
    ];

    return e("div", { className: "mapper-toolbox mb-3" }, [
      e("div", { key: "title", className: "mapper-toolbox-title" }, "Metadata Summary"),
      e("dl", { key: "rows", className: "detail-list" },
        rows
          .filter((row) => row[1] !== undefined && row[1] !== null && row[1] !== "")
          .map(([label, value]) => [
            e("dt", { key: `${label}-dt` }, label),
            e("dd", { key: `${label}-dd` }, typeof value === "object" ? pretty(value) : String(value)),
          ]).flat()
      ),
      warnings.length ? renderTextList("Warnings", warnings, "warning") : null,
      assumptions.length ? renderTextList("Assumptions", assumptions) : null,
      unresolved.length ? renderTextList("Unresolved control targets", unresolved, "warning") : null,
      orphanNodes.length ? renderTextList("Orphan nodes", orphanNodes, "warning") : null,
    ]);
  }

  function renderTextList(title, values, tone = "") {
    return e("div", { className: `detail-section ${tone}` }, [
      e("div", { key: "title", className: "detail-section-title" }, title),
      e("ul", { key: "list", className: "detail-value-list" },
        asArray(values).map((value, index) =>
          e("li", { key: `${title}-${index}` }, displayValue(value))
        )
      ),
    ]);
  }

  function renderField(label, value) {
    const text = displayValue(value);
    if (!text) return null;
    return [
      e("dt", { key: `${label}-dt` }, label),
      e("dd", { key: `${label}-dd` }, text),
    ];
  }

  function renderSelectedDetails(selectedNode, selectedEdge, options) {
    if (selectedNode) {
      const data = asObject(selectedNode.data);
      const rows = [
        renderField("Label", data.label || selectedNode.id),
        renderField("Node type", data.nodeType),
        renderField("Role", data.role),
        renderField("Kind", data.kind),
        renderField("Contained by", data.containedBy),
        renderField("Data classification", data.data_classification),
        renderField("Boundary type", data.boundaryType || data.boundary_type),
        renderField("Contains", data.contains),
      ].filter(Boolean).flat();

      return e("div", { className: "mapper-toolbox mb-3" }, [
        e("div", { key: "title", className: "mapper-toolbox-title" }, "Selected Node"),
        rows.length ? e("dl", { key: "rows", className: "detail-list" }, rows) : null,
        options.showEvidence ? renderTextList("Evidence", data.evidence) : null,
        options.showControls ? renderTextList("Controls", data.controls) : null,
        options.showMetadata ? renderObjectBlock("Node metadata", data.metadata) : null,
      ]);
    }

    if (selectedEdge) {
      const data = asObject(selectedEdge.data);
      const rows = [
        renderField("Label", selectedEdge.label || data.label || selectedEdge.id),
        renderField("Source", selectedEdge.source),
        renderField("Target", selectedEdge.target),
        renderField("Edge type", data.edgeType),
      ].filter(Boolean).flat();

      return e("div", { className: "mapper-toolbox mb-3" }, [
        e("div", { key: "title", className: "mapper-toolbox-title" }, "Selected Flow"),
        rows.length ? e("dl", { key: "rows", className: "detail-list" }, rows) : null,
        options.showEvidence ? renderTextList("Evidence", data.evidence) : null,
        options.showMetadata ? renderObjectBlock("Flow metadata", data.metadata) : null,
      ]);
    }

    return e("div", { className: "mapper-toolbox mb-3" }, [
      e("div", { key: "title", className: "mapper-toolbox-title" }, "Selected Element"),
      e("p", { key: "empty", className: "mapper-status mb-0" }, "Click a node or flow to inspect it."),
    ]);
  }

  function renderObjectBlock(title, value) {
    const data = asObject(value);
    if (!Object.keys(data).length) return null;
    return e("div", { className: "detail-section" }, [
      e("div", { key: "title", className: "detail-section-title" }, title),
      e("pre", { key: "json", className: "detail-json" }, pretty(data)),
    ]);
  }

  function App() {
    const initialGraph = React.useMemo(storageGraph, []);
    const initialResponseFiles = window.dfdMapperLabResponseFiles || [];
    const initialDfdFiles = window.dfdMapperLabDfdFiles || [];
    const [activeMode, setActiveMode] = React.useState("static");
    const [dfdFiles, setDfdFiles] = React.useState(initialDfdFiles);
    const [selectedDfd, setSelectedDfd] = React.useState(window.dfdMapperLabSelectedDfd || "");
    const [nodes, setNodes] = React.useState(initialGraph.nodes);
    const [edges, setEdges] = React.useState(initialGraph.edges);
    const [selectedNodeId, setSelectedNodeId] = React.useState(initialGraph.nodes[0]?.id || null);
    const [selectedEdgeId, setSelectedEdgeId] = React.useState(null);
    const [selectedStaticResponse, setSelectedStaticResponse] = React.useState("");
    const [staticGraphMode, setStaticGraphMode] = React.useState("compact");
    const [staticInput, setStaticInput] = React.useState(pretty(STATIC_SAMPLE));
    const [staticOutput, setStaticOutput] = React.useState(null);
    const [staticError, setStaticError] = React.useState("");
    const [showEvidence, setShowEvidence] = React.useState(false);
    const [showControls, setShowControls] = React.useState(false);
    const [showMetadata, setShowMetadata] = React.useState(true);
    const [newEdgeType, setNewEdgeType] = React.useState("data");
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
        edge.id === selectedEdgeId ? decorateEdge({ ...edge, [field]: value }) : edge
      )));
    }, [selectedEdgeId]);

    const updateSelectedEdgeType = React.useCallback((edgeType) => {
      if (!selectedEdgeId) return;
      setEdges((current) => current.map((edge) => {
        if (edge.id !== selectedEdgeId) return edge;
        const option = edgeTypeOption(edgeType);
        const data = asObject(edge.data);
        const shouldUseDefaultLabel = !edge.label || edge.label === "Data Flow" || edge.label === edgeTypeOption(data.edgeType).defaultLabel;
        return decorateEdge({
          ...edge,
          label: shouldUseDefaultLabel ? option.defaultLabel : edge.label,
          data: { ...data, edgeType },
        });
      }));
    }, [selectedEdgeId]);

    const loadStaticSample = React.useCallback(() => {
      setStaticInput(pretty(STATIC_SAMPLE));
      setStaticError("");
      setStatus("Loaded sample static mapper input.");
      setStatusType("info");
    }, []);

    const loadStaticResponse = React.useCallback(async () => {
      if (!selectedStaticResponse) {
        setStaticError("Select a saved response first.");
        setStatus("Select a saved response first.");
        setStatusType("warning");
        return;
      }

      try {
        setStaticError("");
        const response = await fetch(`/api/responses/${encodeURIComponent(selectedStaticResponse)}`);
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.description || "Unable to load response.");
        const responsePayload = payload.raw || { answers_by_flow_id: payload.answers_by_flow_id || {} };
        setStaticInput(pretty(responsePayload));
        setStatus(`Loaded response: ${payload.filename || selectedStaticResponse}.`);
        setStatusType("info");
      } catch (error) {
        setStaticError(error.message || "Unable to load response.");
        setStatus(error.message || "Unable to load response.");
        setStatusType("error");
      }
    }, [selectedStaticResponse]);

    const generateStaticDfd = React.useCallback(async () => {
      let parsed;
      try {
        parsed = JSON.parse(staticInput);
      } catch (error) {
        setStaticError(`Invalid JSON: ${error.message}`);
        setStatus("Static mapper input is not valid JSON.");
        setStatusType("error");
        return;
      }

      try {
        setStaticError("");
        const response = await fetch("/api/static-dfd-map", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ answers: parsed, graph_mode: staticGraphMode }),
        });
        const payload = await response.json();
        if (!response.ok || !payload.ok) throw new Error(payload.error || "Static mapper failed.");

        const graph = payload.graph;
        const flowGraph = graphForFlow(graph);
        setStaticOutput(graph);
        setNodes(flowGraph.nodes);
        setEdges(flowGraph.edges);
        setSelectedNodeId(flowGraph.nodes[0]?.id || null);
        setSelectedEdgeId(null);
        window.localStorage.setItem(GRAPH_KEY, JSON.stringify(graph));
        setStatus(`Generated ${graph.metadata?.graph_mode || staticGraphMode} static DFD with ${flowGraph.nodes.length} nodes and ${flowGraph.edges.length} flows.`);
        setStatusType("info");
        window.setTimeout(() => flowRef.current?.fitView({ padding: 0.18, duration: 250 }), 0);
      } catch (error) {
        setStaticError(error.message || "Static mapper failed.");
        setStatus(error.message || "Static mapper failed.");
        setStatusType("error");
      }
    }, [staticGraphMode, staticInput]);

    const copyStaticOutput = React.useCallback(async () => {
      if (!staticOutput) {
        setStatus("Generate a static DFD before copying JSON.");
        setStatusType("warning");
        return;
      }

      try {
        await navigator.clipboard.writeText(pretty(staticOutput));
        setStatus("Copied generated graph JSON to clipboard.");
        setStatusType("info");
      } catch (error) {
        setStatus("Clipboard copy failed. Select the JSON manually.");
        setStatusType("error");
      }
    }, [staticOutput]);

    return e("div", { className: "mapper-shell" }, [
      e("aside", { key: "left", className: "mapper-panel" }, [
        e("div", { key: "tabs", className: "mapper-tabs", role: "tablist" }, [
          e("button", {
            key: "static",
            type: "button",
            className: `mapper-tab ${activeMode === "static" ? "active" : ""}`,
            onClick: () => setActiveMode("static"),
          }, "Generate DFD"),
          e("button", {
            key: "editor",
            type: "button",
            className: `mapper-tab ${activeMode === "editor" ? "active" : ""}`,
            onClick: () => setActiveMode("editor"),
          }, "Saved DFDs"),
        ]),
        activeMode === "editor"
          ? e("div", { key: "editor-inputs" }, [
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
                e("div", { key: "edge-type-field", className: "selected-field" }, [
                  e("label", { key: "label", className: "form-label", htmlFor: "newEdgeType" }, "New flow type"),
                  e("select", {
                    key: "select",
                    id: "newEdgeType",
                    className: "form-select",
                    value: newEdgeType,
                    onChange: (event) => setNewEdgeType(event.target.value),
                  }, EDGE_TYPE_OPTIONS.map((option) =>
                    e("option", { key: option.value, value: option.value }, option.label)
                  )),
                ]),
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
            ])
          : e("div", { key: "static-inputs" }, [
              e("h5", { key: "title" }, "Static DFD Mapper"),
              e("label", { key: "mode-label", className: "form-label", htmlFor: "staticGraphMode" }, "Graph mode"),
              e("select", {
                key: "mode",
                id: "staticGraphMode",
                className: "form-select mb-3",
                value: staticGraphMode,
                onChange: (event) => setStaticGraphMode(event.target.value),
              }, [
                e("option", { key: "compact", value: "compact" }, "Compact"),
                e("option", { key: "detailed", value: "detailed" }, "Detailed"),
              ]),
              e("label", { key: "response-label", className: "form-label", htmlFor: "staticResponseFile" }, "Saved response"),
              e("div", { key: "response-row", className: "d-flex gap-2 mb-3" }, [
                e("select", {
                  key: "select",
                  id: "staticResponseFile",
                  className: "form-select",
                  value: selectedStaticResponse,
                  onChange: (event) => setSelectedStaticResponse(event.target.value),
                }, [
                  e("option", { key: "empty", value: "" }, initialResponseFiles.length ? "Select response JSON" : "No response files found"),
                  ...initialResponseFiles.map((file) => e("option", { key: file, value: file }, file)),
                ]),
                e("button", {
                  key: "load-response",
                  type: "button",
                  className: "btn btn-outline-primary",
                  onClick: loadStaticResponse,
                }, "Load Response"),
              ]),
              e("label", { key: "label", className: "form-label", htmlFor: "staticDfdInput" }, "Questionnaire responses JSON"),
              e("textarea", {
                key: "textarea",
                id: "staticDfdInput",
                className: "form-control mb-3",
                value: staticInput,
                spellCheck: false,
                onChange: (event) => setStaticInput(event.target.value),
              }),
              e("div", { key: "actions", className: "mapper-actions" }, [
                e("button", { key: "generate", type: "button", className: "btn btn-primary", onClick: generateStaticDfd }, "Generate Static DFD"),
                e("button", { key: "sample", type: "button", className: "btn btn-outline-primary", onClick: loadStaticSample }, "Sample JSON"),
              ]),
              staticError
                ? e("div", { key: "error", className: "mapper-status error mt-3" }, staticError)
                : e("div", { key: "hint", className: "mapper-status mt-3" }, "Accepts flat Q-id answers, answers_by_flow_id, and saved app response JSON."),
            ]),
        e("div", { key: "status", className: `mapper-status mt-3 ${statusType}` }, status),
      ]),
      e("section", { key: "canvas", className: "mapper-canvas" },
        e("div", { className: "mapper-canvas-inner", ref: canvasRef },
          e(ReactFlow, {
            nodes,
            edges,
            nodeTypes,
            edgeTypes,
            onInit: (instance) => {
              flowRef.current = instance;
              window.setTimeout(() => instance.fitView({ padding: 0.18 }), 0);
            },
            onNodesChange: (changes) => setNodes((current) => applyNodeChanges(changes, current)),
            onEdgesChange: (changes) => setEdges((current) => applyEdgeChanges(changes, current)),
            onConnect: (params) => setEdges((current) => addEdge(decorateEdge({
              ...params,
              id: `edge_${Date.now()}`,
              label: edgeTypeOption(newEdgeType).defaultLabel,
              type: "staticDfdEdge",
              animated: false,
              data: { edgeType: newEdgeType, source: "manual" },
            }), current)),
            onNodeClick: (event, node) => {
              setSelectedNodeId(node?.id || null);
              setSelectedEdgeId(null);
            },
            onEdgeClick: (event, edge) => {
              setSelectedEdgeId(edge?.id || null);
              setSelectedNodeId(null);
            },
            onSelectionChange: (selection) => {
              const selectionNodes = selection?.nodes || [];
              const selectionEdges = selection?.edges || [];
              if (selectionNodes.length) {
                setSelectedNodeId(selectionNodes[0]?.id || null);
                setSelectedEdgeId(null);
                return;
              }
              if (selectionEdges.length) {
                setSelectedEdgeId(selectionEdges[0]?.id || null);
                setSelectedNodeId(null);
              }
            },
            fitView: true,
            deleteKeyCode: ["Backspace", "Delete"],
            defaultEdgeOptions: {
              type: "staticDfdEdge",
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
          ])
        )
      ),
      e("aside", { key: "right", className: "mapper-panel" }, [
        activeMode === "static"
          ? e("div", { key: "static-output-panel" }, [
              e("div", { key: "header", className: "static-panel-header d-flex align-items-center justify-content-between gap-2 mb-3" }, [
                e("h5", { key: "title", className: "mb-0" }, "Static DFD Result"),
                e("div", { key: "buttons", className: "d-flex gap-2" }, [
                  e("button", {
                    key: "copy",
                    type: "button",
                    className: "btn btn-outline-primary btn-sm",
                    onClick: copyStaticOutput,
                    disabled: !staticOutput,
                  }, "Copy JSON"),
                  e("button", {
                    key: "download",
                    type: "button",
                    className: "btn btn-outline-primary btn-sm",
                    onClick: () => downloadJson("static-dfd-graph.json", staticOutput || {}),
                    disabled: !staticOutput,
                  }, "Download"),
                ]),
              ]),
              staticOutput?.metadata ? renderMetadataSummary(staticOutput.metadata) : null,
              e("div", { key: "detail-toggles", className: "detail-toggles mb-3" }, [
                e("label", { key: "evidence", className: "detail-toggle" }, [
                  e("input", {
                    key: "input",
                    type: "checkbox",
                    checked: showEvidence,
                    onChange: (event) => setShowEvidence(event.target.checked),
                  }),
                  e("span", { key: "label" }, "Show Evidence"),
                ]),
                e("label", { key: "controls", className: "detail-toggle" }, [
                  e("input", {
                    key: "input",
                    type: "checkbox",
                    checked: showControls,
                    onChange: (event) => setShowControls(event.target.checked),
                  }),
                  e("span", { key: "label" }, "Show Controls"),
                ]),
                e("label", { key: "metadata", className: "detail-toggle" }, [
                  e("input", {
                    key: "input",
                    type: "checkbox",
                    checked: showMetadata,
                    onChange: (event) => setShowMetadata(event.target.checked),
                  }),
                  e("span", { key: "label" }, "Show Metadata"),
                ]),
              ]),
              renderSelectedDetails(selectedNode, selectedEdge, { showEvidence, showControls, showMetadata }),
              e("div", { key: "json-title", className: "mapper-toolbox-title" }, "Raw Graph JSON"),
              e("pre", { key: "json", className: "static-output" }, staticOutput ? pretty(staticOutput) : "Generate a static DFD to preview the graph JSON."),
            ])
          : e("div", { key: "editor-output-panel" }, [
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
                e("div", { key: "type-field", className: "selected-field" }, [
                  e("label", { key: "label", className: "form-label", htmlFor: "edgeType" }, "Flow type"),
                  e("select", {
                    key: "select",
                    id: "edgeType",
                    className: "form-select",
                    value: asObject(selectedEdge.data).edgeType || inferEdgeType(selectedEdge.label, asObject(selectedEdge.data)),
                    onChange: (event) => updateSelectedEdgeType(event.target.value),
                  }, EDGE_TYPE_OPTIONS.map((option) =>
                    e("option", { key: option.value, value: option.value }, option.label)
                  )),
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
      ]),
    ]);
  }

  ReactDOM.createRoot(document.getElementById("dfd-mapper-lab-root")).render(e(App));
})();
