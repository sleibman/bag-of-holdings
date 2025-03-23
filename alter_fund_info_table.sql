-- Migration script to modify fund_info table to allow NULL inception_date values

-- Verify current schema
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns
WHERE table_name = 'fund_info' AND column_name = 'inception_date';

-- Alter the fund_info table to allow NULL values for inception_date
ALTER TABLE fund_info 
ALTER COLUMN inception_date DROP NOT NULL;

-- Verify the change
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns
WHERE table_name = 'fund_info' AND column_name = 'inception_date';

-- Done
SELECT 'Migration complete: fund_info.inception_date now allows NULL values' as result;

