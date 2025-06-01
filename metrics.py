# evaluate_retrieval.py

import json
import time
from typing import List, Dict, Any, Set, Optional # Added Optional

# Import the main function and FlowState from your RAG module
from rag import run_rag_pipeline, FlowState # Make sure FlowState is accessible if needed for type hints

# For splitting text to get chunks consistently
from langchain_text_splitters import RecursiveCharacterTextSplitter

# --- Configuration for Evaluation ---
EVAL_API_KEY = "YOUR_GEMINI_API_KEY" # <<< REPLACE WITH YOUR ACTUAL API KEY

# LONGER AND MORE DIVERSE USER PROFILE FOR EVALUATION
EVAL_USER_PROFILE_CONTENT = """
Name: Dr. Eleanor Vance
Timezone: EST (UTC-5)
Profession: Senior Research Scientist at NovaTech AI Labs.
Contact Preference: Email for work matters (eleanor.vance@novatech.ai), text for urgent personal. Avoids calls during work hours unless scheduled.

Typical Availability:
- Weekdays: Generally in deep work focus 9 AM - 12 PM and 1 PM - 4 PM. Available for quick chats before 9 AM, during lunch (12-1 PM), or after 4 PM.
- Evenings: Prefers to disconnect after 7 PM for family time. Might check messages sporadically.
- Weekends: Flexible, but usually dedicates Saturdays to personal projects and Sundays to relaxation or outings.

Current Status & Projects:
- Leading the 'Athena' project, focusing on explainable AI in natural language understanding. Deadline for phase 1 report: July 15th.
- Mentoring three junior researchers. Regular check-ins on Tuesdays.
- Preparing a keynote presentation for the "AI Frontiers Conference" on August 5th. Abstract due: June 20th.
- Currently experiencing a high workload due to multiple deadlines.

Response Style & Preferences:
- Professional Context: Formal, precise, and data-driven. Prefers bullet points for summaries.
- Casual Context (friends/family): Warm, uses occasional humor, sometimes uses emojis like 🤔, 👍, 🎉.
- When Busy/Stressed: Replies will be very concise, possibly just acknowledgments. May state she's swamped and will follow up.
- Common Phrases when busy: "Currently swamped, will circle back soon.", "In a meeting, can I get back to you?", "Acknowledged. Will review and respond later today."

Technical Skills:
- Programming: Python (Expert), C++, Java (Proficient).
- AI/ML: Deep Learning (CNNs, RNNs, Transformers), NLP (BERT, GPT, LangChain), Explainable AI (XAI), Reinforcement Learning.
- Tools: PyTorch, TensorFlow, Scikit-learn, Hugging Face Transformers, Docker, Kubernetes.

Interests & Hobbies:
- Reading: Science fiction, history of science.
- Outdoor: Hiking, landscape photography.
- Music: Plays classical piano.
- Learning: Currently learning about quantum machine learning.

Travel:
- Upcoming: Attending "AI Frontiers Conference" in San Francisco, August 3rd - 7th. Will have limited availability.
- Past: Presented at "Global AI Summit" in Berlin last year.

Personal Notes:
- Values punctuality for meetings.
- Prefers clear agendas for discussions.
- Not a morning person before her first coffee.
"""

EVAL_USER_PERSONA_DESCRIPTION = """
Dr. Vance is a highly focused and professional research scientist.
During work hours, responses via Flow should be courteous but brief, reflecting her busy schedule.
If the context is clearly personal and from a known contact (not easily determined by Flow alone, but persona aims for general appropriateness),
a slightly warmer but still concise tone can be used.
Flow should prioritize conveying that Dr. Vance has received the message and will address it when her schedule permits,
especially if it pertains to her current high workload or project deadlines.
It should defer to her email for detailed work discussions.
"""

# --- Helper Function to Get Profile Chunks ---
def get_profile_chunks(profile_content: str, chunk_size: int = 500, chunk_overlap: int = 50) -> List[str]:
    if not profile_content.strip():
        return []
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len, # Important: default is character length for this splitter
        is_separator_regex=False,
    )
    chunks = text_splitter.split_text(profile_content)
    return chunks

# --- Generate Actual Chunks from the Profile for Ground Truth ---
CHUNK_SIZE_FOR_EVAL = 500
CHUNK_OVERLAP_FOR_EVAL = 50
ACTUAL_CHUNKS_FROM_PROFILE: List[str] = get_profile_chunks(
    EVAL_USER_PROFILE_CONTENT,
    chunk_size=CHUNK_SIZE_FOR_EVAL,
    chunk_overlap=CHUNK_OVERLAP_FOR_EVAL
)

# --- Assign Chunks to Variables for Easier Reference in TEST_DATASET ---
# This assumes exactly 7 chunks are produced with the above settings and profile.
# If the number of chunks changes, this section will need adjustment or more dynamic handling.
CHUNK_1, CHUNK_2, CHUNK_3, CHUNK_4, CHUNK_5, CHUNK_6, CHUNK_7 = [None] * 7
if len(ACTUAL_CHUNKS_FROM_PROFILE) == 7:
    CHUNK_1 = ACTUAL_CHUNKS_FROM_PROFILE[0]
    CHUNK_2 = ACTUAL_CHUNKS_FROM_PROFILE[1]
    CHUNK_3 = ACTUAL_CHUNKS_FROM_PROFILE[2]
    CHUNK_4 = ACTUAL_CHUNKS_FROM_PROFILE[3]
    CHUNK_5 = ACTUAL_CHUNKS_FROM_PROFILE[4]
    CHUNK_6 = ACTUAL_CHUNKS_FROM_PROFILE[5]
    CHUNK_7 = ACTUAL_CHUNKS_FROM_PROFILE[6]
else:
    print(f"WARNING: Expected 7 chunks from EVAL_USER_PROFILE_CONTENT with current chunking, but got {len(ACTUAL_CHUNKS_FROM_PROFILE)}.")
    print("Evaluation may not be accurate. Please review chunking or TEST_DATASET definitions.")
    # Fallback: if chunk list is shorter, some CHUNK_X variables will remain None.
    # The TEST_DATASET construction below will need to handle this (e.g. by skipping tests that rely on non-existent chunks)

# --- Test Dataset ---
# IMPORTANT: Review and adjust the ground_truth_chunks and best_chunk
# based on the ACTUAL printed chunks after running this script once.
TEST_DATASET = []

# Populate TEST_DATASET only if chunks are available
if CHUNK_1: # Check if at least the first chunk is defined
    # --- 5 Easy Queries ---
    if CHUNK_1:
        TEST_DATASET.append({
            "query": "What is Dr. Vance's profession?",
            "ground_truth_chunks": {CHUNK_1}, "best_chunk": CHUNK_1
        })
    if CHUNK_6:
        TEST_DATASET.append({
            "query": "What are Dr. Vance's hobbies?",
            "ground_truth_chunks": {CHUNK_6}, "best_chunk": CHUNK_6
        })
    if CHUNK_1:
        TEST_DATASET.append({
            "query": "What is your timezone?",
            "ground_truth_chunks": {CHUNK_1}, "best_chunk": CHUNK_1
        })
    if CHUNK_6:
        TEST_DATASET.append({
            "query": "What music does Eleanor play?",
            "ground_truth_chunks": {CHUNK_6}, "best_chunk": CHUNK_6
        })
    if CHUNK_7:
        TEST_DATASET.append({
            "query": "Any upcoming travel plans?",
            "ground_truth_chunks": {CHUNK_7}, "best_chunk": CHUNK_7
        })

    # --- 5 Medium Queries ---
    if CHUNK_1:
        TEST_DATASET.append({
            "query": "How does Dr. Vance prefer to be contacted for work issues?",
            "ground_truth_chunks": {CHUNK_1}, "best_chunk": CHUNK_1
        })
    if CHUNK_3:
        TEST_DATASET.append({
            "query": "What is Eleanor Vance working on right now?",
            "ground_truth_chunks": {CHUNK_3}, "best_chunk": CHUNK_3
        })
    if CHUNK_4 and CHUNK_5:
        TEST_DATASET.append({
            "query": "What is her response style when she is under pressure?",
            "ground_truth_chunks": {CHUNK_4, CHUNK_5}, "best_chunk": CHUNK_4
        })
    if CHUNK_2:
        TEST_DATASET.append({
            "query": "Tell me about her availability on weekends.",
            "ground_truth_chunks": {CHUNK_2}, "best_chunk": CHUNK_2
        })
    if CHUNK_6:
        TEST_DATASET.append({
            "query": "What are some of Dr. Vance's technical skills in AI?",
            "ground_truth_chunks": {CHUNK_6}, "best_chunk": CHUNK_6
        })

    # --- 5 Hard Queries ---
    if CHUNK_7:
        TEST_DATASET.append({
            "query": "Is Dr. Vance a punctual person and how does she like her meetings?",
            "ground_truth_chunks": {CHUNK_7}, "best_chunk": CHUNK_7
        })
    if CHUNK_3 and CHUNK_7:
        TEST_DATASET.append({
            "query": "Given her current workload and upcoming conference, how likely is she to take on a new side project this month?",
            "ground_truth_chunks": {CHUNK_3, CHUNK_7}, "best_chunk": CHUNK_3
        })
    if CHUNK_2 and CHUNK_3:
        TEST_DATASET.append({
            "query": "How does Eleanor balance her work, personal projects, and family time?",
            "ground_truth_chunks": {CHUNK_2, CHUNK_3}, "best_chunk": CHUNK_2
        })
    if CHUNK_3 and CHUNK_4 and CHUNK_5:
        TEST_DATASET.append({
            "query": "What are some phrases Eleanor might use if I message her while she's in a meeting about the Athena project?",
            "ground_truth_chunks": {CHUNK_5, CHUNK_3, CHUNK_4}, "best_chunk": CHUNK_5
        })
    if CHUNK_6:
        TEST_DATASET.append({
            "query": "What's something new Dr. Vance is learning about outside of her main research at NovaTech?",
            "ground_truth_chunks": {CHUNK_6}, "best_chunk": CHUNK_6
        })
else:
    print("CRITICAL: Not enough chunks generated from profile to build TEST_DATASET. Check profile content and chunking settings.")


K_FOR_EVALUATION = 3

# --- Evaluation Metrics Functions (Same as before) ---
def calculate_precision_at_k(retrieved_docs: List[str], ground_truth_docs: Set[str], k: int) -> float:
    if not retrieved_docs or k == 0: return 0.0
    top_k_retrieved = retrieved_docs[:k]
    relevant_retrieved_count = sum(1 for doc in top_k_retrieved if doc in ground_truth_docs)
    return relevant_retrieved_count / k

def calculate_recall_at_k(retrieved_docs: List[str], ground_truth_docs: Set[str], k: int) -> float:
    if not ground_truth_docs: return 1.0 if not retrieved_docs else 0.0 # All retrieved are non-relevant if GT is empty
    if not retrieved_docs or k == 0: return 0.0
    top_k_retrieved = retrieved_docs[:k]
    relevant_retrieved_count = sum(1 for doc in top_k_retrieved if doc in ground_truth_docs)
    return relevant_retrieved_count / len(ground_truth_docs) if len(ground_truth_docs) > 0 else 0.0

def calculate_mrr(retrieved_docs: List[str], best_ground_truth_doc: Optional[str]) -> float:
    if not best_ground_truth_doc: return 0.0 # Or handle as "not applicable" / skip
    for i, doc in enumerate(retrieved_docs):
        if doc == best_ground_truth_doc:
            return 1.0 / (i + 1)
    return 0.0

def calculate_hit_miss(retrieved_docs: List[str], ground_truth_docs: Set[str]) -> bool:
    if not ground_truth_docs: return True # Vacuously true
    return any(doc in ground_truth_docs for doc in retrieved_docs)

# --- Main Evaluation Loop ---
def run_evaluation():
    if EVAL_API_KEY == "YOUR_GOOGLE_API_KEY_HERE":
        print("FATAL ERROR: Please set your actual Google API Key in EVAL_API_KEY at the top of this script.")
        return

    print(f"--- Generated {len(ACTUAL_CHUNKS_FROM_PROFILE)} Chunks from EVAL_USER_PROFILE_CONTENT (Size: {CHUNK_SIZE_FOR_EVAL}, Overlap: {CHUNK_OVERLAP_FOR_EVAL}) ---")
    if CHUNK_1 is None and len(ACTUAL_CHUNKS_FROM_PROFILE) > 0 : # If CHUNK_X vars weren't set due to length mismatch
        print("Actual Chunks from Profile (please use these to define CHUNK_X variables or update TEST_DATASET directly):")
        for i, chunk_content in enumerate(ACTUAL_CHUNKS_FROM_PROFILE):
            print(f"ACTUAL_CHUNK_{i+1}:\n{json.dumps(chunk_content)}\n--------------------")
    elif CHUNK_1 is not None: # If CHUNK_X vars were set
        for i in range(1, 8): # Assuming up to CHUNK_7
            chunk_var = globals().get(f"CHUNK_{i}")
            if chunk_var:
                print(f"CHUNK_{i} (used in TEST_DATASET):\n{json.dumps(chunk_var)}\n--------------------")

    print("IMPORTANT: Manually review the printed chunks and ensure your TEST_DATASET ground truth uses these exact strings.\n")

    if not TEST_DATASET:
        print("WARNING: TEST_DATASET is empty. No queries to evaluate. This might be due to an unexpected number of chunks from the profile.")
        return

    print(f"Starting retrieval evaluation with K={K_FOR_EVALUATION} using {len(ACTUAL_CHUNKS_FROM_PROFILE)} total profile chunks...\n")

    all_precisions_at_k: List[float] = []
    all_recalls_at_k: List[float] = []
    all_mrr_scores: List[float] = []
    hit_count = 0
    total_queries = len(TEST_DATASET)
    dummy_chat_history: List[str] = []

    for i, test_case in enumerate(TEST_DATASET):
        query = test_case["query"]
        ground_truth_chunks = test_case.get("ground_truth_chunks", set()) # Default to empty set if missing
        best_chunk = test_case.get("best_chunk")

        print(f"--- Query {i+1}/{total_queries}: \"{query}\" ---")
        # print(f"Ground Truth Chunks: {json.dumps(list(ground_truth_chunks), indent=2)}") # Verbose
        # if best_chunk: print(f"Best Ground Truth Chunk: \"{best_chunk[:100]}...\"")

        try:
            result_state: Dict[str, Any] = run_rag_pipeline(
                api_key=EVAL_API_KEY,
                profile_content=EVAL_USER_PROFILE_CONTENT,
                persona_description=EVAL_USER_PERSONA_DESCRIPTION,
                combined_message=query,
                chat_history_for_rag=dummy_chat_history
            )
        except Exception as e:
            print(f"ERROR running RAG pipeline for query '{query}': {e}")
            all_precisions_at_k.append(0.0)
            all_recalls_at_k.append(0.0)
            all_mrr_scores.append(0.0) # Add 0 for MRR in case of error
            continue

        retrieved_docs_content: List[str] = []
        if result_state.get("error_message"):
            print(f"RAG Pipeline Error: {result_state['error_message']}")
        else:
            retrieved_docs_content = result_state.get("_raw_retrieved_docs_content", [])
            if not isinstance(retrieved_docs_content, list):
                print(f"Warning: _raw_retrieved_docs_content is not a list: {type(retrieved_docs_content)}. Treating as empty.")
                retrieved_docs_content = []

        # print(f"Retrieved Docs ({len(retrieved_docs_content)}): {json.dumps(retrieved_docs_content, indent=2)}")

        precision = calculate_precision_at_k(retrieved_docs_content, ground_truth_chunks, K_FOR_EVALUATION)
        recall = calculate_recall_at_k(retrieved_docs_content, ground_truth_chunks, K_FOR_EVALUATION)
        mrr = calculate_mrr(retrieved_docs_content, best_chunk)
        hit = calculate_hit_miss(retrieved_docs_content, ground_truth_chunks)

        all_precisions_at_k.append(precision)
        all_recalls_at_k.append(recall)
        all_mrr_scores.append(mrr)
        if hit:
            hit_count += 1

        print(f"Precision@{K_FOR_EVALUATION}: {precision:.4f}")
        print(f"Recall@{K_FOR_EVALUATION}: {recall:.4f}")
        print(f"Reciprocal Rank: {mrr:.4f}")
        print(f"Hit (at least one relevant retrieved): {hit}")
        print("---------------------------------------\n")

    avg_precision = sum(all_precisions_at_k) / total_queries if total_queries > 0 else 0.0
    avg_recall = sum(all_recalls_at_k) / total_queries if total_queries > 0 else 0.0
    mean_mrr = sum(all_mrr_scores) / total_queries if total_queries > 0 else 0.0 # MRR is calculated for all, will be 0 if no best_chunk or not found
    hit_rate = hit_count / total_queries if total_queries > 0 else 0.0

    print("\n--- Overall Retrieval Evaluation Summary ---")
    print(f"Total Queries Evaluated: {total_queries}")
    print(f"Average Precision@{K_FOR_EVALUATION}: {avg_precision:.4f}")
    print(f"Average Recall@{K_FOR_EVALUATION}: {avg_recall:.4f}")
    print(f"Mean Reciprocal Rank (MRR): {mean_mrr:.4f}")
    print(f"Hit Rate (at least one relevant doc retrieved): {hit_rate:.4f} ({hit_count}/{total_queries})")
    print("------------------------------------------")

if __name__ == "__main__":
    if EVAL_API_KEY == "YOUR_GOOGLE_API_KEY_HERE":
        print("FATAL ERROR: Please set your actual Google API Key in EVAL_API_KEY at the top of this script before running.")
    else:
        run_evaluation()