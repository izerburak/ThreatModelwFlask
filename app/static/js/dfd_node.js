(function (global) {
  const nodeStyles = {
    actor: {
      accent: "#38bdf8",
      background: "rgba(14, 165, 233, 0.16)",
      borderRadius: 999,
      width: 218,
      minHeight: 86,
      badge: "Actor",
    },
    interface: {
      accent: "#22c55e",
      background: "rgba(34, 197, 94, 0.15)",
      borderRadius: 12,
      width: 220,
      minHeight: 86,
      badge: "Interface",
    },
    process: {
      accent: "#818cf8",
      background: "rgba(99, 102, 241, 0.16)",
      borderRadius: 12,
      width: 220,
      minHeight: 86,
      badge: "Process",
    },
    database: {
      accent: "#f59e0b",
      background: "rgba(245, 158, 11, 0.15)",
      borderRadius: "22px 22px 10px 10px",
      width: 230,
      minHeight: 90,
      badge: "Data Store",
      inset: "inset 0 10px 0 rgba(245, 158, 11, 0.12)",
    },
    data_store: {
      accent: "#f59e0b",
      background: "rgba(245, 158, 11, 0.15)",
      borderRadius: "22px 22px 10px 10px",
      width: 230,
      minHeight: 90,
      badge: "Data Store",
      inset: "inset 0 10px 0 rgba(245, 158, 11, 0.12)",
    },
    llm: {
      accent: "#f472b6",
      background: "rgba(244, 114, 182, 0.15)",
      borderRadius: 16,
      width: 238,
      minHeight: 96,
      badge: "LLM",
      inset: "inset 0 0 24px rgba(244, 114, 182, 0.08)",
    },
    external_api: {
      accent: "#fb7185",
      background: "rgba(251, 113, 133, 0.15)",
      borderRadius: 12,
      width: 232,
      minHeight: 88,
      badge: "External API",
      borderStyle: "dashed",
    },
    external: {
      accent: "#fb7185",
      background: "rgba(251, 113, 133, 0.15)",
      borderRadius: 12,
      width: 232,
      minHeight: 88,
      badge: "External",
      borderStyle: "dashed",
    },
    trust_boundary: {
      accent: "#94a3b8",
      background: "rgba(148, 163, 184, 0.06)",
      borderRadius: 18,
      width: 560,
      minHeight: 320,
      badge: "Trust Boundary",
      borderStyle: "dashed",
    },
    tool: {
      accent: "#a78bfa",
      background: "rgba(167, 139, 250, 0.15)",
      borderRadius: 12,
      width: 220,
      minHeight: 86,
      badge: "Tool",
    },
    output: {
      accent: "#2dd4bf",
      background: "rgba(45, 212, 191, 0.15)",
      borderRadius: 12,
      width: 220,
      minHeight: 86,
      badge: "Output",
    },
    action: {
      accent: "#f97316",
      background: "rgba(249, 115, 22, 0.15)",
      borderRadius: 12,
      width: 220,
      minHeight: 86,
      badge: "Action",
    },
  };

  function nodeTypeFromData(data) {
    const explicit = String(data?.nodeType || "").toLowerCase();
    if (explicit) return explicit;

    const role = String(data?.role || "").toLowerCase();
    if (role === "data_store") return "database";
    if (role === "external") return "external_api";
    return role || "process";
  }

  function DfdNode({ data, selected }) {
    const React = global.React;
    const e = React.createElement;
    const Handle = global.ReactFlow.Handle;
    const Position = global.ReactFlow.Position;
    const safeData = data && typeof data === "object" ? data : {};
    const nodeType = nodeTypeFromData(safeData);
    const style = nodeStyles[nodeType] || nodeStyles.process;
    const items = Array.isArray(safeData.items) ? safeData.items : [];
    const isBoundary = nodeType === "trust_boundary";
    const label = safeData.label || "Unnamed Node";
    const detailLine = [safeData.role, safeData.kind].filter(Boolean).join(" / ");
    const width = Number(safeData.width || safeData.w) || style.width;
    const minHeight = Number(safeData.height || safeData.h) || style.minHeight;

    return e("div", { style: { position: "relative" } }, [
      isBoundary
        ? null
        : e(Handle, {
            key: "target",
            type: "target",
            position: Position.Left,
            style: { width: 8, height: 8, background: style.accent, border: "1px solid #0f172a" },
          }),
      e("div", {
        key: "body",
        className: `dfd-node-body dfd-node-${nodeType.replace(/_/g, "-")}`,
        style: {
          width,
          minHeight,
          border: `1px ${style.borderStyle || "solid"} ${style.accent}`,
          borderRadius: style.borderRadius,
          background: isBoundary
            ? style.background
            : `linear-gradient(135deg, ${style.background}, rgba(12, 18, 34, 0.96))`,
          color: "#f8fafc",
          padding: isBoundary ? "0.85rem 1rem" : "0.8rem 0.9rem",
          boxShadow: selected
            ? `0 0 0 2px ${style.accent}`
            : isBoundary
              ? "none"
              : style.inset
                ? `0 12px 26px rgba(2, 6, 23, 0.28), ${style.inset}`
                : "0 12px 26px rgba(2, 6, 23, 0.28)",
          opacity: isBoundary ? 0.86 : 1,
        },
      }, [
        e("div", {
          key: "badge-row",
          style: {
            alignItems: "center",
            display: "flex",
            gap: "0.45rem",
            justifyContent: "space-between",
            marginBottom: "0.4rem",
          },
        }, [
          e("span", {
            key: "badge",
            style: {
              background: isBoundary ? "rgba(15, 23, 42, 0.5)" : style.background,
              border: `1px solid ${style.accent}`,
              borderRadius: 999,
              color: "#e2e8f0",
              fontSize: "0.66rem",
              fontWeight: 700,
              padding: "0.12rem 0.45rem",
              textTransform: "uppercase",
            },
          }, style.badge || nodeType.replace(/_/g, " ")),
        ]),
        e("div", {
          key: "label",
          style: {
            fontWeight: 750,
            lineHeight: 1.25,
            maxWidth: "100%",
            overflowWrap: "anywhere",
          },
        }, label),
        detailLine
          ? e("div", {
              key: "detail",
              style: {
                color: "#cbd5e1",
                fontSize: "0.74rem",
                lineHeight: 1.35,
                marginTop: "0.35rem",
                overflowWrap: "anywhere",
              },
            }, detailLine)
          : null,
        items.length
          ? e("ul", {
              key: "items",
              style: {
                margin: "0.55rem 0 0",
                paddingLeft: "1rem",
                color: "#cbd5e1",
                fontSize: "0.78rem",
                lineHeight: 1.35,
              },
            }, items.slice(0, 5).map((item) => e("li", { key: item }, item)))
          : null,
        safeData.source
          ? e("div", {
              key: "source",
              style: {
                marginTop: "0.55rem",
                color: "#94a3b8",
                fontSize: "0.72rem",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              },
              title: safeData.source,
            }, safeData.source)
          : null,
      ]),
      isBoundary
        ? null
        : e(Handle, {
            key: "source",
            type: "source",
            position: Position.Right,
            style: { width: 8, height: 8, background: style.accent, border: "1px solid #0f172a" },
          }),
    ]);
  }

  global.DfdNode = DfdNode;
  global.StaticDfdNode = DfdNode;
})(window);
