-- Update CDC trigger function to include tenant_id
CREATE OR REPLACE FUNCTION log_data_change()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        INSERT INTO data_change_log(table_name, operation, record_id, old_data, tenant_id)
        VALUES (TG_TABLE_NAME, TG_OP, OLD.ctid::text, row_to_json(OLD), 1);
        RETURN OLD;
    ELSIF TG_OP = 'INSERT' THEN
        INSERT INTO data_change_log(table_name, operation, record_id, new_data, tenant_id)
        VALUES (TG_TABLE_NAME, TG_OP, NEW.ctid::text, row_to_json(NEW), 1);
        RETURN NEW;
    ELSE
        INSERT INTO data_change_log(table_name, operation, record_id, old_data, new_data, tenant_id)
        VALUES (TG_TABLE_NAME, TG_OP, NEW.ctid::text, row_to_json(OLD), row_to_json(NEW), 1);
        RETURN NEW;
    END IF;
END;
$$;
SELECT 'CDC trigger updated with tenant_id' AS status;
