# app.py (updated with database authentication)
import os
import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query, Depends, Security, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database connection parameters
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME", "fundholdings")
DB_USER = os.getenv("DB_USER", "funder")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# API authentication settings
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

app = FastAPI(title="Fund Holdings API", 
              description="API to retrieve ETF fund holdings information",
              version="1.0.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define response models
class Holding(BaseModel):
    holding_symbol: str
    holding_name: str
    percent: float
    timestamp_reported: str

class FundResponse(BaseModel):
    fund_id: str
    fund_symbol: str
    fund_name: str
    inception_date: Optional[str] = None
    issuer: str
    holdings: List[Holding] = []

class ApiKeyCreate(BaseModel):
    user_id: str
    description: str

class ApiKeyResponse(BaseModel):
    key_id: str
    api_key: str
    user_id: str
    description: str
    created_at: datetime

def get_db_connection():
    """Create and return a database connection."""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            cursor_factory=RealDictCursor  # Returns results as dictionaries
        )
        return conn
    except psycopg2.Error as e:
        print(f"Error connecting to database: {e}")
        raise HTTPException(status_code=500, detail="Database connection error")

# Modify the setup_api_keys_table function
def setup_api_keys_table():
    """Create the api_keys table if it doesn't exist."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # First check if the table exists
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'api_keys'
                );
            """)
            table_exists = cur.fetchone()['exists']
            
            if table_exists:
                # Alter the existing table to set the api_key field size
                cur.execute("""
                    ALTER TABLE api_keys 
                    ALTER COLUMN api_key TYPE VARCHAR(32);
                """)
                conn.commit()
            else:
                # Create the table with the correct field size
                cur.execute("""
                    CREATE TABLE api_keys (
                        key_id VARCHAR(50) PRIMARY KEY,
                        api_key VARCHAR(32) NOT NULL UNIQUE,
                        user_id VARCHAR(50) NOT NULL,
                        description VARCHAR(255),
                        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                        last_used_at TIMESTAMP,
                        is_active BOOLEAN NOT NULL DEFAULT TRUE
                    );
                    
                    CREATE INDEX idx_api_keys_api_key ON api_keys(api_key);
                    CREATE INDEX idx_api_keys_user_id ON api_keys(user_id);
                """)
                conn.commit()
    finally:
        conn.close()

# Create api_keys table at startup
setup_api_keys_table()

def create_api_log_table():
    """Create the api_logs table if it doesn't exist."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS api_logs (
                    log_id SERIAL PRIMARY KEY,
                    key_id VARCHAR(50) REFERENCES api_keys(key_id),
                    user_id VARCHAR(50) NOT NULL,
                    endpoint VARCHAR(255) NOT NULL,
                    method VARCHAR(10) NOT NULL,
                    status_code INTEGER NOT NULL,
                    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
                    request_params JSONB,
                    ip_address VARCHAR(45)
                );
                
                CREATE INDEX IF NOT EXISTS idx_api_logs_user_id ON api_logs(user_id);
                CREATE INDEX IF NOT EXISTS idx_api_logs_timestamp ON api_logs(timestamp);
            """)
            conn.commit()
    finally:
        conn.close()

# Create api_logs table at startup
create_api_log_table()

async def verify_api_key(api_key: str = Security(api_key_header)):
    """Verify the API key provided in the request header and return user info."""
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key is required",
            headers={"WWW-Authenticate": API_KEY_NAME},
        )
        
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT key_id, user_id, is_active
                FROM api_keys
                WHERE api_key = %s
            """, (api_key,))
            
            key_data = cur.fetchone()
            
            if not key_data or not key_data['is_active']:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or inactive API key",
                    headers={"WWW-Authenticate": API_KEY_NAME},
                )
            
            # Update last_used_at timestamp
            cur.execute("""
                UPDATE api_keys
                SET last_used_at = NOW()
                WHERE key_id = %s
            """, (key_data['key_id'],))
            
            conn.commit()
            
            return {"key_id": key_data['key_id'], "user_id": key_data['user_id']}
    finally:
        conn.close()

async def log_api_request(
    endpoint: str,
    method: str,
    status_code: int,
    user_info: dict,
    request_params: dict = None,
    ip_address: str = None
):
    """Log API request to the database."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO api_logs
                (key_id, user_id, endpoint, method, status_code, request_params, ip_address)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                user_info['key_id'],
                user_info['user_id'],
                endpoint,
                method,
                status_code,
                psycopg2.extras.Json(request_params) if request_params else None,
                ip_address
            ))
            conn.commit()
    except Exception as e:
        print(f"Error logging API request: {e}")
    finally:
        conn.close()

@app.get("/")
def read_root():
    return {"message": "Fund Holdings API"}

@app.get("/api/fund/{symbol}", response_model=FundResponse)
async def get_fund(
    symbol: str, 
    holdings: List[str] = Query(None, description="List of holding symbols to filter by"),
    user_info: dict = Depends(verify_api_key)
):
    """
    Get fund information and holdings for a specific fund symbol.
    
    - symbol: The fund symbol (e.g., 'PLTL')
    - holdings: Optional list of specific holding symbols to filter by
    
    Requires API key authentication via X-API-Key header.
    """
    status_code = 200
    request_params = {"symbol": symbol, "holdings": holdings}
    
    try:
        conn = get_db_connection()
        
        try:
            with conn.cursor() as cur:
                # Get fund information
                cur.execute("""
                    SELECT fund_id, fund_symbol, fund_name, 
                           inception_date, issuer
                    FROM fund_info
                    WHERE fund_symbol = %s
                """, (symbol.upper(),))
                
                fund_data = cur.fetchone()
                
                if not fund_data:
                    status_code = 404
                    raise HTTPException(status_code=404, detail=f"Fund with symbol {symbol} not found")
                
                # Convert fund_data to dict for response
                fund_response = dict(fund_data)
                
                # Format inception_date as string if it exists
                if fund_response.get('inception_date'):
                    fund_response['inception_date'] = fund_response['inception_date'].isoformat()
                
                # Get latest report date for this fund
                cur.execute("""
                    SELECT MAX(timestamp_reported) as latest_date
                    FROM holdings
                    WHERE fund_id = %s
                """, (fund_response['fund_id'],))
                
                latest_date = cur.fetchone()['latest_date']
                
                if latest_date:
                    # Build query for holdings
                    holdings_query = """
                        SELECT h.holding_symbol, h.holding_name, h.percent,
                               h.timestamp_reported
                        FROM holdings h
                        WHERE h.fund_id = %s
                        AND h.timestamp_reported = %s
                    """
                    
                    params = [fund_response['fund_id'], latest_date]
                    
                    # Add filter for specific holdings if provided
                    if holdings and len(holdings) > 0:
                        holdings_list = [h.upper() for h in holdings]
                        placeholders = ','.join(['%s'] * len(holdings_list))
                        holdings_query += f" AND h.holding_symbol IN ({placeholders})"
                        params.extend(holdings_list)
                    
                    cur.execute(holdings_query, params)
                    holdings_data = cur.fetchall()
                    
                    # Format the holdings data
                    formatted_holdings = []
                    for holding in holdings_data:
                        holding_dict = dict(holding)
                        holding_dict['timestamp_reported'] = holding_dict['timestamp_reported'].isoformat()
                        formatted_holdings.append(holding_dict)
                    
                    fund_response['holdings'] = formatted_holdings
                else:
                    fund_response['holdings'] = []
                
                return fund_response
        finally:
            conn.close()
    except HTTPException as e:
        status_code = e.status_code
        raise
    except Exception as e:
        status_code = 500
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Log the API request
        await log_api_request(
            endpoint=f"/api/fund/{symbol}",
            method="GET",
            status_code=status_code,
            user_info=user_info,
            request_params=request_params
        )

@app.post("/admin/api-keys", response_model=ApiKeyResponse)
async def create_api_key(key_data: ApiKeyCreate):
    """
    Create a new API key (admin only endpoint).
    This should be protected further in production.
    """
    conn = get_db_connection()
    try:
        # Generate a unique key_id and API key
        key_id = str(uuid.uuid4())
        
        # Generate a 32-character API key
        # Option 1: Use uuid4 and take first 32 chars
        api_key = str(uuid.uuid4()).replace('-', '')[:32]
        
        # Option 2: Use more randomness with secrets module
        # import secrets
        # api_key = secrets.token_hex(16)  # 16 bytes = 32 hex characters
        
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO api_keys
                (key_id, api_key, user_id, description)
                VALUES (%s, %s, %s, %s)
                RETURNING key_id, api_key, user_id, description, created_at
            """, (
                key_id,
                api_key,
                key_data.user_id,
                key_data.description
            ))
            
            new_key = cur.fetchone()
            conn.commit()
            
            return dict(new_key)
    finally:
        conn.close()

@app.get("/admin/api-keys/{user_id}")
async def list_user_api_keys(user_id: str):
    """
    List all API keys for a user (admin only endpoint).
    This should be protected further in production.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT key_id, user_id, description, created_at, last_used_at, is_active
                FROM api_keys
                WHERE user_id = %s
            """, (user_id,))
            
            keys = cur.fetchall()
            return {"keys": [dict(key) for key in keys]}
    finally:
        conn.close()

@app.delete("/admin/api-keys/{key_id}")
async def deactivate_api_key(key_id: str):
    """
    Deactivate an API key (admin only endpoint).
    This should be protected further in production.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE api_keys
                SET is_active = FALSE
                WHERE key_id = %s
                RETURNING key_id
            """, (key_id,))
            
            deactivated = cur.fetchone()
            conn.commit()
            
            if not deactivated:
                raise HTTPException(status_code=404, detail="API key not found")
            
            return {"message": "API key deactivated successfully"}
    finally:
        conn.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

