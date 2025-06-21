# NLP_Flow

## 💬 Flow: A Smarter Auto-Reply Assistant
Project for WID3002 - Natural Language Programming (Semester 2, 2024/2025)
Group 28 – Universiti Malaya

## 📌 Overview
Flow is an intelligent, NLP-powered conversational assistant designed to help users reply to messages promptly and contextually—even when they're unavailable. Unlike generic canned replies, Flow mimics the user’s tone, style, and preferences using a Retrieval-Augmented Generation (RAG) architecture combined with real-time user profiling.

This project aims to reduce communication delays and keep conversations flowing naturally by generating personalized and situationally aware replies.

## 🚩 Problem Statement
Modern users frequently find themselves too busy—driving, in meetings, or taking exams—to respond to messages, leading to:

1. Delayed or missed replies
2. Miscommunication or relational strain
3. Generic and impersonal canned messages
4. Flow addresses these challenges with fast, personalized, and context-aware auto-replies.

## ✅ Proposed Solution
Flow intelligently generates replies using:

🔹 NLP Core Components
RAG (Retrieval-Augmented Generation):
Retrieves relevant user data from a vector store (e.g., FAISS/ChromaDB) and feeds it into a generator (e.g., OpenAI GPT or Gemini) for response crafting.

Prompt Engineering:
Constructs dynamic prompts using retrieved facts, user personas, chat history, and tone/language preferences.

Burst Message Grouping:
Messages received within a short timeframe (e.g., 5 seconds) are grouped for context continuity.

Tone & Language Matching:
The system adapts to informal/formal tones, emojis, or multilingual contexts based on prior message patterns and user data.


## To run, just click run on app.py.
