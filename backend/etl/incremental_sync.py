"""
Incremental Sync – CDC-driven synchronisation.

Bugs fixed vs. previous version
--------------------------------
1. Connection string was hard-coded; now pulled from Settings.
2. "record not found" after a DELETE is normal – no longer counted as error.
3. DELETE handler is idempotent (WHERE … checks row exists before deleting).
4. Duplicate changes for the same (table, record_id) in one batch are
   collapsed to the last one so we never try to INSERT a row that was
   immediately DELETEd.
"""
from typing import Dict, List, Optional
from datetime import datetime
from sqlalchemy import text
import sys
import os

# ── path bootstrap ─────────────────────────────────────────────────────────
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.insert(0, backend_dir)
sys.path.insert(0, os.path.join(backend_dir, 'connector'))
sys.path.insert(0, os.path.join(backend_dir, 'schema_mapper'))

from common.config import settings                          # ← use Settings
from common.database import hospital_db_session, shared_db_session
from common.models import Patient, Encounter
from pipeline import ETLPipeline
from cdc_monitor import CDCMonitor
from common.models import LabResult, Medication


class IncrementalSync:
    """Incremental synchronization driven by data_change_log."""

    def __init__(self, tenant_id: int = 1):
        self.tenant_id = tenant_id
        self.pipeline = ETLPipeline(tenant_id)
        # ── FIX 1: use settings, not a hard-coded literal ──
        self.cdc_monitor = CDCMonitor(settings.hospital_db_url)

    # ── helpers ──────────────────────────────────────────────────────────────
    def get_changes_since_last_sync(self, last_sync_id: Optional[int] = None) -> List[Dict]:
        """
        Eager-load one batch of CDC rows for callers that still use a list.
        Delegates to CDCMonitor.get_changes_since() so query logic lives
        in exactly one place.
        """
        since_id = last_sync_id if last_sync_id is not None else 0
        return self.cdc_monitor.get_changes_since(
            last_change_id=since_id,
            tenant_id=self.tenant_id,
        )

    def _load_persisted_watermark(self) -> int:
        """Load watermark from DB; falls back to 0 for fresh deployments."""
        return self.cdc_monitor.load_watermark(self.tenant_id)

    def _persist_watermark(self, last_change_id: int) -> None:
        """Advance the durable watermark — never moves backwards."""
        self.cdc_monitor.advance_watermark(self.tenant_id, last_change_id)

    @staticmethod
    def _deduplicate(changes: List[Dict]) -> List[Dict]:
        """
        FIX 4 – collapse duplicate (table, record_id) pairs.

        If the same row was INSERTed and then DELETEd inside the same batch
        the intermediate INSERT is meaningless.  Keep only the *last* change
        for each (table_name, record_id) pair, preserving overall ordering.
        """
        seen: Dict[tuple, int] = {}          # key -> index in output list
        out: List[Dict] = []
        for change in changes:
            key = (change['table_name'], change['record_id'])
            if key in seen:
                out[seen[key]] = None        # mark old entry for removal
            seen[key] = len(out)
            out.append(change)
        return [c for c in out if c is not None]

    # ── per-record sync ──────────────────────────────────────────────────────
    def _sync_patient(self, patient_id: int, operation: str) -> bool:
        """
        Sync one patient.  Returns True when the outcome is *expected*
        (success OR a benign "not found after DELETE").
        """
        try:
            if operation == 'DELETE':
                with shared_db_session() as shared_db:
                    shared_db.execute(text("SET app.tenant_id = :tid"), {"tid": str(self.tenant_id)})
                    shared_db.execute(text("""
                        DELETE FROM fhir_patient
                        WHERE  tenant_id          = :tenant_id
                          AND  source_patient_id  = :src
                    """), {'tenant_id': self.tenant_id, 'src': str(patient_id)})
                    shared_db.commit()
                print(f"  Deleted patient {patient_id}")
                return True

            # INSERT / UPDATE – fetch from source
            with hospital_db_session() as hospital_db:
                patient = (
                    hospital_db.query(Patient)
                    .filter(Patient.patient_id == patient_id)
                    .first()
                )

                # FIX 2 – "not found" after an INSERT that was later DELETEd
                # in the same window is normal; treat as success, not error.
                if not patient:
                    print(f"  Patient {patient_id} no longer exists – skipped")
                    return True

                fhir_patient = self.pipeline.mapping_service.map_patient_to_fhir(patient)

                with shared_db_session() as shared_db:
                    self.pipeline.load_patients(shared_db, [fhir_patient])

            print(f"  Synced patient {patient_id} ({operation})")
            return True

        except Exception as e:
            print(f"  ERROR syncing patient {patient_id}: {e}")
            return False

    def _sync_encounter(self, encounter_id: int, operation: str) -> bool:
        """Sync one encounter (same pattern as _sync_patient)."""
        try:
            if operation == 'DELETE':
                with shared_db_session() as shared_db:
                    shared_db.execute(text("SET app.tenant_id = :tid"), {"tid": str(self.tenant_id)})
                    shared_db.execute(text("""
                        DELETE FROM fhir_encounter
                        WHERE  tenant_id             = :tenant_id
                          AND  source_encounter_id   = :src
                    """), {'tenant_id': self.tenant_id, 'src': str(encounter_id)})
                    shared_db.commit()
                print(f"  Deleted encounter {encounter_id}")
                return True

            with hospital_db_session() as hospital_db:
                encounter = (
                    hospital_db.query(Encounter)
                    .filter(Encounter.encounter_id == encounter_id)
                    .first()
                )
                if not encounter:
                    print(f"  Encounter {encounter_id} no longer exists – skipped")
                    return True

                fhir_enc = self.pipeline.mapping_service.map_encounter_to_fhir(encounter)

                with shared_db_session() as shared_db:
                    self.pipeline._load_encounters(shared_db, [fhir_enc])

            print(f"  Synced encounter {encounter_id} ({operation})")
            return True

        except Exception as e:
            print(f"  ERROR syncing encounter {encounter_id}: {e}")
            return False

    def _sync_observation(self, lab_id: int, operation: str) -> bool:
        """Sync one lab result → fhir_observation."""
        try:
            if operation == 'DELETE':
                with shared_db_session() as sdb:
                    sdb.execute(text("SET app.tenant_id = :tid"), {"tid": str(self.tenant_id)})
                    sdb.execute(text("""
                        DELETE FROM fhir_observation
                        WHERE tenant_id = :tid AND source_observation_id = :src
                    """), {'tid': self.tenant_id, 'src': str(lab_id)})
                    sdb.commit()
                return True
            with hospital_db_session() as hdb:
                from common.models import LabResult
                lab = hdb.query(LabResult).filter(LabResult.lab_id == lab_id).first()
                if not lab:
                    return True
                fhir_obs = self.pipeline.mapping_service.map_lab_result_to_fhir(lab)
                with shared_db_session() as sdb:
                    self.pipeline._load_observations(sdb, [fhir_obs])
            return True
        except Exception as e:
            print(f"  ERROR syncing lab {lab_id}: {e}")
            return False

    def _sync_medication(self, med_id: int, operation: str) -> bool:
        """Sync one medication → fhir_medication_request."""
        try:
            if operation == 'DELETE':
                with shared_db_session() as sdb:
                    sdb.execute(text("SET app.tenant_id = :tid"), {"tid": str(self.tenant_id)})
                    sdb.execute(text("""
                        DELETE FROM fhir_medication_request
                        WHERE tenant_id = :tid AND source_medication_id = :src
                    """), {'tid': self.tenant_id, 'src': str(med_id)})
                    sdb.commit()
                return True
            with hospital_db_session() as hdb:
                from common.models import Medication
                med = hdb.query(Medication).filter(Medication.medication_id == med_id).first()
                if not med:
                    return True
                fhir_med = self.pipeline.mapping_service.map_medication_to_fhir(med)
                with shared_db_session() as sdb:
                    self.pipeline._load_medications(sdb, [fhir_med])
            return True
        except Exception as e:
            print(f"  ERROR syncing medication {med_id}: {e}")
            return False

    # ── main entry point ─────────────────────────────────────────────────────
    def sync_incremental(self, last_sync_id: Optional[int] = None) -> Dict:
        """
        Run one incremental-sync cycle.
        Uses iter_changes_since() for memory-safe streaming, and
        advance_watermark() for partial-failure-safe cursor persistence.

        Args:
            last_sync_id: Override watermark (e.g. for replay).
                          When None, loads the durable watermark from DB.
        """
        print("\n" + "=" * 60)
        print("INCREMENTAL SYNC (CDC-Driven, streaming)")
        print("=" * 60)

        if last_sync_id is None:
            last_sync_id = self._load_persisted_watermark()

        print(f"Tenant ID     : {self.tenant_id}")
        print(f"Starting from : change_id > {last_sync_id}")

        stats = {
            'total_changes':  0,
            'synced':         0,
            'errors':         0,
            'by_table':       {},
            'by_operation':   {},
            'last_change_id': last_sync_id,
        }

        TABLE_HANDLERS = {
            'patients':    self._sync_patient,
            'encounters':  self._sync_encounter,
            'lab_results': self._sync_observation,
            'medications': self._sync_medication,
        }

        # Stream in batches — no full list in memory (Risk 3)
        for batch in self.cdc_monitor.iter_changes_since(
            last_sync_id,
            tenant_id=self.tenant_id,
            batch_size=500,
        ):
            raw = batch
            changes = self._deduplicate(raw)
            stats['total_changes'] += len(changes)
            print(f"  Batch: raw={len(raw)}  dedup={len(changes)}")

            batch_ok = True
            for change in changes:
                table  = change['table_name']
                op     = change['operation']
                rec_id = change['record_id']

                stats['by_table'][table]  = stats['by_table'].get(table, 0) + 1
                stats['by_operation'][op] = stats['by_operation'].get(op, 0) + 1

                handler = TABLE_HANDLERS.get(table)
                if handler is None:
                    stats['synced'] += 1
                    continue

                if handler(rec_id, op):
                    stats['synced'] += 1
                    stats['last_change_id'] = change['change_id']
                else:
                    stats['errors'] += 1
                    batch_ok = False

            # Advance watermark only for fully-successful batches (Risk 4)
            if batch_ok and changes:
                self._persist_watermark(changes[-1]['change_id'])

        print("-" * 60)
        print(f"Sync Summary:")
        print(f"  Total Changes      : {stats['total_changes']}")
        print(f"  Successfully Synced: {stats['synced']}")
        print(f"  Errors             : {stats['errors']}")
        print(f"  Last Change ID     : {stats['last_change_id']}")
        return stats
