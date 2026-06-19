# Module 6 — Document Management System (DMS) + OCR + Financial Document Intelligence

This module turns uploads into **versioned, searchable, workflow-linked, auditable document objects** (not “dumb files”). OCR/extraction produces **suggestions** with confidence and review routing; it **must not** directly mutate accounting.

## What’s implemented (current)

### Data model (`documents.*`)

Core tables (with RLS org isolation policies):
- **`documents.documents`**: document registry (current version pointers + security/retention metadata)
- **`documents.document_versions`**: immutable version history
- **`documents.extractions`**: structured extracted data + confidence + status (`completed|needs_review|corrected`)
- **`documents.classifications`**: classification results + confidence
- **`documents.evidence_links`**: link documents to workflows/entities/audit evidence
- **`documents.semantic_embeddings`**: whole-doc embeddings (pgvector) for semantic search
- **`documents.semantic_chunks`**: **chunk/page embeddings + keyword index** for hybrid search
- **`documents.duplicate_candidates`**: detected duplicates (checksum + fuzzy invoice matching + semantic similarity)

Migrations:
- `021_documents_dms.sql`
- `022_documents_semantic_search.sql`
- `023_documents_security_retention.sql`
- `024_documents_review_workflow.sql`
- `025_documents_versioning_current.sql`
- `026_documents_semantic_chunks.sql`

### Storage (Cloudinary-first)

- **Cloudinary upload** (server-side upload for base64; and direct-to-cloud signed uploads).
- **Signed delivery URLs** with short expiry.
- **Preview URLs** for UI (thumbnail + preview render, including **PDF first-page render**).

### OCR (provider-selectable) + extraction

OCR is provider-selectable via env:
- **`OCR_PROVIDER=auto|aws_textract|gcp_documentai|pypdf|openai_vision`**
- Optional hybrid cleanup validation: **`OCR_HYBRID_VALIDATE=true|false`**

Providers implemented:
- **AWS Textract** adapter (sync `DetectDocumentText` path; normalized `page_outputs`)
- **Google Document AI** adapter (sync `process_document`; normalized `page_outputs`)
- PDF text extraction (`pypdf`) fallback
- Image OCR (`openai_vision`) fallback

### Security pipeline

- MIME validation + size validation at API layer (upload validators).
- Malware scanning:
  - **Exec mode** (`clamscan`) and **daemon mode** (`clamd` INSTREAM protocol).
- Retention metadata (`retention_until`) and enforcement hook.

### Search

- Whole-doc semantic search: `/documents/search/semantic`
- Hybrid chunk search: `/documents/search/hybrid` (vector + optional keyword filter + optional doc_type filter)

### Duplicate detection (enterprise upgrades)

- Checksum match
- Invoice matching (fuzzy normalization)
- Vendor + total heuristics
- Semantic similarity using **chunk embeddings**

### Human review correction loop

- Correction endpoint creates:
  - a new immutable extraction (`human_correction`)
  - a new document version with `change_reason="extraction_correction"` (audit milestone)

### Workflow / Action Center integration

- Realtime events are pushed to workflow realtime hub and are **enriched with preview URLs** for UI.

---

## Environment variables

### Cloudinary
- `CLOUDINARY_CLOUD_NAME`
- `CLOUDINARY_API_KEY`
- `CLOUDINARY_API_SECRET`
- `CLOUDINARY_SECURE=true`
- `CLOUDINARY_UPLOAD_PRESET` (recommended; see UI notes below)
- `DOCUMENTS_BUCKET_PREFIX=finance-docs`

### OCR selection
- `OCR_PROVIDER=auto|aws_textract|gcp_documentai|pypdf|openai_vision`
- `OCR_HYBRID_VALIDATE=true|false`

### AWS Textract
- `AWS_REGION`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_SESSION_TOKEN` (optional)
- `TEXTRACT_S3_BUCKET` (reserved for async job path)

### Google Document AI
- `GCP_PROJECT_ID`
- `GCP_LOCATION=us`
- `GCP_DOCUMENTAI_PROCESSOR_ID`
- `GCP_CREDENTIALS_JSON` (service account JSON string; use secrets manager in prod)

### Quality / security / retention
- `DOCUMENT_CONFIDENCE_THRESHOLD=0.85`
- `DOCUMENT_RETENTION_YEARS=8`
- `CLAMAV_ENABLED=true|false`
- `CLAMAV_MODE=exec|clamd`
- `CLAMAV_EXECUTABLE=clamscan`
- `CLAMAV_CLAMD_HOST=127.0.0.1`
- `CLAMAV_CLAMD_PORT=3310`

---

## API Reference (Module 6)

All routes are under the FastAPI prefix: **`/api/v1`**.

### Documents

#### `POST /documents`
Create a document via server-side upload (base64 payload).

Request (Pydantic: `DocumentCreateRequest`):
```json
{
  "document_type": "invoice",
  "file_name": "acme_invoice_001.pdf",
  "mime_type": "application/pdf",
  "file_size": 123456,
  "base64_content": "base64-encoded-bytes-or-null",
  "metadata": {
    "source": "email",
    "vendor_hint": "ACME"
  }
}
```

Response:
```json
{
  "request_id": "…",
  "item": {
    "id": "…",
    "document_type": "invoice",
    "file_name": "acme_invoice_001.pdf",
    "mime_type": "application/pdf",
    "storage_path": "cloudinary://<cloud>/<resource_type>/<public_id>",
    "checksum_hash": "…",
    "status": "uploaded",
    "file_size": 123456,
    "created_at": "…",
    "signed_url": "https://…",
    "requires_human_review": false,
    "confidence_threshold": 0.85
  }
}
```

#### `GET /documents`
List documents.

Query params:
- `limit` (1..200, default 50)
- `document_type` (optional)

Response:
```json
{
  "request_id": "…",
  "items": [
    {
      "id": "…",
      "document_type": "invoice",
      "file_name": "…",
      "mime_type": "…",
      "storage_path": "…",
      "checksum_hash": "…",
      "status": "…",
      "file_size": 123,
      "created_at": "…",
      "signed_url": "https://…"
    }
  ]
}
```

#### `POST /documents/bulk`
Bulk create (server-side base64).

Request:
```json
[
  { "document_type": "invoice", "file_name": "a.pdf", "mime_type": "application/pdf", "file_size": 1, "base64_content": "…", "metadata": {} }
]
```

Response:
```json
{
  "request_id": "…",
  "results": [
    { "index": 0, "status": "created", "item": { "id": "…" } }
  ]
}
```

#### `POST /documents/{document_id}/versions`
Create a new document version (immutably) via server-side base64 upload.

Request (`DocumentVersionRequest`):
```json
{
  "change_reason": "corrected_scan",
  "file_name": "acme_invoice_001_v2.pdf",
  "mime_type": "application/pdf",
  "file_size": 123456,
  "base64_content": "…",
  "metadata": { "note": "rescanned" }
}
```

Response:
```json
{ "request_id": "…", "item": { "id": "…", "document_id": "…", "version_number": 2, "storage_path": "…" } }
```

---

### Uploads (Cloudinary direct-to-cloud)

This is the **recommended frontend flow** for large files.

#### `POST /uploads/cloudinary/sign`
Returns signed parameters for direct upload to Cloudinary.

Backpressure:
- returns `{ "error": "OCR pipeline busy; try again shortly" }` if OCR queue lag is high.

Request (`CloudinaryDirectUploadSignRequest`):
```json
{
  "document_type": "invoice",
  "file_name": "acme.pdf",
  "mime_type": "application/pdf"
}
```

Response:
```json
{
  "request_id": "…",
  "item": {
    "cloud_name": "…",
    "api_key": "…",
    "timestamp": 1716…,
    "folder": "finance-docs/<org_id>/invoice/2026/05/28",
    "resource_type": "raw",
    "public_id": "finance-docs/<org_id>/invoice/2026/05/28/acme-1716…",
    "signature": "…",
    "upload_preset": "optional"
  }
}
```

Frontend must upload to Cloudinary using:
- the provided `folder`, `public_id`, `timestamp`, `signature`, and optionally `upload_preset`.

#### `POST /uploads/cloudinary/sign-batch`
Same as sign, but accepts a list and returns `{results:[…]}`.

#### `GET /uploads/cloudinary/resumable-config`
Returns recommended chunk size + endpoints.

#### `POST /uploads/cloudinary/finalize`
After successful Cloudinary upload, register document in DB (creates document + version, queues OCR, requests malware scan).

Request (`CloudinaryFinalizeRequest`):
```json
{
  "document_type": "invoice",
  "file_name": "acme.pdf",
  "mime_type": "application/pdf",
  "file_size": 123456,
  "checksum_hash": "sha256-hex",
  "resource_type": "raw",
  "public_id": "finance-docs/<org_id>/invoice/2026/05/28/acme-1716…",
  "secure_url": "https://res.cloudinary.com/…",
  "metadata": {}
}
```

Response:
```json
{ "request_id": "…", "item": { "id": "…", "storage_path": "cloudinary://…" , "signed_url": "https://…" } }
```

Policy enforcement:
- `public_id` must start with: `DOCUMENTS_BUCKET_PREFIX/<org_id>/<document_type>/`

---

### OCR

#### `POST /ocr/request`
Queue OCR job.

Request (`OCRRequest`):
```json
{ "document_id": "…", "extraction_type": "invoice_ocr", "force": false }
```

For expense receipts, use `extraction_type: "receipt_ocr"` (or upload with `document_type: "receipt"` — the pipeline selects `receipt_ocr` automatically).

Response:
```json
{ "request_id": "…", "queued": true }
```

#### `POST /ocr/process`
Process OCR synchronously (debug/admin usage).

Request:
```json
{ "document_id": "…", "extraction_type": "invoice_ocr", "force": false }
```

Response:
```json
{
  "request_id": "…",
  "result": {
    "ocr": {
      "provider": "aws_textract|gcp_documentai|pypdf|openai_vision|stub",
      "text": "…",
      "pages": 1,
      "signed_url": "https://…",
      "page_outputs": [ { "page_number": 1, "text": "…" } ]
    },
    "extraction": {
      "id": "…",
      "document_id": "…",
      "extraction_type": "invoice_ocr",
      "extracted_data": { "…": "…" },
      "confidence_score": 0.9,
      "extraction_status": "completed|needs_review",
      "processed_at": "…"
    }
  }
}
```

---

### Classification

#### `POST /documents/classify`
Request:
```json
{ "document_id": "…", "hint": "invoice" }
```

Response:
```json
{ "request_id": "…", "item": { "id": "…", "classification": "invoice", "confidence_score": 0.9 } }
```

---

### Evidence links

#### `POST /evidence/links`
Request (`EvidenceLinkRequest`):
```json
{
  "document_id": "…",
  "entity_type": "journal|payment|workflow|approval|audit",
  "entity_id": "…",
  "workflow_id": "optional",
  "metadata": {}
}
```

Response:
```json
{ "request_id": "…", "item": { "id": "…", "document_id": "…", "entity_type": "…", "entity_id": "…" } }
```

#### `GET /evidence/links?entity_type=…&entity_id=…`
Response:
```json
{ "request_id": "…", "items": [ { "id": "…", "document_id": "…" } ] }
```

#### `POST /evidence/links/bulk`
Request: array of `EvidenceLinkRequest`  
Response: `{ results: [...] }`

---

### Previews (UI)

#### `GET /documents/{document_id}/previews`
Response:
```json
{
  "request_id": "…",
  "item": {
    "document_id": "…",
    "download_url": "https://…",
    "thumbnail_url": "https://…",
    "preview_url": "https://…"
  }
}
```

---

### Search

#### `GET /documents/search/semantic?q=...&limit=20&document_type=invoice`
Response: `{ items: [...] }` (whole-doc embedding matches)

#### `GET /documents/search/hybrid?q=...&keyword=...&limit=20&document_type=invoice`
Response:
```json
{
  "request_id": "…",
  "items": [
    {
      "document_id": "…",
      "page_number": 1,
      "chunk_index": 0,
      "distance": 0.12,
      "snippet": "…",
      "document_type": "invoice",
      "file_name": "…",
      "mime_type": "…",
      "storage_path": "…",
      "status": "…",
      "metadata": {}
    }
  ]
}
```

---

### Human correction loop

#### `POST /documents/extractions/correct`
Request (`ExtractionCorrectionRequest`):
```json
{
  "document_id": "…",
  "corrected_data": {
    "invoice_number": "INV-001",
    "total_amount": 1234.56,
    "gstin": "…"
  },
  "reviewer_notes": "Fixed invoice number OCR artifact"
}
```

Response:
```json
{
  "request_id": "…",
  "item": {
    "extraction": { "id": "…", "extraction_type": "human_correction", "extraction_status": "corrected", "confidence_score": 1.0 },
    "version": { "id": "…", "change_reason": "extraction_correction" }
  }
}
```

---

### Pipeline / reliability

#### `GET /documents/pipeline/status`
Response:
```json
{
  "request_id": "…",
  "queues": { "ai_ocr": "ai.ocr", "processing_extract": "processing.extract", "processing_embed": "processing.embed" },
  "lag": { "ai_ocr": 0, "processing_extract": 0, "processing_embed": 0 },
  "dlq_lag": { "ai_ocr": 0, "processing_extract": 0, "processing_embed": 0 }
}
```

---

## Frontend integration notes (high-signal)

### Recommended upload path (direct-to-Cloudinary)
- Use `POST /uploads/cloudinary/sign` to get **server-approved** `public_id` and signature.
- Upload directly to Cloudinary using those fields (and `upload_preset` if provided).
- Call `POST /uploads/cloudinary/finalize` to register document and trigger OCR + malware scanning.
- UI should treat `storage_path` as opaque; use `signed_url` / `/previews` for display.

### Preview rendering
- For PDFs, UI should use `preview_url` / `thumbnail_url` (first-page render), not attempt inline PDF rendering unless desired.
- Always assume URLs expire; refresh by calling `/previews` again.

### Realtime updates
- Document/OCR/duplicate events are pushed to realtime hub on `channel="documents"`.
- Payloads include `previews` when possible:
  - `payload.previews.download_url`
  - `payload.previews.thumbnail_url`
  - `payload.previews.preview_url`

### Review UX pattern
- If extraction is `needs_review` (triggered by confidence threshold), show:
  - preview image
  - extracted fields + per-field confidence (from extracted_data)
  - correction form that calls `/documents/extractions/correct`
- Corrections create an immutable history (new extraction row + new document version).

### Search UX pattern
- Use `/documents/search/hybrid` for “search inside docs” (chunk/page results + snippet).
- Use `/documents/search/semantic` for “find similar docs” (whole-doc similarity).

---

## Cloudinary hardening (recommended operational config)

To complete enforcement at Cloudinary-side (not just server-side signing):
- Create an **upload preset** and set:
  - allowed formats (pdf, png, jpg, jpeg, webp)
  - max file size
  - unsigned disabled (require signature)
- Configure folder restrictions to avoid cross-org folder writes (Cloudinary account policy + preset).

### Copy/paste: Cloudinary upload preset checklist (match backend validators)

Backend API validators currently enforce:
- **Max size**: **50 MB** (`file_size > 50 * 1024 * 1024` rejected)
- **Allowed MIME types**:
  - `application/pdf`
  - `image/png`
  - `image/jpeg` / `image/jpg`
  - `image/webp`
  - `text/csv`
  - `application/xml`
  - `application/zip`
  - `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`

Recommended Cloudinary preset(s):

#### Preset A (Documents UI upload — strict, recommended)

Use this preset for the frontend “Upload documents” UI (invoices, receipts, PDFs, images). Keep it tight.

- **Preset name**: `finance_documents_strict` (example)
- **Unsigned**: **OFF** (signed uploads only)
- **Allowed formats**:
  - `pdf`
  - `png`
  - `jpg`
  - `jpeg`
  - `webp`
- **Max file size**: `52428800` (50 * 1024 * 1024)
- **Unique filename**: ON
- **Overwrite**: OFF
- **Use filename**: OFF (server provides `public_id`)
- **Resource type**:
  - `raw` for PDFs
  - `image` for images
  - (The backend returns `resource_type` in `/uploads/cloudinary/sign`.)

Optional (strongly recommended) delivery/transform defaults for UI:
- **PDF preview** (first page render): deliver as `image` with transformation `{ page: 1, fetch_format: "jpg", quality: "auto" }`
- **Thumbnail**: `{ width: 320, height: 320, crop: "fit", fetch_format: "jpg", quality: "auto" }`

#### Preset B (Data imports — optional, only if you really want CSV/XLSX/XML/ZIP via Cloudinary)

If you plan to ingest structured files (CSV/XLSX/XML/ZIP) through the same direct-upload channel, create a separate preset so the UI “documents” preset remains strict.

- **Preset name**: `finance_documents_imports` (example)
- **Unsigned**: OFF
- **Allowed formats** (Cloudinary is extension-based):
  - `csv`
  - `xlsx`
  - `xml`
  - `zip`
- **Max file size**: `52428800`
- **Resource type**: `raw`

#### Folder / org isolation policy (critical)

The backend enforces that `public_id` begins with:

`<DOCUMENTS_BUCKET_PREFIX>/<org_id>/<document_type>/`

So in the frontend:
- Do **not** generate `public_id` yourself.
- Always use the server-provided `public_id` from `POST /uploads/cloudinary/sign`.

#### Backpressure behavior (UI hint)

If `POST /uploads/cloudinary/sign` returns:
- `{ "error": "OCR pipeline busy; try again shortly" }`

then the UI should show a retry-able error (and/or exponential backoff) before attempting the Cloudinary upload.
