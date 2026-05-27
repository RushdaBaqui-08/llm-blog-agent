"use client";

import React, { useState } from "react";
import Link from "next/link";

// Nodes specification for the LangGraph interactive flowchart
interface GraphNode {
  id: string;
  title: string;
  sublabel: string;
  icon: string;
  tech: string;
  details: string;
  bullets: string[];
  footnote: string;
}

const GRAPH_NODES: GraphNode[] = [
  {
    id: "router",
    title: "Case-Insensitive Router Node",
    sublabel: "Evergreen vs. Search Routing",
    icon: "🧭",
    tech: "LangGraph Conditional Router",
    details: "Analyzes the user's blog post request to determine the appropriate workflow strategy. Avoids unnecessary API costs by separating queries.",
    bullets: [
      "Performs case-insensitive checks on input queries.",
      "Routes to Open-Book / Hybrid mode for real-time topics.",
      "Routes directly to Evergreen mode for generic topics.",
      "Configures search lookback dates dynamically."
    ],
    footnote: "Under the hood: Direct graph routing based on LLM decision matrices."
  },
  {
    id: "research",
    title: "Research Node",
    sublabel: "Tavily Web Search Engine",
    icon: "🔍",
    tech: "Tavily API + URL Evidence Parser",
    details: "Performs real-time web research to gather factual information, code references, and historical evidence for the topic.",
    bullets: [
      "Executes parallel queries using Tavily API.",
      "Normalizes dates and filters evidence by publication date.",
      "Performs URL and query deduplication to prevent redundant searches.",
      "Compiles source citations and links for the article."
    ],
    footnote: "Fallbacks: Skips research gracefully if TAVILY_API_KEY is missing."
  },
  {
    id: "orchestrator",
    title: "Orchestrator Node",
    sublabel: "Structured Blog Outline Planning",
    icon: "📋",
    tech: "Structured Plan Generator",
    details: "Uses LLM reasoning to outline the final blog post structure, dividing the work into 5-9 independent sections.",
    bullets: [
      "Creates a detailed task checklist with sub-goals.",
      "Specifies targeted word counts for each section.",
      "Assigns specific flags (requires_code, requires_research, requires_citations).",
      "Defines the target audience, tone, constraints, and keywords."
    ],
    footnote: "Output: A structured JSON outline matching the Plan interface."
  },
  {
    id: "worker",
    title: "Parallel Section Workers",
    sublabel: "Concurrent Content Generation",
    icon: "⚡",
    tech: "Async Parallel Tasks",
    details: "Generates multiple blog sections at the same time, speeding up the overall creation process.",
    bullets: [
      "Spawns asynchronous writing workers for each section in the plan.",
      "Ensures inline citations ([Source](url)) are attached where required.",
      "Injects clean, syntactically correct markdown formatting.",
      "Maintains context using shared graph state variables."
    ],
    footnote: "Implements high-concurrency node workflows in LangGraph."
  },
  {
    id: "reducer",
    title: "Reducer Node",
    sublabel: "Content Merge & Illustration Planning",
    icon: "🧩",
    tech: "State Reducer + Prompt Designer",
    details: "Merges the independently written sections back into a cohesive markdown document and plans image layouts.",
    bullets: [
      "Stitches sections in chronological order.",
      "Cleans up layout mismatches and redundant phrases.",
      "Identifies logical insertion points for custom illustrations.",
      "Generates detailed descriptive prompts for the image generator."
    ],
    footnote: "Transforms multiple section results back into a single blog state."
  },
  {
    id: "imagegen",
    title: "Image Gen Pipeline",
    sublabel: "Google Imagen 4.0 & Fallbacks",
    icon: "🖼️",
    tech: "Imagen API + Pollinations AI Fallback",
    details: "Illustrates the blog posts with high-quality visual aids, utilizing premium models with zero-dependency fallbacks.",
    bullets: [
      "Calls Google Imagen 4.0 for high-fidelity technical vector diagrams.",
      "Detects rate-limits or quota errors automatically.",
      "Falls back to Pollinations AI without interrupting the workflow.",
      "Places images and caption specs in correct markdown tags."
    ],
    footnote: "Ensures 100% success rate even when API keys are restricted."
  },
  {
    id: "sse",
    title: "SSE Stream Engine",
    sublabel: "Real-time Dashboard Connection",
    icon: "📡",
    tech: "FastAPI Server-Sent Events",
    details: "Streams live state updates from the backend graph directly to the developer dashboard interface in real time.",
    bullets: [
      "Provides granular progress bars for parallel sections.",
      "Streams system logs to the developer console.",
      "Allows instant file previews while compilation runs.",
      "Sends final zip packages of text and visual bundles."
    ],
    footnote: "Connection: Persistent EventSource channel on port 8000."
  }
];

// Preloaded articles data for the showcase explorer
interface ArticleShowcase {
  title: string;
  audience: string;
  tone: string;
  category: string;
  outline: { title: string; goal: string; words: number; tags: string[] }[];
  markdown: string;
}

const ARTICLE_SHOWCASE: ArticleShowcase[] = [
  {
    title: "FastAPI vs Node.js for AI Backend Development in 2026",
    audience: "Technical Architects & CTOs",
    tone: "Analytical and benchmark-driven",
    category: "Technical Explainer",
    outline: [
      { title: "Introduction to FastAPI and Node.js", goal: "Overview of both web frameworks in AI-native contexts.", words: 250, tags: ["Research"] },
      { title: "Benchmarks and Performance Comparison", goal: "Requests-per-second, memory footprint, and parallel concurrency test.", words: 400, tags: ["Code", "Research"] },
      { title: "Deployment Ecosystem and Tools", goal: "Docker, Kubernetes, and modern cloud deployment integrations.", words: 350, tags: ["Citations"] },
      { title: "Why AI Startups Prefer Python and FastAPI", goal: "Analysis of the ML library ecosystem and async execution benefit.", words: 300, tags: [] },
      { title: "Conclusion and Future Outlook", goal: "Edge AI and serverless trends summary.", words: 200, tags: ["Citations"] }
    ],
    markdown: `# FastAPI vs Node.js for AI Backend Development in 2026

## Introduction to FastAPI and Node.js
FastAPI and Node.js are two popular frameworks used for AI backend development.
- **FastAPI**: A modern, high-performance web framework for building APIs with Python 3.7+, based on standard Python type hints.
- **Node.js**: A JavaScript runtime environment that allows developers to run JavaScript on the server-side, offering a vast ecosystem for building scalable web apps.

According to recent benchmarks, FastAPI beats Node.js for AI-native applications [Source](https://www.linkedin.com/posts/sidharthsatapathy_from-frontend-to-ai-engineer-day-5-why-activity-7413206943416348672-toKX), being considered a highly optimized backend framework.

## Benchmarks and Performance Comparison
The performance of a backend framework is crucial for AI startups as it impacts speed. Recent studies reveal that FastAPI generally outperforms Node.js in latency when integrating LLM calls. Analysis of performance metrics shows:
- FastAPI's native ASGI supports highly concurrent async network requests.
- Node.js's single-threaded event loop can suffer when handling CPU-bound data parsing operations.

## Deployment Ecosystem and Tools
Both frameworks offer a range of deployment options:
- Containerization tools like **Docker** and orchestration tools like **Kubernetes** are industry standards.
- Monitoring and logging integrations with **Prometheus**, **Grafana**, and **ELK Stack** verify uptime.
`
  },
  {
    title: "RAG vs Fine-Tuning: Choosing the Right Approach for AI Architecture",
    audience: "AI Engineers & Decision Makers",
    tone: "Professional and objective",
    category: "Architectural Guide",
    outline: [
      { title: "Defining RAG & Fine-Tuning Core Differences", goal: "Parametric vs. Non-parametric memory comparison.", words: 300, tags: ["Research"] },
      { title: "Data Freshness and Knowledge Updates", goal: "Handling real-time vector indexes vs. expensive retraining weights.", words: 350, tags: ["Citations"] },
      { title: "Cost Analysis: Compute & Vector Storage", goal: "Compute budgets, API embedding tokens, and database maintenance costs.", words: 400, tags: ["Code"] },
      { title: "Accuracy, Hallucinations, and Factuality", goal: "Mitigating false information and anchoring responses with evidence.", words: 300, tags: ["Research"] },
      { title: "Hybrid Approaches: RAG-Assisted Fine-Tuning", goal: "Combining both paradigms for domain-specific models.", words: 250, tags: ["Citations"] }
    ],
    markdown: `# RAG vs Fine-Tuning: Choosing the Right Approach for AI Architecture

## Defining RAG & Fine-Tuning Core Differences
When architecting domain-specific LLM systems, developers face a critical choice: Retrieval-Augmented Generation (RAG) or Fine-Tuning.
- **RAG**: Dynamically retrieves relevant context documents and injects them into the model's prompt window during inference.
- **Fine-Tuning**: Permanently bakes knowledge and style behaviors into the model's neural weights through supervised training.

## Data Freshness and Knowledge Updates
RAG excels at handling continuously updating data. Since the vector database can be indexed in real-time, the model immediately gains access to fresh source material. Fine-Tuning, conversely, requires subsequent training runs, which are time-consuming and costly.

## Cost Analysis: Compute & Vector Storage
- **Fine-Tuning**: Requires significant upfront training compute costs but lowers per-token prompt costs.
- **RAG**: Has negligible setup costs but incurs constant storage fees and increases prompt tokens due to large injected contexts.
`
  },
  {
    title: "Revolutionizing Software Development: The Rise of Multi-Agent AI Systems",
    audience: "Software Engineers & Tech Leaders",
    tone: "Inspiring and forward-looking",
    category: "Industry Analysis",
    outline: [
      { title: "From Single Prompt to Collaborative Agent Networks", goal: "The evolution from chat prompts to state-based agentic graphs.", words: 300, tags: [] },
      { title: "Orchestrator-Worker & Parallel Graph Design", goal: "How LangGraph structures complex concurrent workflows.", words: 450, tags: ["Code"] },
      { title: "State Sharing, Validation & Memory Retention", goal: "Managing shared memory and validating worker outputs.", words: 350, tags: ["Research"] },
      { title: "Real-world Applications & Developer Productivity", goal: "Practical workflows: writing, editing, and code compilation.", words: 400, tags: ["Research", "Citations"] },
      { title: "Future Outlook: Self-Correcting Autonomous Workflows", goal: "Where multi-agent architectures are heading.", words: 250, tags: ["Citations"] }
    ],
    markdown: `# Revolutionizing Software Development: The Rise of Multi-Agent AI Systems

## From Single Prompt to Collaborative Agent Networks
Software engineering is transitioning from simple chatbot completions to collaborative agent networks. These networks split a complex problem into smaller tasks managed by dedicated agents.

## Orchestrator-Worker & Parallel Graph Design
In an Orchestrator-Worker pattern:
1. A master agent designs a structured task plan.
2. The orchestrator delegates writing segments to parallel workers.
3. Workers generate code and text in parallel, reducing overall time-to-output.

## State Sharing, Validation & Memory Retention
Managing a shared state enables multi-agent architectures to validate their output before presenting it to the user. If an agent's code block fails validation, the graph routes the error back to a compiler worker for self-correction.
`
  }
];

export default function LandingPage() {
  const [selectedNode, setSelectedNode] = useState<string>("router");
  const [selectedArticleIdx, setSelectedArticleIdx] = useState<number>(0);

  const activeNodeData = GRAPH_NODES.find((node) => node.id === selectedNode) || GRAPH_NODES[0];
  const activeArticle = ARTICLE_SHOWCASE[selectedArticleIdx];

  return (
    <div className="landing-container">
      {/* Background glowing gradients */}
      <div className="hero-glow-1"></div>
      <div className="hero-glow-2"></div>

      {/* Navigation Header */}
      <nav className="landing-nav">
        <div className="landing-nav-logo">
          <span className="dot"></span>
          BlogWriter <span style={{ color: "var(--text-secondary)", fontWeight: 400 }}>AI</span>
        </div>
        <div className="landing-nav-links">
          <a href="#features">Features</a>
          <a href="#workflow">Architecture</a>
          <a href="#demo">Generated Blogs</a>
          <Link href="/dashboard" className="landing-nav-btn">
            Launch Console ⚡
          </Link>
        </div>
      </nav>

      {/* Hero Section */}
      <header className="hero-section">
        <h1 className="hero-title">
          Unleash Autonomous <br />
          <span className="highlight">Content Engineering</span>
        </h1>
        <p className="hero-desc">
          An orchestrator-worker multi-agent AI assistant powered by <strong>LangGraph</strong>. 
          Research the web, design structures, write sections in parallel, and generate visuals automatically.
        </p>

        <div className="hero-ctas">
          <Link href="/dashboard" className="btn-hero-primary">
            Launch Agent Dashboard ⚡
          </Link>
          <a href="#workflow" className="btn-hero-secondary">
            Explore Architecture Graph
          </a>
        </div>

        {/* Dashboard Mockup Browser Preview */}
        <div className="hero-mockup-wrapper">
          <div className="hero-mockup">
            <div className="mockup-header">
              <div className="mockup-dots">
                <span className="mockup-dot dot-red"></span>
                <span className="mockup-dot dot-yellow"></span>
                <span className="mockup-dot dot-green"></span>
              </div>
              <div className="mockup-address">localhost:3000/dashboard</div>
              <div style={{ width: "40px" }}></div>
            </div>
            <div className="mockup-body">
              {/* Sidebar */}
              <div className="mockup-sidebar">
                <div className="mockup-sidebar-item active"></div>
                <div className="mockup-sidebar-item"></div>
                <div className="mockup-sidebar-item" style={{ width: "60%" }}></div>
                <div style={{ marginTop: "auto", width: "50%" }} className="mockup-sidebar-item"></div>
              </div>
              {/* Main Panel */}
              <div className="mockup-main">
                <div className="mockup-main-header">
                  <div className="mockup-title"></div>
                  <div className="mockup-status-tracker">
                    <span className="mockup-tracker-dot completed"></span>
                    <span className="mockup-tracker-dot completed"></span>
                    <span className="mockup-tracker-dot active"></span>
                    <span className="mockup-tracker-dot"></span>
                  </div>
                </div>
                <div className="mockup-content-grid">
                  <div className="mockup-preview-panel">
                    <div className="mockup-line header"></div>
                    <div className="mockup-line"></div>
                    <div className="mockup-line medium"></div>
                    <div className="mockup-line"></div>
                    <div className="mockup-line short"></div>
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                    <div className="mockup-preview-panel" style={{ flex: 1, justifyContent: "center" }}>
                      <div className="mockup-image-box">
                        <span className="mockup-image-icon">🖼️</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Interactive LangGraph Workflow Section */}
      <section id="workflow" className="landing-section alt">
        <div className="landing-section-title-wrap">
          <h2 className="landing-section-title">
            LangGraph <span className="glow">Orchestration Graph</span>
          </h2>
          <p className="landing-section-subtitle">
            Click on the interactive state nodes below to explore the underlying multi-agent coordination workflow and APIs.
          </p>
        </div>

        <div className="graph-section-container">
          {/* SVG Flowchart & Interactive Buttons */}
          <div className="graph-visual">
            <div className="graph-nodes-flow">
              {/* Node 1 */}
              <div className="graph-node-row">
                <div
                  className={`graph-interactive-node ${selectedNode === "router" ? "selected" : ""}`}
                  onClick={() => setSelectedNode("router")}
                >
                  <span className="node-icon-circle">🧭</span>
                  <div className="node-text-wrap">
                    <span className="node-label">Router Node</span>
                    <span className="node-sublabel">Conditional workflow router</span>
                  </div>
                </div>
              </div>
              <div className="graph-arrow-down">↓</div>

              {/* Node 2 - Split Row */}
              <div className="node-split-row">
                <div
                  className={`graph-interactive-node ${selectedNode === "research" ? "selected" : ""}`}
                  onClick={() => setSelectedNode("research")}
                  style={{ width: "240px" }}
                >
                  <span className="node-icon-circle">🔍</span>
                  <div className="node-text-wrap">
                    <span className="node-label">Research Node</span>
                    <span className="node-sublabel">Tavily Web Search</span>
                  </div>
                </div>
                <div
                  className={`graph-interactive-node ${selectedNode === "orchestrator" ? "selected" : ""}`}
                  onClick={() => setSelectedNode("orchestrator")}
                  style={{ width: "240px" }}
                >
                  <span className="node-icon-circle">📋</span>
                  <div className="node-text-wrap">
                    <span className="node-label">Orchestrator Node</span>
                    <span className="node-sublabel">Structure Plan creator</span>
                  </div>
                </div>
              </div>

              {/* Merge arrows down */}
              <div className="graph-arrow-down glow-line">↓</div>

              {/* Node 3 */}
              <div className="graph-node-row">
                <div
                  className={`graph-interactive-node ${selectedNode === "worker" ? "selected" : ""}`}
                  onClick={() => setSelectedNode("worker")}
                >
                  <span className="node-icon-circle">⚡</span>
                  <div className="node-text-wrap">
                    <span className="node-label">Parallel Workers</span>
                    <span className="node-sublabel">Concurrent content writing</span>
                  </div>
                </div>
              </div>
              <div className="graph-arrow-down">↓</div>

              {/* Node 4 */}
              <div className="graph-node-row">
                <div
                  className={`graph-interactive-node ${selectedNode === "reducer" ? "selected" : ""}`}
                  onClick={() => setSelectedNode("reducer")}
                >
                  <span className="node-icon-circle">🧩</span>
                  <div className="node-text-wrap">
                    <span className="node-label">Reducer Node</span>
                    <span className="node-sublabel">Content merge & images plan</span>
                  </div>
                </div>
              </div>
              <div className="graph-arrow-down">↓</div>

              {/* Node 5 */}
              <div className="graph-node-row">
                <div
                  className={`graph-interactive-node ${selectedNode === "imagegen" ? "selected" : ""}`}
                  onClick={() => setSelectedNode("imagegen")}
                >
                  <span className="node-icon-circle">🖼️</span>
                  <div className="node-text-wrap">
                    <span className="node-label">Image Gen Pipeline</span>
                    <span className="node-sublabel">Imagen 4.0 + fallbacks</span>
                  </div>
                </div>
              </div>
              <div className="graph-arrow-down">↓</div>

              {/* Node 6 */}
              <div className="graph-node-row">
                <div
                  className={`graph-interactive-node ${selectedNode === "sse" ? "selected" : ""}`}
                  onClick={() => setSelectedNode("sse")}
                >
                  <span className="node-icon-circle">📡</span>
                  <div className="node-text-wrap">
                    <span className="node-label">SSE Stream Update</span>
                    <span className="node-sublabel">SSE streaming payload</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Node detail display sidebar panel */}
          <div className="node-detail-card">
            <div>
              <div className="detail-node-header">
                <div className="detail-node-icon">{activeNodeData.icon}</div>
                <div>
                  <h3 className="detail-node-title">{activeNodeData.title}</h3>
                  <span className="detail-node-tech">{activeNodeData.tech}</span>
                </div>
              </div>
              <p className="detail-node-body">{activeNodeData.details}</p>
              
              <ul className="detail-node-bullets">
                {activeNodeData.bullets.map((bullet, idx) => (
                  <li key={idx}>{bullet}</li>
                ))}
              </ul>
            </div>
            
            <div className="detail-node-footer">
              💡 {activeNodeData.footnote}
            </div>
          </div>
        </div>
      </section>

      {/* Preloaded Generated Articles Explorer Section */}
      <section id="demo" className="landing-section">
        <div className="landing-section-title-wrap">
          <h2 className="landing-section-title">
            Generated <span className="glow">Articles Showcase</span>
          </h2>
          <p className="landing-section-subtitle">
            See the structured outlining and factual text outputs built in real-world generation tests by our agent.
          </p>
        </div>

        <div className="demo-explorer">
          {/* Tabs header bar */}
          <div className="demo-tabs-bar">
            {ARTICLE_SHOWCASE.map((art, idx) => (
              <button
                key={idx}
                className={`demo-tab-button ${selectedArticleIdx === idx ? "active" : ""}`}
                onClick={() => setSelectedArticleIdx(idx)}
              >
                {art.title.length > 45 ? `${art.title.slice(0, 45)}...` : art.title}
              </button>
            ))}
          </div>

          <div className="demo-split-workspace">
            {/* Left: outlines */}
            <div className="demo-left-outline">
              <div className="section-label" style={{ marginBottom: "6px" }}>
                Generated Outline ({activeArticle.outline.length} Sections)
              </div>
              <div style={{ display: "flex", gap: "12px", marginBottom: "16px", fontSize: "0.8rem", color: "var(--text-muted)" }}>
                <span>Tone: <strong>{activeArticle.tone}</strong></span>
                <span>•</span>
                <span>Type: <strong>{activeArticle.category}</strong></span>
              </div>
              
              {activeArticle.outline.map((section, idx) => (
                <div key={idx} className="demo-outline-card completed">
                  <div className="demo-outline-header">
                    <h4 className="demo-outline-title">0{idx + 1}. {section.title}</h4>
                    <span className="demo-outline-badge">{section.words} words</span>
                  </div>
                  <p className="demo-outline-goal">{section.goal}</p>
                  
                  <div style={{ display: "flex", gap: "6px", marginTop: "4px" }}>
                    {section.tags.map((tag, tIdx) => (
                      <span
                        key={tIdx}
                        className="badge"
                        style={{
                          fontSize: "0.6rem",
                          padding: "2px 6px",
                          background: tag === "Research" ? "rgba(99, 102, 241, 0.15)" : tag === "Code" ? "rgba(139, 92, 246, 0.15)" : "rgba(16, 185, 129, 0.15)",
                          color: tag === "Research" ? "#a5b4fc" : tag === "Code" ? "#ddd6fe" : "#a7f3d0"
                        }}
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            {/* Right: Markdown content display */}
            <div className="demo-right-preview">
              <div className="section-label" style={{ marginBottom: "16px" }}>Raw Markdown Output Preview</div>
              <div dangerouslySetInnerHTML={{
                __html: activeArticle.markdown
                  .replace(/# (.*)/g, "<h1 style='font-size: 1.8rem; font-weight: 700; margin-bottom: 16px; border-bottom: 1px solid rgba(255,255,255,0.08); padding-bottom: 8px;'>$1</h1>")
                  .replace(/## (.*)/g, "<h2 style='font-size: 1.2rem; font-weight: 600; margin-top: 24px; margin-bottom: 12px; color: #fff;'>$1</h2>")
                  .replace(/\*\*([^*]+)\*\*/g, "<strong style='color:#fff;'>$1</strong>")
                  .replace(/- \*\*([^*]+)\*\*/g, "<li><strong style='color:#fff;'>$1</strong>")
                  .replace(/\[Source\]\((.*?)\)/g, "<a href='$1' target='_blank' style='color:var(--accent-emerald); text-decoration:underline;'>[Source]</a>")
              }} />
              <div style={{ marginTop: "32px", padding: "16px", background: "rgba(255,255,255,0.02)", border: "1px dashed rgba(255,255,255,0.1)", borderRadius: "8px", fontSize: "0.85rem", color: "var(--text-muted)", textAlign: "center" }}>
                📄 Excerpt shown. Launch the agent dashboard to generate the full article.
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Feature Capabilities Grid */}
      <section id="features" className="landing-section alt">
        <div className="landing-section-title-wrap">
          <h2 className="landing-section-title">
            Designed for <span className="glow">Visual Excellence</span>
          </h2>
          <p className="landing-section-subtitle">
            Underpinned by advanced API services, strict constraints, and state validation.
          </p>
        </div>

        <div className="capabilities-grid">
          <div className="capability-card">
            <span className="capability-icon">📡</span>
            <h3 className="capability-title">Real-Time Streaming</h3>
            <p className="capability-desc">
              Watch sections build live. Our Server-Sent Events (SSE) server handles granular state updates instantly.
            </p>
          </div>
          <div className="capability-card">
            <span className="capability-icon">🖼️</span>
            <h3 className="capability-title">Resilient Image Pipeline</h3>
            <p className="capability-desc">
              Generates visual assets with Google Imagen 4.0. Automatically falls back to Pollinations AI under rate limits.
            </p>
          </div>
          <div className="capability-card">
            <span className="capability-icon">🔍</span>
            <h3 className="capability-title">Tavily Web Research</h3>
            <p className="capability-desc">
              Normalizes publication dates, dedupes URLs, and references domain sources automatically.
            </p>
          </div>
          <div className="capability-card">
            <span className="capability-icon">📄</span>
            <h3 className="capability-title">Complete Markdown Bundle</h3>
            <p className="capability-desc">
              Download clean markdown files, local image asset packs, or complete compressed ZIP bundles in one click.
            </p>
          </div>
        </div>
      </section>



      {/* Action Banner */}
      <section className="landing-section alt" style={{ paddingBottom: "120px" }}>
        <div className="cta-banner">
          <h2 className="cta-banner-title">Ready to automate your publishing loop?</h2>
          <p className="cta-banner-desc">
            Experience the future of multi-agent collaborative writing. Outline, draft, illustrate, and refine in seconds.
          </p>
          <Link href="/dashboard" className="btn-hero-primary" style={{ marginTop: "16px" }}>
            Start Writing for Free ⚡
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="landing-footer">
        <div className="footer-left">
          <div className="footer-logo">BlogWriter AI</div>
          <span className="footer-copyright">
            © {new Date().getFullYear()} BlogWriter AI. Developed by Rushda Baqui.
          </span>
        </div>
        <div className="footer-right">
          <a href="https://github.com/RushdaBaqui-08" target="_blank" rel="noopener noreferrer">GitHub</a>
          <a href="https://www.linkedin.com/in/rushda-baqui-945581276/" target="_blank" rel="noopener noreferrer">LinkedIn</a>
          <a href="mailto:rushdabaqui@gmail.com">Contact</a>
        </div>
      </footer>
    </div>
  );
}
