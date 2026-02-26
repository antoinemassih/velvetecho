-- Initialize databases for VelvetEcho integrations

-- Create Temporal database
CREATE DATABASE temporal;

-- Create PatientComet database
CREATE DATABASE patientcomet;

-- Create Lobsterclaws database
CREATE DATABASE lobsterclaws;

-- Create test database
CREATE DATABASE velvetecho_test;

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE temporal TO velvetecho;
GRANT ALL PRIVILEGES ON DATABASE patientcomet TO velvetecho;
GRANT ALL PRIVILEGES ON DATABASE lobsterclaws TO velvetecho;
GRANT ALL PRIVILEGES ON DATABASE velvetecho_test TO velvetecho;
