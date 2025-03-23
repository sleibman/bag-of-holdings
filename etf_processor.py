#!/usr/bin/env python3
import os
import re
import csv
import psycopg2
from datetime import datetime
import glob
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Database connection parameters from environment variables
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME", "fundholdings")
DB_USER = os.getenv("DB_USER", "funder")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DATA_DIR = os.getenv("DATA_DIR", "./etf_data")

# Regular expression to match filenames like 4220_PLTL-holdings.csv
FILE_PATTERN = r"(\d+)_([A-Z]+)-holdings\.csv"

def parse_date(date_str):
    """Parse date from string format YYYY-MM-DD."""
    if not date_str or date_str.strip() == "":
        return None
        
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        print(f"Warning: Could not parse date '{date_str}', using None")
        return None

def parse_percentage(percentage_str):
    """Parse percentage string (e.g., '0.87%') to decimal value."""
    try:
        return float(percentage_str.strip('%')) / 100
    except ValueError:
        print(f"Warning: Could not parse percentage '{percentage_str}', using 0")
        return 0.0

def clean_string(s):
    """Remove quotes and whitespace from string."""
    if s:
        return s.strip().strip('"\'')
    return s

def process_file(conn, filepath):
    """Process a single ETF holdings file and update the database."""
    filename = os.path.basename(filepath)
    match = re.match(FILE_PATTERN, filename)
    if not match:
        print(f"Skipping file {filename} - doesn't match expected pattern")
        return

    fund_id, fund_symbol = match.groups()
    
    # Get file modification time for timestamp_observed
    file_mtime = os.path.getmtime(filepath)
    timestamp_observed = datetime.fromtimestamp(file_mtime)
    
    fund_info = {}
    holdings = []
    timestamp_reported = None
    
    # Parse the file
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        lines = content.split('\n')
        
        # Extract fund information from header
        for line in lines[:15]:  # Check first 15 lines for header info
            # Clean the line first - remove quotes around the entire line
            line = clean_string(line)
            
            # Skip empty lines
            if not line:
                continue
                
            # Check for lines with the format "Key: Value"
            if ":" in line:
                # Split only on the first colon
                parts = line.split(':', 1)
                if len(parts) == 2:
                    key = clean_string(parts[0])
                    value = clean_string(parts[1])
                    
                    if key == fund_symbol:
                        fund_info['fund_name'] = value
                    elif key == "Inception Date":
                        fund_info['inception_date'] = parse_date(value)
                    elif key == "Fund Holdings as of":
                        parsed_date = parse_date(value)
                        if parsed_date:
                            timestamp_reported = datetime.combine(parsed_date, datetime.min.time())
                    elif key == "Issuer":
                        fund_info['issuer'] = value
        
        # Extract holdings data
        in_holdings = False
        reader = None
        for i, line in enumerate(lines):
            if "Holding,Symbol,Weighting" in line:  # Look for the header row
                in_holdings = True
                # Use remaining lines for CSV reading
                reader = csv.reader(lines[i+1:])
                break
        
        if reader:
            for row in reader:
                if len(row) >= 3 and row[0] and row[1] and row[2]:  # Make sure we have all fields
                    holdings.append({
                        'holding_name': clean_string(row[0]),
                        'holding_symbol': clean_string(row[1]),
                        'percent': parse_percentage(row[2])
                    })
    
    # Check if we have all required fund info
    missing_info = []
    if not fund_info.get('fund_name'):
        missing_info.append("fund name")
    if not fund_info.get('issuer'):
        missing_info.append("issuer")
    
    if missing_info:
        print(f"Skipping file {filename} - missing required fund information: {', '.join(missing_info)}")
        return
    
    # If timestamp_reported is not found or blank, use timestamp_observed
    if not timestamp_reported:
        print(f"Warning: 'Fund Holdings as of' not found or blank in {filename}, using file timestamp")
        timestamp_reported = timestamp_observed
    
    # Now update the database
    with conn.cursor() as cur:
        # Check if the fund already exists
        cur.execute("SELECT fund_id FROM fund_info WHERE fund_id = %s", (fund_id,))
        existing_fund = cur.fetchone()
        
        if not existing_fund:
            # Insert fund info if it doesn't exist
            cur.execute("""
                INSERT INTO fund_info (fund_id, fund_symbol, fund_name, inception_date, issuer)
                VALUES (%s, %s, %s, %s, %s)
            """, (fund_id, fund_symbol, fund_info['fund_name'], fund_info.get('inception_date'), fund_info['issuer']))
            print(f"Inserted fund info for {fund_symbol}")
        else:
            # Update fund info if it exists
            cur.execute("""
                UPDATE fund_info
                SET fund_symbol = %s, fund_name = %s, inception_date = %s, issuer = %s
                WHERE fund_id = %s
            """, (fund_symbol, fund_info['fund_name'], fund_info.get('inception_date'), fund_info['issuer'], fund_id))
            print(f"Updated fund info for {fund_symbol}")
        
        # Only attempt to insert holdings if there are any
        if holdings:
            # For holdings, we need to handle idempotency based on the report date
            # First check if we have holdings for this fund and report date
            cur.execute("""
                SELECT COUNT(*) FROM holdings
                WHERE fund_id = %s AND timestamp_reported = %s
            """, (fund_id, timestamp_reported))
            existing_holdings_count = cur.fetchone()[0]
            
            if existing_holdings_count > 0:
                print(f"Holdings for {fund_symbol} as of {timestamp_reported.date()} already exist, skipping")
            else:
                # Insert all holdings
                for holding in holdings:
                    cur.execute("""
                        INSERT INTO holdings
                        (fund_id, holding_name, holding_symbol, percent, timestamp_observed, timestamp_reported)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        fund_id,
                        holding['holding_name'],
                        holding['holding_symbol'],
                        holding['percent'],
                        timestamp_observed,
                        timestamp_reported
                    ))
                print(f"Inserted {len(holdings)} holdings for {fund_symbol} as of {timestamp_reported.date()}")
        else:
            print(f"No holdings found for {fund_symbol} as of {timestamp_reported.date()}")
        
        conn.commit()

def main():
    # Check for required environment variables
    if not DB_HOST:
        print("Error: DB_HOST environment variable is not set")
        return
    
    if not DB_PASSWORD:
        print("Error: DB_PASSWORD environment variable is not set")
        return
    
    # Connect to the database
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
    except psycopg2.Error as e:
        print(f"Error connecting to database: {e}")
        return
    
    # Find all files matching the pattern
    file_paths = glob.glob(os.path.join(DATA_DIR, "*-holdings.csv"))
    
    print(f"Found {len(file_paths)} files to process")
    
    # Process each file
    for filepath in file_paths:
        filename = os.path.basename(filepath)
        if re.match(FILE_PATTERN, filename):
            print(f"Processing {filename}...")
            try:
                process_file(conn, filepath)
            except Exception as e:
                print(f"Error processing {filename}: {e}")
                conn.rollback()
    
    conn.close()
    print("Processing complete")

if __name__ == "__main__":
    main()


