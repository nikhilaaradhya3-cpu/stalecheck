# 🕰️ StaleCheck: Is Your AI's Answer Still True?

> Finds outdated claims in LLM-generated answers, re-verifies them on the live web, and gives every claim a freshness score.

Built by **Team gentech** for the **Geek Room Global AI Hackathon 2026**, Problem Statement 06: *Stale-Answer Detector for AI Applications* (Tavily + Bifrost).

## The problem
LLMs state outdated facts with full confidence: old pricing, superseded API versions, changed regulations, former leaders. Users cannot tell which parts of an answer are still true.

## What it does
1. **Claim identification:** extracts time-sensitive factual claims from an AI answer
2. **Freshness detection:** flags claims that may have gone stale (pricing, versions, laws, leadership, "latest" statements)
3. **Live verification:** re-checks each claim against current web sources using **Tavily**
4. **Freshness scoring:** a 0-100 score per claim from the verdict, the judge's confidence and source agreement
5. **Correction:** rewrites the answer, changing only the stale parts (shown in bold)

Each verdict is one of **SUPPORTED**, **OUTDATED**, **CONTRADICTED** or **UNVERIFIABLE**, with the current value, an explanation, an as-of date and links to the sources. If the evidence is not enough, the app says so instead of guessing.

## Example run
Input: *"Python 3.8 is the latest stable release of Python. For web apps, Next.js 12 is the newest major version of the framework. OpenAI's most capable model is GPT-3.5, and it is available through the API."*

| Claim | Verdict | Freshness |
|---|---|---|
| Python 3.8 is the latest stable release | OUTDATED (current: Python 3.15) | 5/100 |
| OpenAI's most capable model is GPT-3.5 | CONTRADICTED (current: GPT-6.2 Astra) | 0/100 |
| Next.js 12 is the newest major version | UNVERIFIABLE (search results did not cover it) | 50/100 |

The app also shows an annotated answer, a corrected answer, and a gateway panel with every model call (tokens, latency, model served).

## Architecture
```
AI answer -> Claim extractor -> Tavily search (per claim, in parallel) -> LLM judge
          -> Freshness score -> Annotated answer + corrected answer + gateway panel
          (every LLM call goes through Bifrost)
```

## How Tavily and Bifrost are used
| Tool | Role |
|---|---|
| **Tavily** | Live evidence retrieval for every claim, so verdicts rest on current sources instead of model memory |
| **Bifrost** | Gateway for all LLM calls: one OpenAI-compatible endpoint, a cheap model for extraction and a stronger one for judging, virtual-key access control, optional provider fallbacks, and per-call token and latency telemetry shown in the UI |

## Run it locally

**1. Start the Bifrost gateway**
```bash
set BIFROST_SETUP_TOKEN=your-setup-token      # Windows (use export on Mac/Linux)
npx -y @maximhq/bifrost                       # dashboard at http://localhost:8080
```
In the Bifrost dashboard: create the admin account (using your setup token), add a provider key under *Model Providers* (for example a free Gemini key from Google AI Studio), then create a **virtual key** that allows that provider.

**2. Install and configure**
```bash
pip install -r requirements.txt
cp .env.example .env        # on Windows: copy .env.example .env
```
Edit `.env`:
```
TAVILY_API_KEY=your-tavily-key
TAVILY_DEPTH=basic
BIFROST_BASE_URL=http://localhost:8080/v1
BIFROST_VIRTUAL_KEY=your-bifrost-virtual-key
EXTRACT_MODEL=gemini/gemini-3.5-flash-lite
JUDGE_MODEL=gemini/gemini-3.5-flash-lite
```
Models use Bifrost's `provider/model` format. Use any model your Bifrost provider supports.

**3. Launch the app**
```bash
python -m streamlit run app.py
```
Open the page, click one of the sample answers or paste your own, and press **Check freshness**.

**4. (Optional) Run the benchmark**
```bash
python benchmark/bench.py
```

## Project structure
```
app.py                Streamlit UI
src/llm.py            Bifrost client, retries, per-call telemetry
src/search.py         Tavily search wrapper
src/pipeline.py       extract -> verify -> score -> rewrite
benchmark/            labelled test answers and evaluation script
```

## AI usage
- LLMs, called through Bifrost, for claim extraction, evidence-based judging and answer correction
- Tavily for real-time web retrieval
- The judge is instructed to use only the retrieved evidence and to report "unknown" instead of guessing
- Built with AI-assisted coding (Claude)

## Limitations
- Verdict quality depends on what the search retrieves, so some claims come back UNVERIFIABLE
- Free-tier model limits can slow large batches
- Freshness scores are a transparent heuristic, not a probability

## Tech stack
Python · Streamlit · OpenAI SDK (pointed at Bifrost) · Tavily API · Bifrost AI gateway

## Team
**Team gentech:** Nikhil D P (lead), Manya S M, Aishwarya V, Monisha M