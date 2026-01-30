# Security Layer - Comprehensive Audit Report

**Version:** v0.1.6
**Audit Date:** January 2026
**Project:** Security Layer - Physical Port Security for Enterprise

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Project Overview](#project-overview)
3. [Architecture Analysis](#architecture-analysis)
4. [Technology Stack](#technology-stack)
5. [Security Assessment](#security-assessment)
6. [Code Quality Analysis](#code-quality-analysis)
7. [Database Schema](#database-schema)
8. [API Documentation](#api-documentation)
9. [Dependency Analysis](#dependency-analysis)
10. [Performance Considerations](#performance-considerations)
11. [Recommendations](#recommendations)

---

## Executive Summary

**Security Layer** is a USB port monitoring solution for enterprise environments. The system consists of:
- A **Flask-based server** with real-time dashboard
- A **Windows agent** for USB device monitoring
- **Server-Sent Events (SSE)** for real-time updates

### Key Findings

| Category | Status | Notes |
|----------|--------|-------|
| Architecture | ⚠️ Fair | Well-structured but CSV-based storage limits scalability |
| Security | 🔴 Critical Issues | Plaintext passwords, no API authentication |
| Code Quality | ✅ Good | Clean, modular, well-documented |
| Documentation | ⚠️ Partial | Marketing docs exist, technical docs missing |
| Performance | ⚠️ Limited | Single-worker, CSV file locks create bottlenecks |

### Risk Summary

- **Critical:** 3 vulnerabilities (passwords, auth, session management)
- **High:** 5 issues (rate limiting, binary verification, input validation)
- **Medium:** 4 concerns (database, logging, monitoring)

---

## Project Overview

### Purpose
Enterprise USB port security monitoring system that tracks physical USB ports across organization endpoints and provides real-time visibility through a centralized dashboard.

### Components

```
SecurityLayer/
├── DASHBOARD/                    # Flask server + Web UI
│   ├── AA_waiting_for_csv.py     # Main server (538 lines)
│   ├── login-page/               # Authentication UI
│   ├── landing-page/             # Marketing page
│   ├── dashboard-page/           # Admin dashboard
│   │   └── download-zip/         # Agent package builder
│   │       └── SecurityLayer/    # Agent source code
│   │           └── usbSecurity/  # 9 Python scripts
├── DATA/                         # CSV databases
├── TOOLS/                        # Utilities
├── config.yaml                   # Configuration
└── docker-compose.yml            # Container orchestration
```

### Workflow

1. **Agent Installation** → Windows endpoint installs portable agent from ZIP
2. **USB Monitoring** → Agent detects USB connect/disconnect events via WMI
3. **Data Collection** → UsbTreeView.exe enumerates USB ports
4. **Server Sync** → Agent sends CSV data to `/update-dashboard`
5. **Real-time Display** → Dashboard receives updates via SSE stream

---

## Architecture Analysis

### Server Component (`AA_waiting_for_csv.py`)

| Aspect | Implementation | Assessment |
|--------|----------------|------------|
| Framework | Flask with Gunicorn/Gevent | ✅ Appropriate |
| Data Store | CSV files with file locking | ⚠️ Not scalable |
| Real-time | Server-Sent Events (SSE) | ✅ Efficient |
| Auth | CSV-based user storage | 🔴 Insecure |
| Deployment | Docker with auto-deploy | ✅ Good |

### Agent Components

| Script | Purpose | Lines |
|--------|---------|-------|
| `B_run.py` | Main launcher, process locking | 291 |
| `BA_usb_watcher.py` | WMI-based USB monitoring | 254 |
| `C_run.py` | Async orchestrator | 46 |
| `CA_get_pc_id.py` | Machine ID generation | 76 |
| `CB_create_usb_report.py` | USB enumeration | 90 |
| `CC_convert_report_to_csv.py` | Report parsing | 187 |
| `CD_send_final_csv_to_server.py` | Data transmission | 32 |
| `AA_installer.py` | Setup & registration | 400+ |
| `AA_uninstaller.py` | Cleanup | 150+ |

### Frontend Architecture

- **SPA** with dynamic page loading
- **Vanilla JavaScript** (no frameworks)
- **SessionStorage** for authentication state
- **EventSource API** for SSE connections

### Architecture Strengths

✅ Clean separation of concerns (server/agent/UI)
✅ Real-time updates via efficient SSE protocol
✅ Atomic CSV operations with file locking
✅ Portable agent distribution (embedded Python)
✅ GitHub webhook auto-deployment

### Architecture Weaknesses

❌ CSV storage not scalable beyond small deployments
❌ No API authentication layer
❌ Client-side session management
❌ Monolithic Flask application
❌ No message queue for agent communication

---

## Technology Stack

### Backend (Server)

| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.11+ | Runtime |
| Flask | Latest | Web framework |
| Gunicorn | Latest | WSGI server |
| Gevent | Latest | Async I/O |
| PyYAML | Latest | Configuration |
| Watchdog | Latest | File monitoring |

### Frontend

| Technology | Purpose |
|------------|---------|
| HTML5/CSS3 | Structure & styling |
| Vanilla JS (ES6+) | Logic |
| Server-Sent Events | Real-time sync |
| Google Fonts | Typography |

### Agent (Windows)

| Technology | Version | Purpose |
|------------|---------|---------|
| Python Embedded | 3.11.9 | Runtime |
| PyMI | 1.0.8+ | WMI wrapper |
| psutil | 5.9.0+ | Process management |
| requests | 2.31.0+ | HTTP client |
| UsbTreeView.exe | External | USB enumeration |

### Infrastructure

| Technology | Purpose |
|------------|---------|
| Docker | Containerization |
| Docker Compose | Orchestration |
| Git Webhooks | Auto-deployment |
| HMAC-SHA256 | Webhook security |

---

## Security Assessment

### 🔴 CRITICAL Vulnerabilities

#### 1. Plaintext Password Storage
```
Location: DATA/users.csv
Impact: Complete account compromise if database accessed
Current: Passwords stored as plaintext in CSV
```
**Recommendation:** Implement bcrypt/argon2 password hashing

#### 2. No API Authentication
```
Location: /update-dashboard endpoint
Impact: Any source can inject data for any organization
Current: No token, API key, or signature verification
```
**Recommendation:**
- Add API key/token for agent authentication
- Bind agent to ORG_ID at build time
- Verify signature on all agent requests

#### 3. Insecure Session Management
```
Location: auth.js (sessionStorage)
Impact: Credential exposure, no server-side session invalidation
Current: User object with password stored in browser sessionStorage
```
**Recommendation:**
- Use HTTP-only secure cookies
- Implement server-side sessions
- Never include password in client-side storage

### ⚠️ HIGH Severity Issues

#### 4. No Rate Limiting
- Login endpoint vulnerable to brute-force
- `/api/check` enables username enumeration
- Registration can be automated

#### 5. Unverified Third-Party Binary
```
Binary: UsbTreeView.exe
Source: uwe-sieber.de
Issue: Downloaded without SHA256 verification
```

#### 6. Weak Password Policy
```
Current: Minimum 3 characters
Required: 8+ chars, mixed case, numbers, symbols
```

#### 7. Exposed Webhook Secret
```
Location: .env and .env_EXAMPLE in repository
Secret: Wj3Kp9Lm2Xv8Qr5Tn1Yc6Bh4Gf7Ds0Za
Impact: Webhook can be forged by attackers
```

#### 8. No Input Validation
- `/update-dashboard` accepts unvalidated CSV
- No field format checking
- Potential CSV injection vulnerability

### ⚠️ MEDIUM Severity Issues

#### 9. HTTPS Not Enforced
- HTTP fallback exists in agent
- Mixed content warnings possible

#### 10. No Audit Logging
- No record of login attempts
- No tracking of configuration changes
- No agent activity logs

#### 11. Docker Socket Exposure
- Container has access to Docker socket
- Enables container escape scenarios

#### 12. SSE Stream Filtering
- Only filtered by ORG_ID parameter
- No session verification for SSE endpoint

---

## Code Quality Analysis

### Metrics

| Metric | Value |
|--------|-------|
| Total Python Lines (Agent) | ~1,517 |
| Total Python Lines (Server) | ~538 |
| Frontend Files | 7 |
| Configuration Files | 3 |
| Code Comments | Extensive (RU/EN) |

### Strengths

✅ **Modular Design** - Each agent script has single responsibility
✅ **Error Handling** - Try/except blocks with logging
✅ **Code Comments** - Extensive documentation in code
✅ **Lock Mechanisms** - File locking prevents race conditions
✅ **Fallback Logic** - Multiple methods for hardware ID retrieval

### Areas for Improvement

❌ **No Type Hints** - Python code lacks type annotations
❌ **No Unit Tests** - No test files present
❌ **Hardcoded Values** - Some URLs/paths hardcoded in code
❌ **Mixed Languages** - Comments in both Russian and English

### File Complexity

| File | Complexity | Notes |
|------|------------|-------|
| `AA_waiting_for_csv.py` | High | 538 lines, multiple responsibilities |
| `CC_convert_report_to_csv.py` | Medium | Complex regex parsing |
| `AA_installer.py` | Medium | System integration complexity |
| `build_zip.py` | Medium | Multiple external downloads |

---

## Database Schema

### Users Database (`DATA/users.csv`)

| Field | Type | Constraints |
|-------|------|-------------|
| ORG_ID | String | Unique, `ORG_` + UUID[:8] |
| ORG_NAME | String | Unique, min 2 chars |
| USER_ID | String | Unique, `USER_` + UUID[:8] |
| USER_NAME | String | Unique per org, min 2 chars |
| USER_MAIL | String | Unique, valid email format |
| USER_PASSWORD | String | **PLAINTEXT** (CRITICAL ISSUE) |

### Port Inventory (`DATA/system_database.csv`)

| Field | Type | Description |
|-------|------|-------------|
| ORG_ID | String | Organization identifier |
| PC_ID | String | Machine identifier (SHA256[:8]) |
| PORT_ID | String | Port hash (MD5[:8]) |
| PORT_MAP | String | USB chain (e.g., "1-1-1") |
| PORT_STATUS | Enum | "Free" or "Secured" |
| PORT_NAME | String | Device name or "Empty USB Port" |

---

## API Documentation

### Authentication

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/login` | POST | User authentication |
| `/api/register` | POST | New user registration |
| `/api/check` | POST | Field uniqueness validation |

### Data

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/update-dashboard` | POST | Agent data submission |
| `/sse` | GET | Real-time event stream |
| `/api/build-zip` | POST | Generate agent package |

### Static

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | SPA entry point |
| `/static/*` | GET | CSS, JS assets |
| `/webhook/github` | POST | Auto-deploy trigger |

### API Security Status

| Endpoint | Auth Required | Rate Limited | Input Validated |
|----------|---------------|--------------|-----------------|
| `/api/login` | No | ❌ No | ⚠️ Partial |
| `/api/register` | No | ❌ No | ⚠️ Partial |
| `/update-dashboard` | ❌ No | ❌ No | ❌ No |
| `/sse` | ❌ No | No | ⚠️ Partial |
| `/api/build-zip` | Session | Yes (lock) | ✅ Yes |

---

## Dependency Analysis

### Server Dependencies (`requirements.txt`)

| Package | Purpose | Known Issues |
|---------|---------|--------------|
| flask | Web framework | None |
| requests | HTTP client | None |
| pyyaml | Config parsing | None |
| watchdog | File monitoring | None |
| gunicorn | WSGI server | None |
| gevent | Async I/O | None |

### Agent Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| PyMI | 1.0.8+ | WMI access |
| psutil | 5.9.0+ | Process management |
| requests | 2.31.0+ | HTTP client |

### Third-Party Binaries

| Binary | Source | Verification |
|--------|--------|--------------|
| UsbTreeView.exe | uwe-sieber.de | ❌ No SHA256 check |
| Python 3.11.9 | python.org | ❌ No verification |

---

## Performance Considerations

### Current Limitations

1. **Single Worker** - Gunicorn runs with 1 worker
2. **CSV File Locks** - Global lock on writes creates bottleneck
3. **No Caching** - All data read from CSV on every request
4. **SSE Queues** - Memory-based, lost on restart

### Scalability Assessment

| Users | PCs | Status |
|-------|-----|--------|
| 1-10 | 1-50 | ✅ Functional |
| 10-50 | 50-500 | ⚠️ Performance degradation |
| 50+ | 500+ | 🔴 Not recommended |

### Recommendations for Scale

1. Migrate to PostgreSQL/SQLite database
2. Implement Redis for SSE queues
3. Add read replicas for dashboard queries
4. Consider message queue (RabbitMQ) for agent data

---

## Recommendations

### Priority 1: Critical Security Fixes

- [ ] **Implement password hashing** (bcrypt/argon2)
- [ ] **Add API authentication** for agents (API keys/tokens)
- [ ] **Fix session management** (server-side sessions, HTTP-only cookies)
- [ ] **Rotate webhook secret** and remove from repository

### Priority 2: High Security Improvements

- [ ] **Add rate limiting** on auth endpoints
- [ ] **Verify third-party binaries** with SHA256 checksums
- [ ] **Enforce strong passwords** (8+ chars, complexity rules)
- [ ] **Validate all input** on `/update-dashboard`
- [ ] **Enforce HTTPS only** in production

### Priority 3: Architecture Improvements

- [ ] Migrate from CSV to proper database (PostgreSQL/SQLite)
- [ ] Add server-side session management
- [ ] Implement audit logging
- [ ] Add health check endpoints
- [ ] Create API documentation (OpenAPI/Swagger)

### Priority 4: Code Quality

- [ ] Add type hints to Python code
- [ ] Create unit test suite
- [ ] Standardize code comments (single language)
- [ ] Extract configuration to environment variables
- [ ] Add error monitoring (Sentry)

### Priority 5: Documentation

- [ ] Technical architecture document
- [ ] API documentation
- [ ] Deployment guide
- [ ] Agent installation guide
- [ ] Security hardening guide

---

## Conclusion

Security Layer is a well-architected proof-of-concept with clean code structure and modular design. However, **critical security vulnerabilities must be addressed before production deployment**, particularly:

1. Password storage (plaintext → hashed)
2. API authentication (none → token-based)
3. Session management (client-side → server-side)

The CSV-based storage is adequate for small deployments but will require database migration for scale. The agent design is solid but needs binary verification and secure configuration handling.

**Overall Assessment:** Ready for internal testing; **NOT ready for production** until critical security issues are resolved.

---

*Generated: January 2026*
*Auditor: Claude Code*
