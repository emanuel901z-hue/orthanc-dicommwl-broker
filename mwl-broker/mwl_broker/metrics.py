"""Prometheus metrics — single place for all instrumentation."""
from prometheus_client import Counter, Gauge, Histogram

CFIND_REQUESTS = Counter(
    "mwl_cfind_requests_total", "Incoming C-FIND MWL requests", ["result"]
)
CFIND_DURATION = Histogram(
    "mwl_cfind_duration_seconds", "End-to-end C-FIND duration (all upstreams)"
)
UPSTREAM_ANSWERS = Counter(
    "mwl_cfind_upstream_answers_total",
    "Answers returned per upstream source",
    ["source"],
)
CSTORE_TOTAL = Counter(
    "mwl_cstore_total", "Incoming C-STORE forwards", ["target", "status"]
)
ECHO_UP = Gauge(
    "mwl_echo_up", "Last C-ECHO result (1=ok, 0=fail)", ["kind", "name"]
)
SEEN_ITEMS = Gauge("mwl_seen_items", "Rows in seen_items table")
LOCAL_ITEMS = Gauge("mwl_local_worklist_items", "Active local worklist items")
HL7_MESSAGES = Counter(
    "mwl_hl7_messages_total", "Inbound HL7 messages", ["transport", "result"]
)
ATNA_SENT = Counter("mwl_atna_sent_total", "ATNA audit messages delivered", ["event"])
ATNA_FAILED = Counter("mwl_atna_failed_total", "ATNA audit messages that failed", ["event"])
ATNA_DROPPED = Counter("mwl_atna_dropped_total", "ATNA audit messages dropped (queue full)")
ATNA_QUEUE = Gauge("mwl_atna_queue_size", "Buffered ATNA audit messages")
NOTIFY_SENT = Counter("mwl_notify_sent_total", "Alerts delivered to the webhook", ["event"])
NOTIFY_FAILED = Counter(
    "mwl_notify_failed_total", "Alerts that could not be delivered", ["event"]
)
NOTIFY_SUPPRESSED = Counter(
    "mwl_notify_suppressed_total", "Alerts suppressed by the de-bounce", ["event"]
)
SPOOL_ITEMS = Gauge(
    "mwl_spool_items", "Spooled C-STORE instances by status", ["status"]
)
SPOOL_BYTES = Gauge("mwl_spool_bytes", "Bytes held in the C-STORE spool")
SPOOL_OLDEST = Gauge(
    "mwl_spool_oldest_seconds", "Age of the oldest spooled instance"
)
SPOOL_QUEUED = Counter(
    "mwl_spool_queued_total", "Instances spooled because forwarding failed", ["target"]
)
SPOOL_FORWARDED = Counter(
    "mwl_spool_forwarded_total", "Spooled instances that reached their target", ["target"]
)
SPOOL_DEAD = Counter(
    "mwl_spool_dead_total", "Instances that gave up (dead letter)", ["target"]
)
CACHE_ENTRIES = Gauge(
    "mwl_cache_entries", "Cached worklist items per source", ["source"]
)
CACHE_AGE = Gauge(
    "mwl_cache_age_seconds", "Age of the newest cached answer at serve time", ["source"]
)
CACHE_SERVED = Counter(
    "mwl_cache_served_total", "Queries answered from the worklist cache", ["source"]
)
CACHE_REFRESH = Counter(
    "mwl_cache_refresh_total", "Cache snapshot refreshes", ["source", "result"]
)
CACHE_DROPPED = Counter(
    "mwl_cache_dropped_total", "Cached items dropped from the snapshot", ["source", "reason"]
)
CONFIG_FINDINGS = Gauge(
    "mwl_config_findings",
    "Configuration consistency findings by severity",
    ["severity"],
)
BREAKER_STATE = Gauge(
    "mwl_upstream_breaker_state",
    "Circuit breaker state per source (0=closed, 1=half_open, 2=open)",
    ["source"],
)
