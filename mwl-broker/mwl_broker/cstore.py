"""Outgoing C-STORE — the single place an instance is pushed to a PACS target.

Used by the live forwarding path (`dimse`) and by the spool retry worker, so a
spooled instance takes exactly the same route as a live one.
"""
import logging

from pydicom.dataset import Dataset
from pynetdicom import AE
from pynetdicom.presentation import build_context

from . import routing

log = logging.getLogger("mwl_broker.cstore")


def send_store(ds: Dataset, target: routing.TargetCfg) -> None:
    """Send one instance; raises on any failure."""
    ae = AE(ae_title=target.calling_aet)
    ctx = build_context(ds.SOPClassUID, [ds.file_meta.TransferSyntaxUID])
    from .upstream import _tls_args

    assoc = ae.associate(target.host, target.port, ae_title=target.aet, contexts=[ctx],
                         tls_args=_tls_args(getattr(target, "tls", False),
                                            getattr(target, "tls_verify", True), target.host))
    if not assoc.is_established:
        raise ConnectionError("association rejected")
    try:
        status = assoc.send_c_store(ds)
        if status is None or status.Status != 0x0000:
            raise ConnectionError(f"C-STORE status {getattr(status, 'Status', 'none')}")
    finally:
        assoc.release()


def resolve_target(session, target_id: int | None) -> routing.TargetCfg | None:
    """Current configuration of a target (used by the spool retry worker)."""
    from .models import PacsTarget

    if target_id is None:
        return None
    return routing._target_cfg(session.get(PacsTarget, target_id))
