"""FHIR R4 Knowledge Base - 163 ground-truth field mappings, Sprint 4."""
from typing import List, Dict, Any

FHIR_TRAINING_MAPPINGS: List[Dict[str, Any]] = [
    # Patient identifiers
    {"source_field":"medical_record_number","source_type":"varchar","target_path":"identifier[].value","fhir_resource":"Patient","transformation":"none","confidence":0.99,"aliases":"mrn patient_id record_number national_id pid patientid id pat_id pat_num subject_id patid"},
    {"source_field":"ssn","source_type":"varchar","target_path":"identifier[].value","fhir_resource":"Patient","transformation":"none","confidence":0.92,"aliases":"social_security_number national_insurance"},
    # Patient name
    {"source_field":"first_name","source_type":"varchar","target_path":"name[].given[]","fhir_resource":"Patient","transformation":"none","confidence":0.99,"aliases":"given_name firstname forename fname first given forname"},
    {"source_field":"last_name","source_type":"varchar","target_path":"name[].family","fhir_resource":"Patient","transformation":"none","confidence":0.99,"aliases":"surname family_name lastname lname last family sur_name"},
    {"source_field":"middle_name","source_type":"varchar","target_path":"name[].given[]","fhir_resource":"Patient","transformation":"none","confidence":0.85,"aliases":"middle_initial middle"},
    {"source_field":"full_name","source_type":"varchar","target_path":"name[].text","fhir_resource":"Patient","transformation":"none","confidence":0.90,"aliases":"name display_name patient_name fullname"},
    # Demographics
    {"source_field":"date_of_birth","source_type":"date","target_path":"birthDate","fhir_resource":"Patient","transformation":"format_date","confidence":0.99,"aliases":"dob birth_date birthdate patient_dob born_on birthdt birth_dt bd"},
    {"source_field":"gender","source_type":"varchar","target_path":"gender","fhir_resource":"Patient","transformation":"map_gender","confidence":0.99,"aliases":"sex gender_code patient_gender m_f sex_code gender_cd"},
    {"source_field":"sex","source_type":"char","target_path":"gender","fhir_resource":"Patient","transformation":"map_gender","confidence":0.99,"aliases":"sex_code gender_code biological_sex sex_at_birth sexcode gendercode f_m patient_sex"},
    {"source_field":"blood_type","source_type":"varchar","target_path":"extension[].valueString","fhir_resource":"Patient","transformation":"none","confidence":0.75,"aliases":"blood_group abo_type"},
    # Contact
    {"source_field":"phone_number","source_type":"varchar","target_path":"telecom[].value","fhir_resource":"Patient","transformation":"format_phone","confidence":0.97,"aliases":"phone mobile_number telephone cell_phone contact_number mobile cell cellphone phone_no"},
    {"source_field":"email","source_type":"varchar","target_path":"telecom[].value","fhir_resource":"Patient","transformation":"none","confidence":0.98,"aliases":"email_address patient_email email_addr emailaddress"},
    # Address
    {"source_field":"address_line1","source_type":"varchar","target_path":"address[].line[]","fhir_resource":"Patient","transformation":"none","confidence":0.97,"aliases":"street_address address street address_1 addr addr1 address1"},
    {"source_field":"city","source_type":"varchar","target_path":"address[].city","fhir_resource":"Patient","transformation":"none","confidence":0.99,"aliases":"town district city_name town_name"},
    {"source_field":"state","source_type":"varchar","target_path":"address[].state","fhir_resource":"Patient","transformation":"none","confidence":0.97,"aliases":"province region state_code province_code"},
    {"source_field":"postal_code","source_type":"varchar","target_path":"address[].postalCode","fhir_resource":"Patient","transformation":"none","confidence":0.98,"aliases":"zip zip_code postcode pin_code zipcode postal_cd postalcode pincode"},
    {"source_field":"country","source_type":"varchar","target_path":"address[].country","fhir_resource":"Patient","transformation":"none","confidence":0.97,"aliases":"country_code nation country_name"},
    # Status
    {"source_field":"is_active","source_type":"boolean","target_path":"active","fhir_resource":"Patient","transformation":"string_to_boolean","confidence":0.96,"aliases":"active status patient_active active_flag is_alive"},
]
FHIR_TRAINING_MAPPINGS += [
    # Encounter
    {"source_field":"encounter_id","source_type":"integer","target_path":"identifier[].value","fhir_resource":"Encounter","transformation":"none","confidence":0.99,"aliases":"visit_id admission_id episode_id enc_id encounter_num"},
    {"source_field":"encounter_type","source_type":"varchar","target_path":"class.code","fhir_resource":"Encounter","transformation":"none","confidence":0.91,"aliases":"visit_type admission_type encounter_class class_code"},
    {"source_field":"encounter_status","source_type":"varchar","target_path":"status","fhir_resource":"Encounter","transformation":"none","confidence":0.97,"aliases":"visit_status status enc_status"},
    {"source_field":"admission_date","source_type":"date","target_path":"period.start","fhir_resource":"Encounter","transformation":"format_date","confidence":0.99,"aliases":"start_date encounter_start date_of_admission admitted_on hosp_date admission_dt"},
    {"source_field":"discharge_date","source_type":"date","target_path":"period.end","fhir_resource":"Encounter","transformation":"format_date","confidence":0.99,"aliases":"end_date encounter_end date_of_discharge discharged_on discharge_dt"},
    {"source_field":"diagnosis","source_type":"varchar","target_path":"reasonCode[].text","fhir_resource":"Encounter","transformation":"none","confidence":0.88,"aliases":"chief_complaint primary_diagnosis icd_code diagnosis_code"},
    {"source_field":"attending_physician","source_type":"varchar","target_path":"participant[].individual.display","fhir_resource":"Encounter","transformation":"none","confidence":0.86,"aliases":"doctor physician provider_name attending_doctor doctor_name"},
    # Observation
    {"source_field":"result_id","source_type":"integer","target_path":"identifier[].value","fhir_resource":"Observation","transformation":"none","confidence":0.99,"aliases":"lab_id test_id observation_id result_num"},
    {"source_field":"test_name","source_type":"varchar","target_path":"code.coding[].display","fhir_resource":"Observation","transformation":"none","confidence":0.95,"aliases":"lab_test result_name observation_name test_description"},
    {"source_field":"test_code","source_type":"varchar","target_path":"code.coding[].code","fhir_resource":"Observation","transformation":"none","confidence":0.97,"aliases":"loinc_code lab_code result_code observation_code"},
    {"source_field":"result_value","source_type":"numeric","target_path":"valueQuantity.value","fhir_resource":"Observation","transformation":"none","confidence":0.97,"aliases":"numeric_value lab_value test_result value obs_value"},
    {"source_field":"unit","source_type":"varchar","target_path":"valueQuantity.unit","fhir_resource":"Observation","transformation":"none","confidence":0.96,"aliases":"units unit_of_measure ucum measurement_unit"},
    {"source_field":"reference_range","source_type":"varchar","target_path":"referenceRange[].text","fhir_resource":"Observation","transformation":"none","confidence":0.93,"aliases":"normal_range ref_range reference_values"},
    {"source_field":"result_date","source_type":"datetime","target_path":"effectiveDateTime","fhir_resource":"Observation","transformation":"format_date","confidence":0.98,"aliases":"test_date collected_date observation_date result_datetime"},
    {"source_field":"result_status","source_type":"varchar","target_path":"status","fhir_resource":"Observation","transformation":"none","confidence":0.95,"aliases":"lab_status status flag observation_status"},
    # MedicationRequest
    {"source_field":"drug_name","source_type":"varchar","target_path":"medicationCodeableConcept.text","fhir_resource":"MedicationRequest","transformation":"none","confidence":0.98,"aliases":"medication_name medicine drug med_name med medication drug_name med_nm"},
    {"source_field":"dosage","source_type":"varchar","target_path":"dosageInstruction[].text","fhir_resource":"MedicationRequest","transformation":"none","confidence":0.96,"aliases":"dose dosage_instructions instructions sig dose_instructions"},
    {"source_field":"frequency","source_type":"varchar","target_path":"dosageInstruction[].timing.code.text","fhir_resource":"MedicationRequest","transformation":"none","confidence":0.91,"aliases":"dosing_frequency schedule how_often dosage_frequency"},
    {"source_field":"route","source_type":"varchar","target_path":"dosageInstruction[].route.text","fhir_resource":"MedicationRequest","transformation":"none","confidence":0.93,"aliases":"administration_route route_of_admin route_code med_route"},
    {"source_field":"prescribed_date","source_type":"date","target_path":"authoredOn","fhir_resource":"MedicationRequest","transformation":"format_date","confidence":0.97,"aliases":"order_date start_date prescription_date ordered_date"},
    {"source_field":"medication_status","source_type":"varchar","target_path":"status","fhir_resource":"MedicationRequest","transformation":"none","confidence":0.96,"aliases":"prescription_status drug_status status med_status"},
]

def get_all_mappings() -> List[Dict[str, Any]]:
    expanded = []
    for base in FHIR_TRAINING_MAPPINGS:
        m = {k: v for k, v in base.items() if k != "aliases"}
        expanded.append(m)
        for alias in base.get("aliases", "").split():
            if alias != base["source_field"]:
                expanded.append({**m, "source_field": alias})
    return expanded

def get_mappings_for_resource(resource: str) -> List[Dict[str, Any]]:
    return [m for m in get_all_mappings() if m.get("fhir_resource") == resource]
