# app.py
from flask import Flask, render_template, request, jsonify, session
import threading
import time
from collections import deque
import secrets

# Import your RAG logic module (assuming it's now named rag.py)
import rag # CHANGED from your_rag_module

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

message_burst_buffer = {}
burst_timers = {}
_pending_bot_responses = {} # Key: session_id, Value: deque of individual message strings
_processing_locks = {}

BURST_DELAY_SECONDS = 5

@app.route('/')
def index():
    if 'session_id' not in session:
        session['session_id'] = secrets.token_hex(16)
    session_id = session['session_id']
    if session_id not in message_burst_buffer: message_burst_buffer[session_id] = deque()
    if session_id not in _pending_bot_responses: _pending_bot_responses[session_id] = deque()
    if session_id not in _processing_locks: _processing_locks[session_id] = threading.Lock()
    if 'chat_history' not in session: session['chat_history'] = []
    return render_template('index.html', chat_history=session.get('chat_history', []))

def process_rag_for_session(session_id_to_process, api_key, profile, persona, history_snapshot_for_rag):
    global message_burst_buffer, burst_timers, _pending_bot_responses, _processing_locks
    session_lock = _processing_locks.get(session_id_to_process)
    if not session_lock:
        print(f"FLASK_RAG_THREAD: No lock for session {session_id_to_process}.")
        return

    with session_lock:
        if session_id_to_process not in message_burst_buffer or not message_burst_buffer[session_id_to_process]:
            if session_id_to_process in burst_timers: del burst_timers[session_id_to_process]
            return

        buffered_messages = list(message_burst_buffer[session_id_to_process])
        message_burst_buffer[session_id_to_process].clear()
        combined_message_for_rag = " ".join(buffered_messages)
        
        print(f"FLASK_RAG_THREAD: Processing RAG for session {session_id_to_process}: '{combined_message_for_rag}'")
        chat_history_for_rag_flat = []
        for item in history_snapshot_for_rag:
            if item["role"] == "user": chat_history_for_rag_flat.append(f"Sender: {item['content']}")
            elif item["role"] == "assistant": chat_history_for_rag_flat.append(f"Flow: {item['content']}")
            else: chat_history_for_rag_flat.append(f"System: {item['content']}")

        rag_result = rag.run_rag_pipeline(
            api_key, profile, persona, combined_message_for_rag, chat_history_for_rag_flat
        )

        bot_response_parts: List[str] = []
        if rag_result.get("error_message"):
            bot_response_parts = [f"Flow Error: {rag_result['error_message']}"]
        elif rag_result.get("generated_response"):
            complete_thought = rag_result["generated_response"]
            if complete_thought.strip():
                print(f"FLASK_RAG_THREAD: RAG generated: '{complete_thought[:100]}...'")
                print(f"FLASK_RAG_THREAD: Formatting response into burst for session {session_id_to_process}.")
                try:
                    bot_response_parts = rag.format_response_as_burst_by_llm(
                        api_key=api_key, # Pass current API key
                        full_response_content=complete_thought,
                        persona_description=persona,
                        original_user_query=combined_message_for_rag # Use the combined query
                    )
                    if not bot_response_parts: bot_response_parts = [complete_thought]
                except Exception as e_format:
                    print(f"FLASK_RAG_THREAD: Error formatting burst: {e_format}")
                    bot_response_parts = [complete_thought]
            else:
                bot_response_parts = ["Flow: (No response generated)"]
        else:
            bot_response_parts = ["Flow Error: No response content from RAG."]

        if session_id_to_process not in _pending_bot_responses:
             _pending_bot_responses[session_id_to_process] = deque()
        
        for part in bot_response_parts:
            _pending_bot_responses[session_id_to_process].append(part) # Add each part to the queue

        print(f"FLASK_RAG_THREAD: Queued {len(bot_response_parts)} response parts for {session_id_to_process}.")
    
    if session_id_to_process in burst_timers:
        del burst_timers[session_id_to_process]

@app.route('/chat', methods=['POST'])
def chat_api():
    global message_burst_buffer, burst_timers, _processing_locks
    if 'session_id' not in session:
        session['session_id'] = secrets.token_hex(16)
        session_id = session['session_id']
        if session_id not in message_burst_buffer: message_burst_buffer[session_id] = deque()
        if session_id not in _pending_bot_responses: _pending_bot_responses[session_id] = deque()
        if session_id not in _processing_locks: _processing_locks[session_id] = threading.Lock()
        if 'chat_history' not in session: session['chat_history'] = []
    else:
        session_id = session['session_id']

    session_lock = _processing_locks.get(session_id)
    if not session_lock:
        return jsonify({'error': 'Internal server error: session lock missing'}), 500

    data = request.json
    user_message = data.get('message')
    session['api_key_for_rag'] = data.get('api_key')
    session['profile_for_rag'] = data.get('user_profile')
    session['persona_for_rag'] = data.get('user_persona')
    history_snapshot_for_timer = []

    with session_lock:
        if session_id not in message_burst_buffer: message_burst_buffer[session_id] = deque()
        message_burst_buffer[session_id].append(user_message)
        # print(f"FLASK_CHAT_API: Msg added to buffer for {session_id}. Buffer: {list(message_burst_buffer[session_id])}")

        if len(message_burst_buffer[session_id]) == 1:
            history_snapshot_for_timer = list(session.get('chat_history', []))
            session['history_snapshot_for_timer'] = history_snapshot_for_timer
        else:
            history_snapshot_for_timer = session.get('history_snapshot_for_timer', [])

        if session_id in burst_timers and burst_timers[session_id].is_alive():
            burst_timers[session_id].cancel()
        
        current_api_key = session.get('api_key_for_rag', "")
        current_profile = session.get('profile_for_rag', "")
        current_persona = session.get('persona_for_rag', "")

        burst_timers[session_id] = threading.Timer(
            BURST_DELAY_SECONDS,
            process_rag_for_session,
            args=[session_id, current_api_key, current_profile, current_persona, history_snapshot_for_timer]
        )
        burst_timers[session_id].start()
    
    if 'chat_history' not in session: session['chat_history'] = []
    session['chat_history'].append({"role": "user", "content": user_message})
    session.modified = True
    return jsonify({'status': 'message_received_buffering'})

@app.route('/get_bot_response', methods=['GET'])
def get_bot_response_api():
    # This endpoint remains the same. It will serve one message part per call.
    global _pending_bot_responses, _processing_locks
    session_id = session.get('session_id')
    bot_message_content = None
    if not session_id: return jsonify({})
    session_lock = _processing_locks.get(session_id)
    if not session_lock: return jsonify({})

    with session_lock:
        if session_id in _pending_bot_responses and _pending_bot_responses[session_id]:
            bot_message_content = _pending_bot_responses[session_id].popleft()
            if 'chat_history' not in session: session['chat_history'] = []
            session['chat_history'].append({"role": "assistant", "content": bot_message_content})
            session.modified = True
            # print(f"FLASK_GET_BOT_RESPONSE: Sent to client for {session_id}: {bot_message_content[:50]}...")
            return jsonify({'role': 'assistant', 'content': bot_message_content})
        else:
            return jsonify({})

if __name__ == '__main__':
    app.run(debug=True, threaded=True, use_reloader=False)