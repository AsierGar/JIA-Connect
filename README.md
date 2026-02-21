# 🏥 JIA-Connect

**Pediatric Rheumatology Platform powered by Generative AI**

An end-to-end clinical application for managing patients with Juvenile Idiopathic Arthritis (JIA), featuring AI-driven prescription validation through Retrieval-Augmented Generation (RAG).

![Python](https://img.shields.io/badge/Python-3.11-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.x-red)
![Ollama](https://img.shields.io/badge/LLM-Ollama%2FLlama3-green)
![License](https://img.shields.io/badge/License-Academic-lightgrey)

---

## 📋 Overview

JIA-Connect is designed for pediatric rheumatologists and provides:

- **Patient management** — Registration, follow-up, and a full clinical dashboard
- **Visit recording** — Forms with interactive joint examination (homunculus)
- **AI prescription validation** — RAG system that queries indexed medical guidelines to validate doses and detect contraindications
- **Patient portal** — Medication calendar and support chatbot
- **Automatic calculations** — JADAS-27, BSA, WHO growth percentiles

---

## 🎯 Problem Statement

Dosing errors with high-risk medications (such as Methotrexate) are a critical concern in pediatric rheumatology. JIA-Connect addresses this by:

1. **Automatically validating** prescriptions against indexed clinical guidelines
2. **Alerting the physician** when a dose exceeds recommended limits
3. **Documenting the evidence** used for each decision
4. **Streamlining follow-up** with visual dashboards and clinical metrics

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| **Frontend** | Streamlit |
| **AI Backend** | CrewAI + LangChain |
| **LLM** | Ollama (Llama 3) — runs locally |
| **Embeddings** | nomic-embed-text / all-MiniLM-L6-v2 |
| **Vector Store** | ChromaDB / FAISS |
| **PDF Processing** | PyPDF |

---

## 📁 Project Structure

```
JIA-Connect/
├── mobile_app/                 # Main Streamlit application
│   ├── app.py                  # Entry point
│   ├── ui_dashboard.py         # Patient clinical dashboard
│   ├── ui_visita.py            # New visit form
│   ├── ui_alta.py              # New patient registration
│   ├── ui_patient.py           # Patient portal (calendar + chatbot)
│   ├── patient_bot.py          # Patient assistant chatbot
│   ├── rag_engine.py           # RAG engine for the chatbot
│   ├── homunculo_visita.py     # Interactive joint homunculus
│   ├── homunculo_dashboard.py  # Joint involvement heatmap
│   ├── auth.py                 # Authentication system
│   ├── data_manager.py         # JSON persistence layer
│   └── styles.py               # Custom CSS styles
│
├── ai_backend/                 # AI validation system (CrewAI)
│   ├── agents/
│   │   ├── tripulacion.py      # Medical validation crew
│   │   └── run_tripulacion.py  # Alternative CLI runner
│   ├── tools/
│   │   └── mis_herramientas.py # RAG tools & processing
│   └── ingest_knowledge.py     # PDF indexer (ChromaDB)
│
├── ai_engine/                  # Alternative AI engine (direct Ollama)
│   ├── auditor.py              # Safety auditor agent
│   ├── structurer.py           # Structurer + math agent
│   └── ingest.py               # Indexer with Ollama embeddings
│
├── backend/                    # REST API (FastAPI)
│   ├── main.py                 # API endpoints
│   └── models.py               # Pydantic models
│
└── data/                       # Medical guidelines & drug datasheets (PDFs)
                                # (not included — see Setup below)
```

---

## 🚀 Setup

### Prerequisites

- Python 3.11+
- [Ollama](https://ollama.ai/) installed and running

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/AsierGar/JIA-Connect.git
cd JIA-Connect

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Download Ollama models
ollama pull llama3
ollama pull nomic-embed-text

# 5. Add medical PDFs
#    Place your clinical guidelines and drug datasheets in the data/ folder.
#    These are required for the RAG system to work.

# 6. Index medical documents (first time only)
python ai_backend/ingest_knowledge.py

# 7. Run the application
streamlit run mobile_app/app.py
```

### Default Credentials

- **Username:** `admin`
- **Password:** `admin`

---

## 📸 Key Features

### 🌐 Global Dashboard

Overview of all patients with aggregated metrics and filters.

### 📊 Patient Dashboard

- JADAS score evolution over time
- Weight vs. WHO growth percentile charts
- Historical joint involvement heatmap
- Full visit history

### 🩺 New Visit

- Interactive homunculus for joint examination
- Clinical scales (physician and patient VAS)
- AI validation of the treatment plan
- Attach documents (lab results, reports)

### 🤖 AI Prescription Validation

The system analyzes the treatment plan by:

1. Extracting drug, dose, and frequency
2. Querying indexed medical guidelines (RAG)
3. Comparing against maximum recommended doses
4. Issuing a decision: ✅ **APPROVED** · ⚠️ **ALERT** · ❌ **REJECTED**

### 👶 Patient Portal

- Medication calendar with scheduled doses
- Chatbot for patient questions
- Clinical photo gallery

---

## 🎥 Demo

[![JIA-Connect Demo](https://img.youtube.com/vi/DX9yS_NGM3M/maxresdefault.jpg)](https://youtu.be/DX9yS_NGM3M)

---

## 👨‍💻 Author

**Asier García**

Presented at the [8th Digital Rheumatology Days](https://digitalrheumatology.org/8th-digital-rheumatology-days/) — Berlin, May 2026

---

## 📄 License

This project is for educational and research purposes only.
