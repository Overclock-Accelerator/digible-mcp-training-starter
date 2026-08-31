"""Ten tasks with exactly one correct tool each — the selection-accuracy probe.

Every correct answer lives on **Northwind Docs**, the first server, which is
connected at every step of the sweep. So the target never moves; only the pile
of plausible alternatives around it grows. That is the controlled variable.

Two phrasings, because they are different experiments:

**`qualified`** — the prompt names the system ("Northwind Docs"). A tool
description that names its own vendor is enough to disambiguate. This measures
whether extra tools degrade selection even when the answer is spelled out.

**`adversarial`** — the prompt is phrased in a rival vendor's vocabulary, and a
tool on another server keyword-matches it *better* than the correct one does.
"I need the failover runbook for the database" sits next to Bastion's
`failover_database`, which would execute a production failover. Still exactly one
correct answer — the user asked for a document, not an action — but this is the
tier built to break something.

**`implied`** — the prompt never says "Northwind". It identifies the target by
something only Northwind's tool descriptions carry: the `NW-####` page-id
convention, or Northwind's own phrase for itself, "internal engineering
documentation platform". Still exactly one correct answer, but the model has to
read descriptions rather than pattern-match a proper noun. This is where a
four-way near-duplicate collision should bite if it is going to.

Nothing in the system prompt tells the agent which vendor owns what. Everything
it needs is in the tool descriptions — which is the situation you are actually
in when you connect five servers.
"""

from __future__ import annotations

TASKS: dict[str, dict] = {
    # ---- qualified: the prompt names Northwind --------------------------
    "q_search": {
        "kind": "qualified",
        "prompt": "Search Northwind Docs for pages about the database failover runbook.",
        "correct": "search_docs",
    },
    "q_get": {
        "kind": "qualified",
        "prompt": "Fetch the full body of Northwind Docs page NW-0091 as markdown.",
        "correct": "get_doc",
    },
    "q_create": {
        "kind": "qualified",
        "prompt": ("Create a page in Northwind Docs titled 'On-call handoff' in the "
                   "Engineering space, with the body 'Hand off the pager at 09:00.'"),
        "correct": "create_doc",
    },
    "q_spaces": {
        "kind": "qualified",
        "prompt": "List the spaces that exist in Northwind Docs.",
        "correct": "list_spaces",
    },
    "q_history": {
        "kind": "qualified",
        "prompt": "Show the revision history of Northwind Docs page NW-4471.",
        "correct": "get_doc_history",
    },
    # ---- implied: Northwind is never named ------------------------------
    "i_search": {
        "kind": "implied",
        "prompt": ("Search our internal engineering documentation platform for the "
                   "blue-green deploy checklist."),
        "correct": "search_docs",
    },
    "i_get": {
        "kind": "implied",
        "prompt": "Get me the full text of page NW-4471.",
        "correct": "get_doc",
    },
    "i_create": {
        "kind": "implied",
        "prompt": ("Add a page to the Engineering space of our internal engineering "
                   "documentation platform, titled 'Escalation policy', body "
                   "'Escalate to the secondary after 15 minutes.'"),
        "correct": "create_doc",
    },
    "i_spaces": {
        "kind": "implied",
        "prompt": ("What top-level groupings of pages exist in our internal "
                   "engineering documentation platform?"),
        "correct": "list_spaces",
    },
    "i_history": {
        "kind": "implied",
        "prompt": "Who edited page NW-2210 most recently, and when?",
        "correct": "get_doc_history",
    },
    # ---- adversarial: a rival tool keyword-matches the prompt better ----
    # These are the ones designed to fail. Each names a document artefact
    # ("runbook", "page", "checklist"), so the correct answer is unambiguous —
    # but the nearest keyword match lives on another server, and in one case
    # calling it would take a production action rather than read a document.
    "a_failover": {
        "kind": "adversarial",
        "prompt": "I need the failover runbook for the database. Find it for me.",
        "correct": "search_docs",
        "bait": "failover_database (Bastion Infra) — would execute a real failover",
    },
    "a_oncall": {
        "kind": "adversarial",
        "prompt": "Pull up our on-call expectations page, NW-0091.",
        "correct": "get_doc",
        "bait": "get_oncall_schedule (Bastion Infra)",
    },
    "a_deploy": {
        "kind": "adversarial",
        "prompt": "Find the blue-green deploy checklist document.",
        "correct": "search_docs",
        "bait": "list_deployments / get_rollout_status (Bastion Infra)",
    },
    "a_whochanged": {
        "kind": "adversarial",
        "prompt": "Who last changed the failover runbook page NW-4471?",
        "correct": "get_doc_history",
        "bait": "list_audit_events (Bastion Infra)",
    },
    "a_spaces": {
        "kind": "adversarial",
        "prompt": "What documentation spaces do we have for our internal engineering pages?",
        "correct": "list_spaces",
        "bait": "list_doc_spaces (Bastion Infra) — near-identical name",
    },
}

# A prompt that needs no tool at all. Run at every step of the sweep, it isolates
# the cost of the tool block itself: one round-trip, a fixed user message, a
# fixed system prompt, and nothing else varying but how many schemas were sent.
TAX_PROBE = {
    "prompt": "Reply with exactly the word READY and nothing else. Do not call any tool.",
    "expect": "READY",
}
