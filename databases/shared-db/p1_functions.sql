\set ON_ERROR_STOP on

-- SECTION 0: extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- SECTION 1: completeness trigger function
CREATE OR REPLACE FUNCTION trg_calc_patient_completeness()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.completeness_score :=
        CASE WHEN NEW.family_name IS NOT NULL THEN 15 ELSE 0 END
      + CASE WHEN NEW.given_name IS NOT NULL AND array_length(NEW.given_name,1) > 0 THEN 15 ELSE 0 END
      + CASE WHEN NEW.birth_date IS NOT NULL THEN 15 ELSE 0 END
      + CASE WHEN NEW.gender IS NOT NULL THEN 10 ELSE 0 END
      + CASE WHEN NEW.email IS NOT NULL THEN 10 ELSE 0 END
      + CASE WHEN NEW.phone IS NOT NULL THEN 10 ELSE 0 END
      + CASE WHEN NEW.address_city IS NOT NULL THEN 10 ELSE 0 END
      + CASE WHEN NEW.identifier_value IS NOT NULL THEN 8 ELSE 0 END
      + CASE WHEN NEW.address_postal_code IS NOT NULL THEN 7 ELSE 0 END;
    NEW.updated_at := CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;

SELECT 'Completeness trigger function created' AS status;
