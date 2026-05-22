"use client";

import React, { useState, useEffect, useRef } from "react";

// Types matching the API state
interface Task {
  id: number;
  title: string;
  goal: string;
  bullets: string[];
  target_words: number;
  tags?: string[];
  requires_research?: boolean;
  requires_citations?: boolean;
  requires_code?: boolean;
}

interface Plan {
  blog_title: string;
  audience: string;
  tone: string;
  blog_kind: string;
  constraints?: string[];
  tasks: Task[];
}

interface EvidenceItem {
  title: string;
  url: string;
  published_at?: string;
  snippet?: string;
  source?: string;
}

interface ImageSpec {
  placeholder: string;
  filename: string;
  alt: string;
  caption: string;
  prompt: string;
  size: string;
}

interface BlogState {
  node: string | null;
  mode: string;
  needs_research: boolean;
  queries: string[] | null;
  evidence_count: number;
  evidence: EvidenceItem[];
  plan: Plan | null;
  sections_count: number;
  image_specs: ImageSpec[] | null;
  final: string;
}

interface PastBlog {
  filename: string;
  title: string;
  updated_at: number;
}

export default function BlogDashboard() {
  // Inputs
  const [topic, setTopic] = useState("");
  const [asOf, setAsOf] = useState("");
  
  // UI states
  const [activeTab, setActiveTab] = useState<"plan" | "evidence" | "preview" | "images" | "logs">("preview");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [logs, setLogs] = useState<{ time: string; msg: string; type: "info" | "success" | "error" }[]>([]);
  const [currentNode, setCurrentNode] = useState<string | null>(null);
  
  // Loaded / Generated blog state
  const [currentState, setCurrentState] = useState<BlogState | null>(null);
  const [pastBlogs, setPastBlogs] = useState<PastBlog[]>([]);
  const [selectedFilename, setSelectedFilename] = useState<string | null>(null);

  const logsEndRef = useRef<HTMLDivElement>(null);

  // Set default as-of date to today on client mount
  useEffect(() => {
    const today = new Date().toISOString().split("T")[0];
    setAsOf(today);
    fetchPastBlogs();
  }, []);

  // Auto-scroll logs console to bottom
  useEffect(() => {
    if (logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs]);

  // Fetch past blogs list
  const fetchPastBlogs = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/blogs");
      if (res.ok) {
        const data = await res.json();
        setPastBlogs(data);
      }
    } catch (e) {
      addLog("Failed to fetch past blogs list.", "error");
    }
  };

  // Log adding helper
  const addLog = (msg: string, type: "info" | "success" | "error" = "info") => {
    const time = new Date().toLocaleTimeString();
    setLogs((prev) => [...prev, { time, msg, type }]);
  };

  // Load a blog file
  const loadBlog = async (filename: string) => {
    try {
      addLog(`Loading blog: ${filename}...`, "info");
      const res = await fetch(`http://localhost:8000/api/blogs/${filename}`);
      if (res.ok) {
        const data = await res.json();
        setSelectedFilename(filename);
        setCurrentState({
          node: "end",
          mode: data.metadata?.mode || "loaded",
          needs_research: data.metadata?.needs_research || false,
          queries: data.metadata?.queries || null,
          evidence_count: data.metadata?.evidence?.length || 0,
          evidence: data.metadata?.evidence || [],
          plan: data.metadata?.plan || {
            blog_title: data.title,
            audience: "Loaded from file",
            tone: "N/A",
            blog_kind: "explainer",
            tasks: [],
          },
          sections_count: data.metadata?.sections_count || 0,
          image_specs: data.metadata?.image_specs || null,
          final: data.content,
        });
        setActiveTab("preview");
        addLog(`Blog loaded successfully: ${data.title}`, "success");
      } else {
        addLog(`Failed to load blog: ${filename}`, "error");
      }
    } catch (e) {
      addLog(`Error loading blog: ${e}`, "error");
    }
  };

  // Handle generation form submit
  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!topic.trim()) {
      alert("Please enter a topic.");
      return;
    }

    setIsGenerating(true);
    setCurrentNode("router");
    setSelectedFilename(null);
    setLogs([]);
    setActiveTab("logs");
    addLog(`Starting agent run for topic: "${topic}"`, "info");
    
    // Reset state
    setCurrentState({
      node: "router",
      mode: "",
      needs_research: false,
      queries: [],
      evidence_count: 0,
      evidence: [],
      plan: null,
      sections_count: 0,
      image_specs: null,
      final: "",
    });

    try {
      const response = await fetch("http://localhost:8000/api/generate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          topic: topic.trim(),
          as_of: asOf,
        }),
      });

      if (!response.ok) {
        throw new Error(`Server returned status ${response.status}`);
      }

      if (!response.body) {
        throw new Error("Response body is not readable.");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split(/\r?\n\r?\n/);
        buffer = parts.pop() || "";

        for (const part of parts) {
          if (!part.trim()) continue;
          
          const lines = part.split(/\r?\n/);
          let eventName = "";
          let dataStr = "";
          
          for (const line of lines) {
            if (line.startsWith("event:")) {
              eventName = line.slice(6).trim();
            } else if (line.startsWith("data:")) {
              dataStr = line.slice(5).trim();
            }
          }

          if (eventName === "update" || eventName === "final") {
            try {
              const payload = JSON.parse(dataStr);
              if (payload.error) {
                addLog(`Agent error: ${payload.error}`, "error");
                setIsGenerating(false);
                break;
              }

              // Update node tracker
              if (payload.node) {
                setCurrentNode(payload.node);
                addLog(`Entering state node: [${payload.node.toUpperCase()}]`, "info");
              }

              // Update state
              setCurrentState((prev) => {
                const newState = {
                  node: payload.node || (prev ? prev.node : null),
                  mode: payload.mode || (prev ? prev.mode : ""),
                  needs_research: payload.needs_research !== undefined ? payload.needs_research : (prev ? prev.needs_research : false),
                  queries: payload.queries || (prev ? prev.queries : null),
                  evidence_count: payload.evidence_count !== undefined ? payload.evidence_count : (prev ? prev.evidence_count : 0),
                  evidence: payload.evidence || (prev ? prev.evidence : []),
                  plan: payload.plan || (prev ? prev.plan : null),
                  sections_count: payload.sections_count !== undefined ? payload.sections_count : (prev ? prev.sections_count : 0),
                  image_specs: payload.image_specs || (prev ? prev.image_specs : null),
                  final: payload.final || (prev ? prev.final : ""),
                };
                return newState;
              });

              if (eventName === "final") {
                setCurrentNode("end");
                setIsGenerating(false);
                setActiveTab("preview");
                addLog("Blog writing completed successfully!", "success");
                fetchPastBlogs(); // refresh list
                
                // If a plan exists, calculate the filename
                if (payload.plan && payload.plan.blog_title) {
                  const slug = payload.plan.blog_title.trim().toLowerCase()
                    .replace(/[^a-z0-9 _-]+/g, "")
                    .replace(/\s+/g, "_")
                    .replace(/^_+|_+$/g, "");
                  setSelectedFilename(`${slug || "blog"}.md`);
                }
              }
            } catch (err) {
              console.error("Error parsing stream chunk", err);
            }
          } else if (eventName === "error") {
            const payload = JSON.parse(dataStr);
            addLog(`Error stream event: ${payload.error || dataStr}`, "error");
            setIsGenerating(false);
          }
        }
      }
    } catch (err: any) {
      addLog(`Network or execution error: ${err.message}`, "error");
      setIsGenerating(false);
    }
  };

  // Helper to parse Markdown and render preview reactively
  const renderMarkdown = (text: string) => {
    if (!text) return <p>No preview content available.</p>;

    const lines = text.split("\n");
    const elements: React.ReactNode[] = [];
    let key = 0;
    
    let inCodeBlock = false;
    let codeContent: string[] = [];

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];

      // Code Block handling
      if (line.startsWith("```")) {
        if (inCodeBlock) {
          elements.push(
            <pre key={key++}>
              <code>{codeContent.join("\n")}</code>
            </pre>
          );
          codeContent = [];
          inCodeBlock = false;
        } else {
          inCodeBlock = true;
        }
        continue;
      }

      if (inCodeBlock) {
        codeContent.push(line);
        continue;
      }

      // Headers
      if (line.startsWith("# ")) {
        elements.push(<h1 key={key++}>{line.slice(2)}</h1>);
        continue;
      }
      if (line.startsWith("## ")) {
        elements.push(<h2 key={key++}>{line.slice(3)}</h2>);
        continue;
      }
      if (line.startsWith("### ")) {
        elements.push(<h3 key={key++}>{line.slice(4)}</h3>);
        continue;
      }

      // Blockquotes
      if (line.startsWith("> ")) {
        elements.push(<blockquote key={key++}>{line.slice(2)}</blockquote>);
        continue;
      }

      // Bullet lists
      if (line.startsWith("- ") || line.startsWith("* ")) {
        elements.push(<li key={key++}>{line.slice(2)}</li>);
        continue;
      }

      // Image render pattern e.g. ![alt](images/filename.png)
      const imgMatch = line.match(/!\[(.*?)\]\((.*?)\)/);
      if (imgMatch) {
        const alt = imgMatch[1];
        let src = imgMatch[2];
        
        // Rewrite local image paths to backend server
        if (!src.startsWith("http") && src.includes("images/")) {
          const filename = src.split("images/")[1];
          src = `http://localhost:8000/images/${filename}`;
        }
        
        elements.push(
          <div key={key++} style={{ textAlign: "center", margin: "20px 0" }}>
            <img 
              src={src} 
              alt={alt} 
              style={{ maxWidth: "100%", borderRadius: "8px", border: "1px solid var(--border-glow)" }} 
            />
            {/* If the next line is a caption in italic, render it */}
            {i + 1 < lines.length && lines[i + 1].startsWith("*") && lines[i + 1].endsWith("*") ? (
              <span className="markdown-image-caption" style={{ display: "block", marginTop: "8px" }}>
                {lines[++i].slice(1, -1)}
              </span>
            ) : (
              alt && <span className="markdown-image-caption" style={{ display: "block", marginTop: "8px" }}>{alt}</span>
            )}
          </div>
        );
        continue;
      }

      // Parse inline formatting (bold, links, inline code)
      if (line.trim()) {
        let content: React.ReactNode = line;
        
        // Inline code mapping
        if (line.includes("`")) {
          const parts = line.split("`");
          content = parts.map((part, index) => {
            if (index % 2 === 1) {
              return <code key={index}>{part}</code>;
            }
            return part;
          });
        }

        elements.push(<p key={key++}>{content}</p>);
      }
    }

    return <div className="markdown-body">{elements}</div>;
  };

  return (
    <>
      {/* Sidebar Past Blogs & Input */}
      <aside className={`sidebar ${sidebarCollapsed ? "collapsed" : ""}`}>
        <div className="sidebar-header">
          <h2 className="sidebar-title">Blog Writer</h2>
          <button 
            className="sidebar-toggle-btn"
            onClick={() => setSidebarCollapsed(true)}
            style={{ border: "none", background: "transparent", fontSize: "1.2rem" }}
          >
            ✕
          </button>
        </div>

        <div className="sidebar-content">
          <form onSubmit={handleGenerate}>
            <div className="section-label">New Blog Configuration</div>
            
            <div className="config-group">
              <label>Topic / Prompt</label>
              <textarea
                className="textarea-input"
                placeholder="E.g., System Design of a Multi-Language RAG Chatbot using FastAPI and Next.js"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                disabled={isGenerating}
                required
              />
            </div>

            <div className="config-group">
              <label>As-of Date</label>
              <input
                type="date"
                className="date-input"
                value={asOf}
                onChange={(e) => setAsOf(e.target.value)}
                disabled={isGenerating}
              />
            </div>

            <button 
              type="submit" 
              className="btn-primary"
              disabled={isGenerating}
            >
              {isGenerating ? "⚡ Generating..." : "🚀 Generate Blog"}
            </button>
          </form>

          <div style={{ marginTop: "32px" }}>
            <div className="section-label">Past Articles ({pastBlogs.length})</div>
            <div className="past-blogs-list">
              {pastBlogs.map((b) => (
                <button
                  key={b.filename}
                  className={`past-blog-item ${selectedFilename === b.filename ? "active" : ""}`}
                  onClick={() => loadBlog(b.filename)}
                  disabled={isGenerating}
                >
                  <div className="past-blog-title">{b.title}</div>
                  <div className="past-blog-meta">
                    {b.filename} · {new Date(b.updated_at * 1000).toLocaleDateString()}
                  </div>
                </button>
              ))}
              {pastBlogs.length === 0 && (
                <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", fontStyle: "italic" }}>
                  No articles generated yet.
                </div>
              )}
            </div>
          </div>
        </div>
      </aside>

      {/* Main Panel */}
      <main className="main-content">
        {/* Top Header */}
        <div className="header">
          <div className="header-left">
            {sidebarCollapsed && (
              <button 
                className="sidebar-toggle-btn"
                onClick={() => setSidebarCollapsed(false)}
              >
                ☰
              </button>
            )}
            <h1 className="main-title">
              {currentState?.plan?.blog_title || "Blog Writing Workspace"}
            </h1>
          </div>
          
          {isGenerating && (
            <div style={{ fontSize: "0.9rem", color: "var(--accent-indigo)", fontWeight: 600 }}>
              Running agent graph execution...
            </div>
          )}
        </div>

        {/* Status Tracker */}
        {(isGenerating || currentState) && (
          <div className="status-container">
            <div className={`status-step ${currentNode === "router" ? "active" : (currentNode && currentNode !== "router" ? "completed" : "")}`}>
              <span className="status-dot"></span>
              Router
            </div>
            {currentState?.needs_research && (
              <div className={`status-step ${currentNode === "research" ? "active" : ((currentState?.evidence_count ?? 0) > 0 ? "completed" : "")}`}>
                <span className="status-dot"></span>
                Research
              </div>
            )}
            <div className={`status-step ${currentNode === "orchestrator" ? "active" : (currentState?.plan ? "completed" : "")}`}>
              <span className="status-dot"></span>
              Orchestrator
            </div>
            <div className={`status-step ${currentNode === "worker" ? "active" : ((currentState?.sections_count ?? 0) > 0 ? "completed" : "")}`}>
              <span className="status-dot"></span>
              Workers ({currentState?.sections_count || 0}/{currentState?.plan?.tasks?.length || 0})
            </div>
            <div className={`status-step ${currentNode === "reducer" ? "active" : (currentState?.final ? "completed" : "")}`}>
              <span className="status-dot"></span>
              Reducer
            </div>
          </div>
        )}

        {/* Tabs Bar */}
        <div className="tabs-header">
          <button
            className={`tab-btn ${activeTab === "plan" ? "active" : ""}`}
            onClick={() => setActiveTab("plan")}
          >
            🧩 Plan
          </button>
          <button
            className={`tab-btn ${activeTab === "evidence" ? "active" : ""}`}
            onClick={() => setActiveTab("evidence")}
          >
            🔎 Evidence ({currentState?.evidence_count || 0})
          </button>
          <button
            className={`tab-btn ${activeTab === "preview" ? "active" : ""}`}
            onClick={() => setActiveTab("preview")}
          >
            📝 Markdown Preview
          </button>
          <button
            className={`tab-btn ${activeTab === "images" ? "active" : ""}`}
            onClick={() => setActiveTab("images")}
          >
            🖼️ Images
          </button>
          <button
            className={`tab-btn ${activeTab === "logs" ? "active" : ""}`}
            onClick={() => setActiveTab("logs")}
          >
            🧾 Logs
          </button>
        </div>

        {/* Tab Contents */}
        <div className="tab-content">
          {/* Plan Tab */}
          {activeTab === "plan" && (
            <div>
              {currentState?.plan ? (
                <div>
                  <div className="plan-summary">
                    <div className="summary-card">
                      <span className="summary-label">Target Audience</span>
                      <span className="summary-value">{currentState.plan.audience}</span>
                    </div>
                    <div className="summary-card">
                      <span className="summary-label">Tone Style</span>
                      <span className="summary-value">{currentState.plan.tone}</span>
                    </div>
                    <div className="summary-card">
                      <span className="summary-label">Post Category</span>
                      <span className="summary-value" style={{ textTransform: "capitalize" }}>
                        {currentState.plan.blog_kind}
                      </span>
                    </div>
                  </div>

                  <div className="task-grid">
                    {currentState.plan.tasks.map((task) => (
                      <div key={task.id} className="task-card">
                        <div className="task-id">0{task.id}</div>
                        <h3 className="task-title">{task.title}</h3>
                        <p className="task-goal">{task.goal}</p>
                        
                        <ul className="task-bullets">
                          {task.bullets.map((b, idx) => (
                            <li key={idx}>{b}</li>
                          ))}
                        </ul>

                        <div className="task-badge-row">
                          <span className="badge badge-words">{task.target_words} words</span>
                          {task.requires_research && <span className="badge badge-research">Research</span>}
                          {task.requires_code && <span className="badge badge-code">Code</span>}
                          {task.requires_citations && <span className="badge badge-citation">Citations</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="info-empty">
                  <div className="info-empty-icon">🧩</div>
                  <h3 className="info-empty-title">No Plan Available</h3>
                  <p className="info-empty-desc">
                    Plans are generated by the agent during active blog generation. Run a new generation to see the task outline.
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Evidence Tab */}
          {activeTab === "evidence" && (
            <div>
              {currentState?.evidence && currentState.evidence.length > 0 ? (
                <div className="evidence-list">
                  {currentState.evidence.map((item, idx) => (
                    <div key={idx} className="evidence-card">
                      <div className="evidence-header">
                        <h3 className="evidence-title">{item.title}</h3>
                        {item.url && (
                          <a 
                            href={item.url} 
                            target="_blank" 
                            rel="noopener noreferrer" 
                            className="evidence-link-btn"
                          >
                            Visit Source ↗
                          </a>
                        )}
                      </div>
                      
                      {item.snippet && (
                        <p className="evidence-snippet">{item.snippet}</p>
                      )}

                      <div className="evidence-meta">
                        {item.source && <span>Source: <strong>{item.source}</strong></span>}
                        {item.published_at && <span>Published: <strong>{item.published_at}</strong></span>}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="info-empty">
                  <div className="info-empty-icon">🔎</div>
                  <h3 className="info-empty-title">No Evidence Sources</h3>
                  <p className="info-empty-desc">
                    Web research findings and citation sources will populate here if the router flags research queries for the topic.
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Markdown Preview Tab */}
          {activeTab === "preview" && (
            <div>
              {currentState?.final ? (
                <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
                  {selectedFilename && (
                    <div className="preview-actions">
                      <a
                        href={`http://localhost:8000/api/blogs/${selectedFilename}/download`}
                        className="btn-secondary"
                        download
                      >
                        ⬇️ Download Markdown
                      </a>
                      <a
                        href={`http://localhost:8000/api/blogs/${selectedFilename}/bundle`}
                        className="btn-secondary"
                      >
                        📦 Download Bundle (MD + Images)
                      </a>
                    </div>
                  )}
                  {renderMarkdown(currentState.final)}
                </div>
              ) : (
                <div className="info-empty">
                  <div className="info-empty-icon">📝</div>
                  <h3 className="info-empty-title">No Article Content</h3>
                  <p className="info-empty-desc">
                    Enter a topic in the sidebar config panel and start generation, or select an article from the past list.
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Images Tab */}
          {activeTab === "images" && (
            <div>
              {currentState?.image_specs || selectedFilename ? (
                <div>
                  <div style={{ display: "flex", gap: "12px", marginBottom: "24px" }}>
                    <a
                      href="http://localhost:8000/api/blogs/all/images-zip"
                      className="btn-secondary"
                    >
                      ⬇️ Download Images (ZIP)
                    </a>
                  </div>

                  {currentState?.image_specs && (
                    <div className="image-specs-section">
                      <div className="section-label" style={{ marginBottom: "8px" }}>Image Generation Plan</div>
                      <pre style={{ fontSize: "0.8rem", overflowX: "auto" }}>
                        <code>{JSON.stringify(currentState.image_specs, null, 2)}</code>
                      </pre>
                    </div>
                  )}

                  {/* Render the images gallery if we have specs, or just general gallery */}
                  <div className="image-gallery">
                    {currentState?.image_specs?.map((spec, idx) => (
                      <div key={idx} className="image-card">
                        <div className="image-wrapper">
                          <img
                            className="img-element"
                            src={`http://localhost:8000/images/${spec.filename}`}
                            alt={spec.alt}
                            onError={(e) => {
                              // If image fails to load, display placeholder
                              (e.target as HTMLImageElement).src = "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=500&auto=format&fit=crop&q=60";
                            }}
                          />
                        </div>
                        <div className="image-card-content">
                          <div className="image-card-title">{spec.filename}</div>
                          <p className="image-card-caption">{spec.caption}</p>
                          <div className="image-card-prompt">Prompt: {spec.prompt}</div>
                        </div>
                      </div>
                    ))}
                    {(!currentState?.image_specs || currentState.image_specs.length === 0) && (
                      <div style={{ gridColumn: "1/-1", textAlign: "center", color: "var(--text-muted)", fontStyle: "italic", padding: "40px" }}>
                        No specific generated image logs. Check if files exist in the backend images directory.
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div className="info-empty">
                  <div className="info-empty-icon">🖼️</div>
                  <h3 className="info-empty-title">No Generated Visuals</h3>
                  <p className="info-empty-desc">
                    AI diagrams or workflow visual plans will show up here after the reducer node runs drawing assets.
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Logs Tab */}
          {activeTab === "logs" && (
            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              <div className="logs-console">
                {logs.map((logItem, idx) => (
                  <div key={idx} className={`log-entry ${logItem.type}`}>
                    <span className="log-time">[{logItem.time}]</span>
                    <span>{logItem.msg}</span>
                  </div>
                ))}
                {logs.length === 0 && (
                  <div style={{ color: "var(--text-muted)", fontStyle: "italic" }}>
                    Console idle. Ready for next event stream.
                  </div>
                )}
                <div ref={logsEndRef} />
              </div>
            </div>
          )}
        </div>
      </main>
    </>
  );
}
