# 🤖 Job Automation Agent

[![GitHub stars](https://img.shields.io/github/stars/shriyashsoni/Job-Automation-agent.svg?style=social&label=Star)](https://github.com/shriyashsoni/Job-Automation-agent)
[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An advanced AI-powered agent designed to automate the tedious process of job searching and applying. This agent uses LLMs (Gemini/Groq) to analyze job descriptions, parse your resume, and fill out application forms autonomously.

> [!IMPORTANT]
> **Community Support:** If you find this project useful, please **star the repository**! It helps the project grow and encourages more features. You are encouraged to star before using.

---

## 🚀 Workflow Overview

The agent follows a sophisticated multi-step process to ensure high-quality applications:

1.  **Job Discovery:** Scours platforms like LinkedIn for relevant job postings based on your criteria.
2.  **Contextual Analysis:** Uses AI to read the job description and compare it against your resume.
3.  **Dynamic Decision Making:** Decides if the job is a good fit before proceeding.
4.  **Form Filling:** Automatically navigates through application pages, filling in personal details, work history, and custom questions.
5.  **Logging:** Keeps a detailed CSV log of every application attempted, including status and job details.

---

## 🛠️ Comparison: Why use this Agent?

| Feature | Manual Applying | Typical Browser Bots | **Job Automation Agent** |
| :--- | :---: | :---: | :---: |
| **Speed** | 🐌 Slow | ⚡ Fast | 🚀 Ultra-Fast |
| **Quality** | ✅ High | ❌ Low (Generic) | ✅ High (AI-Tailored) |
| **Custom Questions** | ✅ Yes | ❌ No | ✅ Yes (AI-Generated) |
| **Scalability** | ❌ No | ✅ Yes | ✅ Yes |
| **Success Rate** | Medium | Low | **High** |

### ✅ The Good (Pros)
- **AI-Powered:** Handles complex questions that standard bots fail at.
- **Human-like Interaction:** Uses Playwright to simulate real user behavior, reducing bot detection.
- **Multi-Model Support:** Works with Google Gemini and Groq (Llama 3).
- **Comprehensive Logging:** Track your progress automatically.

### ❌ The Bad (Cons)
- **API Dependency:** Requires a stable internet connection and LLM API keys.
- **Browser Specific:** Currently optimized for Chromium-based flows.
- **Complex UI:** Some highly non-standard application forms might still require manual intervention.

---

## ⚙️ Setup Instructions

### 1. Prerequisites
- Python 3.8 or higher installed.
- A GitHub account.
- API keys for either [Google Gemini](https://aistudio.google.com/app/apikey) or [Groq](https://console.groq.com/keys).

### 2. Installation

Clone the repository:
```bash
git clone https://github.com/shriyashsoni/Job-Automation-agent.git
cd Job-Automation-agent
```

Install dependencies:
```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. API Key & Environment Setup

**CRITICAL: Never share your `.env` file or push it to GitHub.**

1.  Copy the example environment file:
    ```bash
    cp .env.example .env
    ```
2.  Open `.env` and fill in your details:
    - `AI_API_KEY`: Your Gemini or Groq key.
    - `RESUME_PATH`: Path to your resume file (e.g., `resume/my_resume.docx`).
    - `USER_...`: Your personal information for form filling.

### 4. Prepare your Resume
Place your resume in the `resume/` directory. Ensure the path in `.env` matches the filename.

---

## 🏃 How to Run

Execute the main script:
```bash
python src/main.py
```

The agent will launch a browser window, log in (if required), and start the application process.

---

## 📂 Project Structure

- `src/`: Core logic (AI Agent, Browser Manager, Job Searcher).
- `data/`: Stores logs and browser profiles (locally only).
- `resume/`: Place your resumes here.
- `.env`: (Private) Configuration and Secrets.
- `.gitignore`: Ensures private data stays private.

---

## 🤝 Contributing

Contributions are welcome! If you have ideas for new features or find a bug, please open an issue or submit a pull request.

**Please remember to Star the repo! ⭐**

---

## 📜 Disclaimer
This tool is for educational and productivity purposes. Use it responsibly and according to the terms of service of job boards. The authors are not responsible for any misuse.
