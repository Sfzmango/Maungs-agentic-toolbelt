# Sample live run — `@code-translator` translation eval

A captured, point-in-time run of the **`--live`** tier (translate a reference solution →
**run the output against the vectors**). It is illustrative, not a reproducible gate — the
deterministic gate is `--check` (see [`README.md`](./README.md)). Re-run with:

```bash
python3 tests/translator_eval/eval.py --live --from python --to ruby,cpp,java,go,csharp
```

## Results — source = Python (`two-sum`, `reverse-string`)

| Problem | Target | Status | Vectors | Docs gathered |
|---|---|---|---|---|
| two-sum | Ruby | **VERIFIED** | 8/8 ran & passed | ruby-lang.org — IO, String, Hash |
| two-sum | C++ | **VERIFIED** | 8/8 ran & passed | cppreference / cplusplus — `unordered_map`, `getline` |
| two-sum | Java | **VERIFIED** | 8/8 ran & passed | oracle javase — `BufferedReader`, `HashMap` |
| reverse-string | C++ | **VERIFIED** | 8/8 ran & passed | cppreference — `std::reverse`, `istreambuf_iterator` |
| two-sum | Go | SHOWCASED | run skipped (no toolchain) | pkg.go.dev — `bufio`, `strings`, `strconv` |
| two-sum | C# | SHOWCASED | run skipped (no toolchain) | learn.microsoft.com — `Console`, `Dictionary` |

**4 verified by execution (Ruby, C++ ×2, Java); 2 showcased (Go, C#)** — the harness's
graceful degradation: it compiles + runs where a toolchain exists, and translates + asserts
doc-grounding where it doesn't.

## The doc-grounding paid off

Each cell cited real docs *and* caught a subtlety a memory-only translation would miss:

- **Ruby** — used `Integer(tok)` not `.to_i`: `.to_i` silently returns `0` on bad input, while
  Python's `int()` raises. Behavioral fidelity, not just syntax.
- **Java** — used `.trim().split("\\s+")` not `split(" ")`, avoiding a leading-empty-token
  `NumberFormatException` and matching Python's bare `split()`.
- **C++ (reverse-string)** — used `std::istreambuf_iterator` rather than `cin >>` to **preserve
  interior spaces** and strip exactly one trailing newline; verified against the empty-input
  and trailing-space vectors.
- **Idiom map** landed across all targets: python `dict` → Ruby `Hash` / C++ `unordered_map` /
  Java `HashMap` / Go comma-ok `map` / C# `Dictionary.TryGetValue`.

## Caveats (so this reads honestly)

- This run used a **stand-in** for the agent (a general agent given `@code-translator`'s exact
  instructions), because at capture time the agent wasn't yet installed as a plugin.
- **Context7 MCP was not connected**, so docs came from the **web fallback** path. The real
  `--live` run (agent installed + Context7 wired) uses the Context7-first path.
- The role, the gather-first behavior, and the compile-and-run verification were all genuine;
  only the doc *source* and the invocation wrapper differ from a fully-wired run.
