# Foresight AI — PCAP Processing Engine & Security Controls

## 1. Asynchronous PCAP Ingestion Architecture

```mermaid
sequenceDiagram
    autonumber
    actor Analyst as SOC Analyst / Probe
    participant API as FastAPI /api/v1/telemetry/pcap
    participant Manager as TelemetryJobManager
    participant Worker as Background Worker (Scapy)
    participant DB as SQLAlchemy Storage
    participant UI as Next.js Live Hub

    Analyst->>API: POST /telemetry/pcap (multipart binary)
    API->>Manager: Validate file size & extension
    Manager->>Manager: Sanitize filename & save to isolated temp storage
    Manager->>API: Return 202 Accepted (job_id, status_url)
    API-->>Analyst: PcapUploadResponse { job_id, status: QUEUED }
    API->>Worker: Spawn background task(process_pcap_job)
    Worker->>Worker: Stream packets with PcapStreamParser
    Worker->>Worker: Bidirectional flow reconstruction
    Worker->>DB: Asynchronously persist reconstructed FlowRecords
    Worker->>Manager: Update status -> COMPLETED (metrics, latency)
    Worker->>Manager: Guaranteed temporary file removal
    UI->>API: GET /telemetry/ingestion/{job_id} (polling)
    API-->>UI: PcapJobStatus { status: COMPLETED, flows: 842 }
```

---

## 2. Defensive Security Controls for PCAP Processing

1. **Path Traversal Defense**:
   - Client-provided filenames are completely stripped of directory paths, relative path tokens (`..`), slashes, and control characters:
     ```python
     safe_name = "".join(c for c in base if c.isalnum() or c in (".", "-", "_"))
     ```
   - Server-side files are stored exclusively with cryptographically unique UUIDs in an isolated temporary staging directory (`foresight_pcap_staging`).

2. **File Size & Memory Limits**:
   - Maximum upload payload size enforced: **50 MB**.
   - Streaming packet iterator (`PcapReader`) processes packets one-by-one without holding entire multi-gigabyte captures in memory.

3. **Concurrency Backpressure**:
   - Background processing worker uses an `asyncio.Semaphore(max_concurrent=4)` to prevent Denial-of-Service or resource exhaustion during high burst upload activity.

4. **Guaranteed File Cleanup**:
   - Every temporary upload file is removed in a `finally` block regardless of whether parsing succeeds, fails, or throws exceptions.
