(function (global) {
  const roleColors = {
    actor: ["#38bdf8", "rgba(14, 165, 233, 0.16)"],
    interface: ["#22c55e", "rgba(34, 197, 94, 0.15)"],
    process: ["#818cf8", "rgba(99, 102, 241, 0.16)"],
    llm: ["#f472b6", "rgba(244, 114, 182, 0.15)"],
    data_store: ["#f59e0b", "rgba(245, 158, 11, 0.15)"],
    tool: ["#a78bfa", "rgba(167, 139, 250, 0.15)"],
    external: ["#fb7185", "rgba(251, 113, 133, 0.15)"],
    output: ["#2dd4bf", "rgba(45, 212, 191, 0.15)"],
    action: ["#f97316", "rgba(249, 115, 22, 0.15)"],
  };

  function DfdNode({ data, selected }) {
    const React = global.React;
    const e = React.createElement;
    const Handle = global.ReactFlow.Handle;
    const Position = global.ReactFlow.Position;
    const [accent, background] = roleColors[data.role] || roleColors.process;
    const items = Array.isArray(data.items) ? data.items : [];

    return e("div", { style: { position: "relative" } }, [
      e(Handle, {
        key: "target",
        type: "target",
        position: Position.Left,
        style: { width: 8, height: 8, background: accent, border: "1px solid #0f172a" },
      }),
      e("div", {
        key: "body",
        style: {
          width: 220,
          minHeight: 86,
          border: `1px solid ${accent}`,
          borderRadius: 12,
          background: `linear-gradient(135deg, ${background}, rgba(12, 18, 34, 0.96))`,
          color: "#f8fafc",
          padding: "0.8rem 0.9rem",
          boxShadow: selected ? `0 0 0 2px ${accent}` : "0 12px 26px rgba(2, 6, 23, 0.28)",
        },
      }, [
        e("div", {
          key: "role",
          style: {
            color: "#cbd5e1",
            fontSize: "0.68rem",
            letterSpacing: "0.12em",
            textTransform: "uppercase",
            marginBottom: "0.35rem",
          },
        }, String(data.role || "process").replace(/_/g, " ")),
        e("div", { key: "label", style: { fontWeight: 700, lineHeight: 1.25 } }, data.label || "Unnamed Node"),
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
        data.source
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
              title: data.source,
            }, data.source)
          : null,
      ]),
      e(Handle, {
        key: "source",
        type: "source",
        position: Position.Right,
        style: { width: 8, height: 8, background: accent, border: "1px solid #0f172a" },
      }),
    ]);
  }

  global.DfdNode = DfdNode;
})(window);
