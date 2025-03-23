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
