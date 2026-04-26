import React, { useCallback, useMemo, useRef, useState } from "https://esm.sh/react@18.3.1";
import { createRoot } from "https://esm.sh/react-dom@18.3.1/client";
import ReactFlow, {
  addEdge,
  Background,
  Controls,
  MiniMap,
  Panel,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  useReactFlow,
} from "https://esm.sh/reactflow@11.11.4?external=react,react-dom";

const palette = [
  // Actors
  { type: "external_user", label: "External User", notes: "Anonymous public internet user." },
  { type: "authenticated_user", label: "Authenticated User", notes: "Logged-in customer or public user." },
  { type: "admin", label: "Administrator", notes: "Privileged internal operator." },
  { type: "internal_user", label: "Internal Employee", notes: "Internal business user." },
  { type: "third_party_actor", label: "Third Party System", notes: "External integrated system." },

  // Application / Services
  { type: "web_app", label: "Web Application", notes: "Frontend or browser-facing application." },
  { type: "mobile_app", label: "Mobile App", notes: "Mobile client application." },
  { type: "api_service", label: "API Service", notes: "REST / GraphQL / backend API." },
  { type: "backend_service", label: "Backend Service", notes: "Internal business logic service." },
  { type: "admin_panel", label: "Admin Panel", notes: "Privileged management interface." },

  // Identity / Security
  { type: "auth_service", label: "Auth Service", notes: "Authentication / identity provider." },
  { type: "waf", label: "WAF", notes: "Web Application Firewall." },
  { type: "gateway", label: "API Gateway", notes: "Traffic broker / access control layer." },
  { type: "secrets_vault", label: "Secrets Vault", notes: "Credential / secrets manager." },
  { type: "logging", label: "Logging / SIEM", notes: "Audit logging and monitoring." },

  // AI / LLM
  { type: "llm", label: "LLM", notes: "Hosted or local language model." },
  { type: "rag_engine", label: "RAG Engine", notes: "Retrieval orchestration layer." },
  { type: "vector_db", label: "Vector Database", notes: "Embedding storage / semantic search." },
  { type: "tool_executor", label: "Tool Executor", notes: "LLM tool-calling execution layer." },
  { type: "prompt_store", label: "Prompt Store", notes: "Prompt templates / policies." },

  // Data Stores
  { type: "database", label: "Database", notes: "Structured persistent data." },
  { type: "file_storage", label: "File Storage", notes: "Documents / object storage." },
  { type: "cache", label: "Cache", notes: "Temporary in-memory storage." },

  // Boundaries
  { type: "trust_boundary", label: "Trust Boundary", notes: "Logical security boundary." },
  { type: "internet_zone", label: "Internet Zone", notes: "Public untrusted network." },
  { type: "internal_zone", label: "Internal Zone", notes: "Trusted corporate network." },
  { type: "cloud_boundary", label: "Cloud Boundary", notes: "Cloud provider trust zone." },

  // Utility
  { type: "text_note", label: "Text Note", notes: "Annotation or analyst note." }
];

const nodeStyles = {
  user: {
    border: "1px solid #38bdf8",
    background: "linear-gradient(135deg, rgba(14, 165, 233, 0.18), rgba(12, 18, 34, 0.96))",
  },
  external_user: {
    border: "1px solid #38bdf8",
    background: "linear-gradient(135deg, rgba(14, 165, 233, 0.18), rgba(12, 18, 34, 0.96))",
  },
  authenticated_user: {
    border: "1px solid #0ea5e9",
    background: "linear-gradient(135deg, rgba(2, 132, 199, 0.18), rgba(12, 18, 34, 0.96))",
  },
  admin: {
    border: "1px solid #f43f5e",
    background: "linear-gradient(135deg, rgba(244, 63, 94, 0.18), rgba(12, 18, 34, 0.96))",
  },
  internal_user: {
    border: "1px solid #06b6d4",
    background: "linear-gradient(135deg, rgba(6, 182, 212, 0.16), rgba(12, 18, 34, 0.96))",
  },
  third_party_actor: {
    border: "1px solid #8b5cf6",
    background: "linear-gradient(135deg, rgba(139, 92, 246, 0.18), rgba(12, 18, 34, 0.96))",
  },
  process: {
    border: "1px solid #22c55e",
    background: "linear-gradient(135deg, rgba(34, 197, 94, 0.18), rgba(12, 18, 34, 0.96))",
  },
  web_app: {
    border: "1px solid #22c55e",
    background: "linear-gradient(135deg, rgba(34, 197, 94, 0.18), rgba(12, 18, 34, 0.96))",
  },
  mobile_app: {
    border: "1px solid #10b981",
    background: "linear-gradient(135deg, rgba(16, 185, 129, 0.18), rgba(12, 18, 34, 0.96))",
  },
  api_service: {
    border: "1px solid #14b8a6",
    background: "linear-gradient(135deg, rgba(20, 184, 166, 0.18), rgba(12, 18, 34, 0.96))",
  },
  backend_service: {
    border: "1px solid #16a34a",
    background: "linear-gradient(135deg, rgba(22, 163, 74, 0.18), rgba(12, 18, 34, 0.96))",
  },
  admin_panel: {
    border: "1px solid #84cc16",
    background: "linear-gradient(135deg, rgba(132, 204, 22, 0.18), rgba(12, 18, 34, 0.96))",
  },
  auth_service: {
    border: "1px solid #f97316",
    background: "linear-gradient(135deg, rgba(249, 115, 22, 0.18), rgba(12, 18, 34, 0.96))",
  },
  waf: {
    border: "1px solid #ef4444",
    background: "linear-gradient(135deg, rgba(239, 68, 68, 0.18), rgba(12, 18, 34, 0.96))",
  },
  gateway: {
    border: "1px solid #fb7185",
    background: "linear-gradient(135deg, rgba(251, 113, 133, 0.16), rgba(12, 18, 34, 0.96))",
  },
  secrets_vault: {
    border: "1px solid #f59e0b",
    background: "linear-gradient(135deg, rgba(245, 158, 11, 0.18), rgba(12, 18, 34, 0.96))",
  },
  logging: {
    border: "1px solid #eab308",
    background: "linear-gradient(135deg, rgba(234, 179, 8, 0.16), rgba(12, 18, 34, 0.96))",
  },
  llm: {
    border: "1px solid #f472b6",
    background: "linear-gradient(135deg, rgba(244, 114, 182, 0.16), rgba(12, 18, 34, 0.96))",
  },
  rag_engine: {
    border: "1px solid #ec4899",
    background: "linear-gradient(135deg, rgba(236, 72, 153, 0.16), rgba(12, 18, 34, 0.96))",
  },
  vector_db: {
    border: "1px solid #c084fc",
    background: "linear-gradient(135deg, rgba(192, 132, 252, 0.16), rgba(12, 18, 34, 0.96))",
  },
  tool_executor: {
    border: "1px solid #f43f5e",
    background: "linear-gradient(135deg, rgba(244, 63, 94, 0.16), rgba(12, 18, 34, 0.96))",
  },
  prompt_store: {
    border: "1px solid #d946ef",
    background: "linear-gradient(135deg, rgba(217, 70, 239, 0.16), rgba(12, 18, 34, 0.96))",
  },
  database: {
    border: "1px solid #f59e0b",
    background: "linear-gradient(135deg, rgba(245, 158, 11, 0.16), rgba(12, 18, 34, 0.96))",
  },
  file_storage: {
    border: "1px solid #fbbf24",
    background: "linear-gradient(135deg, rgba(251, 191, 36, 0.16), rgba(12, 18, 34, 0.96))",
  },
  cache: {
    border: "1px solid #fb923c",
    background: "linear-gradient(135deg, rgba(251, 146, 60, 0.16), rgba(12, 18, 34, 0.96))",
  },
  external_api: {
    border: "1px solid #a78bfa",
    background: "linear-gradient(135deg, rgba(129, 140, 248, 0.18), rgba(12, 18, 34, 0.96))",
  },
  queue: {
    border: "1px solid #fb7185",
    background: "linear-gradient(135deg, rgba(251, 113, 133, 0.16), rgba(12, 18, 34, 0.96))",
  },
  trust_boundary: {
    border: "1px dashed rgba(148, 163, 184, 0.6)",
    background: "rgba(15, 23, 42, 0.25)",
  },
  internet_zone: {
    border: "1px dashed rgba(56, 189, 248, 0.7)",
    background: "rgba(8, 47, 73, 0.18)",
  },
  internal_zone: {
    border: "1px dashed rgba(34, 197, 94, 0.7)",
    background: "rgba(20, 83, 45, 0.18)",
  },
  cloud_boundary: {
    border: "1px dashed rgba(168, 85, 247, 0.7)",
    background: "rgba(59, 7, 100, 0.16)",
  },
  text_note: {
    border: "1px solid #94a3b8",
    background: "linear-gradient(135deg, rgba(148, 163, 184, 0.12), rgba(12, 18, 34, 0.96))",
  },
};

const wideNodeKinds = new Set([
  "trust_boundary",
  "internet_zone",
  "internal_zone",
  "cloud_boundary",
]);

function getNodeDimensions(kind) {
  if (wideNodeKinds.has(kind)) {
    return { width: 860, height: 390, minWidth: 320, minHeight: 180, borderRadius: "20px" };
  }

  return { width: undefined, height: undefined, minWidth: 180, minHeight: "auto", borderRadius: "16px" };
}

function getCanvasCenterPosition(wrapper, project) {
  const center = {
    x: (wrapper?.clientWidth || 960) / 2,
    y: (wrapper?.clientHeight || 640) / 2,
  };

  return project(center);
}

function addNodeStylesForKind(style, kind) {
  return {
    ...style,
    ...(nodeStyles[kind] || nodeStyles.process),
  };
}

function createPaletteEntryElement(item, onAdd) {
  return React.createElement(
    "div",
    {
      key: item.type,
      className: "palette-item",
      draggable: true,
      onClick: () => onAdd(item.type),
      onDragStart: (event) => {
        event.dataTransfer.setData("application/reactflow", item.type);
        event.dataTransfer.effectAllowed = "move";
      },
      title: "Click to add at canvas center or drag into canvas.",
    },
    [
      React.createElement("strong", { key: "label" }, item.label),
      React.createElement("small", { key: "notes" }, item.notes),
    ]
  );
}

function ThreatNode({ data, selected }) {
  const style = nodeStyles[data.kind] || nodeStyles.process;
  const dimensions = getNodeDimensions(data.kind);
  return React.createElement(
    "div",
    {
      style: {
        minWidth: dimensions.minWidth,
        minHeight: dimensions.minHeight,
        padding: "0.9rem 1rem",
        borderRadius: dimensions.borderRadius,
        color: "#f8fafc",
        boxShadow: selected ? "0 0 0 2px rgba(96, 165, 250, 0.75)" : "0 12px 30px rgba(2, 6, 23, 0.28)",
        ...style,
      },
    },
    [
      React.createElement(
        "div",
        {
          key: "kind",
          style: {
            fontSize: "0.72rem",
            letterSpacing: "0.14em",
            textTransform: "uppercase",
            color: "#cbd5e1",
            marginBottom: "0.45rem",
          },
        },
        data.kind.replace(/_/g, " ")
      ),
      React.createElement(
        "div",
        {
          key: "label",
          style: { fontWeight: 700, fontSize: "0.98rem", lineHeight: 1.3 },
        },
        data.label
      ),
      data.notes
        ? React.createElement(
            "div",
            {
              key: "notes",
              style: { marginTop: "0.45rem", color: "#cbd5e1", fontSize: "0.86rem", lineHeight: 1.4 },
            },
            data.notes
          )
        : null,
    ]
  );
}

const nodeTypes = {
  threatNode: ThreatNode,
};

function storageNodeToFlowNode(node) {
  const dimensions = getNodeDimensions(node.type);
  return {
    ...node,
    type: "threatNode",
    data: {
      label: node.label,
      kind: node.type,
      notes: node.notes || "",
    },
    position: node.position || { x: 0, y: 0 },
    style: {
      width: node.width ?? dimensions.width,
      height: node.height ?? dimensions.height,
      ...addNodeStylesForKind({}, node.type),
    },
  };
}

function flowNodeToStorageNode(node) {
  return {
    id: node.id,
    type: node.data.kind,
    label: node.data.label,
    notes: node.data.notes || "",
    position: {
      x: Math.round(node.position.x),
      y: Math.round(node.position.y),
    },
    width: typeof node.width === "number" ? node.width : undefined,
    height: typeof node.height === "number" ? node.height : undefined,
  };
}

function createNode(kind, position, label, notes) {
  const dimensions = getNodeDimensions(kind);
  return storageNodeToFlowNode({
    id: `node_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    type: kind,
    label: label || palette.find((item) => item.type === kind)?.label || "New Node",
    notes: notes || palette.find((item) => item.type === kind)?.notes || "",
    position,
    width: dimensions.width,
    height: dimensions.height,
  });
}

function EditorApp({ initialModel, saveUrl, exportJsonUrl, exportMermaidUrl, exportPlantumlUrl }) {
  const defaultViewport = initialModel.diagram.viewport || { x: 0, y: 0, zoom: 1 };
  const initialNodes = useMemo(
    () => (initialModel.diagram.nodes || []).map(storageNodeToFlowNode),
    [initialModel]
  );
  const initialEdges = useMemo(
    () =>
      (initialModel.diagram.edges || []).map((edge) => ({
        ...edge,
        animated: false,
        markerEnd: { type: "arrowclosed" },
        style: { stroke: "#60a5fa", strokeWidth: 1.6 },
        labelStyle: { fill: "#cbd5e1", fontSize: 12 },
      })),
    [initialModel]
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [selectedNodeId, setSelectedNodeId] = useState(initialNodes[0]?.id || null);
  const [saveStatus, setSaveStatus] = useState("Unsaved changes are stored only in your browser until you click Save Model.");
  const reactFlowWrapper = useRef(null);
  const { project, getViewport } = useReactFlow();

  const selectedNode = nodes.find((node) => node.id === selectedNodeId) || null;

  const onConnect = useCallback(
    (connection) => {
      setEdges((currentEdges) =>
        addEdge(
          {
            ...connection,
            id: `edge_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
            label: "Data Flow",
            markerEnd: { type: "arrowclosed" },
            style: { stroke: "#60a5fa", strokeWidth: 1.6 },
            labelStyle: { fill: "#cbd5e1", fontSize: 12 },
          },
          currentEdges
        )
      );
      setSaveStatus("Connection added. Save when ready.");
    },
    [setEdges]
  );

  const onDragOver = useCallback((event) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  }, []);

  const onDrop = useCallback(
    (event) => {
      event.preventDefault();

      const type = event.dataTransfer.getData("application/reactflow");
      if (!type || !reactFlowWrapper.current) {
        return;
      }

      const bounds = reactFlowWrapper.current.getBoundingClientRect();
      const position = project({
        x: event.clientX - bounds.left,
        y: event.clientY - bounds.top,
      });

      const newNode = createNode(type, position);
      setNodes((currentNodes) => currentNodes.concat(newNode));
      setSelectedNodeId(newNode.id);
      setSaveStatus(`${newNode.data.label} added to the canvas.`);
    },
    [project, setNodes]
  );

  const onSelectionChange = useCallback(({ nodes: selectedNodes }) => {
    setSelectedNodeId(selectedNodes[0]?.id || null);
  }, []);

  const addNodeFromPalette = useCallback(
    (kind) => {
      if (!reactFlowWrapper.current) {
        return;
      }

      const position = getCanvasCenterPosition(reactFlowWrapper.current, project);
      const newNode = createNode(kind, position);
      setNodes((currentNodes) => currentNodes.concat(newNode));
      setSelectedNodeId(newNode.id);
      setSaveStatus(`${newNode.data.label} added to the canvas.`);
    },
    [project, setNodes]
  );

  const updateSelectedNode = useCallback(
    (field, value) => {
      if (!selectedNodeId) {
        return;
      }

      setNodes((currentNodes) =>
        currentNodes.map((node) => {
          if (node.id !== selectedNodeId) {
            return node;
          }

          const nextData = { ...node.data };
          if (field === "type") {
            nextData.kind = value;
            node.style = {
              ...node.style,
              ...nodeStyles[value],
            };
          } else if (field === "label") {
            nextData.label = value;
          } else if (field === "notes") {
            nextData.notes = value;
          }

          return {
            ...node,
            data: nextData,
            style: {
              ...node.style,
              ...(field === "type" ? nodeStyles[value] : {}),
            },
          };
        })
      );
      setSaveStatus("Properties updated. Save when ready.");
    },
    [selectedNodeId, setNodes]
  );

  const applyAutoLayout = useCallback(() => {
    setNodes((currentNodes) =>
      currentNodes.map((node, index) => ({
        ...node,
        position: {
          x: 120 + (index % 3) * 320,
          y: 120 + Math.floor(index / 3) * 220,
        },
      }))
    );
    setSaveStatus("Auto layout applied. Save when ready.");
  }, [setNodes]);

  const saveModel = useCallback(async () => {
    const payload = {
      saved_at: new Date().toISOString(),
      diagram: {
        nodes: nodes.map(flowNodeToStorageNode),
        edges: edges.map(({ id, source, target, label }) => ({ id, source, target, label: label || "" })),
        viewport: getViewport(),
      },
    };

    setSaveStatus("Saving model...");

    try {
      const response = await fetch(saveUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });
      const result = await response.json();
      if (!response.ok || !result.success) {
        throw new Error(result.error || "Unable to save the model.");
      }
      setSaveStatus(`Saved at ${new Date().toLocaleTimeString()}.`);
    } catch (error) {
      setSaveStatus(error.message);
    }
  }, [edges, getViewport, nodes, saveUrl]);

  return React.createElement("div", null, [
    React.createElement(
      "div",
      { className: "editor-toolbar", key: "toolbar" },
      [
        React.createElement(
          "div",
          { className: "toolbar-meta", key: "meta" },
          [
            React.createElement("h3", { key: "title", style: { marginBottom: "0.2rem" } }, initialModel.title),
            React.createElement(
              "span",
              { key: "sub" },
              `${initialModel.project_name} · ${initialModel.environment} · ${initialModel.generation_mode}`
            ),
          ]
        ),
        React.createElement(
          "div",
          { className: "editor-toolbar-actions", key: "actions" },
          [
            React.createElement("button", { key: "save", className: "btn btn-primary", onClick: saveModel }, "Save Model"),
            React.createElement("button", { key: "layout", className: "btn btn-outline-primary", onClick: applyAutoLayout }, "Auto Layout"),
            React.createElement("a", { key: "json", className: "btn btn-outline-primary", href: exportJsonUrl }, "Export JSON"),
            React.createElement("a", { key: "mermaid", className: "btn btn-outline-primary", href: exportMermaidUrl }, "Export Mermaid"),
            React.createElement("a", { key: "plantuml", className: "btn btn-outline-primary", href: exportPlantumlUrl }, "Export PlantUML"),
          ]
        ),
      ]
    ),
    React.createElement(
      "div",
      { className: "editor-shell", key: "shell" },
      [
        React.createElement(
          "aside",
          { className: "editor-panel", key: "palette" },
          [
            React.createElement("h5", { key: "heading" }, "Components"),
            React.createElement(
              "p",
              { key: "copy", className: "properties-empty" },
              "Drag components into the canvas or click to add them at the center."
            ),
            ...palette.map((item) => createPaletteEntryElement(item, addNodeFromPalette)),
          ]
        ),
        React.createElement(
          "section",
          { className: "editor-canvas", key: "canvas" },
          React.createElement(
            "div",
            { className: "canvas-wrapper", ref: reactFlowWrapper },
            React.createElement(
              ReactFlow,
              {
                nodes,
                edges,
                nodeTypes,
                defaultViewport,
                onNodesChange,
                onEdgesChange,
                onConnect,
                onDrop,
                onDragOver,
                onSelectionChange,
                fitView: true,
                deleteKeyCode: ["Backspace", "Delete"],
                defaultEdgeOptions: {
                  markerEnd: { type: "arrowclosed" },
                  style: { stroke: "#60a5fa", strokeWidth: 1.6 },
                  labelStyle: { fill: "#cbd5e1", fontSize: 12 },
                },
              },
              [
                React.createElement(Background, { key: "background", color: "#1e293b", gap: 18 }),
                React.createElement(MiniMap, { key: "minimap", zoomable: true, pannable: true }),
                React.createElement(Controls, { key: "controls", showInteractive: false }),
                React.createElement(
                  Panel,
                  { key: "panel", position: "top-left" },
                  React.createElement("div", { className: "save-status" }, saveStatus)
                ),
              ]
            )
          )
        ),
        React.createElement(
          "aside",
          { className: "editor-panel", key: "properties" },
          [
            React.createElement("h5", { key: "heading" }, "Selected Node"),
            selectedNode
              ? React.createElement(
                  "div",
                  { key: "fields" },
                  [
                    React.createElement("label", { key: "label-name", className: "form-label", htmlFor: "nodeLabel" }, "Label"),
                    React.createElement("input", {
                      key: "label-input",
                      id: "nodeLabel",
                      className: "form-control mb-3",
                      value: selectedNode.data.label,
                      onChange: (event) => updateSelectedNode("label", event.target.value),
                    }),
                    React.createElement("label", { key: "type-name", className: "form-label", htmlFor: "nodeType" }, "Type"),
                    React.createElement(
                      "select",
                      {
                        key: "type-input",
                        id: "nodeType",
                        className: "form-select mb-3",
                        value: selectedNode.data.kind,
                        onChange: (event) => updateSelectedNode("type", event.target.value),
                      },
                      palette.map((item) =>
                        React.createElement("option", { key: item.type, value: item.type }, item.label)
                      )
                    ),
                    React.createElement("label", { key: "notes-name", className: "form-label", htmlFor: "nodeNotes" }, "Notes"),
                    React.createElement("textarea", {
                      key: "notes-input",
                      id: "nodeNotes",
                      className: "form-control",
                      rows: 6,
                      value: selectedNode.data.notes || "",
                      onChange: (event) => updateSelectedNode("notes", event.target.value),
                    }),
                  ]
                )
              : React.createElement(
                  "p",
                  { key: "empty", className: "properties-empty" },
                  "Select a node to inspect and edit its properties."
                ),
          ]
        ),
      ]
    ),
  ]);
}

const rootElement = document.getElementById("dfd-editor-root");
const model = JSON.parse(rootElement.dataset.model);

createRoot(rootElement).render(
  React.createElement(
    ReactFlowProvider,
    null,
    React.createElement(EditorApp, {
      initialModel: model,
      saveUrl: rootElement.dataset.saveUrl,
      exportJsonUrl: rootElement.dataset.exportJsonUrl,
      exportMermaidUrl: rootElement.dataset.exportMermaidUrl,
      exportPlantumlUrl: rootElement.dataset.exportPlantumlUrl,
    })
  )
);
