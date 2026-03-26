-- Derived attribute: age is computed from birthdate (not stored in User).
-- Run after the User table exists. Optional for Milestone III queries / demo.

USE DataGov_DB;

CREATE OR REPLACE VIEW UserWithAge AS
SELECT
  email,
  username,
  gender,
  birthdate,
  country,
  TIMESTAMPDIFF(YEAR, birthdate, CURDATE()) AS age
FROM User;
