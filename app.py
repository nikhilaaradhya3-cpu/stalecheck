import html

import pandas as pd
import streamlit as st

from src.pipeline import check_answer

st.set_page_config(page_title="Stale-Answer Detector", page_icon="🕰️", layout="wide")

COLORS = {"SUPPORTED": "#c8f7c5", "OUTDATED": "#ffd6a5", "CONTRADICTED": "#ffadad", "UNVERIFIABLE": "#e0e0e0"}
ICONS = {"SUPPORTED": "🟢", "OUTDATED": "🟠", "CONTRADICTED": "🔴", "UNVERIFIABLE": "⚪"}

SAMPLES = {
    "Dev assistant answer": (
        "Python 3.8 is the latest stable release of Python. For web apps, Next.js 12 is the newest major "
        "version of the framework. OpenAI's most capable model is GPT-3.5, and it is available through the API."
    ),
    "Business answer": (
        "Twitter is led by CEO Jack Dorsey. The US federal minimum wage is $7.25 per hour."
    ),
}

st.title("🕰️ Stale-Answer Detector")
st.caption("Finds outdated claims in LLM answers, re-verifies them on the live web (Tavily), "
           "and scores freshness. All model calls routed through the Bifrost gateway.")

if "text" not in st.session_state:
    st.session_state.text = ""

cols = st.columns(len(SAMPLES) + 1)
for col, (name, txt) in zip(cols, SAMPLES.items()):
    if col.button(f"Load: {name}"):
        st.session_state.text = txt

answer = st.text_area("Paste an AI-generated answer", key="text", height=160)
do_rewrite = st.checkbox("Generate corrected answer", value=True)

if st.button("Check freshness", type="primary", disabled=not answer.strip()):
    with st.spinner("Extracting claims, searching the web, judging..."):
        try:
            res = check_answer(answer, do_rewrite)
        except Exception as e:
            st.error(f"Pipeline failed: {e}")
            st.info("Is Bifrost running (`npx -y @maximhq/bifrost`) and TAVILY_API_KEY set?")
            st.stop()

    claims = res["claims"]
    m1, m2, m3 = st.columns(3)
    m1.metric("Overall trust score", f"{res['trust_score']}/100")
    m2.metric("Claims checked", len(claims))
    m3.metric("Stale / wrong", sum(c["verdict"] in ("OUTDATED", "CONTRADICTED") for c in claims))

    # --- highlighted answer ---
    marked = html.escape(answer)
    for c in claims:
        q = html.escape(c["quote"])
        if q in marked:
            marked = marked.replace(
                q,
                f'<mark style="background:{COLORS.get(c["verdict"], "#eee")};color:#111;padding:2px 4px;'
                f'border-radius:4px">{q}</mark><sup>[{c["id"]}]</sup>',
                1,
            )
    st.subheader("Annotated answer")
    st.markdown(marked.replace("\n", "<br>"), unsafe_allow_html=True)

    # --- claim cards ---
    st.subheader("Claim-by-claim")
    for c in claims:
        with st.expander(f"{ICONS.get(c['verdict'], '⚪')} [{c['id']}] {c['claim']}  —  {c['freshness_score']}/100"):
            st.write(f"**Verdict:** {c['verdict']}  |  **Category:** {c.get('category')}")
            if c.get("current_value"):
                st.write(f"**Current value:** {c['current_value']}")
            st.write(c.get("explanation", ""))
            if c.get("as_of"):
                st.caption(f"Evidence as of: {c['as_of']}")
            for u in c.get("evidence_urls") or []:
                st.markdown(f"- [{u}]({u})")
            if c.get("cached"):
                st.caption("⚡ served from cache")

    if res["corrected"]:
        st.subheader("Corrected answer")
        st.markdown(res["corrected"])

    # --- gateway panel ---
    st.subheader("Bifrost gateway panel")
    df = pd.DataFrame(res["stats"])
    if not df.empty:
        g1, g2, g3 = st.columns(3)
        g1.metric("LLM calls", len(df))
        g2.metric("Total tokens", int(df.prompt_tokens.sum() + df.completion_tokens.sum()))
        g3.metric("Avg latency", f"{df.latency_s.mean():.2f}s")
        st.dataframe(df, use_container_width=True)
        if (df.requested_model != df.served_model).any():
            st.warning("Some calls were served by a different model than requested (gateway fallback/routing).")
