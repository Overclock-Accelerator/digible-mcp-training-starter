# Sample runs

Run these from `00-agent-bee/` with the repo venv active and your key in `.env.local`
set. Each sample states what you should see, so you know immediately whether
your environment is working.

The tool output is deterministic and must match exactly. The model's prose is
not — the wording will differ every run. Check the numbers, not the sentences.

---

## 1. Normal run — solve a puzzle

```bash
python agent.py --letters VALIDTY --center V
```

**Expected:**

```
--- question -----------------------------------------------
  Solve the Spelling Bee for letters VALIDTY with center letter V. How many words, how many points, and what are the pangrams?

  [tool call]   spelling_bee(letters='VALIDTY', center='V')
  [tool result] 34 words, 171 points, pangrams: ['VALIDITY']

--- trajectory ---------------------------------------------
  ai        -> calls spelling_bee({"letters": "VALIDTY", "center": "V"})
  tool      <- {"words": [{"word": "VALIDITY", "points": 15, "pangram": true}, {"word": "ADDITIVITY", "points": 10, "pangram": false},  ...
------------------------------------------------------------
--- answer -------------------------------------------------
**Results for VALIDTY (center: V):**

- **Word count:** 34
- **Total points:** 171
- **Pangram:** VALIDITY (15 points)
```

**The three numbers that must match: 34 words, 171 points, pangram VALIDITY.**
If you get a different count, your `../shared/data/enable1.txt` is not ENABLE1
(it should be 172,823 lines). If you get no `[tool call]` line at all, the
model answered from memory — re-run; the system prompt tells it not to.

---

## 2. Free-form question — the model decides to call the tool

```bash
python agent.py --question "For the Spelling Bee letters VALIDTY with center letter V, which answers are worth 10 or more points?"
```

**Expected:** the same `[tool call]` / `[tool result]` pair as above — nobody
named the tool, the model chose it — followed by an answer naming exactly two
words:

```
  [tool call]   spelling_bee(letters='VALIDTY', center='V')
  [tool result] 34 words, 171 points, pangrams: ['VALIDITY']
...
--- answer -------------------------------------------------
Out of 34 total answers (171 points), only **2 words** score 10 or more points:

| Word | Points | Pangram |
|---|---|---|
| **VALIDITY** | 15 | ✅ Yes |
| **ADDITIVITY** | 10 | No |
```

**What must match: VALIDITY at 15 and ADDITIVITY at 10, and nothing else.**
The table formatting is the model's choice and will vary.

---

## 3. Error case — center letter not in the puzzle

```bash
python agent.py --letters VALIDTY --center Z
```

**Expected — immediately, with no API call and exit code 1:**

```
error: --center 'Z' must be one of the letters 'VALIDTY'
```

The same guard lives inside `solve_spelling_bee` itself, so the rule holds
whoever calls it; the CLI just checks first so a typo costs you nothing.

Two more that fail the same way:

```bash
python agent.py --letters VALID --center V
# error: --letters needs exactly 7 distinct letters, got 5 in 'VALID'

python agent.py --letters VALIDTY
# usage: agent.py [-h] [--letters LETTERS] [--center CENTER]
#                 [--question QUESTION]
# agent.py: error: give either --letters and --center, or --question
```

---

## 4. No API key

`.env.local` is what the agents read, so unsetting the shell variable is not
enough — the loader still finds the file. To see the error path, move it aside:

```bash
mv ../.env.local ../.env.local.off
python agent.py --letters VALIDTY --center V
mv ../.env.local.off ../.env.local     # put it back
```

**Expected:**

```
error: ANTHROPIC_API_KEY is not set.
  Create /Users/you/mcp-training/.env.local containing:
    ANTHROPIC_API_KEY=your-key-here
  (or export ANTHROPIC_API_KEY in your shell)
```

The message names the file rather than the environment variable, because the
file is the thing that is actually missing.
