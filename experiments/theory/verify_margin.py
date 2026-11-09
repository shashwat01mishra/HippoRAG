"""Toy-graph closed forms for personalized PageRank (PPR), re-derived with sympy and checked against igraph PRPACK.

Toy graph (all statements below are toy-graph results, not claims about the full HippoRAG graph):
  e  shared subject entity;  D  old object entity;  M  new (corrected) object entity;
  n  old passages P_1..P_n, each containing (e, D);  k  new passages Q_1..Q_k, each containing (e, M).
  Passage edges P_i-e, P_i-D, Q_j-e, Q_j-M have weight 1 (HippoRAG's passage->phrase edges).
  Graph A: passage edges only.
  Graph B: plus the relation edges e-D with weight n and e-M with weight k (HippoRAG's count-weighted fact edges:
           one source count per passage carrying the triple, HippoRAG.add_new_edges).
Reset vector r: r_e on e, r_D on D, r_M on M, r_o on EACH old passage, r_m on EACH new passage (sum = 1).
PPR (igraph convention, d = damping = probability of following an edge; HippoRAG uses d = 0.5):
  pi = (1 - d) r + d W^T pi,   W = row-normalised weighted adjacency (undirected).
x = PPR score of one old passage, y = of one new passage (all old passages are symmetric, as are all new ones).

Claims checked
  (1) Graph A, reset on e only:  x = y = d / ((1 + d)(n + k)).
  (2) Graph B, reset on e only:  x = y = d / ((2 + d)(n + k)).
  (3) Graph B margin:  Delta = x - y = 2(1 - d)/(4 - d^2) * [ d (r_D/n - r_M/k) + 2 (r_o - r_m) ];  coefficient of r_e = 0.
  (4) HippoRAG's seed rule divides a phrase's fact score by the number of passages containing it, so with equal
      scores sigma on D and M: r_D = sigma/n, r_M = sigma/k, and the phrase term becomes d*sigma*(1/n^2 - 1/k^2):
      the side with fewer passages gains per passage.

Run from the repo root:  .venv/bin/python experiments/theory/verify_margin.py      (exit 0 iff every check passes)
"""
import itertools
import sys

import igraph as ig
import numpy as np
import sympy as sp

n, k, d = sp.symbols("n k d", positive=True)
r_e, r_D, r_M, r_o, r_m = sp.symbols("r_e r_D r_M r_o r_m", nonnegative=True)
pe, pD, pM, x, y = sp.symbols("pi_e pi_D pi_M x y")


def equations(graph):
    """Balance equations of the symmetry-reduced chain for graph 'A' or 'B'."""
    if graph == "A":
        deg_e, deg_D, deg_M, w_eD, w_eM = n + k, n, k, 0, 0
    else:
        deg_e, deg_D, deg_M, w_eD, w_eM = 2 * (n + k), 2 * n, 2 * k, n, k
    return [
        sp.Eq(pe, (1 - d) * r_e + d * (n * x / 2 + k * y / 2 + pD * w_eD / deg_D + pM * w_eM / deg_M)),
        sp.Eq(pD, (1 - d) * r_D + d * (n * x / 2 + pe * w_eD / deg_e)),
        sp.Eq(pM, (1 - d) * r_M + d * (k * y / 2 + pe * w_eM / deg_e)),
        sp.Eq(x, (1 - d) * r_o + d * (pe / deg_e + pD / deg_D)),
        sp.Eq(y, (1 - d) * r_m + d * (pe / deg_e + pM / deg_M)),
    ]


def solve(graph):
    return sp.solve(equations(graph), [pe, pD, pM, x, y], dict=True)[0]


def full_graph_ppr(graph, nn, kk, dd, reset):
    """igraph PRPACK on the full (unreduced) toy graph. reset = dict of r_e, r_D, r_M, r_o, r_m (per passage)."""
    names = ["e", "D", "M"] + [f"P{i}" for i in range(nn)] + [f"Q{j}" for j in range(kk)]
    idx = {v: i for i, v in enumerate(names)}
    edges, weights = [], []
    for i in range(nn):
        edges += [(idx[f"P{i}"], idx["e"]), (idx[f"P{i}"], idx["D"])]
        weights += [1.0, 1.0]
    for j in range(kk):
        edges += [(idx[f"Q{j}"], idx["e"]), (idx[f"Q{j}"], idx["M"])]
        weights += [1.0, 1.0]
    if graph == "B":
        edges += [(idx["e"], idx["D"]), (idx["e"], idx["M"])]
        weights += [float(nn), float(kk)]
    g = ig.Graph(n=len(names), edges=edges, directed=False)
    g.es["weight"] = weights
    rv = np.zeros(len(names))
    rv[idx["e"]], rv[idx["D"]], rv[idx["M"]] = reset["r_e"], reset["r_D"], reset["r_M"]
    for i in range(nn):
        rv[idx[f"P{i}"]] = reset["r_o"]
    for j in range(kk):
        rv[idx[f"Q{j}"]] = reset["r_m"]
    pr = np.array(g.personalized_pagerank(vertices=range(len(names)), damping=dd, directed=False, weights="weight",
                                          reset=rv.tolist(), implementation="prpack"))
    return pr[[idx[f"P{i}"] for i in range(nn)]], pr[[idx[f"Q{j}"] for j in range(kk)]]


def main():
    ok = True

    def check(label, cond):
        nonlocal ok
        ok &= bool(cond)
        print(f"[{'PASS' if cond else 'FAIL'}] {label}")

    e_only = {r_e: 1, r_D: 0, r_M: 0, r_o: 0, r_m: 0}
    solA, solB = solve("A"), solve("B")
    xA, yA = sp.simplify(solA[x].subs(e_only)), sp.simplify(solA[y].subs(e_only))
    xB, yB = sp.simplify(solB[x].subs(e_only)), sp.simplify(solB[y].subs(e_only))
    print(f"Graph A, reset on e: x = {xA}, y = {yA}")
    print(f"Graph B, reset on e: x = {xB}, y = {yB}")
    check("(1) Graph A: x = y = d/((1+d)(n+k))", sp.simplify(xA - d / ((1 + d) * (n + k))) == 0 and sp.simplify(xA - yA) == 0)
    check("(2) Graph B: x = y = d/((2+d)(n+k))", sp.simplify(xB - d / ((2 + d) * (n + k))) == 0 and sp.simplify(xB - yB) == 0)

    delta_B = sp.simplify(solB[x] - solB[y])
    claimed = 2 * (1 - d) / (4 - d ** 2) * (d * (r_D / n - r_M / k) + 2 * (r_o - r_m))
    print(f"Graph B margin (sympy): Delta = {sp.factor(delta_B)}")
    check("(3) Graph B margin equals 2(1-d)/(4-d^2)[d(r_D/n - r_M/k) + 2(r_o - r_m)]", sp.simplify(delta_B - claimed) == 0)
    check("(3) coefficient of r_e in the Graph B margin is 0", sp.simplify(sp.diff(delta_B, r_e)) == 0)
    delta_A = sp.simplify(solA[x] - solA[y])
    print(f"Graph A margin (sympy, for reference): Delta = {sp.factor(delta_A)}")
    print(f"  coefficient of r_e in the Graph A margin: {sp.simplify(sp.diff(delta_A, r_e))}")

    sigma = sp.symbols("sigma", positive=True)
    seed_rule = sp.simplify(delta_B.subs({r_D: sigma / n, r_M: sigma / k, r_o: 0, r_m: 0}))
    expected = 2 * (1 - d) / (4 - d ** 2) * d * sigma * (1 / n ** 2 - 1 / k ** 2)
    print(f"(4) HippoRAG seed rule, equal phrase scores sigma: Delta = {sp.factor(seed_rule)}")
    check("(4) phrase term = d*sigma*(1/n^2 - 1/k^2) * 2(1-d)/(4-d^2): fewer passages -> larger per-passage score",
          sp.simplify(seed_rule - expected) == 0)

    # Numeric check on the full graph with igraph PRPACK (also validates the symmetry reduction).
    rng = np.random.default_rng(0)
    worst = 0.0
    for graph, nn, kk, dd in itertools.product("AB", (1, 2, 3, 5), (1, 2, 3, 5), (0.3, 0.5, 0.85)):
        for _ in range(5):
            raw = rng.dirichlet(np.ones(5))
            reset = {"r_e": raw[0], "r_D": raw[1], "r_M": raw[2], "r_o": raw[3] / nn, "r_m": raw[4] / kk}  # sums to 1
            px, py = full_graph_ppr(graph, nn, kk, dd, reset)
            sol = solA if graph == "A" else solB
            subs = {n: nn, k: kk, d: dd, r_e: reset["r_e"], r_D: reset["r_D"], r_M: reset["r_M"],
                    r_o: reset["r_o"], r_m: reset["r_m"]}
            sx, sy = float(sol[x].subs(subs)), float(sol[y].subs(subs))
            worst = max(worst, np.abs(px - sx).max(), np.abs(py - sy).max(), np.ptp(px), np.ptp(py))
            if graph == "B":
                worst = max(worst, abs((px[0] - py[0]) - float(claimed.subs(subs))))
    print(f"igraph PRPACK vs sympy on the full toy graph: 480 random resets, max abs deviation = {worst:.2e}")
    check("igraph PRPACK agrees with the closed forms (max abs deviation < 1e-9)", worst < 1e-9)
    print("ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
