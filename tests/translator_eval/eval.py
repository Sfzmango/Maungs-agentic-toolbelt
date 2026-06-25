#!/usr/bin/env python3
"""
Eval harness for the @code-translator agent — language-agnostic by design.

An LLM code-translator can't be unit-tested by string-matching (many valid
translations). So we test it FUNCTIONALLY: translate a reference solution, RUN the
translated program against known input/output vectors, and compare. LeetCode-style
problems with deterministic I/O make that objective.

We can't install every toolchain, and the agent is meant to be language-agnostic
(it searches docs at run time). So the harness **auto-detects which toolchains are
present** and degrades gracefully:

  - a target language with a runtime here  -> VERIFIED  (compile/run the output, check vectors)
  - a target language with no runtime here -> SHOWCASED (translate + assert doc-grounding; run skipped)

I/O contract (language-neutral on purpose — trivial in C++, Java, COBOL, anything):
each program reads its input from STDIN as plain text and writes the answer to STDOUT
as plain text. Comparison is exact after trailing-whitespace normalization. NO JSON.

Two tiers:
  --check  (default, deterministic, no LLM, CI-able) — run every reference solution
           against its vectors, for every language whose toolchain is present.
  --live --from <lang> --to <lang,lang,...|all> — invoke @code-translator to translate
           each reference[from] into each target, then VERIFY (run) where possible or
           SHOWCASE (docs cited + code emitted) where there's no toolchain.
"""
import os, sys, glob, json, argparse, subprocess, tempfile, shutil, collections

ROOT = os.path.dirname(os.path.abspath(__file__))
PROBLEMS = os.path.join(ROOT, "problems")

# Per language: the reference filename, optional build step, run step, and the
# toolchain binary to detect. {src}=source path, {dir}=its dir, {bin}=built binary.
LANGS = {
    "python":     {"file": "solution.py",   "run": ["python3", "{src}"],                                  "bin": "python3"},
    "ruby":       {"file": "solution.rb",   "run": ["ruby", "{src}"],                                     "bin": "ruby"},
    "javascript": {"file": "solution.js",   "run": ["node", "{src}"],                                     "bin": "node"},
    "java":       {"file": "Solution.java", "build": ["javac", "{src}"], "run": ["java", "-cp", "{dir}", "Solution"], "bin": "javac", "probe": ["javac", "-version"]},
    "cpp":        {"file": "solution.cpp",  "build": ["g++", "-O2", "-std=c++17", "{src}", "-o", "{bin}"], "run": ["{bin}"], "bin": "g++"},
    "go":         {"file": "solution.go",   "run": ["go", "run", "{src}"],                                "bin": "go", "probe": ["go", "version"]},
    "php":        {"file": "solution.php",  "run": ["php", "{src}"],                                      "bin": "php"},
    "rust":       {"file": "solution.rs",   "build": ["rustc", "-O", "{src}", "-o", "{bin}"], "run": ["{bin}"], "bin": "rustc"},
    "csharp":     {"file": "solution.cs",   "showcase_only": True, "bin": "dotnet"},
    "cobol":      {"file": "solution.cob",  "build": ["cobc", "-x", "-free", "{src}", "-o", "{bin}"], "run": ["{bin}"], "bin": "cobc"},
    "kotlin":     {"file": "solution.kt",   "showcase_only": True, "bin": "kotlinc", "probe": ["kotlinc", "-version"]},
}

_TOOL_CACHE = {}

def tool_available(lang):
    """True only when the configured tool binary exists and can actually run."""
    if lang in _TOOL_CACHE:
        return _TOOL_CACHE[lang]
    cfg = LANGS[lang]
    binary = shutil.which(cfg["bin"])
    if binary is None:
        _TOOL_CACHE[lang] = False
        return False
    probe = cfg.get("probe", [cfg["bin"], "--version"])
    try:
        proc = subprocess.run(probe, capture_output=True, text=True, timeout=5)
    except Exception:
        _TOOL_CACHE[lang] = False
        return False
    _TOOL_CACHE[lang] = proc.returncode == 0
    return _TOOL_CACHE[lang]

def runnable(lang):
    return tool_available(lang) and not LANGS[lang].get("showcase_only")

def norm(s):
    return "\n".join(line.rstrip() for line in s.replace("\r\n", "\n").rstrip("\n").split("\n"))

def clip(s, n=120):
    """One-line, length-capped rendering of an I/O value for verbose logs."""
    s = s if isinstance(s, str) else str(s)
    s = s.replace("\r\n", "\n")
    return s if len(s) <= n else s[:n] + f"…(+{len(s)-n} more chars)"

def run_source(lang, src_path, stdin_text, timeout=20):
    """Build (if needed) and run a single source file with stdin_text; return stdout."""
    cfg = LANGS[lang]
    with tempfile.TemporaryDirectory() as td:
        local = os.path.join(td, cfg["file"])
        shutil.copy(src_path, local)
        binpath = os.path.join(td, "prog")
        def fmt(cmd): return [c.format(src=local, dir=td, bin=binpath) for c in cmd]
        if "build" in cfg:
            b = subprocess.run(fmt(cfg["build"]), capture_output=True, text=True, timeout=timeout, cwd=td)
            if b.returncode != 0:
                raise RuntimeError(f"{lang} build failed: {b.stderr.strip()[:300]}")
        r = subprocess.run(fmt(cfg["run"]), input=stdin_text, capture_output=True, text=True, timeout=timeout, cwd=td)
        if r.returncode != 0:
            raise RuntimeError(f"{lang} run exited {r.returncode}: {r.stderr.strip()[:300]}")
        return r.stdout

def load_problems():
    probs = []
    for d in sorted(glob.glob(os.path.join(PROBLEMS, "*"))):
        sp = os.path.join(d, "spec.json")
        if not os.path.isfile(sp):
            continue
        spec = json.load(open(sp))
        refs = {l: os.path.join(d, "reference", cfg["file"])
                for l, cfg in LANGS.items()
                if os.path.isfile(os.path.join(d, "reference", cfg["file"]))}
        probs.append({"slug": os.path.basename(d), "spec": spec, "refs": refs})
    return probs

# ---------------- tier 1: --check --------------------------------------------
def tier_check(verbose=False):
    probs = load_problems()
    ref_langs = sorted({l for p in probs for l in p["refs"]})
    run_langs = [l for l in ref_langs if runnable(l)]
    skip_langs = [l for l in ref_langs if not runnable(l)]
    total = ok = 0
    fails = []
    per_lang = collections.defaultdict(lambda: [0, 0])   # lang -> [ok, total]
    per_prob = collections.defaultdict(lambda: [0, 0])   # slug -> [ok, total]
    cells = []                                           # (slug, lang, ok, total)
    io_rows = []                                         # (slug, lang, i, stdin, expected, got, ok)
    for p in probs:
        for lang in run_langs:
            if lang not in p["refs"]:
                continue
            cok = ctot = 0
            for i, c in enumerate(p["spec"]["cases"]):
                total += 1; ctot += 1
                try:
                    got = run_source(lang, p["refs"][lang], c["stdin"])
                    okc = norm(got) == norm(c["stdout"])
                    if okc:
                        ok += 1; cok += 1
                    else:
                        fails.append((p["slug"], lang, i, c["stdout"], got))
                except Exception as e:
                    okc = False; got = f"<error: {e}>"
                    fails.append((p["slug"], lang, i, "<error>", str(e)))
                if verbose:
                    io_rows.append((p["slug"], lang, i, c["stdin"], c["stdout"], got, okc))
            per_lang[lang][0] += cok; per_lang[lang][1] += ctot
            per_prob[p["slug"]][0] += cok; per_prob[p["slug"]][1] += ctot
            cells.append((p["slug"], lang, cok, ctot))
    print(f"[--check] {ok}/{total} reference case-runs pass | {len(probs)} problems")
    print(f"          verified languages: {', '.join(run_langs)}")
    if skip_langs:
        print(f"          references present but no toolchain here (skipped): {', '.join(skip_langs)}")
    if verbose:
        print("\n  PER-LANGUAGE (case-runs):")
        for l in sorted(per_lang):
            g, n = per_lang[l]
            print(f"    {'✓' if g == n else '✗'} {l:12} {g}/{n}")
        print("\n  PER-PROBLEM (case-runs across all verified languages):")
        for slug in sorted(per_prob):
            g, n = per_prob[slug]
            print(f"    {'✓' if g == n else '✗'} {slug:16} {g}/{n}")
        print("\n  PER-PROBLEM × LANGUAGE:")
        for slug, lang, cok, ctot in cells:
            print(f"    {'✓' if cok == ctot else '✗'} {slug:16} [{lang:10}] {cok}/{ctot}")
        print("\n  PER-CASE I/O (what was passed → expected vs. what was returned):")
        for slug, lang, i, stdin, exp, got, okc in io_rows:
            sym = "✓" if okc else "✗"
            print(f"    {sym} {slug:16} [{lang:10}] case#{i}")
            print(f"        passed   (stdin)  = {clip(stdin)!r}")
            print(f"        expected (stdout) = {clip(exp)!r}")
            print(f"        returned (stdout) = {clip(got)!r}")
        print()
    for slug, lang, i, exp, got in fails:
        print(f"  ✗ FAIL {slug} [{lang}] case#{i}: expected={clip(exp)!r} got={clip(got)!r}")
    print(f"\nRESULT: {'PASS' if not fails else 'FAIL'}  ({ok}/{total} case-runs)")
    return 0 if not fails else 1

# ---------------- tier 2: --live ---------------------------------------------
def parse_eval_output(text):
    docs = next((l.split(":", 1)[1].strip() for l in text.splitlines()
                 if l.strip().upper().startswith("DOCS:")), None)
    code = None
    if "```" in text:
        parts = text.split("```")
        if len(parts) >= 3:
            blk = parts[1]
            nl = blk.find("\n")
            code = blk[nl + 1:] if nl != -1 else blk
    return docs, code

def invoke_agent(src_lang, tgt_lang, src_code, io_desc):
    prompt = (f"@code-translator translate the following {src_lang} program to {tgt_lang}. "
              f"Preserve the exact stdin/stdout text contract: {io_desc} "
              f"Standard library only.\nOUTPUT MODE: eval\n\n```{src_lang}\n{src_code}\n```")
    p = subprocess.run(["claude", "-p", prompt], capture_output=True, text=True, timeout=900)
    if p.returncode != 0:
        raise RuntimeError(f"claude CLI failed: {p.stderr.strip()[:300]}")
    return p.stdout

def tier_live(src_lang, targets):
    if not shutil.which("claude"):
        print("[--live] the `claude` CLI is not on PATH — cannot invoke @code-translator.")
        return 2
    if targets == ["all"]:
        targets = [l for l in LANGS if l != src_lang]
    probs = load_problems()
    rows = []
    verified = showcased = failed = 0
    for p in probs:
        if src_lang not in p["refs"]:
            continue
        src_code = open(p["refs"][src_lang]).read()
        io_desc = p["spec"].get("io", "")
        for tgt in targets:
            if tgt == src_lang or tgt not in LANGS:
                continue
            try:
                docs, code = parse_eval_output(invoke_agent(src_lang, tgt, src_code, io_desc))
                docs_ok = bool(docs) and src_lang.lower() in docs.lower() and tgt.lower() in docs.lower()
                code_ok = bool(code and code.strip())
                if runnable(tgt):
                    cok = ctot = 0
                    with tempfile.TemporaryDirectory() as td:
                        fp = os.path.join(td, LANGS[tgt]["file"])
                        open(fp, "w").write(code or "")
                        for c in p["spec"]["cases"]:
                            ctot += 1
                            try:
                                if norm(run_source(tgt, fp, c["stdin"])) == norm(c["stdout"]):
                                    cok += 1
                            except Exception:
                                pass
                    passed = docs_ok and cok == ctot
                    verified += 1 if passed else 0
                    failed += 0 if passed else 1
                    rows.append((p["slug"], f"{src_lang}->{tgt}", "VERIFIED",
                                 f"{cok}/{ctot} vectors", "docs:OK" if docs_ok else "docs:MISSING",
                                 "PASS" if passed else "FAIL"))
                else:
                    passed = docs_ok and code_ok
                    showcased += 1 if passed else 0
                    failed += 0 if passed else 1
                    rows.append((p["slug"], f"{src_lang}->{tgt}", "SHOWCASED (no toolchain)",
                                 "run skipped", "docs:OK" if docs_ok else "docs:MISSING",
                                 "OK" if passed else "WEAK"))
            except Exception as e:
                failed += 1
                rows.append((p["slug"], f"{src_lang}->{tgt}", "ERROR", "—", "—", str(e)[:100]))
    print(f"[--live {src_lang} -> {','.join(targets)}]  VERIFIED(ran+passed)={verified}  "
          f"SHOWCASED(docs+code, no runtime)={showcased}  FAILED={failed}\n")
    for r in rows:
        print("  " + " | ".join(r))
    return 0 if failed == 0 else 1

def main():
    ap = argparse.ArgumentParser(description="Language-agnostic eval harness for @code-translator")
    ap.add_argument("--live", action="store_true", help="invoke @code-translator (costs tokens)")
    ap.add_argument("--from", dest="src", default="python")
    ap.add_argument("--to", dest="to", default="all", help="comma-separated targets, or 'all'")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="print per-language / per-problem detail (pass AND fail)")
    a = ap.parse_args()
    if a.live:
        sys.exit(tier_live(a.src, [t.strip() for t in a.to.split(",") if t.strip()]))
    sys.exit(tier_check(a.verbose))

if __name__ == "__main__":
    main()
