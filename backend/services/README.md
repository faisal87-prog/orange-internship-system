# Backend Services

Business logic helpers used by Django apps.

- `weekly_score.py`, `pdf.py`, `analytics.py` — existing domain helpers
- `ai/` — **runtime** OpenAI integration (server-side only)
  - Context assembler
  - AI Prompt Builder (OpenAI call #1)
  - Roadmap Generator (OpenAI call #2)
  - Validator + draft persistence

Weekly Report AI and Final Summary AI are not implemented yet.
