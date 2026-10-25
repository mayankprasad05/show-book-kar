-- ============================================================================
-- Show-book-kar — indexes
-- Owner: M | Reviewer: H (justifies each pattern) then S (checks UI reads)
-- ============================================================================
--
-- Add an index only where a real query pattern justifies it (README Phase 7
-- rule). These are the patterns the API is expected to exercise:
--
--   1. list movies                      -> movies(id) already a PK; unique on
--      unique(id) is free. No extra index needed here.
--   2. movie by id                      -> already indexed (PK).
--   3. future shows for a movie/date    -> shows(movie_id, start_at).
--   4. show by id                       -> already indexed (PK).
--   5. seats for a show                -> show_seats(show_id).
--   6. availability counts / status    -> show_seats(show_id, status).
--   7. screens by theatre               -> screens(theatre_id).
--   8. overlapping-show prevention     -> exclusion index on screens (or
--      show, depending on the agreed approach).
-- ============================================================================

-- 1. Future shows for a movie and date: matches queries.sql #3
CREATE INDEX IF NOT EXISTS idx_shows_movie_start
ON shows (movie_id, start_at);

-- 2. Seats for a show: matches queries.sql #5 and #6
CREATE INDEX IF NOT EXISTS idx_show_seats_show_id
ON show_seats (show_id);

-- 3. Availability count by status: matches queries.sql #6
CREATE INDEX IF NOT EXISTS idx_show_seats_show_status
ON show_seats (show_id, status);

-- 4. Screens by theatre: needed for the admin theatre/screen lists
CREATE INDEX IF NOT EXISTS idx_screens_theatre_id
ON screens (theatre_id);
