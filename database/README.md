# Product database

`backend/product_store.py` defines the v2 SQLAlchemy schema: users, hashed login sessions, calls, contacts, delivery statuses and anonymous counters. Fresh databases are initialized at startup. Local development writes `data/product.db`; deployment uses PostgreSQL.

`002_product_postgres.sql` is generated fresh-schema DDL for review/manual provisioning, including indexes and foreign-key cascades. It is not a v1-to-v2 data migration. `001_initial.sql` belongs to the preserved legacy prototype. Do not apply v1 DDL to a product database or replace an existing user's DB with a demo DB.

A future schema alteration needs a versioned migration and backup/restore rehearsal. Image rollback alone does not revert database changes. Runtime database files and actual user records are excluded from the source ZIP.
