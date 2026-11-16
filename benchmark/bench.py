"""Measure detection accuracy. Verify/extend benchmark/cases.json labels yourself before reporting numbers."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.pipeline import check_answer  # noqa: E402

cases = json.loads((Path(__file__).parent / "cases.json").read_text())
tp = fp = tn = fn = 0
rows = []
for case in cases:
    res = check_answer(case["answer"], do_rewrite=False)
    pred = any(c["verdict"] in ("OUTDATED", "CONTRADICTED") for c in res["claims"])
    truth = case["has_stale"]
    tp += pred and truth
    fp += pred and not truth
    tn += (not pred) and (not truth)
    fn += (not pred) and truth
    rows.append({"answer": case["answer"][:60], "truth": truth, "pred": pred, "trust": res["trust_score"]})
    print(rows[-1])

n = len(cases)
print(f"\nAccuracy {(tp + tn) / n:.0%} | Precision {tp / max(tp + fp, 1):.0%} | Recall {tp / max(tp + fn, 1):.0%}")
Path(__file__).with_name("results.json").write_text(json.dumps(rows, indent=2))
