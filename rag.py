import os
from typing import TypedDict, List, Optional, cast

from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langgraph.graph import StateGraph, END
import nltk

# --- FlowState and Global Variables (no change from your last correct version) ---
class FlowState(TypedDict):
    user_api_key: str
    user_profile_content: str
    user_persona_description: str
    incoming_message: str
    chat_history: List[str]
    retrieved_context: str
    generated_response: str
    error_message: Optional[str]
    _raw_retrieved_docs_content: Optional[List[str]]

vector_store: Optional[Chroma] = None
llm: Optional[ChatGoogleGenerativeAI] = None
embeddings_model: Optional[GoogleGenerativeAIEmbeddings] = None
app_graph: Optional[StateGraph] = None
_global_current_api_key: Optional[str] = None # Module-level global
_global_current_profile_hash: Optional[int] = None # Module-level global


# --- get_vector_store (no change from your last correct version) ---
def get_vector_store(user_profile_content: str, api_key: str, force_recreate: bool = False) -> Optional[Chroma]:
    global vector_store, embeddings_model # These are modified directly
    # ... (rest of the function as it was)
    # print(f"RAG_MODULE_DEBUG (get_vector_store): Called. API Key: {api_key[:5]}..., force_recreate={force_recreate}")
    if not api_key:
        raise ValueError("Google API Key is required for get_vector_store.")
    current_embeddings_api_key_attr = getattr(embeddings_model, 'google_api_key', None) if embeddings_model else None
    if embeddings_model is None or force_recreate or (current_embeddings_api_key_attr != api_key):
        try:
            embeddings_model = GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=api_key)
            setattr(embeddings_model, 'google_api_key', api_key)
        except Exception as e:
            embeddings_model = None
            raise ValueError(f"Failed to initialize embeddings. Error: {e}")
    current_profile_hash = hash(user_profile_content)
    if force_recreate or vector_store is None or \
       getattr(vector_store, '_profile_hash', None) != current_profile_hash or \
       getattr(vector_store, '_embedding_api_key', None) != api_key:
        if not user_profile_content.strip():
            vector_store = None
            return None
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50, length_function=len, is_separator_regex=False)
        profile_chunks = text_splitter.split_text(user_profile_content)
        if not profile_chunks:
            vector_store = None
            return None
        documents = [Document(page_content=chunk) for chunk in profile_chunks]
        if embeddings_model is None:
            raise ValueError("Embeddings model somehow became None before Chroma.from_documents call.")
        try:
            new_vector_store = Chroma.from_documents(documents=documents, embedding=embeddings_model)
            vector_store = new_vector_store
            setattr(vector_store, '_profile_hash', current_profile_hash)
            setattr(vector_store, '_embedding_api_key', api_key)
        except Exception as e:
            vector_store = None
            raise
    return vector_store

# --- initialize_models_node (no significant change from your last correct version) ---
def initialize_models_node(state: FlowState) -> FlowState:
    # This function correctly uses and updates module-level globals:
    # llm, app_graph, embeddings_model, vector_store,
    # _global_current_api_key, _global_current_profile_hash
    global llm, app_graph, embeddings_model, vector_store 
    global _global_current_api_key, _global_current_profile_hash

    api_key = state.get("user_api_key")
    user_profile_content = state.get("user_profile_content", "")
    if not api_key: return {**state, "error_message": "Google API Key is missing."}
    force_reinit_major_components = False
    if llm is None or _global_current_api_key != api_key: # Compare with module-level global
        # print(f"RAG_MODULE (initialize_models_node): LLM or API key changed...")
        force_reinit_major_components = True
    try:
        if force_reinit_major_components:
            # print(f"RAG_MODULE (initialize_models_node): Initializing/Re-initializing LLM ...")
            llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest", google_api_key=api_key, temperature=0.7)
            _global_current_api_key = api_key # Update module-level global
        # print(f"RAG_MODULE (initialize_models_node): Calling get_vector_store...")
        get_vector_store(user_profile_content, api_key, force_recreate=force_reinit_major_components)
        if vector_store and hasattr(vector_store, '_profile_hash'):
            _global_current_profile_hash = getattr(vector_store, '_profile_hash') # Update module-level global
        elif not user_profile_content.strip():
            _global_current_profile_hash = hash("")
        if app_graph is None or force_reinit_major_components:
            # print("RAG_MODULE (initialize_models_node): Compiling/Re-compiling LangGraph ...")
            workflow = StateGraph(FlowState) # ... (rest of graph compilation)
            workflow.add_node("retrieve_context_internal", retrieve_context_node)
            workflow.add_node("generate_response_internal", generate_response_node)
            workflow.set_entry_point("retrieve_context_internal")
            workflow.add_edge("retrieve_context_internal", "generate_response_internal")
            workflow.add_edge("generate_response_internal", END)
            app_graph = workflow.compile()
        # print("RAG_MODULE (initialize_models_node): Initialization complete.")
        return {**state, "error_message": None}
    except Exception as e:
        # print(f"RAG_MODULE (initialize_models_node): ERROR during initialization: {e}")
        llm,app_graph,vector_store,embeddings_model = None,None,None,None
        _global_current_api_key,_global_current_profile_hash = None,None
        return {**state, "error_message": f"Failed to initialize models: {str(e)}"}


# --- retrieve_context_node, generate_response_node, run_rag_pipeline (no changes from your last correct versions) ---
def retrieve_context_node(state: FlowState) -> FlowState:
    # ... (as before) ...
    global vector_store
    if state.get("error_message"): return state
    user_profile_content = state.get("user_profile_content", "")
    api_key = state.get("user_api_key", "")
    incoming_message = state.get("incoming_message", "")
    if not user_profile_content.strip():
        return {**state, "retrieved_context": "User profile is not provided.", "_raw_retrieved_docs_content": []}
    try:
        current_vector_store = get_vector_store(user_profile_content, api_key, force_recreate=False)
        if current_vector_store is None:
            return {**state, "retrieved_context": "Vector store not available for retrieval.", "_raw_retrieved_docs_content": []}
        retriever = current_vector_store.as_retriever(search_kwargs={"k": 3})
        retrieved_docs: List[Document] = retriever.invoke(incoming_message)
        raw_docs_content = [doc.page_content for doc in retrieved_docs]
        retrieved_context_str = "\n\n".join(raw_docs_content)
        # print(f"RAG_MODULE_DEBUG (retrieve_context_node): Raw docs content being put into state: {raw_docs_content}")
        if not retrieved_context_str: retrieved_context_str = "No specific relevant information found."
        return {**state, "retrieved_context": retrieved_context_str, "_raw_retrieved_docs_content": raw_docs_content}
    except Exception as e:
        return {**state, "error_message": f"Error retrieving context: {str(e)}", "_raw_retrieved_docs_content": []}

def generate_response_node(state: FlowState) -> FlowState:
    # ... (as before) ...
    global llm
    if state.get("error_message"): return state
    if llm is None: return {**state, "error_message": "LLM not initialized."}
    user_persona = state.get("user_persona_description", "A helpful assistant.")
    retrieved_context = state.get("retrieved_context", "No context provided.")
    incoming_message = state.get("incoming_message", "")
    chat_history_list = state.get("chat_history", [])
    chat_history_str = "\n".join(chat_history_list[-10:])
    prompt_template_str = ChatPromptTemplate.from_messages([
        ("system", "You are 'Flow', an intelligent AI assistant ... Keep the reply concise and human-like.\n\nUSER'S PERSONA & STYLE:\n{user_persona}\n\nRELEVANT INFORMATION FROM USER'S PROFILE (use this to craft the reply):\n{retrieved_context}\n\nRECENT CHAT HISTORY (for overall context, if available):\n{chat_history}"),
        ("human", "Incoming message (potentially a burst combined): {incoming_message}"),
        ("ai", "Generated reply as the user:")])
    chain = prompt_template_str | llm | StrOutputParser()
    try:
        response = chain.invoke({"user_persona": user_persona, "retrieved_context": retrieved_context, "chat_history": chat_history_str, "incoming_message": incoming_message})
        return {**state, "generated_response": response}
    except Exception as e:
        err_str = str(e).lower()
        if "api key" in err_str or "permission" in err_str or "quota" in err_str: return {**state, "error_message": f"LLM API Error: {str(e)}."}
        return {**state, "error_message": f"Error generating response: {str(e)}"}

def run_rag_pipeline(api_key: str, profile_content: str, persona_description: str, combined_message: str, chat_history_for_rag: List[str]) -> dict:
    # ... (as before) ...
    global app_graph
    if not api_key: return {"error_message": "API Key is required."}
    initial_flow_state = FlowState(user_api_key=api_key, user_profile_content=profile_content, user_persona_description=persona_description, incoming_message=combined_message, chat_history=chat_history_for_rag, retrieved_context="", generated_response="", error_message=None, _raw_retrieved_docs_content=None)
    try:
        current_state_after_init = initialize_models_node(initial_flow_state)
        if current_state_after_init.get("error_message"): return cast(dict, current_state_after_init)
        if app_graph is None: return {"error_message": "Critical internal error: LangGraph application not compiled."}
        final_state = app_graph.invoke(current_state_after_init)
        # raw_content_from_final_state = final_state.get("_raw_retrieved_docs_content")
        # print(f"RAG_MODULE_DEBUG (run_rag_pipeline): final_state from graph invoke: {final_state.keys()}")
        # print(f"RAG_MODULE_DEBUG (run_rag_pipeline): _raw_retrieved_docs_content from final_state: {raw_content_from_final_state}")
        return cast(dict, final_state)
    except Exception as e:
        return {"error_message": f"Critical RAG pipeline failure: {str(e)}", "generated_response": ""}


# --- REVISED FUNCTION: Format response into a burst using LLM ---
def format_response_as_burst_by_llm(api_key: str,
                                   full_response_content: str,
                                   persona_description: str,
                                   original_user_query: str) -> List[str]:
    global llm, _global_current_api_key # Added _global_current_api_key for check

    # print(f"RAG_MODULE_FORMAT_BURST: Entered. Original full response length: {len(full_response_content)}")
    # print(f"RAG_MODULE_FORMAT_BURST: Full response to format: '{full_response_content}'")

    if not full_response_content.strip():
        # print("RAG_MODULE_FORMAT_BURST: Full response is empty, returning empty list.")
        return []

    # Check LLM initialization and API key consistency
    if llm is None or _global_current_api_key != api_key:
        # print(f"RAG_MODULE_FORMAT_BURST: LLM is None or API key mismatch (LLM key: {_global_current_api_key}, Expected key: {api_key}). Calling full initialization.")
        temp_init_state = FlowState(user_api_key=api_key, user_profile_content="", 
                                   user_persona_description=persona_description, # Pass current persona
                                   incoming_message=original_user_query, # Pass current query
                                   chat_history=[], retrieved_context="",
                                   generated_response="", error_message=None, _raw_retrieved_docs_content=None)
        init_result = initialize_models_node(temp_init_state) # This updates global llm and _global_current_api_key
        if init_result.get("error_message") or llm is None:
            print(f"RAG_MODULE_FORMAT_BURST: LLM re-initialization failed: {init_result.get('error_message')}. Returning original response.")
            return [full_response_content]
        # print("RAG_MODULE_FORMAT_BURST: LLM (re-)initialized successfully for formatting.")

    # Define the prompt template with explicit placeholders
    # DO NOT use f-strings to embed variables directly into the template strings here
    prompt_template = ChatPromptTemplate.from_messages([
        ("system",
         """You are an AI assistant that reformats a single text response into a series of 1 to 4 short, natural-sounding message bubbles, like a human texting.
The original response was generated by 'Flow' on behalf of a busy user with the following persona: '{input_persona}'.
Flow was responding to the query: "{input_original_query}"
The complete thought Flow wants to convey is: "{input_full_thought}"

Your ONLY task is to break the "complete thought" into 1-4 short message bubbles.
- Each bubble should be concise.
- Preserve the original meaning, tone, and persona.
- **Crucially, you MUST separate each intended message bubble with the exact separator: ||NEXT_MESSAGE||**
- Do not add any text before the first bubble or after the last one. Just the bubbles and separators.
- If the "complete thought" is already very short (e.g., one or two short sentences, less than ~15 words), output it as a single bubble WITHOUT any separators.
- Do not refuse, explain, or apologize. Only provide the formatted response.

Example 1 (Needs splitting):
Complete thought: "Hey, I'm super busy with exams right now, but I can probably meet on Saturday morning before 11 AM if that works for you. Let me know!"
Your output: Hey, I'm super busy with exams right now!||NEXT_MESSAGE||But I can probably do Sat morning before 11?||NEXT_MESSAGE||If that works for you, let me know!

Example 2 (Already short):
Complete thought: "Okay, sounds good."
Your output: Okay, sounds good.

Example 3 (Needs splitting):
Complete thought: "I saw your message about the project. I'm really swamped this week with the Athena report and my conference prep, but I definitely want to sync up. Could we aim for early next week, maybe Monday or Tuesday afternoon? That would give me some breathing room."
Your output: Saw your message about the project!||NEXT_MESSAGE||Definitely want to sync up.||NEXT_MESSAGE||I'm super swamped this week with Athena & conference prep tho. 😅||NEXT_MESSAGE||Could we aim for early next week, like Mon/Tues afternoon?
"""),
        # No explicit "human" message needed if all info is in system prompt for this specific task
    ])

    chain = prompt_template | llm | StrOutputParser()
    
    try:
        # print(f"RAG_MODULE_FORMAT_BURST: Calling LLM for formatting. Full thought: '{full_response_content[:100]}...'")
        
        # Provide values for the placeholders defined in the prompt template
        input_data_for_formatter = {
            "input_persona": persona_description,
            "input_original_query": original_user_query,
            "input_full_thought": full_response_content
        }
        formatted_string = chain.invoke(input_data_for_formatter) # <<< This is the standard LCEL way
        
        # print(f"RAG_MODULE_FORMAT_BURST: LLM output for formatting: '{formatted_string}'")
        
        parts = []
        if "||NEXT_MESSAGE||" in formatted_string:
            parts = [msg.strip() for msg in formatted_string.split("||NEXT_MESSAGE||") if msg.strip()]
        
        if not parts: # Fallback logic
            if len(full_response_content) > 60 and ('.' in full_response_content or '?' in full_response_content or '!' in full_response_content) :
                try:
                    try: nltk.data.find('tokenizers/punkt')
                    except nltk.downloader.DownloadError: nltk.download('punkt', quiet=True)
                    sentences = nltk.sent_tokenize(full_response_content)
                    if 1 < len(sentences) <= 4:
                        parts = [s.strip() for s in sentences if s.strip()]
                except Exception as e_nltk:
                    print(f"RAG_MODULE_FORMAT_BURST: NLTK fallback error: {e_nltk}.")
            if not parts and full_response_content.strip():
                 parts = [full_response_content.strip()]
        return parts if parts else []

    except Exception as e:
        print(f"RAG_MODULE_FORMAT_BURST: General error formatting response: {e}")
        # Check if the error is the specific "contents not specified" to provide more insight
        if "contents is not specified" in str(e).lower():
            print("RAG_MODULE_FORMAT_BURST: DEBUG - The 'contents not specified' error occurred. Input to invoke was:", input_data_for_formatter)
        return [full_response_content] if full_response_content.strip() else []
