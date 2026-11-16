# 🕰️ Stale-Answer Detector

Detects outdated information in LLM-generated answers (pricing, API versions, regulations, company info),
re-verifies each claim against the **live web using Tavily**, and returns a **freshness score** per claim.
Every LLM call is routed through the **Bifrost** gateway.

## Problem
LLMs state outdated facts with full confidence. Users can't tell which sentences of an answer are still true.

## How it works
1. **Extract** atomic, time-sensitive claims (LLM via Bifrost, cheap model)
2. **Verify** each claim in parallel: Tavily search -> LLM judge (stronger model via Bifrost)
3. **Score** 0-100 freshness from verdict x confidence x source corroboration
4. **Rewrite** the answer with only stale parts corrected (changes in bold)
5. **UI**: annotated answer, per-claim evidence, gateway panel (tokens, latency, model actually served)

## Run
```bash
# 1. Gateway
npx -y @maximhq/bifrost          # open http://localhost:8080, add your provider key(s)

# 2. App
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env              # add TAVILY_API_KEY
streamlit run app.py

# 3. Benchmark
python benchmark/bench.py
```

## AI usage (per hackathon rules)
- LLMs (via Bifrost): claim extraction, claim verification judgement, corrected-answer rewrite
- Tavily: real-time web retrieval
- Built with AI-assisted coding (Claude)

## Tech
Python, Streamlit, OpenAI SDK (pointed at Bifrost), Tavily API.
