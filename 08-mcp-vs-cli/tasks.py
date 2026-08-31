"""The task matrix. Both agents get byte-identical prompts — only the seam differs.

Each task isolates one asymmetry between wrapping capability in MCP tools and
wrapping it in a CLI behind a bash tool.
"""

TASKS = {
    # Asymmetry 0 — the baseline. Both sides know how to do this one.
    "solve": {
        "prompt": ("Solve the Spelling Bee with letters VALIDTY and center letter V. "
                   "Report the word count, the total points, and the pangrams."),
        "expect": ["34", "171", "VALIDITY"],
        "measures": "baseline: identical work, both sides briefed",
    },
    # Asymmetry 2 — composition. The answer is one integer. MCP has to drag all
    # 34 words through the context window to get it; the CLI pipes to jq and
    # four bytes come back.
    "aggregate": {
        "prompt": ("For the Spelling Bee with letters VALIDTY and center letter V, how many "
                   "of the answers are 5 or more letters long? Report just the number."),
        "expect": ["24"],
        "measures": "composition: intermediate results in context vs. piped away",
    },
    # Asymmetry 3 — discovery. Neither system prompt mentions crossword patterns.
    # MCP already carries the schema; the CLI agent has to go spelunking in --help.
    "undocumented": {
        "prompt": "Find every dictionary word matching the crossword pattern C_O__W_RD.",
        "expect": ["CROSSWORD"],
        "measures": "discovery: self-describing schema vs. --help spelunking",
    },
}
