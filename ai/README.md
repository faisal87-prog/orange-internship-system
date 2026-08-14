# AI Module

> **Runtime note:** Live OpenAI integration is implemented in
> `backend/services/ai/` (Django server-side only).
> This repository-root `ai/` folder remains documentation/scaffolding only
> and is **not** executed by Django.

AI integration layer for roadmap generation, weekly reports, and final summaries.

Every AI feature uses a **two-stage architecture**: Prompt Builder (Stage 1) then AI Generation (Stage 2).

## Architecture

```
Mentor Input
     ↓
Django Collects Data (context assembler)
     ↓
AI Prompt Builder          (Stage 1 — OpenAI)
     ↓
Generated Prompt
     ↓
OpenAI Roadmap Generator   (Stage 2)
     ↓
Structured JSON
     ↓
Validation
     ↓
Draft
     ↓
Mentor Review & Approval
```

## Rules

- Called only from Django backend
- OpenAI API key never exposed to frontend
- Invalid structured output: retry once; timeout: manual retry only
- Weekly Report AI and Final Summary AI are not implemented yet
