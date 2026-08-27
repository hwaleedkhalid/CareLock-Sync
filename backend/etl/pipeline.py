"""
ETL Pipeline - Extract, Transform, Load
Synchronizes data from hospital database to FHIR shared database
Sprint 1 Fix: tenant context set before every shared-DB write (RLS compliance)
Sprint 1 Add:  sync_observations() and sync_medications() wired into sync_all()
"""
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.insert(0, backend_dir)

from common.database import hospital_db_session, shared_db_session
from common.models import Patient, Encounter, LabResult, Medication

schema_mapper_path = os.path.join(backend_dir, 'schema_mapper')
sys.path.insert(0, schema_mapper_path)
from mapping_service import MappingService


class ETLPipeline:
    """ETL Pipeline for syncing hospital data to FHIR shared database."""

    def __init__(self, tenant_id: int = 1, progress_cb=None):
        """
        progress_cb: optional callable(step: str, progress: int, records: dict) -> None
        Invoked at entity boundaries so sync_store can persist live progress.
        """
        self.tenant_id = tenant_id
        self.mapping_service = MappingService()
        self.progress_cb = progress_cb
        self.stats = {
            'patients':     {'extracted': 0, 'transformed': 0, 'loaded': 0, 'errors': 0},
            'encounters':   {'extracted': 0, 'transformed': 0, 'loaded': 0, 'errors': 0},
            'observations': {'extracted': 0, 'transformed': 0, 'loaded': 0, 'errors': 0},
            'medications':  {'extracted': 0, 'transformed': 0, 'loaded': 0, 'errors': 0},
        }

    def _emit(self, step: str, progress: int) -> None:
        if self.progress_cb is None:
            return
        try:
            self.progress_cb(step, progress, {
                k: v.get('loaded', 0) for k, v in self.stats.items()
            })
        except Exception as e:
            print(f"  [WARN] progress_cb raised: {e}")

    # ── TENANT CONTEXT HELPER ────────────────────────────────────────────────
    def _set_tenant_context(self, shared_db: Session) -> None:
        """Set RLS tenant context on the shared-DB connection before any write."""
        shared_db.execute(
            text("SET app.tenant_id = :tid"),
            {"tid": str(self.tenant_id)}
        )

    # ── PATIENTS ─────────────────────────────────────────────────────────────
    def extract_patients(self, hospital_db: Session,
                         limit: Optional[int] = None) -> List[Patient]:
        query = hospital_db.query(Patient)
        if limit:
            query = query.limit(limit)
        patients = query.all()
        self.stats['patients']['extracted'] = len(patients)
        return patients

    def transform_patients(self, patients: List[Patient]) -> List[Dict]:
        fhir_patients = []
        for patient in patients:
            try:
                fhir_patients.append(
                    self.mapping_service.map_patient_to_fhir(patient))
                self.stats['patients']['transformed'] += 1
            except Exception as e:
                print(f"  [WARN] transform patient {patient.patient_id}: {e}")
                self.stats['patients']['errors'] += 1
        return fhir_patients

    def load_patients(self, shared_db: Session,
                      fhir_patients: List[Dict]) -> int:
        # ── FIX: set tenant context before every write ──
        self._set_tenant_context(shared_db)
        loaded = 0
        for fhir_patient in fhir_patients:
            try:
                name     = fhir_patient.get('name', [{}])[0]
                telecom  = fhir_patient.get('telecom', [])
                address  = fhir_patient.get('address', [{}])[0]
                phone    = telecom[0].get('value') if len(telecom) > 0 else None
                email    = telecom[1].get('value') if len(telecom) > 1 else None

                shared_db.execute(text("""
                    INSERT INTO fhir_patient (
                        tenant_id, source_patient_id, identifier_value,
                        family_name, given_name, gender, birth_date,
                        phone, email, address_line, address_city,
                        address_state, address_postal_code
                    ) VALUES (
                        :tenant_id, :source_patient_id, :identifier_value,
                        :family_name, :given_name, :gender, :birth_date,
                        :phone, :email, :address_line, :address_city,
                        :address_state, :address_postal_code
                    )
                    ON CONFLICT (tenant_id, source_patient_id) DO UPDATE SET
                        family_name = EXCLUDED.family_name,
                        given_name  = EXCLUDED.given_name,
                        gender      = EXCLUDED.gender,
                        birth_date  = EXCLUDED.birth_date,
                        phone       = EXCLUDED.phone,
                        email       = EXCLUDED.email,
                        updated_at  = CURRENT_TIMESTAMP
                """), {
                    'tenant_id':         self.tenant_id,
                    'source_patient_id': fhir_patient.get('id'),
                    'identifier_value':  fhir_patient.get('identifier', [{}])[0].get('value'),
                    'family_name':       name.get('family'),
                    'given_name':        name.get('given', []),
                    'gender':            fhir_patient.get('gender'),
                    'birth_date':        fhir_patient.get('birthDate'),
                    'phone':             phone,
                    'email':             email,
                    'address_line':      address.get('line', []),
                    'address_city':      address.get('city'),
                    'address_state':     address.get('state'),
                    'address_postal_code': address.get('postalCode'),
                })
                loaded += 1
                self.stats['patients']['loaded'] += 1
            except Exception as e:
                print(f"  [WARN] load patient {fhir_patient.get('id')}: {e}")
                self.stats['patients']['errors'] += 1
        shared_db.commit()
        return loaded

    # ── ENCOUNTERS ───────────────────────────────────────────────────────────
    def _load_encounters(self, shared_db: Session,
                         fhir_encounters: List[Dict]) -> int:
        self._set_tenant_context(shared_db)
        loaded = 0
        for fhir_enc in fhir_encounters:
            try:
                subject_ref       = fhir_enc.get('subject', {}).get('reference', '')
                source_patient_id = subject_ref.split('/')[-1] if '/' in subject_ref else None
                period            = fhir_enc.get('period', {})
                reason            = fhir_enc.get('reasonCode', [{}])[0]
                diagnosis_list    = fhir_enc.get('diagnosis', [])

                shared_db.execute(text("""
                    INSERT INTO fhir_encounter (
                        tenant_id, source_encounter_id, patient_id,
                        class_code, status, period_start, period_end,
                        reason_display, diagnosis
                    )
                    SELECT
                        :tenant_id, :source_encounter_id, fp.id,
                        :class_code, :status, :period_start, :period_end,
                        :reason_display, :diagnosis
                    FROM fhir_patient fp
                    WHERE fp.tenant_id = :tenant_id
                      AND fp.source_patient_id = :source_patient_id
                    ON CONFLICT (tenant_id, source_encounter_id) DO UPDATE SET
                        status     = EXCLUDED.status,
                        period_end = EXCLUDED.period_end,
                        updated_at = CURRENT_TIMESTAMP
                """), {
                    'tenant_id':          self.tenant_id,
                    'source_encounter_id': fhir_enc.get('id'),
                    'source_patient_id':  source_patient_id,
                    'class_code':         fhir_enc.get('class', {}).get('code'),
                    'status':             fhir_enc.get('status'),
                    'period_start':       period.get('start'),
                    'period_end':         period.get('end'),
                    'reason_display':     [reason.get('text')] if reason.get('text') else None,
                    'diagnosis':          [d.get('condition', {}).get('display')
                                           for d in diagnosis_list] or None,
                })
                loaded += 1
                self.stats['encounters']['loaded'] += 1
            except Exception as e:
                print(f"  [WARN] load encounter {fhir_enc.get('id')}: {e}")
                self.stats['encounters']['errors'] += 1
        shared_db.commit()
        return loaded

    # ── OBSERVATIONS (Lab Results) ────────────────────────────────────────────
    def _load_observations(self, shared_db: Session,
                            fhir_observations: List[Dict]) -> int:
        self._set_tenant_context(shared_db)
        loaded = 0
        for obs in fhir_observations:
            try:
                value_qty = obs.get('valueQuantity', {})
                ref_range = obs.get('referenceRange', [{}])[0]
                interp    = obs.get('interpretation', [{}])[0].get('coding', [{}])[0]
                category  = obs.get('category', [{}])[0].get('coding', [{}])[0]
                code      = obs.get('code', {}).get('coding', [{}])[0]
                subject   = obs.get('subject', {}).get('reference', '')
                src_pat   = subject.split('/')[-1] if '/' in subject else None
                enc_ref   = obs.get('encounter', {}).get('reference', '')
                src_enc   = enc_ref.split('/')[-1] if '/' in enc_ref else None

                shared_db.execute(text("""
                    INSERT INTO fhir_observation (
                        tenant_id, patient_id, encounter_id,
                        source_observation_id, status,
                        category_code, category_display,
                        code_value, code_display,
                        value_quantity_value, value_quantity_unit,
                        value_string,
                        interpretation_code, interpretation_display,
                        reference_range_low, reference_range_high,
                        reference_range_text,
                        effective_datetime
                    )
                    SELECT
                        :tenant_id, fp.id,
                        (SELECT fe.id FROM fhir_encounter fe
                         WHERE fe.tenant_id = :tenant_id
                           AND fe.source_encounter_id = :src_enc LIMIT 1),
                        :src_obs_id, :status,
                        :cat_code, :cat_display,
                        :code_val, :code_display,
                        :val_qty_val, :val_qty_unit,
                        :val_str,
                        :interp_code, :interp_display,
                        :ref_low, :ref_high, :ref_text,
                        :effective_dt
                    FROM fhir_patient fp
                    WHERE fp.tenant_id = :tenant_id
                      AND fp.source_patient_id = :src_pat
                    ON CONFLICT (tenant_id, source_observation_id) DO UPDATE SET
                        status                 = EXCLUDED.status,
                        value_quantity_value   = EXCLUDED.value_quantity_value,
                        value_quantity_unit    = EXCLUDED.value_quantity_unit,
                        value_string           = EXCLUDED.value_string,
                        interpretation_code    = EXCLUDED.interpretation_code,
                        effective_datetime     = EXCLUDED.effective_datetime,
                        updated_at             = CURRENT_TIMESTAMP
                """), {
                    'tenant_id':    self.tenant_id,
                    'src_pat':      src_pat,
                    'src_enc':      src_enc,
                    'src_obs_id':   obs.get('id'),
                    'status':       obs.get('status'),
                    'cat_code':     category.get('code'),
                    'cat_display':  category.get('display'),
                    'code_val':     code.get('code'),
                    'code_display': obs.get('code', {}).get('text') or code.get('display'),
                    'val_qty_val':  value_qty.get('value'),
                    'val_qty_unit': value_qty.get('unit'),
                    'val_str':      obs.get('valueString'),
                    'interp_code':  interp.get('code'),
                    'interp_display': interp.get('display'),
                    'ref_low':      ref_range.get('low', {}).get('value'),
                    'ref_high':     ref_range.get('high', {}).get('value'),
                    'ref_text':     ref_range.get('text'),
                    'effective_dt': obs.get('effectiveDateTime'),
                })
                loaded += 1
                self.stats['observations']['loaded'] += 1
            except Exception as e:
                print(f"  [WARN] load observation {obs.get('id')}: {e}")
                self.stats['observations']['errors'] += 1
        shared_db.commit()
        return loaded

    # ── MEDICATIONS ──────────────────────────────────────────────────────────
    def _load_medications(self, shared_db: Session,
                           fhir_medications: List[Dict]) -> int:
        self._set_tenant_context(shared_db)
        loaded = 0
        for med in fhir_medications:
            try:
                dosage   = med.get('dosageInstruction', [{}])[0]
                dose_qty = dosage.get('doseAndRate', [{}])[0].get('doseQuantity', {})
                med_code = med.get('medicationCodeableConcept', {}).get('coding', [{}])[0]
                subject  = med.get('subject', {}).get('reference', '')
                src_pat  = subject.split('/')[-1] if '/' in subject else None
                enc_ref  = med.get('encounter', {}).get('reference', '')
                src_enc  = enc_ref.split('/')[-1] if '/' in enc_ref else None

                shared_db.execute(text("""
                    INSERT INTO fhir_medication_request (
                        tenant_id, patient_id, encounter_id,
                        source_medication_id, status, intent,
                        medication_code_value, medication_code_display,
                        dosage_text, dosage_dose_value, dosage_dose_unit,
                        dosage_frequency_code, dosage_route_code,
                        authored_on
                    )
                    SELECT
                        :tenant_id, fp.id,
                        (SELECT fe.id FROM fhir_encounter fe
                         WHERE fe.tenant_id = :tenant_id
                           AND fe.source_encounter_id = :src_enc LIMIT 1),
                        :src_med_id, :status, :intent,
                        :med_code_val, :med_code_display,
                        :dosage_text, :dose_val, :dose_unit,
                        :freq_code, :route_code,
                        :authored_on
                    FROM fhir_patient fp
                    WHERE fp.tenant_id = :tenant_id
                      AND fp.source_patient_id = :src_pat
                    ON CONFLICT (tenant_id, source_medication_id) DO UPDATE SET
                        status                  = EXCLUDED.status,
                        intent                  = EXCLUDED.intent,
                        medication_code_value   = EXCLUDED.medication_code_value,
                        medication_code_display = EXCLUDED.medication_code_display,
                        dosage_text             = EXCLUDED.dosage_text,
                        dosage_dose_value       = EXCLUDED.dosage_dose_value,
                        dosage_dose_unit        = EXCLUDED.dosage_dose_unit,
                        authored_on             = EXCLUDED.authored_on,
                        updated_at              = CURRENT_TIMESTAMP
                """), {
                    'tenant_id':      self.tenant_id,
                    'src_pat':        src_pat,
                    'src_enc':        src_enc,
                    'src_med_id':     med.get('id'),
                    'status':         med.get('status'),
                    'intent':         med.get('intent', 'order'),
                    'med_code_val':   med_code.get('code'),
                    'med_code_display': (
                        med.get('medicationCodeableConcept', {}).get('text')
                        or med_code.get('display')
                    ),
                    'dosage_text':    dosage.get('text'),
                    'dose_val':       dose_qty.get('value'),
                    'dose_unit':      dose_qty.get('unit'),
                    'freq_code':      dosage.get('timing', {}).get('code', {}).get('coding', [{}])[0].get('code'),
                    'route_code':     dosage.get('route', {}).get('coding', [{}])[0].get('code'),
                    'authored_on':    med.get('authoredOn'),
                })
                loaded += 1
                self.stats['medications']['loaded'] += 1
            except Exception as e:
                print(f"  [WARN] load medication {med.get('id')}: {e}")
                self.stats['medications']['errors'] += 1
        shared_db.commit()
        return loaded

    # ── HIGH-LEVEL SYNC METHODS ───────────────────────────────────────────────
    def sync_patients(self, limit: Optional[int] = None) -> Dict:
        print(f"\n{'='*55}\nSyncing Patients  [tenant={self.tenant_id}]\n{'='*55}")
        with hospital_db_session() as hdb:
            patients      = self.extract_patients(hdb, limit)
            print(f"  Extracted : {len(patients)}")
            fhir_patients = self.transform_patients(patients)
            print(f"  Transformed: {len(fhir_patients)}")
            with shared_db_session() as sdb:
                loaded = self.load_patients(sdb, fhir_patients)
                print(f"  Loaded    : {loaded}")
        return self.stats['patients']

    def sync_encounters(self, limit: Optional[int] = None) -> Dict:
        print(f"\n{'='*55}\nSyncing Encounters  [tenant={self.tenant_id}]\n{'='*55}")
        with hospital_db_session() as hdb:
            q = hdb.query(Encounter)
            if limit:
                q = q.limit(limit)
            encounters = q.all()
            self.stats['encounters']['extracted'] = len(encounters)
            print(f"  Extracted : {len(encounters)}")
            fhir_encs = []
            for enc in encounters:
                try:
                    fhir_encs.append(self.mapping_service.map_encounter_to_fhir(enc))
                    self.stats['encounters']['transformed'] += 1
                except Exception as e:
                    print(f"  [WARN] transform encounter {enc.encounter_id}: {e}")
                    self.stats['encounters']['errors'] += 1
            print(f"  Transformed: {len(fhir_encs)}")
            with shared_db_session() as sdb:
                loaded = self._load_encounters(sdb, fhir_encs)
                print(f"  Loaded    : {loaded}")
        return self.stats['encounters']

    def sync_observations(self, limit: Optional[int] = None) -> Dict:
        print(f"\n{'='*55}\nSyncing Observations  [tenant={self.tenant_id}]\n{'='*55}")
        with hospital_db_session() as hdb:
            q = hdb.query(LabResult)
            if limit:
                q = q.limit(limit)
            labs = q.all()
            self.stats['observations']['extracted'] = len(labs)
            print(f"  Extracted : {len(labs)}")
            fhir_obs = []
            for lab in labs:
                try:
                    fhir_obs.append(self.mapping_service.map_lab_result_to_fhir(lab))
                    self.stats['observations']['transformed'] += 1
                except Exception as e:
                    print(f"  [WARN] transform lab {lab.lab_result_id}: {e}")
                    self.stats['observations']['errors'] += 1
            print(f"  Transformed: {len(fhir_obs)}")
            with shared_db_session() as sdb:
                loaded = self._load_observations(sdb, fhir_obs)
                print(f"  Loaded    : {loaded}")
        return self.stats['observations']

    def sync_medications(self, limit: Optional[int] = None) -> Dict:
        print(f"\n{'='*55}\nSyncing Medications  [tenant={self.tenant_id}]\n{'='*55}")
        with hospital_db_session() as hdb:
            q = hdb.query(Medication)
            if limit:
                q = q.limit(limit)
            meds = q.all()
            self.stats['medications']['extracted'] = len(meds)
            print(f"  Extracted : {len(meds)}")
            fhir_meds = []
            for med in meds:
                try:
                    fhir_meds.append(self.mapping_service.map_medication_to_fhir(med))
                    self.stats['medications']['transformed'] += 1
                except Exception as e:
                    print(f"  [WARN] transform med {med.medication_id}: {e}")
                    self.stats['medications']['errors'] += 1
            print(f"  Transformed: {len(fhir_meds)}")
            with shared_db_session() as sdb:
                loaded = self._load_medications(sdb, fhir_meds)
                print(f"  Loaded    : {loaded}")
        return self.stats['medications']

    def sync_all(self, limit: Optional[int] = None) -> Dict:
        print(f"\n{'='*55}")
        print(f"FULL ETL SYNC  tenant_id={self.tenant_id}  limit={limit or 'all'}")
        print(f"{'='*55}")
        start = datetime.now()
        self._emit('patients', 5)
        self.sync_patients(limit)
        self._emit('encounters', 30)
        self.sync_encounters(limit)
        self._emit('observations', 55)
        self.sync_observations(limit)
        self._emit('medications', 80)
        self.sync_medications(limit)
        self._emit('finalising', 95)
        duration = (datetime.now() - start).total_seconds()
        total_loaded = sum(v['loaded'] for v in self.stats.values())
        total_errors = sum(v['errors'] for v in self.stats.values())
        print(f"\n{'='*55}")
        print(f"SYNC COMPLETE  {duration:.2f}s  loaded={total_loaded}  errors={total_errors}")
        print(f"{'='*55}")
        for resource, s in self.stats.items():
            print(f"  {resource:12s}: extracted={s['extracted']:4d}  "
                  f"loaded={s['loaded']:4d}  errors={s['errors']}")
        return self.stats


if __name__ == "__main__":
    pipeline = ETLPipeline(tenant_id=1)
    pipeline.sync_all(limit=10)
