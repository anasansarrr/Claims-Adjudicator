# Backend Deployment & Development Guide

This README walks you through **everything** your Flask backend needs:

* Local development setup
* Environment variables
* Folder structure
* API usage

It’s the full end‑to‑end backend blueprint.

---

## 🚀 Project Overview

This backend is built with **Flask**, exposed via REST APIs, and deployed on **Render**.
It processes claim logic, performs OCR, and communicates with a Postgres database.

The backend is packaged with a production-ready **Gunicorn** server for deployment.

---

## 📁 Folder Structure

```
backend/
├── app.py               # Flask entry point
├── requirements.txt     # Python dependencies
├── processor.py         # Core business logic
├── db_manager.py        # Database layer
├── utils/               # OCR + helpers
├── uploads/             # File uploads (if needed)
└── README.md            # This file
```

---

## 🔧 Local Development Setup

### 1. Create virtual environment

```
python -m venv venv
venv\Scripts\activate         # Windows
```

### 2. Install dependencies

```
pip install -r requirements.txt
```

### 3. Run backend locally

```
python app.py
```

This serves the backend on:

```
http://localhost:5000
```

---

## 🔐 Environment Variables

Create a `.env` file in the root:

```
PORT=5000
GEMINI_API_KEY-(insert you api key)
```


---

## 🌍 API Endpoints

### POST `/api/process-claim`

POST "https://claims-adjudicator.onrender.com/api/process-claim" \
  -F "prescription=@prescription_sample.pdf" \
  -F "medical_bill=@medical_bill_sample.pdf" \
  -F "pharmacy_bill=@pharmacy_bill_sample.pdf" \
  -F "lab_results=@lab_report_sample.pdf" \
  -F "claim_date=2024-10-20"



### REQUIRED: Bind Flask to Render's PORT

Your `app.py` must have:

```python
import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
```

If this is missing, the backend will not start.

---

## ⏳ Handling Render Free Tier Sleep Mode

Render shuts down after 15 minutes of inactivity.

To wake it:

* Hit any endpoint (browser/Postman/curl)
* First request takes **20–40 seconds** (cold start)

Optional: Keep it alive using GitHub Actions cron.

---

