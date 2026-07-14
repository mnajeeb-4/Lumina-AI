import os
import tempfile
from typing import List, Optional
import streamlit as st
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.chains import ConversationalRetrievalChain
from langchain_openai import ChatOpenAI
from langchain.memory import ConversationBufferMemory
from modules.database import add_knowledge_entry, update_bot_vector_path

VECTOR_STORE_ROOT = "data/faiss_index"

def get_openai_api_key() -> str:
    """Retrieve API key from Streamlit secrets or session state (local fallback)."""
    # First check Streamlit secrets
    if "OPENAI_API_KEY" in st.secrets:
        return st.secrets["OPENAI_API_KEY"]
    # Fallback: session state from sidebar input (set in app.py)
    if "api_key" in st.session_state and st.session_state["api_key"]:
        return st.session_state["api_key"]
    raise ValueError("OpenAI API key not found. Please set it in secrets.toml or enter it in the sidebar.")

def load_document(file) -> List:
    """Load a PDF or TXT file and return a list of Document objects."""
    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=file.name) as tmp:
        tmp.write(file.getvalue())
        tmp_path = tmp.name

    try:
        if file.name.lower().endswith(".pdf"):
            loader = PyPDFLoader(tmp_path)
        else:
            loader = TextLoader(tmp_path, encoding='utf-8')
        docs = loader.load()
    finally:
        os.unlink(tmp_path)  # clean up
    return docs

def chunk_documents(docs: List, chunk_size: int = 1000, chunk_overlap: int = 150) -> List:
    """Split documents into manageable chunks."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", " ", ""]
    )
    return splitter.split_documents(docs)

def create_vector_store(chunks: List, api_key: str, bot_id: int) -> str:
    """Create a FAISS vector store from chunks and persist it locally."""
    embeddings = OpenAIEmbeddings(openai_api_key=api_key)
    vector_store = FAISS.from_documents(chunks, embeddings)

    # Persist to a bot-specific directory
    store_dir = os.path.join(VECTOR_STORE_ROOT, f"bot_{bot_id}")
    os.makedirs(store_dir, exist_ok=True)
    vector_store.save_local(store_dir)
    return store_dir

def load_vector_store(bot_id: int, api_key: str) -> Optional[FAISS]:
    """Load a persisted FAISS vector store for a bot."""
    store_dir = os.path.join(VECTOR_STORE_ROOT, f"bot_{bot_id}")
    if not os.path.exists(store_dir):
        return None
    embeddings = OpenAIEmbeddings(openai_api_key=api_key)
    return FAISS.load_local(store_dir, embeddings, allow_dangerous_deserialization=True)

def get_conversation_chain(vector_store: FAISS, system_prompt: str, api_key: str):
    """Build a ConversationalRetrievalChain with memory."""
    llm = ChatOpenAI(
        openai_api_key=api_key,
        model="gpt-4o-mini",  # fast, cost-effective for support
        temperature=0.3
    )
    memory = ConversationBufferMemory(
        memory_key="chat_history",
        return_messages=True,
        output_key="answer"
    )
    # Inject system prompt into the condense question prompt to maintain persona
    from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder, SystemMessagePromptTemplate
    # Customize the condense question prompt
    condense_prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(
            "Given the following conversation and a follow up question, rephrase the follow up question to be a standalone question.\n"
            "You are an AI with the persona: " + system_prompt
        ),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{question}"),
    ])
    # Build the chain
    chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=vector_store.as_retriever(search_kwargs={"k": 3}),
        memory=memory,
        condense_question_prompt=condense_prompt,
        return_source_documents=False,
        verbose=False
    )
    return chain

def train_bot(bot_id: int, files, system_prompt: str) -> bool:
    """
    Ingest uploaded files, create vector store, and update bot status.
    Returns True if successful.
    """
    api_key = get_openai_api_key()
    all_chunks = []
    for file in files:
        docs = load_document(file)
        chunks = chunk_documents(docs)
        all_chunks.extend(chunks)
        # Save knowledge base entry
        preview = docs[0].page_content[:200] if docs else ""
        add_knowledge_entry(bot_id, file.name, preview)

    if not all_chunks:
        return False

    path = create_vector_store(all_chunks, api_key, bot_id)
    update_bot_vector_path(bot_id, path)
    return True
