-- Create tables for local testing

-- Create the fund_info table
CREATE TABLE fund_info (
    fund_id VARCHAR(50) PRIMARY KEY,
    fund_symbol VARCHAR(20) NOT NULL,
    fund_name VARCHAR(255) NOT NULL,
    inception_date DATE,
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

-- Insert sample data
INSERT INTO fund_info (fund_id, fund_symbol, fund_name, inception_date, issuer)
VALUES ('4220', 'PLTL', 'Principal US Small-Cap Adaptive Multi-Factor ETF', '2021-05-19', 'Principal');

-- Insert sample holdings
INSERT INTO holdings (fund_id, holding_name, holding_symbol, percent, timestamp_observed, timestamp_reported)
VALUES 
('4220', 'Comfort Systems USA, Inc.', 'FIX', 0.0087, '2023-10-12 00:00:00', '2023-10-11 00:00:00'),
('4220', 'Meritage Homes Corporation', 'MTH', 0.0077, '2023-10-12 00:00:00', '2023-10-11 00:00:00'),
('4220', 'Radian Group Inc.', 'RDN', 0.0067, '2023-10-12 00:00:00', '2023-10-11 00:00:00'),
('4220', 'Apple Inc.', 'AAPL', 0.0057, '2023-10-12 00:00:00', '2023-10-11 00:00:00'),
('4220', 'Microsoft Corporation', 'MSFT', 0.0042, '2023-10-12 00:00:00', '2023-10-11 00:00:00');

