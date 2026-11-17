# Demo runbook: Presentation 2, 18 Nov 2026

What to run in front of the instructor, in order. Everything on the main path is **offline**: no network, no API key, no cost. Run every command from the repo root:

```zsh
cd ~/work/S50/nlp-hipporag
```

Times are measured on this laptop on 17 Nov 2026. Each step lists its fallback, the saved file to show if the command fails.

---

## 1. Code identity (≈ 1 s)

```zsh
git log -1 --oneline
git diff --stat upstream-base -- src main.py
```

- **Point at:** the commit hash on line 1; the second command prints **nothing**. `src/` and `main.py` are byte-identical to upstream HippoRAG 2 (tag `upstream-base`, commit `d5c8329`). All my code is in `experiments/` and `demo/`.
- **Fallback:** `CODE_MAP.md` (what every file does) and `PROGRESS.md` (every launcher logged this diff).

## 2. One question through HippoRAG 2, stage by stage (≈ 0.03 s to start)

```zsh
.venv/bin/python demo/run_demo.py --q 193 --pause
```

Press Enter between stages. Question 193: "Which season was the runner up of the third season of American Idol on?"

| Section | What it shows | Line to point at |
|---|---|---|
| `[1] query -> triple` | the 5 candidate facts, scored by cosine to the question | `1. 1.000  (adam lambert \| was runner up in \| american idol eighth season)`: the best match is the wrong season |
| `[2] recognition-memory filter` | what gpt-4o-mini kept | `5 in -> 2 kept`: it keeps the two season-3 facts and drops the rest |
| `[3] PPR reset vector` | the seed weights | `phrases 2.0% of mass, passages 98.0%`; entity seeds 0.92, 0.91, 0.46, 0.18 |
| `[4] Personalized PageRank` | the top 10 nodes | seed entities on top; hubs such as "united states" also appear |
| `[5] final top 5 passages vs dense top 5` | both top-5 lists, gold marked | two `GOLD American Idol` rows on the HippoRAG side, none on the dense side; `Recall@5: HippoRAG 1.00   dense 0.00` |
| `[6] reader` | the answer next to the gold answer | `answer: Third season.` vs `gold: season three`, `F1 0.50`: right answer, string-match penalty |
| last line | consistency check | `same top 5 as this trace: True`: matches the recorded n = 500 run |

Second example, retrieval works and the reader still fails:

```zsh
.venv/bin/python demo/run_demo.py --q 96
```

- **Point at:** `5. GOLD Modern history` (gold passage retrieved; dense has none), then `answer: The text does not provide a specific example ...` vs `gold: Yamanote Line loop`, `F1 0.15`.
- **Fallback:** open `demo/traces/q193.md` and `demo/traces/q96.md`: the same traces as tables, with every score.

## 3. Reproduction evidence (≈ 1 s)

```zsh
cat results/musique_n500/bootstrap_n500.txt
```

- **Point at:** `Recall@5  62.00  56.10  +5.90  [ +3.73,  +8.00]` and `F1  44.93  40.27  +4.66  [ +1.52,  +7.69]`.
- **How it was made:** line 1 of the file is the command: `experiments/bootstrap_gap.py` resamples the 500 questions 10,000 times (seed 0) and applies each resample to both systems (paired bootstrap). It reads the per-query files `results/musique_n500/{hipporag,dense}_per_query_n500.json`, written by the paid runs on 8 Nov.
- To rerun it live (offline, a few seconds):

```zsh
.venv/bin/python experiments/bootstrap_gap.py --hipporag results/musique_n500/hipporag_per_query_n500.json --dense results/musique_n500/dense_per_query_n500.json --first 500
```

- Precision, if asked: `cat results/musique_n500/precision_at5.txt` (HippoRAG 2 30.12, dense 27.72, perfect retriever 52.52).
- **Fallback:** deck slide 5 and `RESULTS_BRIEF.md` §1.

## 4. Seal check, live (≈ 0.1 s)

The grid's result files were hashed on 9 Nov before anyone looked at them. The hashes are in `PROGRESS.md` (Session 6, "Seal") and copied verbatim into `results/extension/grid_v5_20261109/SEAL.sha256`.

```zsh
(cd outputs/extension/grid_v5_20261109 && shasum -a 256 -c ../../../results/extension/grid_v5_20261109/SEAL.sha256)
```

- **Expect:** 26 lines ending in `: OK` (20 cell files, `cell_stats.jsonl`, 4 long-context files, `vectors.npz`).

Variant that checks the 25 committed `.jsonl` copies in `results/` (works on any clone, without `outputs/`):

```zsh
(cd results/extension/grid_v5_20261109 && grep '\.jsonl$' SEAL.sha256 | sed 's#  results/#  #' | shasum -a 256 -c -)
```

- **Expect:** 25 lines ending in `: OK`.
- Then: `git log -1 --format='%h %ci %s' 460c50a` shows the prediction commit, 16 Nov 18:59 IST, made before any result was opened.
- **Fallback:** show `PROGRESS.md`, Session 8 cont., "Step 5: seal check" (records 26 of 26 matching).

## 5. The analysis reproduces (≈ 3 s)

```zsh
rm -rf /tmp/pb_check
.venv/bin/python experiments/extension/phase_b.py --out /tmp/pb_check
diff /tmp/pb_check/phase_b.md analysis/grid_v5_final/phase_b.md && echo IDENTICAL
```

- **Expect:** `N = 75; wrote /tmp/pb_check/...`, then `IDENTICAL`. The analysis is recomputed from the sealed records and matches the committed file byte for byte.
- **Fallback:** say it was checked on 17 Nov (`PROGRESS.md`, Session 9, Block 0) and open `analysis/grid_v5_final/phase_b.md`.

## 6. Intermediate results to open if asked

| File | What it holds |
|---|---|
| `analysis/grid_v5_final/phase_b.md` | Per-cell funnel (fact a candidate → kept → both kept), filter keep rates, both-kept ties, n = 1 → 3 change, pooled correction@5 and contamination@5 with CIs, fix detail, long-context labels |
| `analysis/grid_v5_final/followup.md` | Interaction CI (−11.0 [−16.7, −6.0]); k = 0 baseline for the old fact; route of retrieved corrections; o′ absent vs present; lost-at-n = 3 table with node degrees; rank distributions (exploratory sections marked) |
| `analysis/grid_v5_final/summary.md` | `analysis.py` output: every metric by arm × n × k × slice, the first-failure attribution table at 4 tolerances, fix collateral drops |
| `demo/traces/q96.md` | Full trace of Q96: candidates, filter, seeds, PPR top 10, both top 5s, reader answer |
| `demo/graph_stats.md` | Graph size: 113,200 nodes (101,544 entity, 11,656 passage), 322,183 edges by kind, degrees |
| `analysis/grid_v5_final/*.png` | `correction_at5.png`, `contamination_at5.png`, `outranks_old.png`, `attribution.png` (all slices) |
| `deck/figs/*.pdf` | The deck's charts: `correction.pdf`, `funnel.pdf`, `route.pdf` (drawn by `deck/make_figs.py` from the analysis files) |
| `paper/figs/*.pdf` | `pipeline.pdf`, `toy_graph.pdf`, `repro_gap.pdf` |
| `RESULTS_BRIEF.md` | Every result in plain language, each number with its source file |

## 7. Optional live tweak (needs Wi-Fi and the key; ≈ 10 s to load the index; ≈ ₹0.03)

Only if the network works and there is time. It reruns retrieval for Q193 on the saved index (`demo/index/`, an APFS clone of the n = 500 index) with a longer random walk and heavier passage seeds:

```zsh
.venv/bin/python demo/run_demo.py --live --q 193 --damping 0.85 --passage_weight 0.5
```

- **Expect:** in `[4]`, the PPR top 10 becomes hub entities (`united states`, `canada`, `australia`, …); in `[5]`, two off-topic passages enter and `Recall@5 1.00 -> 0.50` in the comparison block at the end.
- Cost: one reader call if the top 5 changes, about ₹0.03; add `--no_reader` to make it about ₹0.00 (one query embedding). Recorded in `PROGRESS.md`, Session 8.
- If `demo/index/` is missing: `.venv/bin/python demo/run_demo.py --make_index` (clones `outputs/hipporag_n500_musique`, read-only, a few seconds).
- **Fallback:** don't retry. Say the result is recorded: `PROGRESS.md`, Session 8, steps 2–3 ("Recall@5 1.00 → 0.50; PPR top 10 becomes all hubs").

---

## If something fails

| Failure | Show instead |
|---|---|
| `.venv` broken or Python error | `demo/traces/q193.md`, `demo/traces/q96.md` |
| `outputs/` missing (e.g. another laptop) | the `results/` seal variant in step 4 |
| `/tmp` not writable | `--out` to any other empty directory, e.g. `~/pb_check` |
| projector can't show the terminal | `deck/deck.pdf` slide 2 (verbatim code and Q193 output) |
| network down | everything except step 7 is offline; skip step 7 |
