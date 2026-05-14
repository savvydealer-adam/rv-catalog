-- Drop NOT NULL on STL RV kb_images.local_path
-- ----------------------------------------------------------------
-- Run in Supabase SQL Editor for project blcoiejnzrdxjwgxmlui ("RV Websits").
--
-- Why: rv-catalog images live as remote URLs (source_url) and have no
-- on-disk local path. The consumer (server/main.py picks
-- `source_url or local_path`) already treats local_path as optional.
-- The NOT NULL is legacy from the original local-disk import pipeline.
--
-- Effect: unblocks `scripts/sync_to_stl_rv.py` running without
-- --skip-images. Existing rows are unaffected.

ALTER TABLE kb_images
  ALTER COLUMN local_path DROP NOT NULL;

-- Verify (should report is_nullable = YES):
SELECT column_name, is_nullable
FROM information_schema.columns
WHERE table_name = 'kb_images' AND column_name = 'local_path';
