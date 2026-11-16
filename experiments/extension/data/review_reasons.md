# Swap screening: reasons for every keep mark in `review_v5.md`

Criteria (any one gives `n`; if in doubt, `n`; no row kept to protect a frequency bin):
**kind**: o′ is the wrong kind of thing for the slot · **contra**: the swap contradicts the rest of the passage ·
**true**: o′ might actually be true · **chain**: o′ is another entity in the question's chain · **broken**: the sentence is broken.

The "chain" criterion was checked programmatically (o′ against the question text, every hop answer, and the title and text of every other supporting paragraph): 0 hits, so no row is dropped for it.

Reviewer: Claude (Opus 5.5), 2026-11-16, from the swapped passages in `targets_v5.jsonl` and the question chains in `reproduce/dataset/musique.json`. Results were not opened. "Borderline keep" marks a `y` row where world knowledge (not the passage) contradicts o′; these are worth a second look.

| # | target | keep | reason |
|---|---|---|---|
| 1 | 2hop__107601_110222 | y | date for date; false; passage stays consistent |
| 2 | 2hop__108158_83769 | n | broken: "Mike McFarland (Matt Damon) (Ben Affleck)", two actor parentheticals |
| 3 | 2hop__12039_11957 | y | mountain range for mountain range; false; consistent |
| 4 | 2hop__130404_59180 | y | release date for release date; false; consistent |
| 5 | 2hop__131275_72870 | n | kind: Elizabeth Warren was not a 2016 presidential candidate, so she cannot fill "won the state" |
| 6 | 2hop__132929_120537 | y | date for date; false; consistent |
| 7 | 2hop__147212_60904 | n | doubt: "John Smith" is a placeholder name, not a plausible specific owner |
| 8 | 2hop__147260_623159 | y | oblast for oblast; false; consistent (Golden Ring, Lake Nero still fit a reader) |
| 9 | 2hop__158275_35739 | y | month for month; false; consistent |
| 10 | 2hop__159737_27110 | y | date range for date range; false; consistent |
| 11 | 2hop__161151_42429 | y | date for date; false; consistent with Hubertusburg on 15 Feb |
| 12 | 2hop__203437_152093 | n | true: Tooth & Nail was Hawk Nelson's real earlier label, so the swap may read as true |
| 13 | 2hop__207476_625987 | n | contra: passage goes on about "Marie's reign as Queen Mother"; Catherine was not Louis XIII's mother |
| 14 | 2hop__21075_5028 | n | contra: £19,943 + £3,812 = £23,755; £25,000 breaks the sentence's own arithmetic |
| 15 | 2hop__21104_16334 | n | contra: next sentence explains the "genetic similarity between Ashkenazi Jews and Italians" |
| 16 | 2hop__23459_35123 | y | lifespan for lifespan; false; consistent |
| 17 | 2hop__235471_565925 | n | contra: same sentence says "Moby Grape's Columbia albums", then "Columbia's decision" |
| 18 | 2hop__258940_135844 | n | contra: city renamed "Tolyatti" after "Giolitti" (name no longer matches); Giolitti was not a communist |
| 19 | 2hop__263728_705527 | y | borderline keep: Bahadur Shah I predates Qudsia Begum, but the passage does not say so |
| 20 | 2hop__274110_413723 | n | kind: Hampshire is a county; West Berkshire is the district the question asks for |
| 21 | 2hop__30905_189318 | n | true: McCain did attend the US Naval Academy, so the answer to "where did he go to college" becomes true |
| 22 | 2hop__354635_174222 | y | company for company; false; consistent |
| 23 | 2hop__358582_189042 | y | label for label; false; consistent |
| 24 | 2hop__363214_590899 | n | contra: "Los Angeles County ... part of Silicon Valley, in the San Francisco Bay Area" |
| 25 | 2hop__415518_616002 | y | borderline keep: Tony Awards began in 1947, after the 1942 opening; passage does not state award year |
| 26 | 2hop__446324_620302 | y | university for university; false; consistent |
| 27 | 2hop__461639_83837 | n | doubt: Miranda Lambert is a solo star, not "of ... Little Big Town"; the appositive reads false on its face |
| 28 | 2hop__463884_807572 | y | county for county; false; consistent |
| 29 | 2hop__481809_184805 | y | borderline keep: Secretariat (b. 1970) could not sire Alluvial (b. 1969); passage gives no years |
| 30 | 2hop__488811_30110 | n | broken: "expelled by the Poland" |
| 31 | 2hop__494659_5385 | y | count for count; false; consistent |
| 32 | 2hop__51760_122023 | y | school for school; false; consistent |
| 33 | 2hop__547045_131879 | y | river for river; false; consistent |
| 34 | 2hop__559076_55984 | y | songwriter for songwriter; false; consistent |
| 35 | 2hop__56851_343058 | y | director for director; false; consistent |
| 36 | 2hop__574496_123283 | y | school for school; false; consistent |
| 37 | 2hop__636597_480615 | y | city for city; false; consistent |
| 38 | 2hop__645448_77615 | n | true: 1935 is a commonly cited ROTC start date (the closed-book probe itself answered 1935) |
| 39 | 2hop__668407_683671 | n | contra: "late-Tang Dynasty warlord Emperor Taizong of Tang"; Taizong is early Tang |
| 40 | 2hop__685930_110949 | y | date for date; false; consistent |
| 41 | 2hop__695364_513121 | n | doubt: an invented half-brother "David Ainley" may exist among Henry Ainley's children; can't verify false |
| 42 | 2hop__71016_75184 | n | contra: next clause "Wells was not available ... the role was recast" |
| 43 | 2hop__734582_74481 | n | kind/contra: "his father, Sonny Corleone"; Sonny is Michael's brother |
| 44 | 2hop__73615_42173 | n | true: the East India Company's charter is dated 1600 |
| 45 | 2hop__757497_78606 | y | borderline keep: Meryl Streep is not 30 years older than Rob Schneider; passage-consistent |
| 46 | 2hop__781079_9237 | y | month for month; false; consistent |
| 47 | 2hop__794999_113442 | y | date for date; false; consistent |
| 48 | 2hop__810884_22402 | y | university for university; false; consistent |
| 49 | 2hop__814856_110882 | y | date for date; false; consistent |
| 50 | 2hop__829358_754719 | y | state for state; false; consistent |
| 51 | 2hop__860241_766393 | y | prize for prize; false; consistent |
| 52 | 3hop1__103890_10659_67187 | y | person for person; false; the rest of the passage (1926 coup, Mościcki) stays consistent |
| 53 | 3hop1__106845_5188_86687 | y | month for month; false; consistent |
| 54 | 3hop1__128554_39743_24526 | n | contra: "mid 60s–low 70s °F (8–12 °C)"; the Celsius range is 46–54 °F |
| 55 | 3hop1__135794_87694_64412 | y | date for date; false; consistent |
| 56 | 3hop1__146155_131905_41948 | y | water body for water body; false; consistent |
| 57 | 3hop1__278222_42197_18397 | y | party body for party body; false; consistent |
| 58 | 3hop1__497845_629431_124169 | y | year for year; false; consistent |
| 59 | 3hop1__652852_2053_5289 | y | label for label; false; consistent |
| 60 | 3hop1__654651_55349_651302 | n | broken: "Los Angeles, Colorado" |
| 61 | 3hop1__79039_131926_87157 | y | state for state; false; every occurrence swapped, passage self-consistent |
| 62 | 3hop1__857_846_7794 | y | population for population; false; consistent |
| 63 | 3hop1__857_846_7798 | n | contra: "as in most of eastern China ... predominantly Zhuang (98.56 %)"; Zhuang is a minority nationality |
| 64 | 3hop1__9285_5188_63702 | y | month for month; false; consistent |
| 65 | 3hop2__125104_90098_10557 | y | language stage for language stage; false; consistent |
| 66 | 3hop2__49541_140712_51068 | n | kind/broken: "Emma Watson ... professionally known as Jenna Coleman"; alias slot filled by another real actress |
| 67 | 4hop1__567737_141375_458768_33632 | n | true: Saint Monica's current feast day is 27 August (the probe also answered it) |
| 68 | 4hop1__58323_375563_161848_53331 | y | year for year; false; consistent |
| 69 | 4hop1__58323_375563_161848_83118 | y | date rule for date rule; false; consistent |
| 70 | 4hop2__161324_14670_8987_8529 | n | true: "Hej Slaveni" as Yugoslav anthem is often dated 1945–1991/92 |
| 71 | 4hop2__161602_426860_88460_126088 | n | kind/broken: "president and former military commander Naypyidaw's mayor" |
| 72 | 4hop2__9988_261673_70784_79935 | n | contra: "between 1902 and 1927 ... wars ... resulted in establishing the Kingdom in 1925" |
| 73 | 2hop__107548_124896 | n | contra: "by his second wife, Anne (Cooke) Bacon"; the father must be a Bacon |
| 74 | 2hop__123214_22402 | y | university for university; false; consistent |
| 75 | 2hop__128342_375952 | y | county for county; false; consistent |
| 76 | 2hop__142699_67465 | y | date for date; false; consistent |
| 77 | 2hop__16844_20510 | n | true: the Company was formed in 1599 (charter 1600), so "1599" reads as true |
| 78 | 2hop__238499_431914 | y | department for department; false; consistent |
| 79 | 2hop__249867_557232 | y | county for county; false; consistent |
| 80 | 2hop__29893_29898 | y | city for city; false; consistent |
| 81 | 2hop__32887_578772 | n | contra: passage gives the Chinese character and pinyin first and calls it "the surname" in three languages |
| 82 | 2hop__351275_75487 | n | true: Rona Ambrose did lead the party (interim, 2015–17) |
| 83 | 2hop__35445_22458 | y | body for body; false; consistent |
| 84 | 2hop__455158_247871 | y | county for county; false; consistent |
| 85 | 2hop__478978_124498 | n | doubt: "son of Jean-Jacques Goldman ... grandson of Andrée Chedid" breaks the surname line |
| 86 | 2hop__496792_392646 | n | broken/contra: "a Irish clan"; chief is the (Scottish) Earl of Huntly |
| 87 | 2hop__581084_828685 | y | university for university; false; consistent |
| 88 | 2hop__58168_1783 | n | true: Walker was re-elected in Nov 1929, after the crash |
| 89 | 2hop__59133_512508 | n | broken: Tube Alloys "merged with the American British Tube Alloys Program" |
| 90 | 2hop__61714_89309 | y | date for date; false; consistent |
| 91 | 2hop__632234_122868 | y | borderline keep: SFU opened in 1965 and "The Ubyssey" is UBC's paper; a reader might not know |
| 92 | 2hop__635185_141338 | n | contra: "public college in Brooklyn, New York City ... part of UCLA" |
| 93 | 2hop__645367_68633 | y | person for person; false; consistent |
| 94 | 2hop__66167_72467 | y | team for team; false; consistent |
| 95 | 2hop__678516_179720 | y | painter for painter; false; consistent |
| 96 | 2hop__6827_49664 | y | bank for bank; false; consistent |
| 97 | 2hop__683835_709167 | n | broken: "won an BAFTA Award" |
| 98 | 2hop__731584_700117 | y | county for county; false; consistent |
| 99 | 2hop__742831_156034 | y | bay for bay; false; consistent |
| 100 | 2hop__75207_365216 | n | contra: "Biobío Province of Chile's Maule Region" |
| 101 | 2hop__771477_149987 | n | contra: Greek etymology, Argive heroes, Theban war, "Thebaid" |
| 102 | 2hop__81682_707195 | n | true: Port Jackson is Sydney Harbour |
| 103 | 2hop__817096_15463 | y | company for company; false; consistent |
| 104 | 2hop__826864_17335 | y | year for year; false; consistent |
| 105 | 2hop__865961_159109 | n | contra: "Indian Ocean ... Macaronesia, with the Azores, Canary Islands, Madeira" |
| 106 | 2hop__96177_62765 | n | contra/kind: Pharaoh is a title; Yul Brynner plays Rameses and Hardwicke plays Sethi in the same list |
| 107 | 2hop__96411_159054 | y | author for author; false; consistent |
| 108 | 2hop__96812_130869 | n | contra: "New York City, located on the National Mall ... Constitution Avenue NW" |
| 109 | 3hop1__103890_10659_83548 | y | borderline keep: Mazowiecki was a Solidarity adviser, not its founding leader |
| 110 | 3hop1__108062_720914_27537 | n | kind: a papal conclave to succeed Pius XII is held in Rome, so "Madrid" cannot fill the slot |
| 111 | 3hop1__131820_59747_43101 | y | date for date; false; consistent |
| 112 | 3hop1__17192_78396_54865 | y | borderline keep: 1754 vs the 1607–1783 span; not a direct contradiction |
| 113 | 3hop1__398232_326948_59893 | y | year for year; false; consistent |
| 114 | 3hop1__423001_503371_21711 | y | borderline keep: construction began c. 1400; "14th century" is wrong but close |
| 115 | 3hop1__71549_486583_84283 | y | owner for owner; false; consistent |
| 116 | 3hop2__87184_90327_76291 | y | month for month; false; consistent |
| 117 | 4hop1__37608_32392_823060_610794 | y | county for county; false; consistent |
| 118 | 4hop1__696484_49925_13759_736921 | y | state for state; false; consistent |
| 119 | 4hop1__88342_49853_128008_89859 | y | date for date; false; consistent |
| 120 | 4hop3__601548_836463_161616_77103 | y | year for year; false; consistent |

## Spot-check sample (10 rows, `random.Random(0).sample(range(1, 121), 10)`, drawn from all 120 rows, y and n alike)

Rows 6, 34, 50, 52, 54, 63, 66, 98, 109, 114. Check each against the swapped passage in `review_v5.md`; if you disagree with any, flip its mark in `review_v5.md` and here, then rerun `finalize_targets.py`.

## Result of `finalize_targets.py` (2026-11-16)

Source: stdout of `.venv/bin/python experiments/extension/finalize_targets.py`; output file `experiments/extension/data/targets_final.jsonl`.

- marked n: 45; final: 75 (groups: 0 → 73, 1 → 2)
- o′ frequency: 0 (absent) 39 · 1–9 27 · ≥10 9 → split **not** used (≥10 bin < 15)
- model_knows_o: no 44 · yes 31 → split **used**
- o′ freq × knows o: absent/no 22 · absent/yes 17 · 1–9/no 18 · 1–9/yes 9 · ≥10/no 4 · ≥10/yes 5
