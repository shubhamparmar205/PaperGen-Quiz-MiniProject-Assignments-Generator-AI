# 🎓 PaperGen AI (v2.0.0)

[![Python](https://img.shields.io/badge/Python-3.9+-blue?style=for-the-badge&logo=python)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.1.0-white?style=for-the-badge&logo=flask)](https://flask.palletsprojects.com/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind-3.4-38B2AC?style=for-the-badge&logo=tailwind-css)](https://tailwindcss.com/)

**PaperGen** is an advanced AI-driven educational architect designed to transform static learning materials into dynamic pedagogical tools. By leveraging **Gemini 1.5 Flash**, it parses complex syllabus documents (PDF/TXT) to generate structured, curriculum-aligned content tailored to specific cognitive levels and difficulty requirements.

---

## ✨ New & Upgraded Features

* **🧠 Cognitive Alignment (Bloom's Taxonomy):** Generate content specifically targeted at levels from *Remembering* to *Creating*.
* **📊 Dynamic Difficulty Scaling:** Choose from *Easy*, *Moderate*, *Challenging*, or *Expert* to match student proficiency.
* **📂 Multimodal Input:** Robust parsing of `.pdf` and `.txt` files using PyMuPDF (`fitz`).
* **⚡ Modernized UX:** Completely redesigned interface using **Tailwind CSS** with a sleek, responsive chat-like workflow.
* **📝 Expanded Content Types:**
    * **Quizzes:** Interactive MCQs with original, conceptually-driven questions.
    * **Assignments:** Deep-dive descriptive questions for conceptual testing.
    * **Mini Projects:** Comprehensive problem statements with 15+ unique ideas.
    * **Presentations:** Structured topics and subtitles for academic seminars.
    * **Follow-up Actions:** One-click "Generate Expected Answers" or "Descriptions" for generated content.
* **💾 Smart History & Dashboard:** Authenticated users can save, view, copy, or download their generation history.

---

## 🛠️ Updated Tech Stack

| Layer | Technologies |
| :--- | :--- |
| **AI Core** | Google Gemini 1.5 Flash API |
| **Backend** | Python 3.x, Flask, python-dotenv |
| **Frontend** | Tailwind CSS, JavaScript (ES6+), Jinja2 Templates |
| **Parsing** | PyMuPDF (fitz), pdfplumber |
| **Version Control** | GitHub |

---

## 🚀 Local Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/shubhamparmar205/PaperGen-Quiz-MiniProject-Assignments-Generator-AI.git](https://github.com/shubhamparmar205/PaperGen-Quiz-MiniProject-Assignments-Generator-AI.git)
   cd PaperGen-Quiz-MiniProject-Assignments-Generator-AI