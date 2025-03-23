#!/bin/bash

# Load database connection details from .env file
source .env

# Run the migration script
export PGPASSWORD=$DB_PASSWORD
psql -h $DB_HOST -U $DB_USER -d $DB_NAME -f alter_fund_info_table.sql

echo "Migration script executed successfully"

