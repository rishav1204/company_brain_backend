import os
import sys

import psycopg

DSN = sys.argv[1] if len(sys.argv) > 1 else os.getenv("POSTGRES_DSN", "")
DB_NAME = sys.argv[2] if len(sys.argv) > 2 else os.getenv("POSTGRES_DB", "company_brain")

if not DSN:
    print(
        "POSTGRES_DSN is required. Pass as first argument or set POSTGRES_DSN env var.",
        file=sys.stderr,
    )
    sys.exit(1)

with psycopg.connect(DSN, autocommit=True) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT version()")
        print(cur.fetchone()[0])
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,))
        if cur.fetchone():
            print(f"Database {DB_NAME} already exists")
        else:
            cur.execute(f'CREATE DATABASE "{DB_NAME}"')
            print(f"Created database {DB_NAME}")
