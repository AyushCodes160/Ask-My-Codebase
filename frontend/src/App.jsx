import { useState, useEffect, useRef } from "react";
import { loadRepo, askQuestion, getStatus } from "./api";
import ReactMarkdown from "react-markdown";

function App() {
  const [repoUrl, setRepoUrl] = useState("");
  const [question, setQuestion] = useState("");
  const [status, setStatus] = useState(null);
  
  const [loadingRepo, setLoadingRepo] = useState(false);
  const [repoMessage, setRepoMessage] = useState("");
  
  const [asking, setAsking] = useState(false);
  const [chatHistory, setChatHistory] = useState([]);
  const [errorItem, setErrorItem] = useState(null);
  const messagesEndRef = useRef(null);

  // Initial fetch
  useEffect(() => {
    fetchStatus();
  }, []);

  // Auto-scroll to bottom of chat
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [chatHistory, asking]);

  const fetchStatus = async () => {
    try {
      const data = await getStatus();
      setStatus(data);
    } catch (e) {
      console.error(e);
    }
  };

  const handleLoadRepo = async () => {
    if (!repoUrl) return;
    setLoadingRepo(true);
    setRepoMessage("");
    setErrorItem(null);
    setChatHistory([]); // reset chat history on new repo load
    try {
      const res = await loadRepo(repoUrl);
      setRepoMessage(res.message);
      await fetchStatus();
    } catch (e) {
      setErrorItem(`Failed to load repo: ${e.message}`);
    } finally {
      setLoadingRepo(false);
    }
  };

  const handleAsk = async () => {
    if (!question.trim()) return;
    
    const currentQ = question;
    // Map existing history to the format required by the backend API
    const historyForAPI = chatHistory.map(msg => ({ role: msg.role, content: msg.content }));
    
    // Add user's question to the UI immediately
    setChatHistory(prev => [...prev, { role: "user", content: currentQ }]);
    setQuestion("");
    setAsking(true);
    setErrorItem(null);

    try {
      const res = await askQuestion(currentQ, historyForAPI);
      setChatHistory(prev => [
        ...prev, 
        { 
          role: "assistant", 
          content: res.answer, 
          sources: res.sources, 
          latency_ms: res.latency_ms 
        }
      ]);
    } catch (e) {
      setErrorItem(`Failed to answer: ${e.message}`);
    } finally {
      setAsking(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleAsk();
    }
  };

  return (
    <div style={{ padding: "20px", fontFamily: "Inter, sans-serif", maxWidth: "800px", margin: "0 auto", display: "flex", flexDirection: "column", height: "95vh" }}>
      <h1>Ask My Codebase</h1>
      <p>Ask continuous questions about your GitHub repository.</p>
      
      {/* Configuration Panel */}
      <div style={{ marginBottom: "20px", border: "1px solid #ddd", padding: "15px", borderRadius: "8px", flexShrink: 0 }}>
        <h3>1. Clone & Index Repository</h3>
        <div style={{ display: "flex", alignItems: "center" }}>
          <input 
            type="text" 
            value={repoUrl} 
            onChange={(e) => setRepoUrl(e.target.value)} 
            placeholder="https://github.com/user/repo"
            style={{ flex: 1, padding: "8px", marginRight: "10px" }}
          />
          <button onClick={handleLoadRepo} disabled={loadingRepo}>
            {loadingRepo ? "Loading..." : "Load Repo"}
          </button>
        </div>
        {repoMessage && <p style={{ color: "green", marginTop: "10px", marginBottom: "0" }}>{repoMessage}</p>}
        {status?.index_loaded && (
           <p style={{ color: "#555", fontSize: "0.9em", marginTop: "5px", marginBottom: "0" }}>
             Indexed {status.chunk_count} chunks from <strong>{status.current_repo}</strong>.
           </p>
        )}
      </div>

      {errorItem && (
        <div style={{ background: "#ffd6d6", color: "red", padding: "10px", borderRadius: "8px", marginBottom: "20px", flexShrink: 0 }}>
          {errorItem}
        </div>
      )}

      {/* Chat Area */}
      <div style={{ flex: 1, border: "1px solid #ddd", borderRadius: "8px", display: "flex", flexDirection: "column", overflow: "hidden", background: "#fafafa" }}>
        
        {/* Chat Log */}
        <div style={{ flex: 1, overflowY: "auto", padding: "20px" }}>
          {chatHistory.length === 0 && !asking ? (
            <div style={{ textAlign: "center", color: "#888", marginTop: "50px" }}>
              {status?.index_loaded ? "Repo loaded! Start chatting below." : "Load a repository to begin."}
            </div>
          ) : (
            chatHistory.map((msg, idx) => (
              <div key={idx} style={{ 
                display: "flex", 
                justifyContent: msg.role === "user" ? "flex-end" : "flex-start",
                marginBottom: "20px" 
              }}>
                <div style={{
                  maxWidth: "85%",
                  padding: "12px 16px",
                  borderRadius: "12px",
                  background: msg.role === "user" ? "#007bff" : "#fff",
                  color: msg.role === "user" ? "#fff" : "#333",
                  border: msg.role === "user" ? "none" : "1px solid #ddd",
                  boxShadow: "0 1px 2px rgba(0,0,0,0.05)"
                }}>
                  {msg.role === "user" ? (
                    <div style={{ whiteSpace: "pre-wrap" }}>{msg.content}</div>
                  ) : (
                    <div>
                      <div className="markdown" style={{ lineHeight: "1.6" }}>
                        <ReactMarkdown>{msg.content}</ReactMarkdown>
                      </div>
                      
                      {/* Latency and Sources collapsible area */}
                      {msg.sources && (
                        <div style={{ marginTop: "15px", paddingTop: "15px", borderTop: "1px solid #eee", fontSize: "0.85em" }}>
                          <span style={{ color: "#777", marginRight: "10px" }}>⏱️ {msg.latency_ms}ms</span>
                          <details>
                            <summary style={{ cursor: "pointer", color: "#555", fontWeight: "bold", display: "inline-block" }}>
                              View Sources ({msg.sources.length})
                            </summary>
                            <ul style={{ paddingLeft: "20px", marginTop: "10px", color: "#555" }}>
                              {msg.sources.map((s, sIdx) => (
                                <li key={sIdx} style={{ marginBottom: "10px" }}>
                                  <strong>{s.file_path}</strong>
                                </li>
                              ))}
                            </ul>
                          </details>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
          
          {asking && (
             <div style={{ display: "flex", justifyContent: "flex-start", marginBottom: "20px" }}>
                <div style={{ padding: "12px 16px", borderRadius: "12px", background: "#fff", border: "1px solid #ddd", color: "#666" }}>
                  Thinking...
                </div>
             </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div style={{ padding: "15px", borderTop: "1px solid #ddd", background: "#fff" }}>
          <div style={{ display: "flex", alignItems: "center" }}>
            <textarea 
              value={question} 
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={status?.index_loaded ? "Ask a question about the code... (Press Enter to send)" : "Load a repo first..."}
              disabled={!status?.index_loaded || asking}
              style={{ 
                flex: 1, 
                padding: "10px", 
                borderRadius: "8px",
                border: "1px solid #ccc",
                resize: "none",
                minHeight: "44px",
                maxHeight: "120px"
              }}
              rows={1}
            />
            <button 
              onClick={handleAsk} 
              disabled={asking || !status?.index_loaded || !question.trim()}
              style={{ marginLeft: "10px", padding: "10px 20px", height: "44px", borderRadius: "8px" }}
            >
              Send
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}

export default App;
