Written 16 Nov 2026, before opening any extension result. The picks are mine; the reasons were worded with Claude from the account I chose: the filter is the bottleneck.

1. The filter keeps the correction in 30–60% of questions. Why: the filter is asked about relevance, but gpt-4o-mini partly judges truth, so a counterfactual that clashes with what it knows looks wrong and gets dropped.
2. When both old and new facts are seeded, the result is a near-tie decided by dense similarity. Why: in the symmetric graph every copy gets the same PageRank score, d/((1+d)(n+k)). The correction is a one-entity edit of the old passage, so the passage seeds (0.05 × dense similarity) are nearly equal and decide the order.
3. Main failure stage for HippoRAG: B, the filter. Why: it follows from 1. Most corrections never reach the graph.
4. As stale copies (n) are added, HippoRAG's correction@5 drops slower than dense. Why: in dense retrieval every stale copy competes for a top-5 slot at full strength; in PageRank the copies split the score among themselves.
5. The fix raises correction@5 by +1–5 points and changes unchanged-fact Recall@5 by about 0. Why: the fix only fires when both facts survive the filter, and the filter is the bottleneck. On unchanged facts it rarely fires, because few relations in these questions legitimately carry two values.
6. My account is wrong if the filter keeps the correction in more than 80% of questions, or the fix adds more than 10 points to correction@5.
7. When gpt-4o-mini already knows the old fact, the filter keeps the correction less often. Why: if the filter partly judges truth, a correction that contradicts something it knows is more likely to be dropped.
8. Rare vs common o′: untested (the ≥10 bin has only 9 targets).
