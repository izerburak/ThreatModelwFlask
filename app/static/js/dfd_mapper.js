(function (global) {
  const ROLES = ["actor", "interface", "process", "llm", "data_store", "tool", "external", "output", "action"];
  const PIPELINE_LABEL = "LLM Pipeline";
  const LLM_LABEL = "LLM / Model Service";

  const QUESTION_ROLE = {
    Q2: "actor",
    Q3: "interface",
    Q7: "process",
    Q8: "data_store",
    Q9: "process",
    Q12: "tool",
    Q13: "data_store",
    Q15: "action",
    Q22: "output",
    Q24: "data_store",
  };

  const FIELD_ROLE = {
    "architecture.actors": "actor",
    "architecture.interfaces": "interface",
    "architecture.tools": "tool",
    "architecture.storage": "data_store",
  };

  const PIPELINE_ITEMS = new Set([
    "input filtering",
    "prompt templating",
    "rag augmentation",
    "routing/classification",
    "routing",
    "classification",
    "basic logic",
    "framework",
    "agent workflow",
    "hardcoded in application logic",
    "stored in configuration files",
    "managed through database or admin panel",
    "dynamically generated at runtime",
  ]);

  const CONTROL_ONLY = new Set([
    "single tenant system",
    "multi tenant with strong isolation",
    "user level isolation",
    "tenant level isolation",
    "no authentication required",
    "no authorization controls",
    "basic request throttling",
    "no validation process",
    "manual trust in vendor source",
    "partially protected",
    "no safeguards",
    "basic redaction or masking",
    "access controls and scoped retrieval",
    "no logging or monitoring",
    "human approval is always required",
    "no informational use only",
    "unknown",
    "none",
    "no",
    "yes",
  ]);

  const ROLE_KEYWORDS = {
    actor: ["user", "users", "employee", "employees", "administrator", "administrators", "developer", "developers", "automated systems", "pipelines", "local system processes"],
    interface: ["web based chat interface", "chat interface", "rest api endpoint", "api endpoint", "frontend", "cli", "sso", "single sign on", "third party integration", "user facing web interface"],
    process: ["backend api", "backend", "application backend", "agent workflow", "orchestration", "basic logic", "framework", "routing", "classification", "prompt templating", "input filtering", "rag augmentation", "document ingestion pipeline", "model hosting", "api integration layer"],
    llm: ["llm", "model service", "language model"],
    data_store: ["database", "vector db", "vector database", "sql", "nosql", "file storage", "cloud storage", "internal knowledge base", "knowledge base", "documentation", "source code", "customer data", "customer support records", "api keys", "credentials", "personally identifiable information", "pii", "internal operational documents"],
    tool: ["search", "database tool", "internal apis", "admin tools", "tool calling", "agent framework"],
    external: ["third party cloud api", "external vendor", "external api", "web urls", "public repositories", "external web content"],
    output: ["api response consumed by other systems", "email", "messaging", "notification", "backend automation", "internal admin dashboard"],
    action: ["create or update tickets", "send emails", "execute workflows", "transactions", "modify system configurations"],
  };

  function buildDfdGraph({ answersByFlowId, qwenExtract, mode = "compact" } = {}) {
    const answers = isObject(answersByFlowId) ? answersByFlowId : {};
    const extract = isObject(qwenExtract) ? qwenExtract : {};
    const builder = createBuilder(mode);
    const pipelineItems = [];
    const trustBoundaries = [];

    const purpose = stringValue(answers.Q1 || answers.q_1) || stringValue(path(extract, ["system_summary", "purpose"])) || "Threat model draft";

    addAnswerNodes(builder, answers, pipelineItems, trustBoundaries);
    addExtractNodes(builder, extract, pipelineItems, trustBoundaries);
    ensureDefaults(builder, answers);
    addPipeline(builder, pipelineItems, mode);
    layoutNodes(builder.nodes);
    addTemplateEdges(builder, trustBoundaries);

    return {
      nodes: builder.nodes,
      edges: builder.edges,
      metadata: {
        purpose,
        generatedFrom: {
          answers: Object.keys(answers).length > 0,
          qwenExtract: Object.keys(extract).length > 0,
        },
        mode,
      },
    };
  }

  function addAnswerNodes(builder, answers, pipelineItems, trustBoundaries) {
    Object.entries(answers).forEach(([rawQuestion, value]) => {
      const question = normalizeQuestionId(rawQuestion);
      const values = asList(value).map(stringValue).filter(Boolean);
      values.forEach((label) => {
        const normalized = normalizeLabel(label);
        if (shouldIgnoreValue(normalized)) return;

        if (question === "Q1" || question === "Q21") return;
        if (question === "Q23") {
          trustBoundaries.push(label);
          return;
        }
        if (["Q40", "Q41", "Q42", "Q43", "Q44", "Q45", "Q46", "Q47"].includes(question) && !isConcreteComponent(label)) {
          return;
        }
        if (["Q7", "Q11", "Q19"].includes(question)) {
          pipelineItems.push(label);
          return;
        }
        if (question === "Q5") {
          addQ5Hint(builder, label);
          return;
        }
        if (question === "Q6") {
          addQ6Hint(builder, label);
          return;
        }
        if (question === "Q8" && normalized === "no rag") return;
        if (question === "Q9" && normalized === "none") return;
        if (question === "Q12" && normalized === "none") return;
        if (question === "Q13" && normalized === "none") return;
        if (question === "Q14") {
          if (["directly", "via backend"].includes(normalized)) {
            builder.addNode("External API", "external", "answers.Q14", "Q14", "External API capability.");
          }
          return;
        }
        if (question === "Q15" && normalized === "generate text responses only") return;
        if (question === "Q17") {
          const description = /third|vendor|cloud|external/i.test(label) ? `LLM hosting: ${label}` : label;
          builder.addNode(LLM_LABEL, "llm", "answers.Q17", "Q17", description);
          return;
        }
        if (question === "Q24" && normalized === "no sensitive data") return;

        const role = inferRole(label, null, question);
        builder.addNode(label, role, `answers.${question}`, question);
      });
    });
  }

  function addExtractNodes(builder, extract, pipelineItems, trustBoundaries) {
    const summary = isObject(extract.system_summary) ? extract.system_summary : {};
    const architecture = isObject(extract.architecture) ? extract.architecture : {};

    asList(summary.trust_boundaries).forEach((value) => {
      const label = stringValue(value);
      if (label) trustBoundaries.push(label);
    });

    [
      ["architecture.actors", architecture.actors],
      ["architecture.interfaces", architecture.interfaces],
      ["architecture.data_sources", architecture.data_sources],
      ["architecture.tools", architecture.tools],
      ["architecture.storage", architecture.storage],
      ["system_summary.key_components", summary.key_components],
    ].forEach(([field, values]) => {
      asList(values).forEach((value) => {
        const label = stringValue(value);
        const normalized = normalizeLabel(label);
        if (!label || shouldIgnoreValue(normalized)) return;
        if (!isArchitectureRelevant(label, field)) return;
        const role = inferRole(label, field, null);
        if (role === "process" && PIPELINE_ITEMS.has(normalized)) {
          pipelineItems.push(label);
          return;
        }
        builder.addNode(label, role, field, null);
      });
    });
  }

  function addQ5Hint(builder, label) {
    const normalized = normalizeLabel(label);
    if (normalized === "direct user prompts" || normalized === "user text input only") return;
    if (normalized.includes("uploaded file")) builder.addNode("Uploaded Files", "external", "answers.Q5", "Q5");
    else if (normalized.includes("retrieved internal document")) builder.addNode("Internal Documents", "data_store", "answers.Q5", "Q5");
    else if (normalized.includes("external web content")) builder.addNode("External Web Content", "external", "answers.Q5", "Q5");
    else if (normalized.includes("api") || normalized.includes("database")) builder.addNode(label, "data_store", "answers.Q5", "Q5");
  }

  function addQ6Hint(builder, label) {
    const normalized = normalizeLabel(label);
    if (normalized === "user text input only") return;
    if (normalized.includes("file upload")) builder.addNode("File Uploads", "external", "answers.Q6", "Q6");
    else if (normalized.includes("web url")) builder.addNode("Web URLs", "external", "answers.Q6", "Q6");
    else if (normalized.includes("email") || normalized.includes("ticket")) builder.addNode(label, "data_store", "answers.Q6", "Q6");
    else if (normalized.includes("public repositor")) builder.addNode("Public Repositories", "external", "answers.Q6", "Q6");
  }

  function ensureDefaults(builder, answers) {
    if (!builder.nodes.some((node) => node.data.role === "actor")) {
      builder.addNode("User", "actor", "default", null);
    }
    if (!builder.nodes.some((node) => node.data.role === "interface")) {
      builder.addNode("Application Interface", "interface", "default", null);
    }
    if (!findBackend(builder)) {
      builder.addNode("Backend API", "process", "default", null);
    }
    if (!findLlm(builder)) {
      const hosting = stringValue(answers.Q17 || answers.q_17);
      builder.addNode(LLM_LABEL, "llm", "default", "Q17", hosting || "Default LLM service.");
    }
  }

  function addPipeline(builder, pipelineItems, mode) {
    const uniqueItems = uniqueLabels(pipelineItems).filter((item) => !shouldIgnoreValue(normalizeLabel(item)));
    if (!uniqueItems.length) return;
    if (mode === "expanded") {
      uniqueItems.forEach((item) => builder.addNode(item, "process", "pipeline", null));
      return;
    }
    const node = builder.addNode(PIPELINE_LABEL, "process", "pipeline", null, "Grouped LLM preprocessing, orchestration, and prompt management.");
    node.data.items = uniqueItems;
  }

  function addTemplateEdges(builder, trustBoundaries) {
    const actors = nodesByRole(builder, "actor");
    const interfaces = nodesByRole(builder, "interface");
    const processes = nodesByRole(builder, "process");
    const tools = nodesByRole(builder, "tool");
    const dataStores = nodesByRole(builder, "data_store");
    const externals = nodesByRole(builder, "external");
    const outputs = nodesByRole(builder, "output");
    const actions = nodesByRole(builder, "action");
    const backend = findBackend(builder) || processes[0];
    const pipeline = findByLabel(builder, PIPELINE_LABEL);
    const llm = findLlm(builder);
    const primaryInterface = interfaces[0];

    actors.forEach((actor) => {
      if (primaryInterface) builder.addEdge(actor, primaryInterface, "uses", trustBoundaries);
    });
    interfaces.forEach((node) => {
      if (backend && node.id !== backend.id) builder.addEdge(node, backend, "request", trustBoundaries);
    });
    if (backend && pipeline) builder.addEdge(backend, pipeline, "prompt/context", trustBoundaries);
    if (pipeline && llm) builder.addEdge(pipeline, llm, "model request", trustBoundaries);
    if (!pipeline && backend && llm) builder.addEdge(backend, llm, "model request", trustBoundaries);
    dataStores.forEach((store) => {
      if (pipeline && isRagSource(store)) builder.addEdge(store, pipeline, "retrieved context", trustBoundaries);
    });
    tools.forEach((tool) => {
      if (llm) builder.addEdge(llm, tool, "uses tool", trustBoundaries);
      matchingToolStores(tool, dataStores).forEach((store) => builder.addEdge(tool, store, "accesses", trustBoundaries));
    });
    externals.forEach((external) => {
      const source = tools[0] || backend;
      if (source) builder.addEdge(source, external, "calls external service", trustBoundaries);
    });
    if (llm && backend) builder.addEdge(llm, backend, "model response", trustBoundaries);
    outputs.forEach((output) => {
      if (backend) builder.addEdge(backend, output, "returns output", trustBoundaries);
    });
    actions.forEach((action) => {
      if (backend) builder.addEdge(backend, action, "triggers action", trustBoundaries);
    });
  }

  function createBuilder(mode) {
    const nodes = [];
    const edges = [];
    const nodeByKey = new Map();
    const edgeKeys = new Set();

    return {
      nodes,
      edges,
      addNode(label, role, source, sourceQuestion, description) {
        const cleanLabel = canonicalLabel(label);
        const cleanRole = ROLES.includes(role) ? role : "process";
        const key = normalizeEquivalent(cleanLabel);
        if (nodeByKey.has(key)) {
          const node = nodeByKey.get(key);
          node.data.source = mergeSource(node.data.source, source);
          if (description && !node.data.description) node.data.description = description;
          return node;
        }
        const node = {
          id: `node_${nodes.length + 1}`,
          type: "dfdNode",
          position: { x: 0, y: 0 },
          data: {
            label: cleanLabel,
            role: cleanRole,
            source: source || "unknown",
            description: description || "",
          },
        };
        nodes.push(node);
        nodeByKey.set(key, node);
        return node;
      },
      addEdge(sourceNode, targetNode, label, trustBoundaries) {
        if (!sourceNode || !targetNode || sourceNode.id === targetNode.id) return null;
        const boundary = chooseBoundary(sourceNode, targetNode, trustBoundaries || []);
        const key = `${sourceNode.id}|${targetNode.id}|${label}`;
        if (edgeKeys.has(key)) return null;
        const edge = {
          id: `edge_${edges.length + 1}`,
          source: sourceNode.id,
          target: targetNode.id,
          label,
          type: "smoothstep",
          animated: false,
          data: {
            source: "deterministic-template",
            boundary,
          },
        };
        edges.push(edge);
        edgeKeys.add(key);
        return edge;
      },
    };
  }

  function inferRole(label, sourceField, sourceQuestion) {
    if (sourceQuestion && QUESTION_ROLE[sourceQuestion]) return QUESTION_ROLE[sourceQuestion];
    if (sourceField && FIELD_ROLE[sourceField]) return FIELD_ROLE[sourceField];
    if (sourceField === "architecture.data_sources") {
      const normalized = normalizeLabel(label);
      if (normalized.includes("web") || normalized.includes("public repositor")) return "external";
      return "data_store";
    }
    const normalized = normalizeLabel(label);
    for (const role of ROLES) {
      if ((ROLE_KEYWORDS[role] || []).some((keyword) => normalized.includes(keyword))) return role;
    }
    return "process";
  }

  function chooseBoundary(sourceNode, targetNode, boundaries) {
    const pair = `${sourceNode.data.role}->${targetNode.data.role}`;
    const normalizedBoundaries = boundaries.map((value) => ({ raw: value, normalized: normalizeLabel(value) }));
    const pick = (terms) => normalizedBoundaries.find((item) => terms.every((term) => item.normalized.includes(term)));
    if (pair === "actor->interface") return pick(["public", "web"])?.raw || pick(["internet"])?.raw || null;
    if (pair === "interface->process") return pick(["web", "internal api"])?.raw || null;
    if ((sourceNode.data.role === "process" || sourceNode.data.label === PIPELINE_LABEL) && targetNode.data.role === "llm") {
      return pick(["model service"])?.raw || pick(["internal api"])?.raw || null;
    }
    return pick(["cross tenant"])?.raw || pick(["cross user"])?.raw || null;
  }

  function layoutNodes(nodes) {
    const columns = {
      actor: 0,
      interface: 1,
      process: 2,
      pipeline: 3,
      llm: 4,
      tool: 5,
      data_store: 5,
      external: 5,
      output: 6,
      action: 6,
    };
    const counts = {};
    nodes.forEach((node) => {
      const columnKey = node.data.label === PIPELINE_LABEL ? "pipeline" : node.data.role;
      const col = columns[columnKey] ?? 2;
      const index = counts[col] || 0;
      node.position = { x: 80 + col * 300, y: 90 + index * 120 };
      counts[col] = index + 1;
    });
  }

  function findBackend(builder) {
    return builder.nodes.find((node) => ["backend api", "application backend", "backend"].includes(normalizeEquivalent(node.data.label)))
      || builder.nodes.find((node) => node.data.role === "process" && normalizeLabel(node.data.label).includes("backend"));
  }

  function findLlm(builder) {
    return builder.nodes.find((node) => node.data.role === "llm") || findByLabel(builder, LLM_LABEL);
  }

  function findByLabel(builder, label) {
    const key = normalizeEquivalent(label);
    return builder.nodes.find((node) => normalizeEquivalent(node.data.label) === key);
  }

  function nodesByRole(builder, role) {
    return builder.nodes.filter((node) => node.data.role === role);
  }

  function isRagSource(node) {
    const label = normalizeLabel(node.data.label);
    return ["knowledge base", "documentation", "source code", "customer data", "vector", "document"].some((term) => label.includes(term));
  }

  function isReasonableToolStorePair(tool, store) {
    const toolLabel = normalizeLabel(tool.data.label);
    const storeLabel = normalizeLabel(store.data.label);
    if (toolLabel.includes("search")) return storeLabel.includes("vector") || storeLabel.includes("knowledge") || storeLabel.includes("documentation");
    if (toolLabel.includes("database")) return storeLabel.includes("database") || storeLabel.includes("sql") || storeLabel.includes("customer");
    if (toolLabel.includes("internal api")) return storeLabel.includes("customer") || storeLabel.includes("database");
    if (toolLabel.includes("admin")) return storeLabel.includes("credential") || storeLabel.includes("configuration");
    return false;
  }

  function matchingToolStores(tool, dataStores) {
    const matches = dataStores.filter((store) => isReasonableToolStorePair(tool, store));
    return matches.slice(0, 3);
  }

  function isArchitectureRelevant(label, field) {
    const normalized = normalizeLabel(label);
    if (CONTROL_ONLY.has(normalized)) return false;
    if (field === "system_summary.key_components") {
      return inferRole(label, null, null) !== "process" || /backend|frontend|api|llm|model|database|vector|storage|interface|source|documentation/i.test(label);
    }
    return true;
  }

  function isConcreteComponent(label) {
    const role = inferRole(label, null, null);
    return ["data_store", "external", "tool", "interface", "process", "llm"].includes(role);
  }

  function shouldIgnoreValue(normalized) {
    return !normalized || CONTROL_ONLY.has(normalized);
  }

  function normalizeQuestionId(value) {
    const text = String(value || "").trim();
    const match = text.match(/^q_?(\d+)$/i);
    return match ? `Q${Number(match[1])}` : text.toUpperCase();
  }

  function normalizeEquivalent(label) {
    const normalized = normalizeLabel(label);
    if (["backend api", "application backend"].includes(normalized)) return "backend";
    if (["vector db", "vector database"].includes(normalized)) return "vector database";
    if (["web based chat interface", "chat interface"].includes(normalized)) return "chat interface";
    if (["llm", "model service", "llm model service"].includes(normalized)) return "llm model service";
    return normalized;
  }

  function normalizeLabel(label) {
    return stringValue(label)
      .toLowerCase()
      .replace(/&/g, " and ")
      .replace(/[^a-z0-9]+/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function canonicalLabel(label) {
    const normalized = normalizeEquivalent(label);
    if (normalized === "backend") return "Backend API";
    if (normalized === "vector database") return "Vector Database";
    if (normalized === "chat interface") return "Web-based Chat Interface";
    if (normalized === "llm model service") return LLM_LABEL;
    return stringValue(label);
  }

  function uniqueLabels(values) {
    const seen = new Set();
    const result = [];
    values.forEach((value) => {
      const label = stringValue(value);
      const key = normalizeEquivalent(label);
      if (label && !seen.has(key)) {
        seen.add(key);
        result.push(label);
      }
    });
    return result;
  }

  function mergeSource(existing, source) {
    const values = new Set(String(existing || "").split(", ").filter(Boolean));
    if (source) values.add(source);
    return Array.from(values).join(", ") || "unknown";
  }

  function asList(value) {
    if (Array.isArray(value)) return value;
    if (value === null || value === undefined || value === "") return [];
    return [value];
  }

  function stringValue(value) {
    return value === null || value === undefined ? "" : String(value).trim();
  }

  function isObject(value) {
    return value !== null && typeof value === "object" && !Array.isArray(value);
  }

  function path(object, keys) {
    return keys.reduce((current, key) => (isObject(current) ? current[key] : undefined), object);
  }

  global.DfdMapper = {
    buildDfdGraph,
    inferRole,
  };
})(window);
