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
