CREATE TABLE contracts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    vendor_id UUID REFERENCES vendors(id),
    contract_number TEXT NOT NULL,
    start_date DATE,
    end_date DATE,
    status TEXT NOT NULL DEFAULT 'active',
    risk_tier TEXT,
    UNIQUE (org_id, contract_number)
);

CREATE TABLE purchase_orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    po_number TEXT NOT NULL,
    vendor_id UUID REFERENCES vendors(id),
    contract_id UUID REFERENCES contracts(id),
    purchase_date DATE,
    amount NUMERIC NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    UNIQUE (org_id, po_number)
);

CREATE TABLE payments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    invoice_id UUID REFERENCES invoices(id),
    amount NUMERIC NOT NULL,
    payment_date DATE,
    payment_method TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
);

ALTER TABLE invoices ADD COLUMN IF NOT EXISTS purchase_order_id UUID REFERENCES purchase_orders(id);

CREATE INDEX idx_contracts_org ON contracts(org_id, contract_number);
CREATE INDEX idx_purchase_orders_org ON purchase_orders(org_id, po_number);
CREATE INDEX idx_payments_org_invoice ON payments(org_id, invoice_id, payment_date DESC);
CREATE INDEX idx_invoices_po ON invoices(org_id, purchase_order_id);

ALTER TABLE contracts ENABLE ROW LEVEL SECURITY;
ALTER TABLE contracts FORCE ROW LEVEL SECURITY;
ALTER TABLE purchase_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE purchase_orders FORCE ROW LEVEL SECURITY;
ALTER TABLE payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments FORCE ROW LEVEL SECURITY;

CREATE POLICY contracts_org_isolation ON contracts
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());

CREATE POLICY purchase_orders_org_isolation ON purchase_orders
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());

CREATE POLICY payments_org_isolation ON payments
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());
