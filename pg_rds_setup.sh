#!/bin/bash

# Set variables
DB_INSTANCE_IDENTIFIER="fund-db"
DB_NAME="fundholdings"
DB_USER="funder"
DB_PASSWORD="diver!tsla" # Replace with a secure password
DB_CLASS="db.t4g.micro" # Choose appropriate instance size
STORAGE=20 # GB
VPC_SECURITY_GROUP_IDS="sg-cf22439f sg-01d01279f9b9abf91" # Replace with your security group ID
DB_SUBNET_GROUP="default" # Replace with your subnet group if needed

# Create the RDS PostgreSQL instance
aws rds create-db-instance \
  --db-instance-identifier $DB_INSTANCE_IDENTIFIER \
  --db-instance-class $DB_CLASS \
  --engine postgres \
  --engine-version 17.2 \
  --allocated-storage $STORAGE \
  --master-username $DB_USER \
  --master-user-password $DB_PASSWORD \
  --db-name $DB_NAME \
  --vpc-security-group-ids $VPC_SECURITY_GROUP_IDS \
  --db-subnet-group-name $DB_SUBNET_GROUP \
  --publicly-accessible \
  --backup-retention-period 7 \
  --port 5432

echo "Waiting for RDS instance to become available..."
aws rds wait db-instance-available --db-instance-identifier $DB_INSTANCE_IDENTIFIER

# Get the endpoint for the RDS instance
ENDPOINT=$(aws rds describe-db-instances \
  --db-instance-identifier $DB_INSTANCE_IDENTIFIER \
  --query "DBInstances[0].Endpoint.Address" \
  --output text)

echo "RDS instance endpoint: $ENDPOINT"

# Create tables in the database
# Install the PostgreSQL client if you haven't already:
# sudo apt-get install postgresql-client  # For Debian/Ubuntu
# sudo yum install postgresql  # For RHEL/CentOS/Amazon Linux

# Create SQL file with table creation commands
cat > create_tables.sql << EOF
-- Create the fund_info table
CREATE TABLE fund_info (
    fund_id VARCHAR(50) PRIMARY KEY,
    fund_symbol VARCHAR(20) NOT NULL,
    fund_name VARCHAR(255) NOT NULL,
    inception_date DATE NOT NULL,
    issuer VARCHAR(255) NOT NULL
);

-- Create the holdings table
CREATE TABLE holdings (
    id SERIAL PRIMARY KEY,
    fund_id VARCHAR(50) NOT NULL,
    holding_name VARCHAR(255) NOT NULL,
    holding_symbol VARCHAR(20) NOT NULL,
    percent DECIMAL(10, 4) NOT NULL,
    timestamp_observed TIMESTAMP NOT NULL,
    timestamp_reported TIMESTAMP NOT NULL,
    FOREIGN KEY (fund_id) REFERENCES fund_info(fund_id)
);

-- Create indexes for better performance
CREATE INDEX idx_holdings_fund_id ON holdings(fund_id);
CREATE INDEX idx_holdings_holding_symbol ON holdings(holding_symbol);
EOF

# Execute the SQL commands to create tables
echo "Creating tables in the database..."
export PGPASSWORD=$DB_PASSWORD
psql -h $ENDPOINT -U $DB_USER -d $DB_NAME -f create_tables.sql

echo "Setup complete! Database and tables have been created."


