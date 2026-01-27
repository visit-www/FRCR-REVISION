-- Migration: Add BodyPart enum values to Neon PostgreSQL
-- Run this in Neon Console SQL Editor or via psql

-- Add new BodyPart enum values
ALTER TYPE bodypart ADD VALUE IF NOT EXISTS 'UPPER_GASTROINTESTINAL';
ALTER TYPE bodypart ADD VALUE IF NOT EXISTS 'LOWER_GASTROINTESTINAL';
ALTER TYPE bodypart ADD VALUE IF NOT EXISTS 'MALE_GENITAL';
ALTER TYPE bodypart ADD VALUE IF NOT EXISTS 'SOFT_TISSUE';
ALTER TYPE bodypart ADD VALUE IF NOT EXISTS 'BRAIN_SPINE';

-- Verify the values were added
SELECT enumlabel 
FROM pg_enum 
WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'bodypart') 
ORDER BY enumsortorder;
