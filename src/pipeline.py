"""Core pipeline: extract claims -> verify on the live web -> score -> rewrite."""
import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date

from . import llm
from .search import search

CACHE_PATH = ".cache.json"
VERDICT_ORDER = ["OUTDATED", "CONTRADICTED", "UNVERIFIABLE", "SUPPORTED"]

EXTRACT_SYSTEM = """You extract checkable factual claims from an AI-generated answer.
Only keep claims that can become STALE or wrong over time: pricing, API/software/model versions,
laws/regulations/rates/deadlines, company facts (leadership, products, funding, policies),
statistics tied to a year, and 'latest/current/newest' style statements.
Skip timeless facts, opinions and vague statements.

Return ONLY JSON:
{"claims":[{"quote":"<exact substring copied from the answer>",
            "claim":"<standalone, self-contained restatement>",
            "category":"pricing|api_version|regulation|company_info|statistic|other",
            "search_query":"<best web search query to verify it right now>"}]}
Maximum 8 claims. If none, return {"claims":[]}."""

JUDGE_SYSTEM = """You are a fact-freshness auditor. Today's date is {today}.
Given ONE claim (from an older AI answer) and fresh web search results, decide:
- SUPPORTED: results confirm the claim is still accurate today
- OUTDATED: the claim was once true but newer information supersedes it
- CONTRADICTED: the claim is simply wrong according to the results
- UNVERIFIABLE: results are insufficient to decide
Use ONLY the provided results, not your own memory.
Return ONLY JSON:
{{"verdict":"...","confidence":0.0-1.0,"current_value":"<what is true now, short, or null>",
"explanation":"<1-2 sentences>","evidence_urls":["<urls you relied on>"],
"as_of":"<date of newest evidence if known, else null>"}}"""

REWRITE_SYSTEM = """Rewrite the answer so it is accurate today. Change ONLY the parts flagged as
OUTDATED or CONTRADICTED, using the provided current values. Keep everything else, including tone and
structure, unchanged. Wrap each changed fragment in **bold**. Return only the rewritten answer."""


# ---------- cache ----------
def _load_cache() -> dict:
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH) as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_cache(cache: dict) -> None:
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f)


def _key(claim: str) -> str:
    return hashlib.sha256((claim + str(date.today())).encode()).hexdigest()


# ---------- stages ----------
def extract_claims(answer: str) -> list[dict]:
    raw = llm.chat(llm.EXTRACT_MODEL, EXTRACT_SYSTEM, answer, stage="extract")
    claims = llm.parse_json(raw).get("claims", [])
    for i, c in enumerate(claims, 1):
        c["id"] = i
    return claims


def verify_claim(claim: dict) -> dict:
    cache = _load_cache()
    k = _key(claim["claim"])
    if k in cache:
        return {**claim, **cache[k], "cached": True}

    results = search(claim.get("search_query") or claim["claim"])
    evidence = "\n\n".join(
        f"[{i}] {r['title']} ({r['url']}) date={r['published_date']}\n{r['content']}"
        for i, r in enumerate(results, 1)
    )
    user = f"CLAIM: {claim['claim']}\n\nSEARCH RESULTS:\n{evidence or 'No results.'}"
    raw = llm.chat(
        llm.JUDGE_MODEL,
        JUDGE_SYSTEM.format(today=date.today().isoformat()),
        user,
        stage="verify",
    )
    verdict = llm.parse_json(raw)
    verdict["verdict"] = str(verdict.get("verdict", "UNVERIFIABLE")).upper()
    verdict["freshness_score"] = freshness_score(verdict, len(results))

    cache = _load_cache()
    cache[k] = verdict
    _save_cache(cache)
    return {**claim, **verdict, "cached": False}


def freshness_score(v: dict, n_results: int) -> int:
    """0 = definitely stale/wrong, 100 = verified current.
    Signed by verdict, scaled by judge confidence, small bonus for corroborating sources."""
    conf = max(0.0, min(1.0, float(v.get("confidence", 0.5) or 0.5)))
    verdict = v["verdict"]
    if verdict == "SUPPORTED":
        score = 50 + 50 * conf
        if len(v.get("evidence_urls") or []) >= 2:
            score = min(100, score + 5)
    elif verdict == "OUTDATED":
        score = 50 - 45 * conf
    elif verdict == "CONTRADICTED":
        score = 50 - 50 * conf
    else:  # UNVERIFIABLE
        score = 50
    if n_results == 0:
        score = min(score, 50)
    return round(score)


def rewrite(answer: str, checked: list[dict]) -> str:
    flagged = [c for c in checked if c["verdict"] in ("OUTDATED", "CONTRADICTED")]
    if not flagged:
        return answer
    notes = "\n".join(
        f"- original: {c['quote']!r} | verdict: {c['verdict']} | current: {c.get('current_value')}"
        for c in flagged
    )
    return llm.chat(
        llm.JUDGE_MODEL,
        REWRITE_SYSTEM,
        f"ANSWER:\n{answer}\n\nFLAGGED CLAIMS:\n{notes}",
        stage="rewrite",
    )


def check_answer(answer: str, do_rewrite: bool = True) -> dict:
    llm.reset_stats()
    claims = extract_claims(answer)
    with ThreadPoolExecutor(max_workers=6) as pool:
        checked = list(pool.map(verify_claim, claims))
    checked.sort(key=lambda c: (VERDICT_ORDER.index(c["verdict"]) if c["verdict"] in VERDICT_ORDER else 9, c["id"]))
    trust = round(sum(c["freshness_score"] for c in checked) / len(checked)) if checked else 100
    corrected = rewrite(answer, checked) if do_rewrite else None
    return {"claims": checked, "trust_score": trust, "corrected": corrected, "stats": list(llm.STATS)}
