"""The five vendor catalogues — 155 tool definitions, in one place.

The scenario: a company that said yes to five vendors. Each ships an MCP server.
Every server is individually reasonable. The question this folder answers is what
happens to the agent when you connect all five at once.

Two things are deliberate here.

**The counts escalate** — 5, 10, 20, 40, 80 — because that is what real adoption
looks like. The knowledge base ships a handful of tools; the infrastructure
platform ships everything it has.

**The names collide.** Five vendors independently solving "let the agent find a
document" produce `search_docs`, `find_documents`, `lookup_document`,
`query_knowledge_base` and `search_documentation`. Nobody coordinated. Each name
is defensible in isolation. Twenty of the 155 tools below are planted
near-duplicates of the five Northwind tools, spread one per rival server, marked
`CONFUSABLE` in the tables. The rest are ordinary domain tools that make the
servers plausible — and that pad the context window exactly as real ones would.

Every tool has real parameters and a real docstring, because the thing being
measured is schema cost, and one-line stubs would understate it.
"""

from __future__ import annotations

Tool = tuple[str, str, str]


def t(name: str, sig: str, summary: str, *args: tuple[str, str]) -> Tool:
    """Build one (name, signature, docstring) entry.

    `agent_name` is prepended to every signature by the server, per the repo
    contract, so it is documented here but not repeated in each `sig`.
    """
    doc = summary + "\n\n    Args:\n        agent_name: The name of the calling agent."
    for arg, desc in args:
        doc += f"\n        {arg}: {desc}"
    return (name, sig, doc)


# ---------------------------------------------------------------------------
# Server 1 — Northwind Docs. The internal documentation platform. 5 tools.
# Every task in tasks.py has its correct answer here. This server is present at
# every step of the sweep, so accuracy across steps is measured against a fixed
# target while only the distractor set grows.
# ---------------------------------------------------------------------------

NORTHWIND_DOCS: list[Tool] = [
    t("search_docs", "query: str, space: str = \"all\", limit: int = 10",
      "Full-text search across Northwind Docs pages. Northwind is the company's "
      "internal engineering documentation platform; page ids look like NW-4471.",
      ("query", "Search terms, e.g. \"database failover runbook\"."),
      ("space", "Restrict to one Northwind space, or \"all\"."),
      ("limit", "Maximum number of pages to return.")),
    t("get_doc", "doc_id: str, format: str = \"markdown\"",
      "Fetch the full body of one Northwind Docs page by its page id.",
      ("doc_id", "The Northwind page id, e.g. \"NW-4471\"."),
      ("format", "\"markdown\", \"html\" or \"plain\".")),
    t("create_doc", "title: str, body: str, space: str",
      "Create a new page in Northwind Docs.",
      ("title", "Title of the new page."),
      ("body", "Page body, in Markdown."),
      ("space", "The Northwind space to create it in, e.g. \"Engineering\".")),
    t("list_spaces", "include_archived: bool = False",
      "List the spaces that exist in Northwind Docs. A space is Northwind's "
      "top-level grouping of pages, one per team or product area.",
      ("include_archived", "Include spaces that have been archived.")),
    t("get_doc_history", "doc_id: str, limit: int = 20",
      "Return the revision history of a Northwind Docs page — who edited it, "
      "when, and the change summary they left.",
      ("doc_id", "The Northwind page id, e.g. \"NW-2210\"."),
      ("limit", "How many revisions to return, newest first.")),
]

# ---------------------------------------------------------------------------
# Server 2 — Helios Helpdesk. Customer support desk. 10 tools.
# 5 CONFUSABLE with Northwind.
# ---------------------------------------------------------------------------

HELIOS_HELPDESK: list[Tool] = [
    # -- CONFUSABLE ---------------------------------------------------------
    t("find_documents", "query: str, collection: str = \"help-center\", limit: int = 10",
      "Search the Helios help-center article library. These are the "
      "customer-facing support articles published by Helios Helpdesk.",
      ("query", "Search terms."),
      ("collection", "Which article collection to search."),
      ("limit", "Maximum number of articles to return.")),
    t("read_document", "document_id: str",
      "Read the full text of a Helios help-center article.",
      ("document_id", "The Helios article id, e.g. \"HC-8812\".")),
    t("create_page", "title: str, content: str, collection: str = \"help-center\"",
      "Publish a new article to the Helios help centre.",
      ("title", "Article title."),
      ("content", "Article body."),
      ("collection", "Collection to publish into.")),
    t("list_workspaces", "",
      "List the Helios Helpdesk workspaces this account can see. A workspace is "
      "one support queue with its own agents and SLAs."),
    t("get_revision_history", "document_id: str, limit: int = 20",
      "Return the edit history of a Helios help-center article.",
      ("document_id", "The Helios article id."),
      ("limit", "How many revisions to return.")),
    # -- ordinary domain tools ---------------------------------------------
    t("create_ticket", "subject: str, body: str, priority: str = \"normal\"",
      "Open a new customer support ticket in Helios.",
      ("subject", "One-line summary of the customer's problem."),
      ("body", "Full description."),
      ("priority", "\"low\", \"normal\", \"high\" or \"urgent\".")),
    t("get_ticket", "ticket_id: str",
      "Fetch one Helios support ticket with its full conversation thread.",
      ("ticket_id", "The Helios ticket id, e.g. \"HD-3391\".")),
    t("list_tickets", "status: str = \"open\", assignee: str = \"\", limit: int = 25",
      "List Helios support tickets matching a filter.",
      ("status", "\"open\", \"pending\", \"solved\" or \"all\"."),
      ("assignee", "Restrict to one agent's queue; empty for all."),
      ("limit", "Maximum tickets to return.")),
    t("add_ticket_comment", "ticket_id: str, body: str, public: bool = True",
      "Add a comment to a Helios ticket.",
      ("ticket_id", "The ticket to comment on."),
      ("body", "Comment text."),
      ("public", "True for a customer-visible reply, False for an internal note.")),
    t("close_ticket", "ticket_id: str, resolution: str",
      "Mark a Helios ticket solved.",
      ("ticket_id", "The ticket to close."),
      ("resolution", "Resolution summary recorded on the ticket.")),
]

# ---------------------------------------------------------------------------
# Server 3 — Meridian CRM. Sales and customer records. 20 tools.
# 5 CONFUSABLE with Northwind.
# ---------------------------------------------------------------------------

MERIDIAN_CRM: list[Tool] = [
    # -- CONFUSABLE ---------------------------------------------------------
    t("lookup_document", "search: str, record_type: str = \"any\", limit: int = 10",
      "Search documents attached to Meridian CRM records — contracts, proposals "
      "and signed order forms filed against an account or deal.",
      ("search", "Search terms."),
      ("record_type", "\"account\", \"deal\", \"contact\" or \"any\"."),
      ("limit", "Maximum documents to return.")),
    t("fetch_document", "document_ref: str, include_metadata: bool = True",
      "Fetch one document attached to a Meridian CRM record.",
      ("document_ref", "The Meridian document reference, e.g. \"MD-DOC-771\"."),
      ("include_metadata", "Include the filing metadata alongside the body.")),
    t("new_document", "name: str, body: str, attach_to: str",
      "File a new document against a Meridian CRM record.",
      ("name", "Document name."),
      ("body", "Document body."),
      ("attach_to", "Record id to attach it to, e.g. \"ACC-204\".")),
    t("list_projects", "owner: str = \"\", status: str = \"active\"",
      "List Meridian CRM projects. A project groups the deals and activities "
      "for one customer engagement.",
      ("owner", "Restrict to one owner; empty for all."),
      ("status", "\"active\", \"closed\" or \"all\".")),
    t("document_history", "document_ref: str",
      "Return the version history of a document filed in Meridian CRM.",
      ("document_ref", "The Meridian document reference.")),
    # -- ordinary domain tools ---------------------------------------------
    t("create_contact", "name: str, email: str, account_id: str = \"\"",
      "Create a contact record in Meridian CRM.",
      ("name", "Full name."), ("email", "Email address."),
      ("account_id", "Account to attach the contact to.")),
    t("get_contact", "contact_id: str",
      "Fetch one Meridian CRM contact record.",
      ("contact_id", "The contact id, e.g. \"CON-9921\".")),
    t("search_contacts", "query: str, limit: int = 25",
      "Search Meridian CRM contacts by name, email or company.",
      ("query", "Search terms."), ("limit", "Maximum contacts to return.")),
    t("update_contact", "contact_id: str, fields: dict",
      "Update fields on a Meridian CRM contact.",
      ("contact_id", "The contact to update."),
      ("fields", "Field name to new value.")),
    t("list_accounts", "segment: str = \"all\", limit: int = 50",
      "List Meridian CRM accounts.",
      ("segment", "\"smb\", \"mid-market\", \"enterprise\" or \"all\"."),
      ("limit", "Maximum accounts to return.")),
    t("get_account", "account_id: str, include_deals: bool = False",
      "Fetch one Meridian CRM account.",
      ("account_id", "The account id, e.g. \"ACC-204\"."),
      ("include_deals", "Include the account's open deals.")),
    t("create_deal", "account_id: str, name: str, amount: float, stage: str = \"discovery\"",
      "Create a deal on a Meridian CRM account.",
      ("account_id", "Account the deal belongs to."), ("name", "Deal name."),
      ("amount", "Deal value in USD."), ("stage", "Pipeline stage.")),
    t("update_deal", "deal_id: str, stage: str = \"\", amount: float = 0.0",
      "Update a Meridian CRM deal's stage or value.",
      ("deal_id", "The deal to update."), ("stage", "New pipeline stage."),
      ("amount", "New deal value; 0 leaves it unchanged.")),
    t("list_deals", "stage: str = \"all\", owner: str = \"\", limit: int = 50",
      "List Meridian CRM deals.",
      ("stage", "Pipeline stage filter."), ("owner", "Restrict to one rep."),
      ("limit", "Maximum deals to return.")),
    t("log_activity", "record_id: str, kind: str, summary: str",
      "Log a call, email or meeting against a Meridian CRM record.",
      ("record_id", "The record the activity relates to."),
      ("kind", "\"call\", \"email\" or \"meeting\"."),
      ("summary", "What happened.")),
    t("get_pipeline_summary", "period: str = \"quarter\", owner: str = \"\"",
      "Summarize the Meridian CRM sales pipeline by stage and value.",
      ("period", "\"month\", \"quarter\" or \"year\"."),
      ("owner", "Restrict to one rep.")),
    t("create_note", "record_id: str, body: str",
      "Attach a free-text note to a Meridian CRM record.",
      ("record_id", "Record to note against."), ("body", "Note text.")),
    t("search_notes", "query: str, record_id: str = \"\", limit: int = 25",
      "Search notes attached to Meridian CRM records.",
      ("query", "Search terms."), ("record_id", "Restrict to one record."),
      ("limit", "Maximum notes to return.")),
    t("assign_owner", "record_id: str, owner: str",
      "Reassign a Meridian CRM record to a different owner.",
      ("record_id", "Record to reassign."), ("owner", "New owner's username.")),
    t("open_issue", "title: str, description: str, severity: str = \"normal\"",
      "Raise a customer-success issue against a Meridian CRM account.",
      ("title", "One-line summary."), ("description", "Full description."),
      ("severity", "\"low\", \"normal\", \"high\" or \"critical\".")),
]

# ---------------------------------------------------------------------------
# Server 4 — Lumen Analytics. Product analytics and BI. 40 tools.
# 5 CONFUSABLE with Northwind.
# ---------------------------------------------------------------------------

LUMEN_ANALYTICS: list[Tool] = [
    # -- CONFUSABLE ---------------------------------------------------------
    t("query_knowledge_base", "question: str, namespace: str = \"default\", top_k: int = 5",
      "Semantic search over the Lumen knowledge base — the indexed corpus of "
      "metric definitions, dashboard descriptions and analyst write-ups.",
      ("question", "Natural-language question."),
      ("namespace", "Which Lumen namespace to search."),
      ("top_k", "How many passages to return.")),
    t("get_document_content", "doc_ref: str, section: str = \"\"",
      "Retrieve the indexed text of one document in the Lumen knowledge base.",
      ("doc_ref", "The Lumen document reference, e.g. \"LU-DOC-55\"."),
      ("section", "Restrict to one section heading; empty for the whole document.")),
    t("create_doc_draft", "title: str, markdown: str, namespace: str = \"default\"",
      "Create a draft analyst write-up in the Lumen knowledge base.",
      ("title", "Draft title."), ("markdown", "Draft body."),
      ("namespace", "Namespace to file it under.")),
    t("list_namespaces", "",
      "List the namespaces in the Lumen knowledge base. A namespace partitions "
      "the index by team or data domain."),
    t("get_page_versions", "doc_ref: str, limit: int = 20",
      "List the stored versions of a Lumen knowledge-base document.",
      ("doc_ref", "The Lumen document reference."),
      ("limit", "How many versions to return.")),
    # -- ordinary domain tools ---------------------------------------------
    t("run_query", "sql: str, warehouse: str = \"default\", timeout_s: int = 60",
      "Run a SQL query against the Lumen warehouse.",
      ("sql", "The SQL to execute."), ("warehouse", "Which warehouse to run on."),
      ("timeout_s", "Abort after this many seconds.")),
    t("list_datasets", "warehouse: str = \"default\"",
      "List datasets available in the Lumen warehouse.",
      ("warehouse", "Which warehouse to list.")),
    t("describe_dataset", "dataset: str",
      "Return the column names, types and row count of a Lumen dataset.",
      ("dataset", "Fully-qualified dataset name.")),
    t("get_metric", "metric: str, period: str = \"7d\", segment: str = \"all\"",
      "Fetch the current value of a defined Lumen metric.",
      ("metric", "Metric name, e.g. \"weekly_active_users\"."),
      ("period", "Look-back window."), ("segment", "Segment filter.")),
    t("list_metrics", "owner: str = \"\"",
      "List the metrics defined in Lumen.", ("owner", "Restrict to one owner.")),
    t("create_metric", "name: str, sql: str, description: str",
      "Define a new Lumen metric.", ("name", "Metric name."),
      ("sql", "SQL that computes it."), ("description", "What it means.")),
    t("get_funnel", "steps: list[str], period: str = \"30d\"",
      "Compute conversion through an ordered funnel of events.",
      ("steps", "Event names in order."), ("period", "Look-back window.")),
    t("get_retention", "cohort_event: str, return_event: str, period: str = \"90d\"",
      "Compute a retention curve between two events.",
      ("cohort_event", "Event that defines the cohort."),
      ("return_event", "Event that counts as a return."),
      ("period", "Look-back window.")),
    t("get_cohort", "cohort_id: str",
      "Fetch the membership and definition of a saved Lumen cohort.",
      ("cohort_id", "The cohort id.")),
    t("create_cohort", "name: str, filter_json: str",
      "Create a saved user cohort in Lumen.",
      ("name", "Cohort name."), ("filter_json", "Filter expression as JSON.")),
    t("list_dashboards", "owner: str = \"\", limit: int = 50",
      "List Lumen dashboards.", ("owner", "Restrict to one owner."),
      ("limit", "Maximum dashboards to return.")),
    t("get_dashboard", "dashboard_id: str",
      "Fetch a Lumen dashboard's tiles and their current values.",
      ("dashboard_id", "The dashboard id.")),
    t("create_dashboard", "name: str, tiles: list[str]",
      "Create a Lumen dashboard from a list of saved charts.",
      ("name", "Dashboard name."), ("tiles", "Chart ids to place on it.")),
    t("share_dashboard", "dashboard_id: str, audience: str",
      "Share a Lumen dashboard with a team or the whole workspace.",
      ("dashboard_id", "The dashboard to share."),
      ("audience", "Team name, or \"workspace\".")),
    t("get_chart", "chart_id: str, format: str = \"json\"",
      "Fetch one saved Lumen chart and its data.",
      ("chart_id", "The chart id."), ("format", "\"json\" or \"csv\".")),
    t("create_chart", "name: str, query: str, chart_type: str = \"line\"",
      "Save a new chart in Lumen.", ("name", "Chart name."),
      ("query", "Query that supplies the data."), ("chart_type", "Chart type.")),
    t("list_events", "since: str = \"7d\", limit: int = 100",
      "List event types seen in the Lumen stream.",
      ("since", "Look-back window."), ("limit", "Maximum event types.")),
    t("get_event_volume", "event: str, period: str = \"30d\", granularity: str = \"day\"",
      "Return a time series of volume for one event.",
      ("event", "Event name."), ("period", "Look-back window."),
      ("granularity", "\"hour\", \"day\" or \"week\".")),
    t("get_user_profile", "user_id: str",
      "Fetch one user's Lumen analytics profile and recent events.",
      ("user_id", "The user id.")),
    t("search_users", "query: str, limit: int = 25",
      "Search Lumen user profiles by property.",
      ("query", "Property filter expression."), ("limit", "Maximum users.")),
    t("get_session_replay", "session_id: str",
      "Fetch the metadata and event list for one recorded session.",
      ("session_id", "The session id.")),
    t("list_experiments", "status: str = \"running\"",
      "List Lumen A/B experiments.", ("status", "\"running\", \"stopped\" or \"all\".")),
    t("get_experiment_results", "experiment_id: str, metric: str = \"primary\"",
      "Fetch results and significance for a Lumen experiment.",
      ("experiment_id", "The experiment id."), ("metric", "Which metric to report.")),
    t("create_experiment", "name: str, variants: list[str], primary_metric: str",
      "Create a Lumen A/B experiment.", ("name", "Experiment name."),
      ("variants", "Variant names."), ("primary_metric", "Metric to judge on.")),
    t("stop_experiment", "experiment_id: str, reason: str",
      "Stop a running Lumen experiment.", ("experiment_id", "The experiment."),
      ("reason", "Why it is being stopped.")),
    t("get_feature_flag", "flag_key: str",
      "Fetch a Lumen feature flag's rollout state.", ("flag_key", "The flag key.")),
    t("set_feature_flag", "flag_key: str, rollout_percent: int",
      "Set a Lumen feature flag's rollout percentage.",
      ("flag_key", "The flag key."), ("rollout_percent", "0 to 100.")),
    t("schedule_report", "report_id: str, cron: str, recipients: list[str]",
      "Schedule a Lumen report for recurring delivery.",
      ("report_id", "The report to send."), ("cron", "Cron expression."),
      ("recipients", "Email addresses.")),
    t("get_report", "report_id: str, period: str = \"last\"",
      "Fetch a generated Lumen report.", ("report_id", "The report id."),
      ("period", "Which run to fetch.")),
    t("list_reports", "owner: str = \"\"",
      "List Lumen reports.", ("owner", "Restrict to one owner.")),
    t("export_data", "query: str, format: str = \"csv\", destination: str = \"download\"",
      "Export the result of a Lumen query.", ("query", "Query to export."),
      ("format", "\"csv\", \"json\" or \"parquet\"."),
      ("destination", "\"download\" or an object-store URI.")),
    t("get_data_freshness", "dataset: str",
      "Report when a Lumen dataset was last loaded and whether it is stale.",
      ("dataset", "The dataset to check.")),
    t("list_alerts", "status: str = \"active\"",
      "List Lumen metric alerts.", ("status", "\"active\", \"muted\" or \"all\".")),
    t("create_alert", "metric: str, condition: str, channel: str",
      "Create a Lumen alert on a metric.", ("metric", "Metric to watch."),
      ("condition", "Threshold expression."), ("channel", "Where to notify.")),
    t("acknowledge_alert", "alert_id: str, note: str = \"\"",
      "Acknowledge a firing Lumen alert.", ("alert_id", "The alert."),
      ("note", "Optional note.")),
]

# ---------------------------------------------------------------------------
# Server 5 — Bastion Infra. Cloud infrastructure platform. 80 tools.
# 5 CONFUSABLE with Northwind. The vendor that ships everything it has.
# ---------------------------------------------------------------------------

BASTION_INFRA: list[Tool] = [
    # -- CONFUSABLE ---------------------------------------------------------
    t("search_documentation", "query: str, product: str = \"all\", limit: int = 10",
      "Search the Bastion product documentation — the vendor's own manuals for "
      "its infrastructure platform.",
      ("query", "Search terms."), ("product", "Restrict to one Bastion product."),
      ("limit", "Maximum results to return.")),
    t("retrieve_doc", "slug: str, version: str = \"latest\"",
      "Retrieve one page of Bastion product documentation by slug.",
      ("slug", "The doc slug, e.g. \"networking/vpc-peering\"."),
      ("version", "Platform version the docs should target.")),
    t("publish_doc", "slug: str, body: str, product: str",
      "Publish a page to the Bastion documentation site.",
      ("slug", "Doc slug to publish at."), ("body", "Page body."),
      ("product", "Which Bastion product it documents.")),
    t("list_doc_spaces", "",
      "List the documentation spaces on the Bastion docs site — one per Bastion "
      "product line."),
    t("list_doc_revisions", "slug: str, limit: int = 20",
      "List revisions of a Bastion documentation page.",
      ("slug", "The doc slug."), ("limit", "How many revisions to return.")),
    # -- ordinary domain tools ---------------------------------------------
    t("list_clusters", "region: str = \"all\"",
      "List Bastion Kubernetes clusters.", ("region", "Restrict to one region.")),
    t("get_cluster", "cluster_id: str",
      "Fetch one Bastion cluster's configuration and health.", ("cluster_id", "The cluster id.")),
    t("create_cluster", "name: str, region: str, node_count: int = 3",
      "Provision a new Bastion cluster.", ("name", "Cluster name."),
      ("region", "Region to create it in."), ("node_count", "Initial node count.")),
    t("delete_cluster", "cluster_id: str, confirm: bool = False",
      "Destroy a Bastion cluster.", ("cluster_id", "The cluster."),
      ("confirm", "Must be True to proceed.")),
    t("scale_cluster", "cluster_id: str, node_count: int",
      "Change a Bastion cluster's node count.", ("cluster_id", "The cluster."),
      ("node_count", "Desired node count.")),
    t("list_nodes", "cluster_id: str, status: str = \"all\"",
      "List nodes in a Bastion cluster.", ("cluster_id", "The cluster."),
      ("status", "\"ready\", \"notready\" or \"all\".")),
    t("drain_node", "node_id: str, grace_seconds: int = 30",
      "Cordon and drain a Bastion node.", ("node_id", "The node."),
      ("grace_seconds", "Eviction grace period.")),
    t("get_node_metrics", "node_id: str, period: str = \"1h\"",
      "Fetch CPU, memory and disk metrics for a Bastion node.",
      ("node_id", "The node."), ("period", "Look-back window.")),
    t("list_deployments", "namespace: str = \"default\", cluster_id: str = \"\"",
      "List Bastion workload deployments.", ("namespace", "Kubernetes namespace."),
      ("cluster_id", "Restrict to one cluster.")),
    t("get_deployment", "deployment_id: str",
      "Fetch one Bastion deployment's spec and rollout status.",
      ("deployment_id", "The deployment id.")),
    t("create_deployment", "name: str, image: str, replicas: int = 1",
      "Create a Bastion deployment.", ("name", "Deployment name."),
      ("image", "Container image reference."), ("replicas", "Replica count.")),
    t("rollback_deployment", "deployment_id: str, to_revision: int = 0",
      "Roll a Bastion deployment back to an earlier revision.",
      ("deployment_id", "The deployment."), ("to_revision", "Revision number; 0 for previous.")),
    t("restart_deployment", "deployment_id: str",
      "Trigger a rolling restart of a Bastion deployment.", ("deployment_id", "The deployment.")),
    t("scale_deployment", "deployment_id: str, replicas: int",
      "Change a Bastion deployment's replica count.", ("deployment_id", "The deployment."),
      ("replicas", "Desired replicas.")),
    t("get_rollout_status", "deployment_id: str",
      "Report progress of an in-flight Bastion rollout.", ("deployment_id", "The deployment.")),
    t("list_pods", "namespace: str = \"default\", label_selector: str = \"\"",
      "List pods in a Bastion cluster.", ("namespace", "Namespace."),
      ("label_selector", "Label selector expression.")),
    t("get_pod_logs", "pod_id: str, container: str = \"\", tail: int = 200",
      "Fetch logs from a Bastion pod.", ("pod_id", "The pod."),
      ("container", "Container name if the pod has several."),
      ("tail", "How many lines from the end.")),
    t("exec_in_pod", "pod_id: str, command: str",
      "Run a command inside a Bastion pod.", ("pod_id", "The pod."),
      ("command", "Command to run.")),
    t("delete_pod", "pod_id: str",
      "Delete a Bastion pod so it is rescheduled.", ("pod_id", "The pod.")),
    t("list_services", "namespace: str = \"default\"",
      "List Bastion services.", ("namespace", "Namespace.")),
    t("get_service", "service_id: str",
      "Fetch one Bastion service and its endpoints.", ("service_id", "The service.")),
    t("list_ingresses", "namespace: str = \"default\"",
      "List Bastion ingress rules.", ("namespace", "Namespace.")),
    t("get_ingress", "ingress_id: str",
      "Fetch one Bastion ingress rule.", ("ingress_id", "The ingress.")),
    t("list_secrets", "namespace: str = \"default\"",
      "List the names of Bastion secrets. Values are never returned.",
      ("namespace", "Namespace.")),
    t("rotate_secret", "secret_id: str, reason: str",
      "Rotate a Bastion secret.", ("secret_id", "The secret."), ("reason", "Why.")),
    t("list_config_maps", "namespace: str = \"default\"",
      "List Bastion config maps.", ("namespace", "Namespace.")),
    t("get_config_map", "config_map_id: str",
      "Fetch one Bastion config map.", ("config_map_id", "The config map.")),
    t("update_config_map", "config_map_id: str, data: dict",
      "Update a Bastion config map.", ("config_map_id", "The config map."),
      ("data", "Key to value.")),
    t("list_volumes", "cluster_id: str = \"\"",
      "List Bastion persistent volumes.", ("cluster_id", "Restrict to one cluster.")),
    t("create_volume", "name: str, size_gb: int, storage_class: str = \"standard\"",
      "Create a Bastion persistent volume.", ("name", "Volume name."),
      ("size_gb", "Size in gigabytes."), ("storage_class", "Storage class.")),
    t("snapshot_volume", "volume_id: str, label: str = \"\"",
      "Snapshot a Bastion volume.", ("volume_id", "The volume."), ("label", "Snapshot label.")),
    t("restore_snapshot", "snapshot_id: str, target_volume: str",
      "Restore a Bastion snapshot onto a volume.", ("snapshot_id", "The snapshot."),
      ("target_volume", "Volume to restore into.")),
    t("list_databases", "engine: str = \"all\"",
      "List Bastion managed databases.", ("engine", "\"postgres\", \"mysql\" or \"all\".")),
    t("get_database", "database_id: str",
      "Fetch one Bastion database's configuration.", ("database_id", "The database.")),
    t("create_database", "name: str, engine: str, size: str = \"small\"",
      "Provision a Bastion managed database.", ("name", "Database name."),
      ("engine", "Engine to use."), ("size", "Instance size.")),
    t("failover_database", "database_id: str, target_replica: str = \"\"",
      "Fail a Bastion database over to a replica.", ("database_id", "The database."),
      ("target_replica", "Replica to promote; empty picks the healthiest.")),
    t("backup_database", "database_id: str, retention_days: int = 30",
      "Take a backup of a Bastion database.", ("database_id", "The database."),
      ("retention_days", "How long to keep it.")),
    t("restore_database", "backup_id: str, target: str",
      "Restore a Bastion database backup.", ("backup_id", "The backup."),
      ("target", "Database to restore into.")),
    t("list_backups", "database_id: str = \"\", limit: int = 25",
      "List Bastion database backups.", ("database_id", "Restrict to one database."),
      ("limit", "Maximum backups to return.")),
    t("get_database_metrics", "database_id: str, period: str = \"1h\"",
      "Fetch connection, IOPS and replication-lag metrics for a Bastion database.",
      ("database_id", "The database."), ("period", "Look-back window.")),
    t("list_queues", "",
      "List Bastion managed message queues."),
    t("get_queue_depth", "queue_id: str",
      "Report the current depth of a Bastion queue.", ("queue_id", "The queue.")),
    t("purge_queue", "queue_id: str, confirm: bool = False",
      "Purge every message from a Bastion queue.", ("queue_id", "The queue."),
      ("confirm", "Must be True to proceed.")),
    t("list_caches", "",
      "List Bastion managed cache instances."),
    t("flush_cache", "cache_id: str, key_pattern: str = \"*\"",
      "Flush keys from a Bastion cache.", ("cache_id", "The cache."),
      ("key_pattern", "Glob of keys to evict.")),
    t("list_buckets", "region: str = \"all\"",
      "List Bastion object-storage buckets.", ("region", "Restrict to one region.")),
    t("list_objects", "bucket: str, prefix: str = \"\", limit: int = 100",
      "List objects in a Bastion bucket.", ("bucket", "Bucket name."),
      ("prefix", "Key prefix filter."), ("limit", "Maximum objects.")),
    t("get_object_metadata", "bucket: str, key: str",
      "Fetch size, content type and checksum for a Bastion object.",
      ("bucket", "Bucket name."), ("key", "Object key.")),
    t("set_bucket_policy", "bucket: str, policy_json: str",
      "Set the access policy on a Bastion bucket.", ("bucket", "Bucket name."),
      ("policy_json", "Policy document as JSON.")),
    t("list_vpcs", "region: str = \"all\"",
      "List Bastion virtual private clouds.", ("region", "Restrict to one region.")),
    t("get_vpc", "vpc_id: str",
      "Fetch one Bastion VPC and its subnets.", ("vpc_id", "The VPC.")),
    t("list_security_groups", "vpc_id: str = \"\"",
      "List Bastion security groups.", ("vpc_id", "Restrict to one VPC.")),
    t("update_security_group", "group_id: str, rules: list[str]",
      "Replace the rules on a Bastion security group.", ("group_id", "The group."),
      ("rules", "Rule expressions.")),
    t("list_load_balancers", "region: str = \"all\"",
      "List Bastion load balancers.", ("region", "Restrict to one region.")),
    t("get_load_balancer_health", "lb_id: str",
      "Report backend health for a Bastion load balancer.", ("lb_id", "The load balancer.")),
    t("list_dns_records", "zone: str",
      "List DNS records in a Bastion zone.", ("zone", "The DNS zone.")),
    t("update_dns_record", "zone: str, name: str, value: str, ttl: int = 300",
      "Create or update a Bastion DNS record.", ("zone", "The zone."),
      ("name", "Record name."), ("value", "Record value."), ("ttl", "TTL in seconds.")),
    t("list_certificates", "expiring_within_days: int = 0",
      "List Bastion TLS certificates.",
      ("expiring_within_days", "Only those expiring within N days; 0 for all.")),
    t("renew_certificate", "certificate_id: str",
      "Renew a Bastion TLS certificate.", ("certificate_id", "The certificate.")),
    t("list_pipelines", "repo: str = \"\"",
      "List Bastion CI/CD pipelines.", ("repo", "Restrict to one repository.")),
    t("trigger_pipeline", "pipeline_id: str, ref: str = \"main\"",
      "Trigger a Bastion pipeline run.", ("pipeline_id", "The pipeline."),
      ("ref", "Git ref to build.")),
    t("get_pipeline_run", "run_id: str",
      "Fetch one Bastion pipeline run and its stage results.", ("run_id", "The run.")),
    t("cancel_pipeline_run", "run_id: str",
      "Cancel an in-flight Bastion pipeline run.", ("run_id", "The run.")),
    t("list_incidents", "status: str = \"open\"",
      "List Bastion platform incidents.", ("status", "\"open\", \"resolved\" or \"all\".")),
    t("get_incident", "incident_id: str",
      "Fetch one Bastion incident and its timeline.", ("incident_id", "The incident.")),
    t("declare_incident", "title: str, severity: str, summary: str",
      "Declare a Bastion platform incident.", ("title", "Incident title."),
      ("severity", "\"sev1\" through \"sev4\"."), ("summary", "What is happening.")),
    t("resolve_incident", "incident_id: str, resolution: str",
      "Resolve a Bastion incident.", ("incident_id", "The incident."),
      ("resolution", "Resolution summary.")),
    t("file_bug", "title: str, details: str, component: str",
      "File a defect against a Bastion platform component.",
      ("title", "One-line summary."), ("details", "Reproduction steps and impact."),
      ("component", "Which component is affected.")),
    t("page_oncall", "rotation: str, message: str",
      "Page the current Bastion on-call engineer.", ("rotation", "Rotation name."),
      ("message", "What to tell them.")),
    t("get_oncall_schedule", "rotation: str, weeks: int = 2",
      "Fetch the upcoming Bastion on-call schedule.", ("rotation", "Rotation name."),
      ("weeks", "How many weeks ahead.")),
    t("list_audit_events", "actor: str = \"\", since: str = \"24h\", limit: int = 100",
      "List Bastion audit-log events.", ("actor", "Restrict to one actor."),
      ("since", "Look-back window."), ("limit", "Maximum events.")),
    t("get_cost_report", "period: str = \"month\", group_by: str = \"service\"",
      "Report Bastion spend for a period.", ("period", "Billing period."),
      ("group_by", "\"service\", \"team\" or \"region\".")),
    t("set_budget_alert", "team: str, monthly_limit_usd: float",
      "Set a Bastion spend alert for a team.", ("team", "Team name."),
      ("monthly_limit_usd", "Monthly threshold in USD.")),
    t("list_service_accounts", "",
      "List Bastion service accounts."),
    t("rotate_service_account_key", "account_id: str",
      "Rotate a Bastion service account's key.", ("account_id", "The service account.")),
]


SERVERS: dict[str, dict] = {
    "northwind-docs": {
        "label": "Northwind Docs",
        "domain": "internal engineering documentation",
        "tools": NORTHWIND_DOCS,
    },
    "helios-helpdesk": {
        "label": "Helios Helpdesk",
        "domain": "customer support desk",
        "tools": HELIOS_HELPDESK,
    },
    "meridian-crm": {
        "label": "Meridian CRM",
        "domain": "sales and customer records",
        "tools": MERIDIAN_CRM,
    },
    "lumen-analytics": {
        "label": "Lumen Analytics",
        "domain": "product analytics and BI",
        "tools": LUMEN_ANALYTICS,
    },
    "bastion-infra": {
        "label": "Bastion Infra",
        "domain": "cloud infrastructure platform",
        "tools": BASTION_INFRA,
    },
}

# The order servers are added to the agent in the cumulative sweep.
ORDER: list[str] = ["northwind-docs", "helios-helpdesk", "meridian-crm",
                    "lumen-analytics", "bastion-infra"]

# One HTTP port per vendor. The servers are separate long-running processes the
# agent connects to by URL — it never spawns them. 8001 and 8002 are taken by
# 01 and 02, so this folder starts at 8010.
PORTS: dict[str, int] = {key: 8010 + i for i, key in enumerate(ORDER)}


def url_for(key: str, host: str = "127.0.0.1") -> str:
    return f"http://{host}:{PORTS[key]}/mcp"

# Which Northwind tool each planted near-duplicate shadows. Used by the harness
# to classify a wrong selection as "near-duplicate of the right tool, wrong
# vendor" rather than a random miss.
CONFUSABLES: dict[str, list[str]] = {
    "search_docs": ["find_documents", "lookup_document", "query_knowledge_base",
                    "search_documentation"],
    "get_doc": ["read_document", "fetch_document", "get_document_content", "retrieve_doc"],
    "create_doc": ["create_page", "new_document", "create_doc_draft", "publish_doc"],
    "list_spaces": ["list_workspaces", "list_projects", "list_namespaces", "list_doc_spaces"],
    "get_doc_history": ["get_revision_history", "document_history", "get_page_versions",
                        "list_doc_revisions"],
}


def tool_owner() -> dict[str, str]:
    """Map every tool name to the server key that exposes it."""
    return {name: key for key, spec in SERVERS.items() for name, _, _ in spec["tools"]}


def cumulative(step: int) -> list[str]:
    """The server keys connected at step N (1-indexed)."""
    return ORDER[:step]


def tool_count(step: int) -> int:
    return sum(len(SERVERS[k]["tools"]) for k in cumulative(step))


def _selfcheck() -> None:
    """Names must be unique across all five servers.

    Real vendors would collide outright — two servers both shipping
    `search_docs` is entirely plausible. We avoid exact collisions because
    `langchain-mcp-adapters` flattens every server's tools into one namespace
    and a duplicate name would silently shadow, turning a measurement of
    *model* confusion into a measurement of *adapter* behaviour. Said out loud
    in the README, because it is a real thing that happens in production.
    """
    seen: dict[str, str] = {}
    for key, spec in SERVERS.items():
        for name, _, _ in spec["tools"]:
            if name in seen:
                raise AssertionError(f"duplicate tool name {name!r}: {seen[name]} and {key}")
            seen[name] = key
    expected = [5, 10, 20, 40, 80]
    actual = [len(SERVERS[k]["tools"]) for k in ORDER]
    if actual != expected:
        raise AssertionError(f"tool counts drifted: {actual} != {expected}")
    owners = tool_owner()
    for right, wrongs in CONFUSABLES.items():
        assert owners[right] == "northwind-docs", right
        for w in wrongs:
            assert w in owners and owners[w] != "northwind-docs", w


_selfcheck()


if __name__ == "__main__":
    for i, key in enumerate(ORDER, 1):
        spec = SERVERS[key]
        print(f"{i}. {spec['label']:<18} {len(spec['tools']):>3} tools   "
              f"cumulative {tool_count(i):>3}   port {PORTS[key]}   ({spec['domain']})")
