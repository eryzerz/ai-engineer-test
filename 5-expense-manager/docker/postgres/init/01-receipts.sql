CREATE TABLE IF NOT EXISTS receipts (
    id SERIAL PRIMARY KEY,
    store_name VARCHAR(255),
    receipt_date DATE,
    total_amount NUMERIC(10, 2),
    tax_amount NUMERIC(10, 2),
    items JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
