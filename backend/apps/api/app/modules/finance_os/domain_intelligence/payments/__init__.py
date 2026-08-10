"""
Payment anomaly intelligence shared by treasury and banking.

Two distinct contracts are kept deliberately: `detect_payment_anomalies` (banking
execution gate, severity-tagged flags, blocks on critical) and
`detect_scheduling_anomalies` (treasury pre-scheduling review, string flags).
They live together so the rules stay in one place.
"""
