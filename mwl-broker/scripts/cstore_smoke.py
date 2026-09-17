#!/usr/bin/env python3
"""C-STORE smoke test: sends a synthetic CT instance to the broker so the
store-routing path can be verified end to end (seen_items → rule → target).

Usage: python scripts/cstore_smoke.py [host] [port] [aet] [accession] [study_uid]

Exit 0 when the broker reports DIMSE success.
"""
import sys

from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import CTImageStorage, ExplicitVRLittleEndian, generate_uid
from pynetdicom import AE

host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
port = int(sys.argv[2]) if len(sys.argv) > 2 else 11113
aet = sys.argv[3] if len(sys.argv) > 3 else "MWLBROKER"
accession = sys.argv[4] if len(sys.argv) > 4 else "ACC-SMOKE"
study_uid = sys.argv[5] if len(sys.argv) > 5 else generate_uid()

sop_uid = generate_uid()
meta = FileMetaDataset()
meta.TransferSyntaxUID = ExplicitVRLittleEndian
meta.MediaStorageSOPClassUID = CTImageStorage
meta.MediaStorageSOPInstanceUID = sop_uid

ds = FileDataset(None, {}, file_meta=meta, preamble=b"\0" * 128)
ds.SOPClassUID = CTImageStorage
ds.SOPInstanceUID = sop_uid
ds.Modality = "CT"
ds.AccessionNumber = accession
ds.StudyInstanceUID = study_uid
ds.SeriesInstanceUID = generate_uid()
ds.SeriesNumber = "1"
ds.InstanceNumber = "1"
ds.PatientID = "SMOKE"
ds.PatientName = "Smoke^Test"

ae = AE(ae_title="SMOKETEST")
ae.add_requested_context(CTImageStorage)
assoc = ae.associate(host, port, ae_title=aet)
if not assoc.is_established:
    print(f"FAIL: association to {aet}@{host}:{port} rejected")
    sys.exit(1)
try:
    status = assoc.send_c_store(ds)
finally:
    assoc.release()

if status is None:
    print("FAIL: no C-STORE response")
    sys.exit(1)
print(f"C-STORE acc={accession} sop={sop_uid} → status 0x{status.Status:04x}")
sys.exit(0 if status.Status == 0x0000 else 1)
