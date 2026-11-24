"""Document loading, retrieval, and grounded Groq audit generation."""

from __future__ import annotations

import io
import os
import re
import tempfile
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv
from langchain_community.document_loaders import Docx2txtLoader, PyPDFLoader, TextLoader

load_dotenv()
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter


SUPPORTED_SUFFIXES = {".pdf", ".docx", ".txt", ".md"}


def get_available_models() -> list[str]:
    """Retrieve available chat models for the current Groq API key, falling back gracefully."""
    api_key = os.getenv("GROQ_API_KEY")
    fallback = ["qwen/qwen3.8-27b", "llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
    if not api_key:
        return fallback

    try:
        from groq import Groq
        client = Groq(api_key=api_key, timeout=3.0)
        models_data = client.models.list().data
        chat_models = []
        for m in models_data:
            mid = m.id.lower()
            if any(x in mid for x in ["whisper", "guard", "audio", "orpheus"]):
                continue
            chat_models.append(m.id)
        if chat_models:
            preferred_order = ["qwen/qwen3.8-27b", "llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
            sorted_models = [m for m in preferred_order if m in chat_models]
            other_models = [m for m in chat_models if m not in preferred_order]
            return sorted_models + other_models
    except Exception:
        pass
    return fallback


class AuditError(Exception):
    """An error which can be shown directly in the UI."""


def _save_upload(filename: str, data: bytes) -> Path:
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise AuditError("Unsupported file type. Upload a PDF, DOCX, TXT, or Markdown file.")
    directory = Path(tempfile.mkdtemp(prefix="haccp_audit_"))
    path = directory / f"upload{suffix}"
    path.write_bytes(data)
    return path


def load_uploaded_document(filename: str, data: bytes) -> list[Document]:
    """Load an uploaded file while retaining its page/source metadata."""
    path = _save_upload(filename, data)
    suffix = path.suffix
    try:
        if suffix == ".pdf":
            documents = PyPDFLoader(str(path)).load()
        elif suffix == ".docx":
            documents = Docx2txtLoader(str(path)).load()
        else:
            documents = TextLoader(str(path), encoding="utf-8", autodetect_encoding=True).load()
    except Exception as error:
        raise AuditError(f"Could not read '{filename}'. Make sure the file is not encrypted or corrupted.") from error

    cleaned = []
    for document in documents:
        text = re.sub(r"\s+", " ", document.page_content).strip()
        if text:
            document.page_content = text
            document.metadata["source"] = filename
            cleaned.append(document)
    if not cleaned:
        raise AuditError(f"No readable text was found in '{filename}'.")
    return cleaned


def build_retriever(filename: str, data: bytes, retrieval_count: int):
    documents = load_uploaded_document(filename, data)
    splitter = RecursiveCharacterTextSplitter(chunk_size=900, chunk_overlap=150)
    chunks = splitter.split_documents(documents)
    if not chunks:
        raise AuditError("The rules document did not contain text that could be indexed.")

    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    vector_store = FAISS.from_documents(chunks, embeddings)
    return vector_store.as_retriever(search_kwargs={"k": min(retrieval_count, len(chunks))}), len(chunks)


AUDIT_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are an expert HACCP and Food Safety Audit Assistant.

Compare the submitted HACCP plan with ONLY the retrieved governing rule evidence.

FINAL STATUS RULES:

1. COMPLIANT
- All critical requirements are satisfied.
- No Critical or High gaps.
- Documentation is complete.

2. NON-COMPLIANT
- One or more Critical food safety violations exist.
- Critical limits are breached or mandatory corrective actions are missing.

3. REQUIRES REVIEW
- No confirmed critical violation exists.
- Supporting evidence is incomplete, so human review is required.

Return Markdown with exactly these sections:

## Executive assessment
Include:
Status: COMPLIANT / NON-COMPLIANT / REQUIRES REVIEW
Compliance Score
Overall Risk

## Findings

Use columns:
ID | Priority | Gap or Strength | Why it matters | Corrective Action | Rule Evidence

## Missing evidence to request

If nothing is missing, write:
- None. Documentation is complete.

## Recommended next steps

Important:
- Missing documents only → REQUIRES REVIEW
- Critical safety violations → NON-COMPLIANT
- Everything satisfied → COMPLIANT
""",
        ),
        (
            "human",
            """AUDIT FOCUS AREAS:
{scope}

USER REQUEST:
{question}

SUBMITTED DOCUMENT ({plan_filename}):
{plan_text}

RETRIEVED RULE EVIDENCE:
{rule_context}
""",
        ),
    ]
)


def _format_rule_context(documents: Iterable[Document]) -> tuple[str, list[dict]]:
    blocks, sources = [], []
    seen = set()
    for document in documents:
        page_number = document.metadata.get("page")
        page = str(page_number + 1) if isinstance(page_number, int) else None
        source = document.metadata.get("source", "Rules document")
        marker = f"[Rule p. {page}]" if page else "[Rule section]"
        excerpt = document.page_content
        blocks.append(f"{marker}\n{excerpt}")
        signature = (source, page, excerpt[:80])
        if signature not in seen:
            sources.append({"source": source, "page": page, "excerpt": excerpt})
            seen.add(signature)
    return "\n\n---\n\n".join(blocks), sources


def run_audit(*, retriever, plan_filename: str, plan_bytes: bytes, user_question: str, scope: list[str], model_name: str):
    if not os.getenv("GROQ_API_KEY"):
        raise AuditError("GROQ_API_KEY is missing. Add it to your .env file and try again.")

    plan_documents = load_uploaded_document(plan_filename, plan_bytes)
    plan_text = "\n\n".join(document.page_content for document in plan_documents)
    # Prevent massive plans from overflowing the model while keeping the beginning and end context.
    if len(plan_text) > 30000:
        plan_text = plan_text[:24000] + "\n\n[Middle of document omitted for length]\n\n" + plan_text[-6000:]

    query = f"{user_question}\nFocus: {', '.join(scope)}"
    retrieved = retriever.invoke(query)
    rule_context, sources = _format_rule_context(retrieved)
    model = ChatGroq(model=model_name, temperature=0, max_tokens=900)
    chain = AUDIT_PROMPT | model
    response = chain.invoke(
        {
            "scope": ", ".join(scope),
            "question": user_question,
            "plan_filename": plan_filename,
            "plan_text": plan_text,
            "rule_context": rule_context,
        }
    )
    report = response.content
    markdown = f"# HACCP Audit Report\n\n{report}\n\n## Retrieved rule evidence\n"
    for source in sources:
        label = f"{source['source']} - page {source['page']}" if source["page"] else source["source"]
        markdown += f"\n### {label}\n{source['excerpt']}\n"
    return {"report": report, "sources": sources, "markdown": markdown}
