-- Module 10: Journal immutability guards (DB-level)

-- Status enum constraint
ALTER TABLE erp.journals
  DROP CONSTRAINT IF EXISTS chk_erp_journals_status;

ALTER TABLE erp.journals
  ADD CONSTRAINT chk_erp_journals_status
  CHECK (journal_status IN ('draft', 'pending_approval', 'approved', 'posted', 'reversed', 'cancelled'));

-- Prevent mutation of posted/reversed/cancelled journals
CREATE OR REPLACE FUNCTION erp.prevent_immutable_journal_update()
RETURNS TRIGGER AS $$
BEGIN
  IF OLD.journal_status IN ('reversed', 'cancelled') THEN
    RAISE EXCEPTION 'Cannot modify journal in status %', OLD.journal_status;
  END IF;
  IF OLD.journal_status = 'posted' THEN
    IF NEW.journal_status = 'reversed' THEN
      RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Cannot modify posted journal (status=%)', OLD.journal_status;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_erp_journals_immutable ON erp.journals;
CREATE TRIGGER trg_erp_journals_immutable
  BEFORE UPDATE ON erp.journals
  FOR EACH ROW
  EXECUTE FUNCTION erp.prevent_immutable_journal_update();

-- Prevent line changes when parent journal is immutable
CREATE OR REPLACE FUNCTION erp.prevent_immutable_journal_line_change()
RETURNS TRIGGER AS $$
DECLARE
  parent_status varchar;
BEGIN
  IF TG_OP = 'DELETE' THEN
    SELECT journal_status INTO parent_status FROM erp.journals WHERE id = OLD.journal_id;
  ELSE
    SELECT journal_status INTO parent_status FROM erp.journals WHERE id = NEW.journal_id;
  END IF;
  IF parent_status IN ('posted', 'reversed', 'cancelled') THEN
    RAISE EXCEPTION 'Cannot modify lines for journal in status %', parent_status;
  END IF;
  IF TG_OP = 'DELETE' THEN
    RETURN OLD;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_erp_journal_lines_immutable ON erp.journal_lines;
CREATE TRIGGER trg_erp_journal_lines_immutable
  BEFORE INSERT OR UPDATE OR DELETE ON erp.journal_lines
  FOR EACH ROW
  EXECUTE FUNCTION erp.prevent_immutable_journal_line_change();
