-- Fix protection levels on remote database
-- Run this manually on the Railway database

-- Update vests table - old ARG prefixed values
UPDATE vests 
SET threat_level = 'ANMaC 2023 - RB2' 
WHERE threat_level = 'ARG_RB2';

UPDATE vests 
SET threat_level = 'ANMaC 2023 - RB3' 
WHERE threat_level = 'ARG_RB3';

UPDATE vests 
SET threat_level = 'ANMaC 2023 - RB4' 
WHERE threat_level = 'ARG_RB4';

UPDATE vests 
SET threat_level = 'NIJ 0101.07 (USA) - HG2' 
WHERE threat_level = 'NIJ_0101.07_HG2';

-- Update vests table - plain RB values (likely STOP III)
UPDATE vests 
SET threat_level = 'STOP III - RB2' 
WHERE threat_level = 'RB2';

UPDATE vests 
SET threat_level = 'STOP III - RB3' 
WHERE threat_level = 'RB3';

UPDATE vests 
SET threat_level = 'STOP III - RB4' 
WHERE threat_level = 'RB4';

-- Update shot_data table - old ARG prefixed values
UPDATE shot_data sd
SET protection_level = 'ANMaC 2023 - RB2'
FROM test_sessions ts
WHERE sd.test_session_id = ts.id
AND ts.protocol = 'ANMaC 2023'
AND sd.protection_level = 'RB2';

UPDATE shot_data sd
SET protection_level = 'ANMaC 2023 - RB3'
FROM test_sessions ts
WHERE sd.test_session_id = ts.id
AND ts.protocol = 'ANMaC 2023'
AND sd.protection_level = 'RB3';

UPDATE shot_data sd
SET protection_level = 'ANMaC 2023 - RB4'
FROM test_sessions ts
WHERE sd.test_session_id = ts.id
AND ts.protocol = 'ANMaC 2023'
AND sd.protection_level = 'RB4';

UPDATE shot_data sd
SET protection_level = 'NIJ 0101.07 (USA) - HG2'
FROM test_sessions ts
WHERE sd.test_session_id = ts.id
AND ts.protocol = 'NIJ 0101.07 (USA)';

-- Update shot_data table - plain RB values (likely STOP III)
UPDATE shot_data sd
SET protection_level = 'STOP III - RB2'
FROM test_sessions ts
WHERE sd.test_session_id = ts.id
AND ts.protocol = 'STOP III'
AND sd.protection_level = 'RB2';

UPDATE shot_data sd
SET protection_level = 'STOP III - RB3'
FROM test_sessions ts
WHERE sd.test_session_id = ts.id
AND ts.protocol = 'STOP III'
AND sd.protection_level = 'RB3';

UPDATE shot_data sd
SET protection_level = 'STOP III - RB4'
FROM test_sessions ts
WHERE sd.test_session_id = ts.id
AND ts.protocol = 'STOP III'
AND sd.protection_level = 'RB4';

-- Update shot_data table - plain RB values (RENAR MA.01-A1 protocol)
UPDATE shot_data sd
SET protection_level = 'RENAR MA01 - RB2'
FROM test_sessions ts
WHERE sd.test_session_id = ts.id
AND ts.protocol = 'RENAR MA.01-A1'
AND sd.protection_level = 'RB2';

UPDATE shot_data sd
SET protection_level = 'RENAR MA01 - RB3'
FROM test_sessions ts
WHERE sd.test_session_id = ts.id
AND ts.protocol = 'RENAR MA.01-A1'
AND sd.protection_level = 'RB3';

UPDATE shot_data sd
SET protection_level = 'RENAR MA01 - RB4'
FROM test_sessions ts
WHERE sd.test_session_id = ts.id
AND ts.protocol = 'RENAR MA.01-A1'
AND sd.protection_level = 'RB4';
