# Viva: the 30 hardest questions

Answer each one aloud before opening `VIVA_ANSWERS.md`. The "predict before you run" questions (28–30) need a terminal: write your prediction down first, then run the command.

## A. The paper (HippoRAG 2)

1. In one minute: what does HippoRAG 2 do at index time and at query time, and what is different from HippoRAG 1?
2. Why does HippoRAG 2 match the query against whole triples instead of extracting entities from the query?
3. What is the "recognition memory" filter, what exactly goes in and comes out, and what happens when it keeps nothing?
4. Passage nodes get a seed of dense score × 0.05. Why seed passages at all, and why such a small weight?
5. The paper calls this "non-parametric continual learning". What does its continual-learning experiment actually test, and what does it leave out?
6. HippoRAG 2 is built from Llama-3.3-70B and NV-Embed-v2 in the paper. Which of its claims could fail to transfer to gpt-4o-mini and text-embedding-3-small?

## B. PageRank maths

7. Write the Personalized PageRank equation HippoRAG 2 solves. What do the reset vector and the damping factor mean, and what convention does igraph use for damping?
8. What is the expected number of steps before a reset at damping 0.5 and at 0.85? What does that imply about how far relevance spreads?
9. The graph is run undirected. What does that do to high-degree nodes such as "united states"?
10. An entity's seed weight is divided by the number of passages that contain it. Why, and which line does it?
11. In the toy graph, why do old and new passages tie when only the shared subject is seeded, whatever n and k are?
12. In your demo trace, entity seeds are about 2 % of the reset mass, yet entities fill the PPR top 10. How can both be true?

## C. The reproduction

13. Your Recall@5 is 62.0; the paper reports 74.7. Why is that a reproduction?
14. How do you know the HippoRAG-vs-dense comparison isolates the graph and not the embeddings?
15. What is a paired bootstrap, why paired, and what would change if you resampled the two systems independently?
16. You evaluated the first 500 questions, not a random 500, and not all 1,000. What does that do to your claim?
17. You did not run OpenIE yourself. What are you trusting, and how could that be wrong?
18. Reruns are not bit-identical. Where does the non-determinism come from and how did the extension avoid it?

## D. The extension

19. State the result of the extension in two sentences, with numbers.
20. You predicted the filter was the bottleneck. It was not. What did the results show instead, and why did you get it wrong?
21. The first-failure attribution labels every failure "not a candidate". Why is that label not a failure mode at all, and what is the effect that actually separates HippoRAG 2 from dense?
22. Your fix changes correction@5 by +0.2 points. Is the fix useless?
23. Detection in your fix is an oracle. What does that mean, and what would break outside this protocol?
24. Nothing in an injected passage says it is newer. So in what sense is it a "correction", and how does that affect the long-context result?
25. 45 of 120 swaps were dropped by an LLM reviewer after the grid had run. Why is that not p-hacking?

## E. The code

26. You claim `src/` is untouched, yet you record internal stages of retrieval. How?
27. How do you know your tracer returns the same ranking as upstream `retrieve()`?
28. **Predict before you run.** `.venv/bin/python demo/run_demo.py --live --no_reader --q 193 --damping 0.85`. Before running: which nodes will top the PPR list, and will Recall@5 (now 1.00) go up, down or stay?
29. **Predict before you run.** `.venv/bin/python demo/run_demo.py --live --no_reader --q 96 --passage_weight 0`. Before running: what happens to the reset-mass split, and does the top 5 change much?
30. **Predict before you run.** `.venv/bin/python demo/run_demo.py --live --no_reader --q 193 --passage_weight 0.5`. Before running: the entity seeds are unchanged. Do entities still lead the PPR top 10?

## F. "Did you write this?"

31. Which parts of this project did an AI assistant write, and which decisions were yours?
32. Open `experiments/extension/attrib_rag.py`. Explain `drop_superseded` line by line.
33. The swap screening was done by Claude. Why should I trust the 75?
34. If I delete `analysis/` and `demo/traces/`, what exactly do you run to get every number on your slides back, and what does it cost?

(34 questions: the 30 hardest plus 4 on authorship, since those will come first.)
