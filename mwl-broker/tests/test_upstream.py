"""Upstream helpers: C-ECHO error handling."""
import pytest
from pynetdicom import AE, evt
from pynetdicom.sop_class import Verification

from mwl_broker.upstream import c_echo


def test_c_echo_raises_on_non_success_status():
    def handle_echo(event):
        return 0xA700  # out of resources

    ae = AE(ae_title="BADECHO")
    ae.add_supported_context(Verification)
    srv = ae.start_server(("127.0.0.1", 0), block=False,
                          evt_handlers=[(evt.EVT_C_ECHO, handle_echo)])
    try:
        with pytest.raises(ConnectionError, match="C-ECHO status"):
            c_echo("BADECHO", "127.0.0.1", srv.server_address[1], "MWLBROKER", timeout_s=5)
    finally:
        srv.shutdown()


def test_c_echo_raises_when_association_rejected():
    with pytest.raises(ConnectionError, match="association rejected"):
        c_echo("NOPE", "127.0.0.1", 1, "MWLBROKER", timeout_s=2)
