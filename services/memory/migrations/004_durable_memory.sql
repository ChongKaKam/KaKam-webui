-- Storage lifetime is independent from the recent-memory recall preference.
ALTER TABLE memory_item ALTER COLUMN expires_at DROP NOT NULL;
ALTER TABLE memory_item ALTER COLUMN expires_at DROP DEFAULT;

-- Only remove the legacy default deadline. Preserve explicit deadlines and
-- lifecycle states, including deletion tombstones. Already purged data is gone.
WITH changed AS (
    UPDATE memory_item SET expires_at=NULL
    WHERE expires_at = created_at + interval '30 days'
    RETURNING id, owner
), events AS (
    INSERT INTO memory_event(owner,memory_id,action)
    SELECT owner,id,'retention_default_removed' FROM changed
)
INSERT INTO memory_revision(owner,revision)
SELECT DISTINCT owner,1 FROM changed
ON CONFLICT(owner) DO UPDATE SET revision=memory_revision.revision+1;
