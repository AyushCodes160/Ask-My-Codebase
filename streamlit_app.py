"""
FILE: streamlit_app.py
PURPOSE: Streamlit frontend for CodeRAG — replaces the React+Vite app.
         Connects to the FastAPI backend at BACKEND_URL (default http://localhost:8000).
RUN:     streamlit run streamlit_app.py
"""

import os
import streamlit as st
import requests

# ── Configuration ─────────────────────────────────────────────
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")

# ── Page Config ───────────────────────────────────────────────
st.set_page_config(
    page_title="CodeRAG — AI Code Analysis",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Minimal Custom Styling ────────────────────────────────────
st.markdown("""
<style>
    /* Dark accent color overrides */
    .stApp { background-color: #0a0a0a; }
    
    [data-testid="stSidebar"] {
        background-color: #111111;
        border-right: 1px solid rgba(240,236,228,0.08);
    }
    
    /* Accent green for headings */
    h1, h2, h3 { color: #f0ece4 !important; }
    
    .accent { color: #c8ff00; }
    
    /* Success / info message tweaks */
    .success-msg {
        color: #c8ff00;
        font-size: 0.85rem;
        padding: 8px 0;
    }
    
    /* Hide default streamlit branding */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    
    /* Chat message tweaks */
    [data-testid="stChatMessage"] {
        background-color: #161616;
        border: 1px solid rgba(240,236,228,0.06);
        border-radius: 12px;
    }
</style>
""", unsafe_allow_html=True)


# ── API Helper Functions ──────────────────────────────────────

def api_get(endpoint):
    """GET request to backend."""
    try:
        r = requests.get(f"{BACKEND_URL}{endpoint}", timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        return None
    except Exception as e:
        st.error(f"API Error: {e}")
        return None


def api_post(endpoint, json_data=None, files=None, timeout=120):
    """POST request to backend."""
    try:
        r = requests.post(
            f"{BACKEND_URL}{endpoint}",
            json=json_data,
            files=files,
            timeout=timeout,
        )
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error("❌ Cannot connect to backend. Make sure FastAPI is running on " + BACKEND_URL)
        return None
    except requests.exceptions.HTTPError as e:
        detail = ""
        try:
            detail = e.response.json().get("detail", str(e))
        except Exception:
            detail = str(e)
        st.error(f"❌ {detail}")
        return None
    except Exception as e:
        st.error(f"❌ API Error: {e}")
        return None


def get_status():
    """Fetch backend status."""
    return api_get("/status")


# ── Session State Init ────────────────────────────────────────

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "doc_chat_history" not in st.session_state:
    st.session_state.doc_chat_history = []
if "link_chat_history" not in st.session_state:
    st.session_state.link_chat_history = []


# ── Sidebar Navigation ───────────────────────────────────────

with st.sidebar:
    st.markdown("## 🤖 CodeRAG")
    st.caption("AI-Powered Code & Document Analysis")
    st.divider()
    
    page = st.radio(
        "Navigate",
        ["📦 GitHub Repo", "📄 Documents", "🔗 Links"],
        label_visibility="collapsed",
    )
    
    st.divider()
    
    # Backend status indicator
    status = get_status()
    if status:
        st.markdown("**System Status**")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Code Chunks", status.get("chunk_count", 0))
            st.metric("Doc Chunks", status.get("doc_chunk_count", 0))
        with col2:
            st.metric("Link Chunks", status.get("link_chunk_count", 0))
            if status.get("current_repo"):
                st.caption(f"Repo: `{status['current_repo']}`")
        
        indicators = []
        if status.get("index_loaded"):
            indicators.append("🟢 Code Index")
        if status.get("doc_index_loaded"):
            indicators.append("🟢 Doc Index")
        if status.get("link_index_loaded"):
            indicators.append("🟢 Link Index")
        if indicators:
            st.caption(" · ".join(indicators))
        else:
            st.caption("🔴 No indexes loaded")
    else:
        st.warning("⚠️ Backend offline")


# ══════════════════════════════════════════════════════════════
# PAGE: GitHub Repo Analyser
# ══════════════════════════════════════════════════════════════

if page == "📦 GitHub Repo":
    st.markdown("# 📦 GitHub Repo Analyser")
    
    # Status bar
    status = get_status()
    if status and status.get("index_loaded"):
        st.success(f"✅ Repo indexed: **{status['current_repo']}** ({status['chunk_count']} chunks)")
    else:
        st.info("No repository loaded yet. Enter a GitHub URL below to begin.")
    
    # Repo input
    with st.container(border=True):
        st.markdown("**① Clone & Index Repository**")
        col_input, col_btn = st.columns([4, 1])
        with col_input:
            repo_url = st.text_input(
                "GitHub URL",
                placeholder="https://github.com/user/repo",
                label_visibility="collapsed",
            )
        with col_btn:
            load_btn = st.button("Load Repo", use_container_width=True, type="primary")
        
        if load_btn and repo_url:
            with st.spinner("Cloning & indexing repository... This may take a minute."):
                result = api_post("/load_repo", {"repo_url": repo_url, "force_reclone": False}, timeout=300)
                if result:
                    st.success(f"✅ {result['message']}")
                    st.rerun()
    
    st.divider()
    
    # Chat interface
    st.markdown("**② Ask Questions**")
    
    # Display chat history
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("sources"):
                with st.expander(f"View Sources ({len(msg['sources'])}) · ⏱️ {msg.get('latency_ms', '?')}ms"):
                    for s in msg["sources"]:
                        st.caption(f"📄 `{s['file_path']}` (score: {s['score']})")
    
    # Chat input
    if prompt := st.chat_input("Ask about the codebase...", disabled=not (status and status.get("index_loaded"))):
        # Add user message
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Get AI response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                history_for_api = [
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.chat_history[:-1]
                ]
                result = api_post("/ask", {"question": prompt, "history": history_for_api})
                if result:
                    st.markdown(result["answer"])
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": result["answer"],
                        "sources": result.get("sources", []),
                        "latency_ms": result.get("latency_ms"),
                    })
                    if result.get("sources"):
                        with st.expander(f"View Sources ({len(result['sources'])}) · ⏱️ {result.get('latency_ms', '?')}ms"):
                            for s in result["sources"]:
                                st.caption(f"📄 `{s['file_path']}` (score: {s['score']})")
                else:
                    st.error("Failed to get a response.")
    
    # Clear chat button
    if st.session_state.chat_history:
        if st.button("🗑️ Clear Chat", key="clear_code_chat"):
            st.session_state.chat_history = []
            st.rerun()


# ══════════════════════════════════════════════════════════════
# PAGE: Document Analyser
# ══════════════════════════════════════════════════════════════

elif page == "📄 Documents":
    st.markdown("# 📄 Document Analyser")
    
    # Status bar
    status = get_status()
    if status and status.get("doc_index_loaded"):
        st.success(f"✅ Documents indexed ({status['doc_chunk_count']} chunks)")
    else:
        st.info("No documents loaded yet. Upload files below to begin.")
    
    # File upload
    with st.container(border=True):
        st.markdown("**① Upload & Index Documents** (PDF, DOCX, TXT)")
        
        uploaded_files = st.file_uploader(
            "Drop files here",
            type=["pdf", "docx", "doc", "txt", "md", "csv", "rtf"],
            accept_multiple_files=True,
            label_visibility="collapsed",
        )
        
        if st.button("Upload & Index", type="primary", disabled=not uploaded_files, use_container_width=True):
            with st.spinner("Uploading & indexing documents..."):
                files_payload = [
                    ("files", (f.name, f.getvalue(), f.type or "application/octet-stream"))
                    for f in uploaded_files
                ]
                result = api_post("/upload_doc", files=files_payload, timeout=300)
                if result:
                    st.success(f"✅ {result['message']}")
                    st.rerun()
    
    st.divider()
    
    # Chat interface
    st.markdown("**② Ask Questions**")
    
    for msg in st.session_state.doc_chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("sources"):
                with st.expander(f"View Sources ({len(msg['sources'])}) · ⏱️ {msg.get('latency_ms', '?')}ms"):
                    for s in msg["sources"]:
                        st.caption(f"📄 `{s['file_path']}` (score: {s['score']})")
    
    if prompt := st.chat_input("Ask about the documents...", disabled=not (status and status.get("doc_index_loaded"))):
        st.session_state.doc_chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                history_for_api = [
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.doc_chat_history[:-1]
                ]
                result = api_post("/ask_doc", {"question": prompt, "history": history_for_api})
                if result:
                    st.markdown(result["answer"])
                    st.session_state.doc_chat_history.append({
                        "role": "assistant",
                        "content": result["answer"],
                        "sources": result.get("sources", []),
                        "latency_ms": result.get("latency_ms"),
                    })
                    if result.get("sources"):
                        with st.expander(f"View Sources ({len(result['sources'])}) · ⏱️ {result.get('latency_ms', '?')}ms"):
                            for s in result["sources"]:
                                st.caption(f"📄 `{s['file_path']}` (score: {s['score']})")
                else:
                    st.error("Failed to get a response.")
    
    if st.session_state.doc_chat_history:
        if st.button("🗑️ Clear Chat", key="clear_doc_chat"):
            st.session_state.doc_chat_history = []
            st.rerun()


# ══════════════════════════════════════════════════════════════
# PAGE: Link Analyser
# ══════════════════════════════════════════════════════════════

elif page == "🔗 Links":
    st.markdown("# 🔗 Link Analyser")
    
    # Status bar
    status = get_status()
    if status and status.get("link_index_loaded"):
        st.success(f"✅ Links indexed ({status['link_chunk_count']} chunks)")
    else:
        st.info("No links loaded yet. Enter URLs below to begin.")
    
    # URL input
    with st.container(border=True):
        st.markdown("**① Enter URLs to scrape** (comma-separated)")
        col_input, col_btn = st.columns([4, 1])
        with col_input:
            urls_input = st.text_input(
                "URLs",
                placeholder="https://docs.python.org, https://wikipedia.org/wiki/AI",
                label_visibility="collapsed",
            )
        with col_btn:
            scrape_btn = st.button("Scrape & Index", use_container_width=True, type="primary")
        
        if scrape_btn and urls_input:
            urls = [
                u.strip()
                for u in urls_input.replace("\n", ",").split(",")
                if u.strip() and (u.strip().startswith("http://") or u.strip().startswith("https://"))
            ]
            if not urls:
                st.error("Please enter valid URL(s) starting with http:// or https://")
            else:
                with st.spinner(f"Scraping & indexing {len(urls)} URL(s)..."):
                    result = api_post("/load_link", {"urls": urls}, timeout=300)
                    if result:
                        st.success(f"✅ {result['message']}")
                        st.rerun()
    
    st.divider()
    
    # Chat interface
    st.markdown("**② Ask Questions**")
    
    for msg in st.session_state.link_chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("sources"):
                with st.expander(f"View Sources ({len(msg['sources'])}) · ⏱️ {msg.get('latency_ms', '?')}ms"):
                    for s in msg["sources"]:
                        st.caption(f"🔗 `{s['file_path']}` (score: {s['score']})")
    
    if prompt := st.chat_input("Ask about the web pages...", disabled=not (status and status.get("link_index_loaded"))):
        st.session_state.link_chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                history_for_api = [
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.link_chat_history[:-1]
                ]
                result = api_post("/ask_link", {"question": prompt, "history": history_for_api})
                if result:
                    st.markdown(result["answer"])
                    st.session_state.link_chat_history.append({
                        "role": "assistant",
                        "content": result["answer"],
                        "sources": result.get("sources", []),
                        "latency_ms": result.get("latency_ms"),
                    })
                    if result.get("sources"):
                        with st.expander(f"View Sources ({len(result['sources'])}) · ⏱️ {result.get('latency_ms', '?')}ms"):
                            for s in result["sources"]:
                                st.caption(f"🔗 `{s['file_path']}` (score: {s['score']})")
                else:
                    st.error("Failed to get a response.")
    
    if st.session_state.link_chat_history:
        if st.button("🗑️ Clear Chat", key="clear_link_chat"):
            st.session_state.link_chat_history = []
            st.rerun()


