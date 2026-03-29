# bugzy-voice

This project, Bugzy, is an advanced Diet Planner Voice Agent. It's a system designed to act as a virtual health coach that users can interact with via live voice calls over WhatsApp or a LiveKit web client to receive personalized diet and exercise plans.

Based on the project files, it is a distributed application built around real-time communication and AI, utilizing an impressive modern tech stack.
🏗 Architecture
The system is divided into four main interconnected components:

🎤 Core Voice Agent (Python): The primary AI engine built using the LiveKit Agents SDK. It orchestrates the voice interaction by handling WebRTC audio streaming, converting speech to text, generating an LLM response, and converting the text back into speech.
🧠 RAG Backend (Python): A dedicated Retrieval-Augmented Generation (RAG) server that provides the voice agent with specific, contextual knowledge (like product-specific nutrition or exercise data) to answer user questions intelligently.
📱 WhatsApp Integration Backend (Node.js/Express): A bridge that connects the Meta WhatsApp API to LiveKit. It listens for WhatsApp webhook events (like incoming calls) and negotiates the WebRTC connections to pipe the WhatsApp audio into the LiveKit rooms.
🌉 Python Audio Bridge (Python): An auxiliary service that assists with specific WebRTC and audio routing scenarios to complement the Node.js backend.
🛠 Tech Stack
Real-time Comms: LiveKit Cloud / Self-hosted LiveKit
Language Models (LLM): OpenAI (specifically gpt-4o-mini)
Speech-to-Text (STT): Deepgram
Text-to-Speech (TTS): Google Cloud TTS
Vector Database: Pinecone (for the RAG knowledge base)
Database: MongoDB (for application data & CRM)
Messaging Integration: WhatsApp Cloud API
