# translator eval

Functional, **language-agnostic** evaluation for the **`@code-translator`** agent.

You can't unit-test an LLM translator by string-matching — there are many valid
translations. So this harness tests it the only objective way: **translate a reference
solution, run the translated program against known input/output vectors, and compare.**
LeetCode-style problems with deterministic I/O make that possible.

We also can't install every toolchain, and the agent is meant to be language-agnostic (it
searches docs at run time). So the harness **auto-detects which toolchains are present** and
degrades gracefully:

- target language **with** a runtime here → **VERIFIED** — compile/run the translated output, check vectors.
- target language **without** a runtime here → **SHOWCASED** — translate + assert it cited docs and emitted code; the run is skipped (and labeled).

That's the whole point: prove correctness where we can run it, and demonstrate the breadth
everywhere else.

## Two tiers

| | command | LLM? | deterministic | where |
|---|---|---|---|---|
| **Tier 1 — corpus check** | `python3 tests/translator_eval/eval.py` | no | yes | **CI** + locally |
| **Tier 2 — live translation eval** | `python3 tests/translator_eval/eval.py --live --from python --to all` | yes | no | on-demand |

- **`--check`** runs every reference solution against its vectors, for every language whose
  toolchain is present. Zero LLM cost, so it gates in CI. It prints which languages it
  **verified** and which it skipped for lack of a toolchain.
- **`--live --from <lang> --to <lang,...|all>`** invokes `@code-translator` to translate each
  `reference[from]` into each target, then VERIFIES (runs) where a toolchain exists or
  SHOWCASES (docs cited + code emitted) where it doesn't. Needs the `claude` CLI (and
  Context7 MCP + network for the agent's gather step); **costs tokens** — run deliberately.

## The plain-text I/O contract (why not JSON)

JSON is native in Python/Ruby/JS but **C++, Java, and COBOL have no standard-library JSON** —
which would block exactly the languages we want to cover. So every program uses a
**language-neutral plain-text protocol**: read input from **stdin** as text, write the answer
to **stdout** as text. The harness compares after normalizing (rstrip each line, drop trailing
blank lines). Trivial in any language; no third-party parsers.

## Languages

- **Verified by execution** (reference solutions in the corpus, run on every `--check`):
  **Python, Ruby, JavaScript, Java, C++.**
- **Declared for `--live` showcase** (run when a toolchain is present — e.g. on CI or your
  machine — otherwise showcased): **Go, PHP, Rust, C#, COBOL, Kotlin.** Add more in the
  `LANGS` map in `eval.py` (filename + optional build step + run step + the binary to detect).

## Corpus

10 problems × the 5 verified languages: fizzbuzz, reverse-string, valid-palindrome,
binary-search, fibonacci, valid-parentheses, max-subarray, roman-to-int, single-number,
two-sum. Each `problems/<slug>/`:

- `spec.json` — `{ "title", "description", "io", "cases": [ {"stdin", "stdout"}, ... ] }`
  (≥ 6 cases incl edge cases; unique deterministic answer per input).
- `reference/{solution.py, solution.rb, solution.js, Solution.java, solution.cpp}` — each reads
  stdin and writes stdout per the contract, standard library only.

## Adding a problem

1. `problems/<slug>/spec.json` with ≥ 6 `{stdin, stdout}` cases (include edge cases).
2. Reference solutions for the verified languages, obeying the stdin→stdout text contract.
3. `python3 tests/translator_eval/eval.py` — every reference case-run must pass before the
   problem is real. Then `--live` translates it as part of the eval.
