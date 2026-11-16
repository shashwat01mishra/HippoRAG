# Graph statistics: HippoRAG 2 index, MuSiQue (11,656-passage corpus)

Source: `demo/index/hipporag_n500_musique/gpt-4o-mini_text-embedding-3-small/graph.pickle` (APFS clone of `outputs/hipporag_n500_musique/gpt-4o-mini_text-embedding-3-small/graph.pickle`), sha256 `e78fa7e4680fb319…`. Written by `.venv/bin/python demo/run_demo.py --graph_stats` (offline). The graph is undirected (`is_directed() = False`); PPR also runs with `directed=False`.

## Nodes

| type | count |
|---|---|
| entity | 101,544 |
| passage | 11,656 |
| **total** | **113,200** |

## Edges by `edge_kind`

| edge_kind | count |
|---|---|
| fact | 119,456 |
| fact+synonym | 1,181 |
| passage | 146,301 |
| synonym | 55,245 |
| **total** | **322,183** |

## Edges by endpoint types

| endpoints | count |
|---|---|
| chunk – entity | 146,301 |
| entity – entity | 175,882 |

## Degree

| node type | mean degree | median | max |
|---|---|---|---|
| entity | 4.90 | 3 | 1906 |
| passage | 12.55 | 11 | 105 |

Entities linked to exactly one passage (passage edges): 89,430 of 101,544 (88.1%).
