BEGIN;

-- UUIDs (via gen_random_uuid) are safer than SERIAL
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Drop order for easy re-runs 
DROP TABLE IF EXISTS queryretrieval, querylog, document, "user" CASCADE;

CREATE TABLE "user" (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  email text NOT NULL UNIQUE,
  username text NOT NULL UNIQUE,
  password_hash text NOT NULL,
  role text NOT NULL, -- 'admin' | 'curator' | 'enduser'
  last_activity_ts timestamptz
);

CREATE TABLE document (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  title text NOT NULL,
  type text,
  source text,
  added_by uuid NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  processed boolean NOT NULL DEFAULT false
);

CREATE TABLE querylog (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid REFERENCES "user"(id) ON DELETE CASCADE,
  query_text text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- Junction table for QueryLog (M) - (N) Document
CREATE TABLE queryretrieval (
  query_id uuid NOT NULL REFERENCES querylog(id) ON DELETE CASCADE,
  document_id uuid NOT NULL REFERENCES document(id) ON DELETE CASCADE,
  PRIMARY KEY (query_id, document_id)
);

COMMIT;