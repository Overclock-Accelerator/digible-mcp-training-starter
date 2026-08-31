# Sample runs

Commands are from the repo root, with the virtualenv active. Tool output is
deterministic; the model's prose varies run to run.

## 1. Solve a puzzle

```bash
python 00-agent-bee/agent.py --letters VALIDTY --center V
```

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

Must match: 34 words, 171 points, pangram VALIDITY.

## 2. Free-form question

```bash
python 00-agent-bee/agent.py --question "For the Spelling Bee letters VALIDTY with center letter V, which answers are worth 10 or more points?"
```

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

Must match: VALIDITY at 15, ADDITIVITY at 10, and nothing else.

## 3. Error cases

```bash
python 00-agent-bee/agent.py --letters VALIDTY --center Z
```

```
error: --center 'Z' must be one of the letters 'VALIDTY'
```

Exit code 1, with no API call.

```bash
python 00-agent-bee/agent.py --letters VALID --center V
# error: --letters needs exactly 7 distinct letters, got 5 in 'VALID'

python 00-agent-bee/agent.py --letters VALIDTY
# usage: agent.py [-h] [--letters LETTERS] [--center CENTER]
#                 [--question QUESTION]
# agent.py: error: give either --letters and --center, or --question
```

## 4. No API key

```bash
mv .env.local .env.local.off
python 00-agent-bee/agent.py --letters VALIDTY --center V
mv .env.local.off .env.local
```

```
error: ANTHROPIC_API_KEY is not set.
  Create /Users/you/mcp-training/.env.local containing:
    ANTHROPIC_API_KEY=your-key-here
  (or export ANTHROPIC_API_KEY in your shell)
```
