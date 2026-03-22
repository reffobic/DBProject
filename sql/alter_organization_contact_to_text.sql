-- Optional: store full publisher contact strings without VARCHAR(45) truncation.
-- Run against DataGov_DB if your instructor allows schema updates for Milestone II+.
-- After running, set ORG_CONTACT_MAX_LEN=65535 (or similar) when running the crawler.

USE DataGov_DB;

ALTER TABLE `Organization`
  MODIFY COLUMN `contact_information` TEXT NULL;
