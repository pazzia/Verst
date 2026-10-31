-- Reverts 0001_api_beta.sql (verst_api.db: `python -m verst_api.db down 1`). Drops all beta runtime data.
DROP TABLE IF EXISTS api.rate_counter;
DROP TABLE IF EXISTS api.feedback;
DROP TABLE IF EXISTS api.trip;
DROP TABLE IF EXISTS api.device;
