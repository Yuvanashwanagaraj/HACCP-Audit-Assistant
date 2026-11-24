"""Production-style Streamlit interface for the HACCP RAG audit assistant."""

import os
import re

import streamlit as st
from dotenv import load_dotenv

from rag import AuditError, build_retriever, get_available_models, run_audit


load_dotenv()

st.set_page_config(page_title="HACCP Audit Workspace", page_icon="S", layout="wide", initial_sidebar_state="collapsed")

SCOPE_AREAS = [
    "Hazard analysis",
    "Critical control points (CCPs)",
    "Critical limits",
    "Monitoring procedures",
    "Corrective actions",
    "Record keeping",
    "Verification and validation",
    "Sanitation, GMPs, and SOPs",
]
DEFAULT_SCOPE = SCOPE_AREAS[:7]


st.markdown(
    """
    <style>
      :root { --ink:#102a43; --muted:#627d98; --line:#d9e2ec; --teal:#087f79; --navy:#0b2438; --mint:#e8f6f4; --paper:#ffffff; }
      .stApp { background: #f5f8fb; color: var(--ink); }
      .block-container { max-width: 1280px; padding: 1.35rem 2.25rem 3rem; }
      #MainMenu, footer, header { visibility: hidden; }
      div[data-testid="stVerticalBlockBorderWrapper"] { border: 1px solid var(--line); border-radius: 18px; background: var(--paper); box-shadow: 0 5px 20px rgba(16,42,67,.035); }
      div[data-testid="stVerticalBlockBorderWrapper"] > div { padding: 1.25rem; }
      .topbar { display:flex; align-items:center; justify-content:space-between; margin-bottom: 1.65rem; }
      .brand { display:flex; align-items:center; gap:.7rem; font-weight:760; letter-spacing:-.025em; font-size:1.1rem; color:var(--navy); }
      .brand-mark { display:grid; place-items:center; width:31px; height:31px; border-radius:9px; color:white; background:linear-gradient(135deg,#0b736f,#0a4b63); font-size:.82rem; box-shadow:0 5px 12px rgba(8,127,121,.22); }
      .top-links { display:flex; align-items:center; gap:1.3rem; font-size:.85rem; color:var(--muted); }
      .secure-badge { display:inline-flex; align-items:center; gap:.35rem; padding:.38rem .66rem; border:1px solid #b8e1dc; border-radius:99px; background:#f2fbf9; color:#07635f; font-size:.75rem; font-weight:650; }
      .hero { position:relative; overflow:hidden; padding:2.35rem 2.55rem; border-radius:22px; color:#fff; background:linear-gradient(115deg,#082f49 0%,#075c66 58%,#0a817b 100%); margin-bottom:1.3rem; }
      .hero:after { content:""; position:absolute; width:360px; height:360px; border:1px solid rgba(255,255,255,.15); border-radius:50%; right:-120px; top:-160px; box-shadow: 0 0 0 38px rgba(255,255,255,.035), 0 0 0 78px rgba(255,255,255,.025); }
      .eyebrow { display:inline-block; margin-bottom:.8rem; color:#a9f0e5; font-size:.72rem; font-weight:750; letter-spacing:.13em; text-transform:uppercase; }
      .hero h1 { position:relative; margin:0; max-width:680px; font-size:clamp(2rem,4vw,3.15rem); line-height:1.08; letter-spacing:-.05em; }
      .hero p { position:relative; max-width:620px; margin:.8rem 0 0; font-size:1rem; line-height:1.6; color:#d7f3f0; }
      .hero-stats { position:relative; display:flex; gap:2rem; margin-top:1.5rem; }
      .hero-stat { font-size:.76rem; color:#bee8e2; } .hero-stat b { display:block; color:white; font-size:1rem; margin-bottom:.12rem; }
      .section-kicker { color:var(--teal); font-size:.72rem; font-weight:750; letter-spacing:.12em; text-transform:uppercase; margin-bottom:.25rem; }
      .section-title { color:var(--navy); font-weight:760; font-size:1.25rem; letter-spacing:-.025em; margin:0 0 .25rem; }
      .section-copy { color:var(--muted); font-size:.88rem; line-height:1.55; margin:0 0 1rem; }
      .step { display:flex; gap:.7rem; align-items:flex-start; margin:.9rem 0; }
      .step-num { flex:0 0 24px; display:grid; place-items:center; height:24px; border-radius:50%; background:var(--mint); color:var(--teal); font-size:.72rem; font-weight:800; }
      .step b { display:block; font-size:.86rem; color:var(--ink); margin-bottom:.08rem; } .step span { color:var(--muted); font-size:.78rem; line-height:1.35; }
      .ready-card { padding:.8rem .85rem; border-radius:11px; background:#f7fafc; border:1px solid var(--line); }
      .ready-card strong { color:var(--navy); font-size:.83rem; } .ready-card p { margin:.18rem 0 0; color:var(--muted); font-size:.77rem; line-height:1.4; }
      .file-card { padding:.6rem .1rem .1rem; }
      .file-card h3 { color:var(--navy); font-size:.95rem; margin:0; } .file-card p { color:var(--muted); font-size:.79rem; margin:.28rem 0 .5rem; min-height:2.2rem; }
      div[data-testid="stFileUploader"] { border: 1.5px dashed #b8c7d5; border-radius: 12px; padding:.3rem .55rem; background:#fbfdff; }
      div[data-testid="stFileUploader"] section { padding:.45rem 0; }
      div[data-testid="stFileUploader"] button { border-radius:8px; border-color:#aebfce; color:#284b63; font-size:.78rem; }
      .stTextArea textarea { border-radius:11px; border-color:#c4d0db; background:#fbfdff; line-height:1.55; }
      .stTextArea textarea:focus { border-color:#0b8f87; box-shadow:0 0 0 1px #0b8f87; }
      .stSelectbox > div > div, .stMultiSelect > div > div { border-radius:10px; }
      .stButton > button, .stDownloadButton > button { border-radius:10px; font-weight:700; min-height:2.7rem; transition:all .18s ease; }
      .stButton > button[kind="primary"] { background:linear-gradient(100deg,#087f79,#0b6775); border:0; box-shadow:0 7px 15px rgba(8,127,121,.18); }
      .stButton > button[kind="primary"]:hover { transform:translateY(-1px); background:linear-gradient(100deg,#066c68,#095a68); }
      .metric-card { padding:.75rem .85rem; border-left:3px solid #13a59c; background:#f7fbfb; border-radius:8px; } 
      .metric-label { color:var(--muted); font-size:.7rem; font-weight:700; text-transform:uppercase; letter-spacing:.08em; } .metric-value { color:var(--navy); font-size:1.3rem; font-weight:780; margin-top:.12rem; }
      .result-intro { padding:1rem 1.05rem; border-radius:12px; background:#eef8f7; border:1px solid #cde9e5; margin:.6rem 0 1.1rem; color:#164e54; font-size:.88rem; }
      .report-body table { width:100%; font-size:.84rem; border-collapse:collapse; } .report-body th { background:#eff6f8; color:#284b63; } .report-body th,.report-body td { border:1px solid #d9e2ec; padding:.55rem; vertical-align:top; }
      .report-body h2 { color:var(--navy); font-size:1.12rem; margin:1.35rem 0 .55rem; } .report-body h3 { color:#284b63; font-size:1rem; }
      @media(max-width:800px) { .block-container { padding:1rem; } .hero { padding:1.7rem 1.35rem; } .top-links { display:none; } .hero-stats { gap:1rem; } }
    </style>
    """,
    unsafe_allow_html=True,
)


def is_configured() -> bool:
    return bool(os.getenv("GROQ_API_KEY"))


def priority_count(report: str, priority: str) -> int:
    """Count only priority rows inside the Findings table."""
    pattern = rf"\|\s*\d+\s*\|\s*{re.escape(priority)}\s*\|"
    return len(re.findall(pattern, report, flags=re.IGNORECASE))

def document_state(uploaded_file, fallback: str) -> str:
    if not uploaded_file:
        return fallback
    size_kb = uploaded_file.size / 1024
    return f"{uploaded_file.name} - {size_kb:.0f} KB"


st.markdown(
    """
    <div class="topbar">
      <div class="brand"><span class="brand-mark">S</span>SafeLine <span style="color:#78909f;font-weight:600">/ Audit workspace</span></div>
      <div class="top-links"><span>Policy-grounded analysis</span><span class="secure-badge">Local document handling</span></div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown(
    """
    <section class="hero">
      <div class="eyebrow">Food safety intelligence</div>
      <h1>Turn HACCP rules into clear, defensible audit feedback.</h1>
      <p>Upload the standard and the plan you want assessed. SafeLine retrieves the right evidence, identifies the gaps, and gives your team practical next actions.</p>
      <div class="hero-stats"><div class="hero-stat"><b>Evidence-led</b>Every finding is source-cited</div><div class="hero-stat"><b>Risk-prioritized</b>Focus on what needs action first</div><div class="hero-stat"><b>Built for review</b>Exportable audit record</div></div>
    </section>
    """,
    unsafe_allow_html=True,
)

main_col, settings_col = st.columns([1.68, 0.82], gap="large")

with main_col:
    with st.container(border=True):
        st.markdown('<div class="section-kicker">New assessment</div><h2 class="section-title">Build your audit</h2><p class="section-copy">Use a regulatory guide, customer standard, or internal policy as the source of truth.</p>', unsafe_allow_html=True)
        upload_col, plan_col = st.columns(2, gap="medium")
        with upload_col:
            st.markdown('<div class="file-card"><h3>01 - Governing rules</h3><p>The standard, regulation, or HACCP guide that defines what good looks like.</p></div>', unsafe_allow_html=True)
            rules_file = st.file_uploader("Rules document", type=["pdf", "docx", "txt", "md"], key="rules", label_visibility="collapsed")
            st.caption(document_state(rules_file, "Accepted: PDF, DOCX, TXT, MD"))
        with plan_col:
            st.markdown('<div class="file-card"><h3>02 - Document to assess</h3><p>The HACCP plan, SOP, inspection report, or process document under review.</p></div>', unsafe_allow_html=True)
            plan_file = st.file_uploader("Audit document", type=["pdf", "docx", "txt", "md"], key="plan", label_visibility="collapsed")
            st.caption(document_state(plan_file, "Accepted: PDF, DOCX, TXT, MD"))

        st.markdown("<br>", unsafe_allow_html=True)
        question = st.text_area(
            "Audit brief",
            placeholder="Example: Assess this HACCP plan against the uploaded rules. Identify food-safety gaps, prioritise risk, and tell me what must be corrected before approval.",
            height=125,
            help="A specific request gives the audit more useful context.",
        )
        st.caption("Tip: Ask for a pre-approval review, CCP verification, documentation gaps, or corrective-action priorities.")

@st.cache_data(ttl=3600)
def load_groq_models():
    return get_available_models()


with settings_col:
    with st.container(border=True):
        st.markdown('<div class="section-kicker">Audit controls</div><h2 class="section-title">Set the lens</h2><p class="section-copy">Choose the areas your review should emphasize.</p>', unsafe_allow_html=True)
        audit_scope = st.multiselect("Focus areas", SCOPE_AREAS, default=DEFAULT_SCOPE)
        with st.expander("Advanced settings"):
            available_models = load_groq_models()
            model_name = st.selectbox("Groq model", available_models, help="The model used for generating audit findings.")
            retrieval_count = st.slider("Rule passages to retrieve", 4, 12, 7, help="More passages can improve coverage but may make the result less focused.")
        if "model_name" not in locals():
            available_models = load_groq_models()
            model_name, retrieval_count = available_models[0], 7
        st.markdown("<br>", unsafe_allow_html=True)
        if is_configured():
            st.markdown('<div class="ready-card"><strong>System ready</strong><p>Groq access is configured. Your API key is not exposed in this workspace.</p></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="ready-card"><strong>API key required</strong><p>Add GROQ_API_KEY to your local .env file to run an assessment.</p></div>', unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown('<div class="section-kicker">Your workflow</div><h2 class="section-title">A focused review in minutes</h2>', unsafe_allow_html=True)
        st.markdown('<div class="step"><span class="step-num">1</span><div><b>Attach evidence</b><span>Provide the rules and the document being assessed.</span></div></div><div class="step"><span class="step-num">2</span><div><b>Retrieve the relevant controls</b><span>Semantic search identifies the most relevant clauses.</span></div></div><div class="step"><span class="step-num">3</span><div><b>Review actions, not noise</b><span>Receive cited gaps and practical corrective actions.</span></div></div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)
run_col, note_col = st.columns([0.56, 1.44], vertical_alignment="center")
with run_col:
    run_audit_clicked = st.button("Run audit", type="primary", use_container_width=True)
with note_col:
    st.caption("The assistant uses the uploaded rules as the source of truth. Review all findings with a qualified food-safety professional before operational use.")

if run_audit_clicked:
    if not is_configured():
        st.error("Groq is not configured. Copy `.env.example` to `.env`, add `GROQ_API_KEY`, and restart the app.")
    elif not rules_file or not plan_file:
        st.error("Attach both the governing rules and the document to assess before starting the audit.")
    elif not question.strip():
        st.error("Add an audit brief so the assistant knows what you need reviewed.")
    elif not audit_scope:
        st.error("Choose at least one focus area.")
    else:
        try:
            with st.status("Preparing your evidence-based audit...", expanded=True) as status:
                st.write("Reading the governing rules and indexing relevant controls.")
                retriever, rule_count = build_retriever(rules_file.name, rules_file.getvalue(), retrieval_count)
                st.write("Comparing the submitted document against retrieved evidence.")
                result = run_audit(
                    retriever=retriever,
                    plan_filename=plan_file.name,
                    plan_bytes=plan_file.getvalue(),
                    user_question=question,
                    scope=audit_scope,
                    model_name=model_name,
                )
                status.update(label="Audit ready for review", state="complete", expanded=False)
            st.session_state.audit_result = result
            st.session_state.rule_count = rule_count
        except AuditError as error:
            st.error(str(error))
        except Exception as error:
            st.error(f"The audit could not be completed: {error}")

if "audit_result" in st.session_state:
    result = st.session_state.audit_result
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="section-kicker">Audit output</div><h2 class="section-title">Decision-ready findings</h2><div class="result-intro">This result is grounded in the rule passages shown below. Use the evidence panel to verify each recommendation before acting.</div>', unsafe_allow_html=True)
    critical, high, medium = (priority_count(result["report"], level) for level in ("Critical", "High", "Medium"))
    metric_cols = st.columns(4)
    metrics = [("Indexed rule passages", str(st.session_state.rule_count)), ("Critical signals", str(critical)), ("High-priority signals", str(high)), ("Medium-priority signals", str(medium))]
    for col, (label, value) in zip(metric_cols, metrics):
        with col:
            st.markdown(f'<div class="metric-card"><div class="metric-label">{label}</div><div class="metric-value">{value}</div></div>', unsafe_allow_html=True)
    report_tab, evidence_tab = st.tabs(["Audit report", "Source evidence"])
    with report_tab:
        with st.container(border=True):
            st.markdown(result["report"])
        st.download_button("Download audit report (.md)", data=result["markdown"], file_name="haccp_audit_report.md", mime="text/markdown")
    with evidence_tab:
        st.caption("These are the passages retrieved from the uploaded rules for this assessment.")
        for index, source in enumerate(result["sources"], start=1):
            page = source["page"]
            label = f"Evidence {index} - {source['source']} - page {page}" if page else f"Evidence {index} - {source['source']}"
            with st.expander(label):
                st.write(source["excerpt"])

st.markdown('<p style="text-align:center;color:#829ab1;font-size:.76rem;margin-top:2.8rem">SafeLine is decision support, not a substitute for a qualified food-safety professional or regulatory authority.</p>', unsafe_allow_html=True)
