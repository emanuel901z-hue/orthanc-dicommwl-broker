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
