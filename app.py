# app.py
from flask import Flask, render_template, request, jsonify, session
import threading
import time
from collections import deque
import secrets
from typing import List # Added for type hint

# Import your RAG logic module
import rag
import os

app = Flask(__name__)
app.secret_key = secrets.token_hex(16) # Make sure this is strong for production

# --- Session-based Global-like Variables ---
# We will store these in the Flask session object where appropriate,
# or handle them carefully if they truly need to be shared across threads
# (though for session-specific data, Flask session is better).

# message_burst_buffer = {} # Now session-specific
# burst_timers = {}         # Now session-specific
# _pending_bot_responses = {}# Now session-specific
# _processing_locks = {}    # Now session-specific, one lock per session

BURST_DELAY_SECONDS = 5 # Keep this global

# --- Helper to initialize session data ---
def initialize_session_vars(session_id):
    if session_id not in app.config.get('APP_PROCESSING_LOCKS', {}):
        if 'APP_PROCESSING_LOCKS' not in app.config:
            app.config['APP_PROCESSING_LOCKS'] = {}
        app.config['APP_PROCESSING_LOCKS'][session_id] = threading.Lock()
    
    if 'message_burst_buffer' not in session:
        session['message_burst_buffer'] = [] # Use list, convert to deque later if needed
    if 'pending_bot_responses' not in session:
        session['pending_bot_responses'] = [] # Use list
    if 'chat_history' not in session:
        session['chat_history'] = []
    # Timers are harder to store in session directly as they are not JSON serializable.
    # We'll manage them in a global dict keyed by session_id for now.
    if 'APP_BURST_TIMERS' not in app.config:
        app.config['APP_BURST_TIMERS'] = {}


@app.route('/')
def index():
    if 'session_id' not in session:
        session['session_id'] = secrets.token_hex(16)
    
    session_id = session['session_id']
    initialize_session_vars(session_id)
    
    # Render with the current session's chat history
    return render_template('index.html', chat_history=session.get('chat_history', []))

# --- RAG Processing Function (Adapted for Flask session) ---
def process_rag_for_session(session_id_to_process, api_key, profile, persona, history_snapshot_for_rag):
    # This function will be called by the timer. It needs access to app.config for locks/timers
    # and will modify session data. This is tricky because timers run in separate threads
    # and Flask session is typically available only within a request context.
    # For simplicity, we'll pass necessary data and assume this function can update a
    # shared structure (like app.config for pending responses) keyed by session_id.

    session_lock = app.config.get('APP_PROCESSING_LOCKS', {}).get(session_id_to_process)
    if not session_lock:
        print(f"FLASK_RAG_THREAD: No lock for session {session_id_to_process}.")
        return

    with session_lock:
        # Get burst buffer from app.config or a shared dict if not using session directly here
        # For this example, we assume the /chat endpoint placed data in a shared structure
        # before starting the timer, or we pass it all in.
        # Let's assume the buffer was cleared by /chat after scheduling this.
        # The `combined_message_for_rag` would have been formed by the /chat endpoint
        # that scheduled this timer.

        # The challenge: `session` object is not directly available in a thread started by Timer.
        # So, the /chat endpoint needs to prepare all data for this function.
        # Let's assume 'profile', 'persona', 'api_key', 'history_snapshot_for_rag'
        # and 'combined_message_for_rag' (which isn't passed here yet) are correctly provided.
        
        # The `message_burst_buffer` needs to be read and cleared by the /chat endpoint
        # before this timer function is scheduled. This function receives the combined message.
        # This function's primary role is to call RAG and queue the response.

        # Simplified: Let's assume combined_message_for_rag was passed or retrieved from a shared dict
        # For this to work, the /chat route needs to pass the actual combined message.
        # The current app.py code structure for process_rag_for_session has combined_message
        # formed *inside* it from a buffer. This needs adjustment.

        # For now, let's simulate that the /chat endpoint already prepared combined_message
        # and we receive it here. We will need to adjust the /chat endpoint.
        # Let's assume `combined_message_for_rag` IS the combined message.
        # We'll need to modify the call to this function from /chat.

        print(f"FLASK_RAG_THREAD: Processing RAG for session {session_id_to_process}")
        # The original process_rag_for_session used its own buffer. This needs to change.
        # The `combined_message_for_rag` parameter will now be the ACTUAL combined message.

        chat_history_for_rag_flat = []
        for item in history_snapshot_for_rag: # This history is from the session at timer start
            if item["role"] == "user": chat_history_for_rag_flat.append(f"Sender: {item['content']}")
            elif item["role"] == "assistant": chat_history_for_rag_flat.append(f"Flow: {item['content']}")
            else: chat_history_for_rag_flat.append(f"System: {item['content']}")
        
        # Ensure original_user_query for format_response_as_burst_by_llm is the combined message
        # This parameter is missing in the current `process_rag_for_session` signature for the timer.
        # We need to pass it from the /chat endpoint.
        # Let's assume it's part of the arguments now.
        # For now, I'll use a placeholder for `combined_message_for_rag_processing`.
        # This indicates a structural change is needed in how /chat calls this.

        # Assuming the call from /chat is now:
        # args=[session_id, current_api_key, current_profile, current_persona, 
        #       history_snapshot_for_timer, combined_messages_from_buffer]
        # So, the signature of this function needs to change if we follow this.
        # For this refactor, I will assume the RAG pipeline gets the combined message
        # from its arguments, which means the `combined_message_for_rag` in `run_rag_pipeline`
        # IS the correct combined user input.

        rag_result = rag.run_rag_pipeline(
            api_key, profile, persona, 
            "Placeholder for combined message - this needs to be passed to process_rag_for_session", # THIS IS A KEY MISSING PIECE
            chat_history_for_rag_flat
        )

        bot_response_parts: List[str] = []
        if rag_result.get("error_message"):
            bot_response_parts = [f"Flow Error: {rag_result['error_message']}"]
        elif rag_result.get("generated_response"):
            complete_thought = rag_result["generated_response"]
            if complete_thought.strip():
                try:
                    # The original_user_query here should be the combined messages from the user's burst
                    # This also needs to be passed correctly to this function.
                    bot_response_parts = rag.format_response_as_burst_by_llm(
                        api_key=api_key,
                        full_response_content=complete_thought,
                        persona_description=persona,
                        original_user_query="Placeholder for combined message" # ANOTHER KEY MISSING PIECE
                    )
                    if not bot_response_parts: bot_response_parts = [complete_thought]
                except Exception as e_format:
                    print(f"FLASK_RAG_THREAD: Error formatting burst: {e_format}")
                    bot_response_parts = [complete_thought]
            else:
                bot_response_parts = ["Flow: (No response generated)"]
        else:
            bot_response_parts = ["Flow Error: No response content from RAG."]

        # Store pending responses in app.config or a globally accessible dict keyed by session_id
        if 'APP_PENDING_BOT_RESPONSES' not in app.config:
            app.config['APP_PENDING_BOT_RESPONSES'] = {}
        if session_id_to_process not in app.config['APP_PENDING_BOT_RESPONSES']:
             app.config['APP_PENDING_BOT_RESPONSES'][session_id_to_process] = deque()
        
        for part in bot_response_parts:
            app.config['APP_PENDING_BOT_RESPONSES'][session_id_to_process].append(part)

        print(f"FLASK_RAG_THREAD: Queued {len(bot_response_parts)} response parts for {session_id_to_process}.")
    
    # Clear timer from global dict
    app_burst_timers = app.config.get('APP_BURST_TIMERS', {})
    if session_id_to_process in app_burst_timers:
        del app_burst_timers[session_id_to_process]


# --- NEW /reset_session ENDPOINT ---
@app.route('/reset_session', methods=['POST'])
def reset_session_api():
    session_id = session.get('session_id')
    if not session_id:
        return jsonify({'error': 'No active session to reset.'}), 400

    initialize_session_vars(session_id) # Ensure session structures exist

    session_lock = app.config.get('APP_PROCESSING_LOCKS', {}).get(session_id)
    if not session_lock:
        return jsonify({'error': 'Internal server error: session lock missing for reset'}), 500

    with session_lock:
        # 1. Clear chat history from session
        session['chat_history'] = []
        print(f"FLASK_RESET_API: Chat history cleared for session {session_id}.")

        # 2. Clear message burst buffer from session
        session['message_burst_buffer'] = []
        print(f"FLASK_RESET_API: Message burst buffer cleared for session {session_id}.")

        # 3. Clear pending bot responses from global dict for this session
        app_pending_responses = app.config.get('APP_PENDING_BOT_RESPONSES', {})
        if session_id in app_pending_responses:
            app_pending_responses[session_id].clear()
            print(f"FLASK_RESET_API: Pending bot responses cleared for session {session_id}.")
        
        # 4. Cancel any active burst timer for this session
        app_burst_timers = app.config.get('APP_BURST_TIMERS', {})
        if session_id in app_burst_timers and app_burst_timers[session_id].is_alive():
            app_burst_timers[session_id].cancel()
            del app_burst_timers[session_id] # Remove from dict
            print(f"FLASK_RESET_API: Active burst timer cancelled for session {session_id}.")

        # 5. Re-initialize RAG components if API key or profile changes significantly
        # This is crucial. Your RAG module manages its own global state for llm, vector_store etc.
        # We need to tell it to update if the core inputs (API key, profile for vector store) change.
        data = request.json
        new_api_key = data.get('api_key')
        new_user_profile = data.get('user_profile')
        new_user_persona = data.get('user_persona') # Persona mainly affects prompts, not usually vector store

        if new_api_key and new_user_profile:
            try:
                print(f"FLASK_RESET_API: Re-initializing RAG for session {session_id} due to persona change.")
                # The rag.initialize_models_node function updates its internal globals.
                # It needs a FlowState-like structure.
                # We don't have an "incoming_message" for a reset, but it's needed by the RAG pipeline if run.
                # For just re-initialization, we primarily care about api_key and profile_content.
                init_state = rag.FlowState(
                    user_api_key=new_api_key,
                    user_profile_content=new_user_profile,
                    user_persona_description=new_user_persona if new_user_persona else "", # Ensure it's a string
                    incoming_message="", # Not used for init only, but good to provide
                    chat_history=[], # Reset history
                    retrieved_context="", generated_response="", error_message=None, _raw_retrieved_docs_content=None
                )
                result_state = rag.initialize_models_node(init_state)
                if result_state.get("error_message"):
                    print(f"FLASK_RESET_API: Error re-initializing RAG: {result_state['error_message']}")
                    # Don't raise HTTP error here, just log. Frontend will see cleared chat.
                    # The next /chat call will attempt init again.
                else:
                    print(f"FLASK_RESET_API: RAG components re-initialized/verified for session {session_id}.")
                    # Update session with new RAG config if needed for /chat
                    session['api_key_for_rag'] = new_api_key
                    session['profile_for_rag'] = new_user_profile
                    session['persona_for_rag'] = new_user_persona if new_user_persona else ""

            except Exception as e:
                print(f"FLASK_RESET_API: Exception during RAG re-initialization: {e}")
                # Log error, but proceed with resetting client-side view
        else:
            print(f"FLASK_RESET_API: API key or profile not provided for RAG re-initialization during reset.")


        session.modified = True
        return jsonify({'message': f'Session reset and RAG re-initialized for persona {data.get("new_persona_id", "N/A")}.'})


@app.route('/chat', methods=['POST'])
def chat_api():
    session_id = session.get('session_id')
    if not session_id: # Should ideally not happen if / always sets it
        session['session_id'] = secrets.token_hex(16)
        session_id = session['session_id']
    
    initialize_session_vars(session_id) # Ensure all session lists/dicts are present

    session_lock = app.config.get('APP_PROCESSING_LOCKS', {}).get(session_id)
    if not session_lock:
        # This case should be rare if initialize_session_vars works.
        app.config.setdefault('APP_PROCESSING_LOCKS', {})[session_id] = threading.Lock()
        session_lock = app.config['APP_PROCESSING_LOCKS'][session_id]

    data = request.json
    user_message = data.get('message')
    
    # Store/update RAG parameters in session for the timer to use
    session['api_key_for_rag'] = data.get('api_key')
    session['profile_for_rag'] = data.get('user_profile')
    session['persona_for_rag'] = data.get('user_persona')
    
    combined_messages_for_rag_processing = "" # Will be built here

    with session_lock:
        # Use session's buffer
        current_buffer = list(session.get('message_burst_buffer', [])) # Get a copy
        current_buffer.append(user_message)
        session['message_burst_buffer'] = current_buffer # Save back
        
        print(f"FLASK_CHAT_API: Msg added for {session_id}. Buffer: {session['message_burst_buffer']}")

        history_snapshot_for_timer_arg = list(session.get('chat_history', [])) # Get current history for the RAG call

        app_burst_timers = app.config.get('APP_BURST_TIMERS', {})
        if session_id in app_burst_timers and app_burst_timers[session_id].is_alive():
            app_burst_timers[session_id].cancel()
            print(f"FLASK_CHAT_API: Cancelled existing timer for {session_id}")
        
        # Prepare data for the timer thread *before* it starts
        api_key_for_timer = session.get('api_key_for_rag', "")
        profile_for_timer = session.get('profile_for_rag', "")
        persona_for_timer = session.get('persona_for_rag', "")
        
        # Combine messages from buffer *now* and clear it for this RAG cycle
        combined_messages_for_rag_processing = " ".join(session['message_burst_buffer'])
        session['message_burst_buffer'] = [] # Clear buffer as we are about to process it

        app_burst_timers[session_id] = threading.Timer(
            BURST_DELAY_SECONDS,
            process_rag_for_session_v2, # MODIFIED: Using a new version of the RAG processor
            args=[session_id, api_key_for_timer, profile_for_timer, persona_for_timer, 
                  history_snapshot_for_timer_arg, combined_messages_for_rag_processing] # Pass combined message
        )
        app_burst_timers[session_id].start()
        app.config['APP_BURST_TIMERS'] = app_burst_timers # Save back to app.config
    
    # Update session chat history immediately for the user's message
    current_chat_history = list(session.get('chat_history', []))
    current_chat_history.append({"role": "user", "content": user_message})
    session['chat_history'] = current_chat_history
    session.modified = True
    
    return jsonify({'status': 'message_received_buffering'})


# --- NEW RAG Processor for Timer ---
# This version takes the combined message directly
def process_rag_for_session_v2(session_id_to_process, api_key, profile, persona, 
                             history_snapshot_for_rag, combined_user_message):
    session_lock = app.config.get('APP_PROCESSING_LOCKS', {}).get(session_id_to_process)
    if not session_lock:
        print(f"FLASK_RAG_V2: No lock for session {session_id_to_process}.")
        return

    with session_lock:
        print(f"FLASK_RAG_V2: Processing RAG for session {session_id_to_process}: '{combined_user_message}'")
        
        chat_history_for_rag_flat = []
        for item in history_snapshot_for_rag:
            if item["role"] == "user": chat_history_for_rag_flat.append(f"Sender: {item['content']}")
            elif item["role"] == "assistant": chat_history_for_rag_flat.append(f"Flow: {item['content']}")
            else: chat_history_for_rag_flat.append(f"System: {item['content']}")

        rag_result = rag.run_rag_pipeline(
            api_key, profile, persona, combined_user_message, chat_history_for_rag_flat
        )

        bot_response_parts: List[str] = []
        if rag_result.get("error_message"):
            bot_response_parts = [f"Flow Error: {rag_result['error_message']}"]
        elif rag_result.get("generated_response"):
            complete_thought = rag_result["generated_response"]
            if complete_thought.strip():
                try:
                    bot_response_parts = rag.format_response_as_burst_by_llm(
                        api_key=api_key,
                        full_response_content=complete_thought,
                        persona_description=persona,
                        original_user_query=combined_user_message # Use the actual combined query
                    )
                    if not bot_response_parts: bot_response_parts = [complete_thought]
                except Exception as e_format:
                    print(f"FLASK_RAG_V2: Error formatting burst: {e_format}")
                    bot_response_parts = [complete_thought]
            else:
                bot_response_parts = ["Flow: (No response generated)"]
        else:
            bot_response_parts = ["Flow Error: No response content from RAG."]

        # Store pending responses in app.config
        app_pending_responses = app.config.setdefault('APP_PENDING_BOT_RESPONSES', {})
        session_pending_queue = app_pending_responses.setdefault(session_id_to_process, deque())
        
        for part in bot_response_parts:
            session_pending_queue.append(part)

        print(f"FLASK_RAG_V2: Queued {len(bot_response_parts)} response parts for {session_id_to_process}.")
    
    app_burst_timers = app.config.get('APP_BURST_TIMERS', {})
    if session_id_to_process in app_burst_timers:
        del app_burst_timers[session_id_to_process]


@app.route('/get_bot_response', methods=['GET'])
def get_bot_response_api():
    session_id = session.get('session_id')
    if not session_id: return jsonify({}), 204 # No content if no session

    initialize_session_vars(session_id) # Ensure session structures exist

    session_lock = app.config.get('APP_PROCESSING_LOCKS', {}).get(session_id)
    if not session_lock: return jsonify({}), 204 

    bot_message_content = None
    with session_lock:
        # Get pending responses from app.config's structure
        app_pending_responses = app.config.get('APP_PENDING_BOT_RESPONSES', {})
        session_pending_queue = app_pending_responses.get(session_id)

        if session_pending_queue and len(session_pending_queue) > 0:
            bot_message_content = session_pending_queue.popleft()
            
            # Update session chat history
            current_chat_history = list(session.get('chat_history', []))
            current_chat_history.append({"role": "assistant", "content": bot_message_content})
            session['chat_history'] = current_chat_history
            session.modified = True
            
            print(f"FLASK_GET_BOT_RESPONSE: Sent to client for {session_id}: {str(bot_message_content)[:50]}...")
            return jsonify({'role': 'assistant', 'content': bot_message_content})
        else:
            return jsonify({}), 204 # No Content

if __name__ == '__main__':
    # Initialize app.config structures if they don't exist
    app.config['APP_PROCESSING_LOCKS'] = {}
    app.config['APP_BURST_TIMERS'] = {}
    app.config['APP_PENDING_BOT_RESPONSES'] = {}
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True, threaded=True, use_reloader=False)  # use_reloader=False is important with threads
