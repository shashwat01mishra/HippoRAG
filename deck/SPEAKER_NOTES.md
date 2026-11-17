# Speaker notes: Presentation 2 (18 Nov 2026; 10 min talk + 5 min questions)

Build: `.venv/bin/python deck/make_figs.py && cd deck && tectonic -X compile deck.tex`. Demo commands: `DEMO_RUNBOOK.md`.

**Timing (limit 10:00).** 1 title 0:20 · 2 code 1:00 · 3 motivation 0:30 · 4 demo 1:30 · 5 reproduction 0:45 · 6 theory 1:00 · 7 design 0:45 · 8 stale copies 1:15 · 9 last-hop 0:45 · 10 fix 0:45 · 11 prediction 0:45 · 12 limits 0:20. Total 9:40, leaving 20 s spare.

Slides 9, 10 and the open question on slide 12 use **exploratory** analyses (not in `notes/prediction.md`). Say so.

**Source letters** (every number on a slide has one):
R = `results/musique_n500/bootstrap_n500.txt` · PR = `results/musique_n500/precision_at5.txt` · S = `analysis/grid_v5_final/summary.md` · U = `analysis/grid_v5_final/followup.md` · B = `analysis/grid_v5_final/bootstrap.csv` · P = `analysis/grid_v5_final/phase_b.md` · G = `demo/graph_stats.md` · Q = `demo/traces/q193.md` · L = `PROGRESS.md` · F = `experiments/extension/data/review_reasons.md` · N = `notes/paper_todo.md`

Metric name: always **correction@5** (a corrected passage is in the top 5). It is a hit rate; never call it "correction recall".

---

## 1. Title (0:20)
- The claim: two extra stale copies of an old fact cost HippoRAG 2 11.7 points of correction@5, and cost dense retrieval 0.7 (P; U §1).

## 2. The code (1:00)
- Top: the two overrides in `experiments/extension/attrib_rag.py`. `rerank_facts` (line 76) records the 5 candidate facts and what the filter kept, then calls upstream unchanged (`super()`), then applies the fix if it is switched on. `run_ppr` (line 96) records the reset vector and the PageRank output, then calls upstream unchanged. That is how I see every stage while `src/` stays byte-identical to upstream.
- Bottom: six verbatim lines of the Q193 replay. The filter keeps 2 of 5 facts; entity seeds are 2.0 % of the reset mass, passages 98.0 %; both gold passages are in HippoRAG 2's top 5; Recall@5 1.00 vs 0.00 for dense (Q).
- The fix is the `if self.apply_fix:` branch: `drop_superseded` keeps the newer of two kept facts with the same subject and relation.

## 3. Memory must be corrected, not just grow (0:30)
- The paper's §6.3, "Robustness to Corpus Expansion", only adds passages; it never changes a fact (confirmed against the arXiv HTML, 17 Nov; N).
- A memory also has to handle a changed fact while the old passage, and copies of it, stay indexed.

## 4. LIVE DEMO (1:30)
- `.venv/bin/python demo/run_demo.py --q 193 --pause` (offline replay, about 0.03 s to start; Enter between stages). Walk: 5 candidate triples → filter keeps 2 → seed weights → PageRank top 10 → both top-5 lists with gold marked → reader "Third season." vs gold "season three", F1 0.50 (Q).
- Index: 11,656 passages, 101,544 entities, 322,183 edges (G).
- Only if Wi-Fi and time allow: the live tweak in `DEMO_RUNBOOK.md` (Recall@5 1.00 → 0.50; L). Otherwise skip it.

## 5. The reproduction holds (0:45)
- Recall@5 62.00 vs 56.10: +5.90 [+3.73, +8.00]. F1 44.93 vs 40.27: +4.66 [+1.52, +7.69] (R).
- The paper's gpt-4o-mini gaps, +4.5 and +3.3, fall inside both intervals (`RESULTS_BRIEF.md` §1). I reproduce the gap, not the absolute numbers: different embedder.

## 6. Theory predicted it; the data tested it (1:00)
- Toy model, graph A (passage edges only; L, Session 7): x − y = [2(1−d)/(2−d²)]·[(r_o − r_m) + d(r_D/n − r_M/k)]. The subject's seed does not appear: it cancels. Old versus new is decided by the passage seeds (r_o, r_m) and the object seeds (r_D, r_M). With fact edges (graph B, the paper's Proposition 2) the constants change, the terms do not.
- The data: the object-seed term is mostly absent, because the corrected fact is a candidate in only 9 of 75 questions (P). In the 35 records lost at n = 3, the PageRank margin has the same sign as the cosine margin in 34, ρ = +0.91; against node degree, ρ = +0.14 (U §3).
- So in practice the passage-seed term decides. (Passage seeds are 0.05 × dense similarity, which is why the PageRank order follows cosine.)

## 7. Design (0:45)
- One swap per gold passage; 75 of 120 kept after two screening passes (F). Grid n ∈ {1, 3} old copies × k ∈ {0, 1, 2, 3, 5} corrections; dense on the same index as the control.
- Blind: results sealed by sha256 on 9 Nov; prediction committed `460c50a`, 16 Nov 18:59 IST; seal re-checked 26 of 26 before opening (L).

## 8. Stale copies hurt the graph, not dense (1:15) — lead result
- 1 → 3 old copies: HippoRAG 2 −11.7 points [−17.0, −6.7], dense −0.7 [−1.7, 0.0]; interaction −11.0 [−16.7, −6.0]; HippoRAG 2 worse for 18 questions, better for 0 (U §1).
- Baseline before any correction (k = 0, n = 1): the original passage is in the top 5 for 0.57 (HippoRAG 2) vs 0.36 (dense) (S).
- Overall correction@5: 41.5 % vs 39.0 %, +2.5 [−6.7, +11.3]: no reliable difference (P).
- correction@5 is a hit rate. The precision-type number in the extension is contamination@5, stale passages in the top 5, as a count.
- This was prediction item 4; I predicted the opposite.

## 9. The last-hop fact is rarely a seed, old or new (0:45) — exploratory
- Funnel at n = 1, k = 1: 75 → 9 → 8 → 7 (P). Before any correction the old fact is a candidate for 9 of 75 too (U §2): "not a candidate" is the normal state. Without its fact, the old passage is still retrieved for 34 of 66 (U §2).

## 10. The fix acts at the seed stage; corrections don't (0:45) — exploratory route
- 249 retrieved corrections: 71 via a candidate fact, 114 via their own passage seed (also in the dense top 5), 64 lifted by graph spread (U §2).
- The fix: +0.2 points [0.0, +0.5]; it fires for 7 questions, removing the old seed in 7 of 7; contamination@5 at n = 3, k = 5: 0.61 → 0.41 (P, B).

## 11. Prediction committed 460c50a (0:45)
- 5 misses, 1 hit (`RESULTS_BRIEF.md` §2). Falsifier: wrong if the filter keeps more than 80 %; it kept 8 of 9, 89 % (P). Caveat: 9 questions.

## 12. Limits and next (0:20)
- 9 and 7 questions carry the filter and fix results; no dates on passages; exact-duplicate copies; N = 75; one dataset, one LLM.
- Next: widen the candidate step from 5 to 20.

---

## Backup slides
- **How HippoRAG 2 differs / MemoryAgentBench.** Hu, Wang & McAuley 2025 (arXiv 2507.05257), v1 Table 2, conflict resolution: HippoRAG-v2 54.0 vs NV-Embed-v2 55.0 single-hop, 5.0 vs 6.0 multi-hop. In the latest version (v4) the category is called "Selective Forgetting" and NV-Embed-v2 has no row. It neither attributes failures to stages nor varies stale copies (N). Other rows are qualitative.
- **Recall@5 is not precision@5.** First 500 questions: 269 have 2 gold passages, 149 have 3, 82 have 4, so a perfect retriever's precision@5 is 52.52; per question, precision@5 = recall@5 × (gold ÷ 5). HippoRAG 2 30.12, dense 27.72 (PR). Contamination@5 at k = 0, n = 3: 1.43 vs 0.99 (S).
- **PPR maths.** d = 0.5 (`src/hipporag/utils/config_utils.py:192`); mean walk d/(1−d): 1 step at 0.5, 5.7 at 0.85. Reset split 2.0 % / 98.0 % (Q).
- **Metric definitions.** `experiments/extension/analysis.py:44–68`.
- **Cost.** ₹17.41 and ₹36.44 actual key usage; ₹3.60, ₹33.29, ₹0.03 estimates at list × 1.1 (L).
- **Where the correction sits** (exploratory, U §4). Retrieved at n = 1: rank 1 in 9 of 142 (HippoRAG 2) vs 49 of 118 (dense); move down 3+ ranks when copies are added: 30 vs 0; lost: 35 vs 2.
- **Long-context reader** (P). Answers o′ / o / neither: (1,1) 7 / 41 / 27; (1,5) 26 / 19 / 30; (3,1) 1 / 43 / 31; (3,5) 16 / 32 / 26.
