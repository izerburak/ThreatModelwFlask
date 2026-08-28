(() => {
  "use strict";

  const categoryTabs = Array.from(document.querySelectorAll("[data-risk-category]"));
  const categoryPanels = Array.from(document.querySelectorAll("[data-risk-panel]"));
  const riskSearch = document.getElementById("riskSearch");
  const levelFilter = document.getElementById("riskLevelFilter");
  const statusFilter = document.getElementById("riskStatusFilter");

  if (!categoryTabs.length || !categoryPanels.length) return;

  let activeCategory =
    categoryTabs.find((tab) => tab.getAttribute("aria-selected") === "true")?.dataset.riskCategory ||
    categoryTabs[0].dataset.riskCategory;

  function activePanel() {
    return categoryPanels.find((panel) => panel.dataset.riskPanel === activeCategory);
  }

  function applyFilters() {
    const panel = activePanel();
    if (!panel) return;

    const query = (riskSearch?.value || "").trim().toLocaleLowerCase();
    const selectedLevel = levelFilter?.value || "all";
    const selectedStatus = statusFilter?.value || "all";
    const items = Array.from(panel.querySelectorAll("[data-risk-item]"));
    let visibleCount = 0;

    items.forEach((item) => {
      const levelMatches = selectedLevel === "all" || item.dataset.level === selectedLevel;
      const statusMatches = selectedStatus === "all" || item.dataset.status === selectedStatus;
      const searchMatches =
        !query || (item.dataset.search || "").toLocaleLowerCase().includes(query);
      const visible = levelMatches && statusMatches && searchMatches;

      item.hidden = !visible;
      if (visible) visibleCount += 1;
    });

    const count = panel.querySelector("[data-visible-count]");
    if (count) count.textContent = `${visibleCount} shown`;

    const empty = panel.querySelector(".risk-filter-empty");
    if (empty) empty.hidden = visibleCount !== 0 || items.length === 0;
  }

  function selectCategory(category, focusTab = false) {
    activeCategory = category;

    categoryTabs.forEach((tab) => {
      const selected = tab.dataset.riskCategory === category;
      tab.setAttribute("aria-selected", selected ? "true" : "false");
      tab.tabIndex = selected ? 0 : -1;
      if (selected && focusTab) tab.focus();
    });

    categoryPanels.forEach((panel) => {
      panel.hidden = panel.dataset.riskPanel !== category;
    });

    applyFilters();
  }

  categoryTabs.forEach((tab, index) => {
    tab.addEventListener("click", () => selectCategory(tab.dataset.riskCategory));
    tab.addEventListener("keydown", (event) => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
      event.preventDefault();

      let nextIndex = index;
      if (event.key === "ArrowLeft") nextIndex = (index - 1 + categoryTabs.length) % categoryTabs.length;
      if (event.key === "ArrowRight") nextIndex = (index + 1) % categoryTabs.length;
      if (event.key === "Home") nextIndex = 0;
      if (event.key === "End") nextIndex = categoryTabs.length - 1;
      selectCategory(categoryTabs[nextIndex].dataset.riskCategory, true);
    });
  });

  document.querySelectorAll(".risk-row-toggle").forEach((toggle) => {
    toggle.addEventListener("click", () => {
      const detailId = toggle.getAttribute("aria-controls");
      const detail = detailId ? document.getElementById(detailId) : null;
      if (!detail) return;

      const expanded = toggle.getAttribute("aria-expanded") === "true";
      toggle.setAttribute("aria-expanded", expanded ? "false" : "true");
      detail.hidden = expanded;
    });
  });

  riskSearch?.addEventListener("input", applyFilters);
  levelFilter?.addEventListener("change", applyFilters);
  statusFilter?.addEventListener("change", applyFilters);

  selectCategory(activeCategory);
})();
