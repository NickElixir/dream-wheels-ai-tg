# Dream Wheels AI Architecture v1.2

> Converted from `/Users/nikolai/Downloads/dream_wheels_ai_architecture_v1.2.docx` for GitHub reference.

**DREAM WHEELS AI**

AI Wheel Fitment Visualizer

Technical Architecture & Development Plan

*For Technical Review by Development Team*

Version 1.1 \| March 2026 \| Confidential

# **1. Product Overview**

## **1.1 Problem Statement**

Buyers of aftermarket wheels cannot accurately visualize how a specific wheel model will look on their vehicle before purchasing. Existing solutions suffer from:

- Catalog photos that do not represent the wheel on the buyer's specific car model and color

- 3D configurators limited to a fixed set of vehicle models, often appearing unrealistic

- High return rates due to incorrect wheel selection, costly for both merchants and buyers

## **1.2 Solution**

Dream Wheels AI is a web application that automatically generates a photorealistic composite image showing the user's own car with selected wheels applied. The system accepts two inputs:

- A photo of the user's car (user-uploaded)

- A product photo of the wheel from the catalog

The AI pipeline performs:

- Wheel detection and segmentation on the car photo

- Perspective correction and 3D alignment of the replacement wheel

- Lighting, shadow, and reflection matching for photorealism

- Realistic depth and offset rendering

## **1.3 Target Audience**

| **Segment** | **User Type** | **Primary Value** |
|----|----|----|
| B2C | Auto enthusiasts, pre-purchase buyers | Confidence, visual wow-effect |
| B2B — Shops | Wheel retailers, e-commerce sites | Higher conversion, fewer returns |
| B2B — Services | Tuning studios, detailing centers | Upsell tool, differentiation |

## **1.4 Product Formats**

- Web SaaS application (primary)

- REST API for third-party integration

- White-label embeddable widget for retail websites

- Mobile-responsive web version (phase 2)

- Telegram-bot web-app

# **2. System Architecture**

## **2.1 High-Level Architecture**

The system is structured into four logical layers communicating via REST and async job queues:

| **LAYER 1 — FRONTEND (Streamlit)**                        |
|-----------------------------------------------------------|
| Streamlit web app served via Python                       |
| User uploads car photo + selects wheel from catalog       |
| Displays progress, renders output image, allows download  |
| Communicates with Backend API via HTTP (requests / httpx) |

| **LAYER 2 — BACKEND API (FastAPI)**                             |
|-----------------------------------------------------------------|
| RESTful API layer handling all business logic                   |
| Manages job queue, user sessions, rate limiting, authentication |
| Coordinates between Streamlit frontend and AI pipeline          |
| Stores job state and results in Redis and PostgresSQL database  |

| **LAYER 3 — AI PIPELINE (VLM API)**                          |
|--------------------------------------------------------------|
| Async worker pool consuming jobs from Redis queue            |
| Stage 1: Wheel compositing via Reve v1.1                     |
| Stage 2 (optional): Wheel compositing via Gemini 3 Pro Image |

| **LAYER 4 — STORAGE & INFRASTRUCTURE**                       |
|--------------------------------------------------------------|
| Object storage: uploaded images, output images (S3 / GCS)    |
| Database: PostgreSQL — users, jobs, catalog, billing         |
| Cache & Queue: Redis — job queue, session state, rate limits |
| CDN: output image delivery to end users                      |

## **2.2 Request Lifecycle**

| **Step** | **Component** | **Action** |
|----|----|----|
| 1 | Streamlit UI | Users upload car and wheel images. UI validates file size and type. |
| 2 | Streamlit -\> FastAPI | POST /jobs with multipart form data (car image, wheel_id) |
| 3 | FastAPI | Validates inputs, stores images to S3, creates job in PostgreSQL, pushes job_id to Redis queue |
| 4 | FastAPI -\> Streamlit | Returns {job_id, status: queued} immediately (non-blocking) |
| 5 | Streamlit UI | Polls GET /jobs/{job_id} every 2-3 seconds, shows progress bar |
| 6 | AI Worker | Picks up job from Redis queue, runs all pipeline stages, stores output image to S3 |
| 7 | AI Worker -\> DB | Updates job status to 'completed', stores output_image_url |
| 8 | Streamlit UI | Receives 'completed' status, fetches and renders output image, offers download |

# 3. AI Pipeline — Detailed Design

## 3.1 Pipeline Stages

Each job passes through three sequential stages in the MVP pipeline. Failures at any stage update job status to ‘failed’ with a diagnostic error code returned to the API.

### Stage 1 — Wheel Detection & Segmentation

Input: raw car photo. Output: binary mask(s) of wheel regions with bounding boxes.

- Primary option: Meta SAM 2 (Segment Anything Model) via local inference or hosted API for zero-shot wheel segmentation

- Alternative: fine-tuned YOLO v11 segmentation model on car wheel dataset for faster, more reliable results in production

- Output: up to 4 wheel masks with bounding boxes and confidence scores per mask

- Filter: select only clearly visible, front-facing wheels (confidence threshold \> 0.75)

- Edge case handling: if no wheel detected, return error code WHEEL_NOT_FOUND with user-facing guidance and example of a valid photo

### 🚧 Post-MVP Research: Perspective & Geometry Estimation (Deferred)

*This stage is intentionally excluded from the MVP pipeline. During MVP and demo, geometric alignment is delegated entirely to the generative model (Stage 2 below). This is an identified area for post-MVP research and quality improvement.*

**Planned post-MVP approach — Iterative generation with quality evaluation:**

- Generate first output using the base prompt (Stage 2 compositing)

- Run a lightweight vision evaluation: check ellipse alignment, angle consistency, and edge artifact score against the original wheel mask

- If score is below threshold: enrich the prompt with specific geometric corrections (e.g. “wheel tilt at 14°, ellipse ratio 0.31, front-left perspective”) and re-generate — up to 3 iterations maximum

- Advanced option (Phase 3+): replace prompt-based correction with OpenCV fitEllipse + homography pre-transform as a geometric anchor fed to the model as reference image conditioning, optionally augmented with MiDaS or Apple DepthPro for monocular depth on difficult angles

### Stage 2 — AI Image Compositing

This is the core generative step. Two model candidates have been pre-evaluated:

|  | **Gemini 3 Pro (Imagen edit)** | **Reve v1.1** |
|----|----|----|
| Approach | Inpainting via masked region with text + image prompt | Image-to-image with reference image conditioning |
| Strength | Strong instruction following, realistic lighting preservation | High photorealism, fine texture and material detail |
| Weakness | May alter car body pixels outside mask boundary | Less precise geometric control over wheel placement |
| API cost | Per-request: token + image pricing (GCP) | Per-generation pricing (API) |
| Recommended use | Primary pipeline — best overall quality and controllability | A/B test alternative or premium quality tier |

Compositing prompt strategy (Gemini inpainting):

| **Inpainting Prompt Template** |
|----|
| Replace the wheel in the masked region with the provided wheel product image. |
| Preserve exact perspective, lighting direction, shadow cast on ground, |
| and ambient reflections visible in the original scene. |
| Match the metallic or matte finish of the replacement wheel to ambient light. |
| Do not alter the tire sidewall, brake caliper, or car body outside the mask. |
| Output: photorealistic, high resolution, no artifacts, no blurring at edges. |

### Stage 3 — Post-Processing

Input: composited image from Stage 2. Output: final delivery-quality image.

- Shadow blending: Gaussian blur at mask boundary (OpenCV) to eliminate hard compositing edges

- Color grading: histogram matching between original car region and composited wheel region

- Sharpness: unsharp mask applied to wheel region only, preserving car body softness

- Output formats: JPEG 90% quality for web delivery; PNG lossless for premium download

- Watermarking: subtle logo overlay for free tier; disabled for B2B API and paid tiers

# **4. Backend API — Detailed Design**

## **4.1 Technology Stack**

| **Component** | **Technology & Rationale** |
|----|----|
| API Framework | FastAPI (Python) — async, auto OpenAPI docs, Pydantic validation, high performance |
| Job Queue | Celery + Redis — reliable async task execution, retry logic, ETA scheduling, monitoring via Flower |
| Database | PostgreSQL — users, jobs, wheel catalog, billing records; strong ACID guarantees |
| ORM | SQLAlchemy 2.0 with Alembic for schema migrations |
| Object Storage | AWS S3 or Google Cloud Storage — pre-signed URLs for secure direct upload and download |
| Authentication | JWT (RS256, access + refresh) for B2C; hashed scoped API Keys for B2B clients |
| Rate Limiting | Redis-backed sliding window counter per user / per API key |
| Containerization | Docker + Docker Compose for local dev; Kubernetes or Cloud Run for production |
| Monitoring | Prometheus + Grafana for metrics; Sentry for error tracking and alerting |
| API Docs | Auto-generated OpenAPI / Swagger UI via FastAPI at /docs |

## **4.2 Core API Endpoints**

| **Method + Path** | **Auth** | **Description** |
|----|----|----|
| POST /auth/register | None | Create B2C account (email + password) |
| POST /auth/login | None | Return JWT access + refresh tokens |
| POST /auth/refresh | Refresh token | Rotate and issue new access token |
| GET /catalog/wheels | Optional | List wheels with filters: brand, size, finish, bolt pattern |
| GET /catalog/wheels/{id} | Optional | Wheel detail with all product images |
| POST /jobs | JWT / API key | Submit new visualizer job (car image upload + wheel_id) |
| GET /jobs/{job_id} | JWT / API key | Poll job status; returns result URL when completed |
| GET /jobs/{job_id}/result | JWT / API key | Download output image via redirect to pre-signed S3 URL |
| GET /jobs/{job_id}/stream | JWT / API key | Production SSE endpoint: streams real-time job progress events (text/event-stream). Events: progress_update, status_update, completion. Replaces polling in production tier. |
| GET /jobs | JWT | List authenticated user's job history with pagination |
| POST /api/v1/visualize | API key | B2B endpoint: submit job, returns job_id for polling |
| GET /health | None | Service health check for load balancer and uptime monitoring |

## **4.3 Job State Machine**

| **Job Status Transitions** |
|----|
| queued -\> processing -\> completed |
| \| |
| failed (error_code + user-facing message) |
|  |
| All states: queued \| processing \| completed \| failed \| expired |
|  |
| Retry policy: up to 2 automatic retries on transient errors (HTTP 429, 503) |
| Backoff: exponential, starting at 5 seconds |
| Expiry: output images deleted after 24h (free tier) / 30 days (paid / B2B) |
| MVP (Short Polling): client discovers state changes via GET /jobs/{id} every 1-5s (adaptive). Simple, no special infrastructure. |
| Production (SSE): server pushes state changes via GET /jobs/{id}/stream. Latency \<200ms per state change. Migration trigger: \>500 DAU or user complaints about update lag. |

## **4.4 Database Schema (Core Tables)**

users — id, email, password_hash, tier (free/pro/b2b), created_at, stripe_customer_id, quota_used

api_keys — id, user_id, key_hash, name, scopes\[\], last_used_at, revoked_at

jobs — id, user_id, status, car_image_url, wheel_image_url, output_image_url, pipeline_version, error_code, created_at, completed_at, processing_ms, model_used

wheels — id, brand, model, finish, image_url\[\], catalog_ref, active, created_at

usage_events — id, user_id, job_id, event_type, metadata_json, timestamp (for billing + analytics)

## **4.5 Real-time Communication Strategy**

| **MVP Approach: HTTP Short Polling** |
|----|
| Technology: standard HTTP GET requests (no special infrastructure) |
| Latency: 1-5 seconds \| Scalability: up to ~500 concurrent users |
| Pros: simple, works everywhere, no special infrastructure \| Cons: higher server load, delayed updates |
| **Production Upgrade: Server-Sent Events (SSE)** |
| Technology: HTTP streaming (text/event-stream) via FastAPI StreamingResponse |
| Latency: \<200ms \| Scalability: 5,000+ concurrent users (with proper load balancing) |
| Pros: real-time, lower server load, better UX \| Cons: requires sticky sessions, complex error handling |
| **Migration Trigger** |
| Migrate when: \>500 daily active users OR user complaints about update lag |
| Backend changes: add /stream endpoints (non-breaking, backward-compatible) \| Frontend: replace polling loop with EventSource API |
| Timeline: 1-2 week sprint, recommended after Next.js migration |

# **5. Streamlit Frontend — Integration Points**

## **5.1 Architecture Note**

Streamlit is selected for rapid MVP development. It runs as a Python process and communicates with the FastAPI backend via httpx (async) or requests (sync). All UI state is managed via st.session_state. Authentication tokens are stored in session state, not in browser storage.

## **5.2 Key Screens & Logic**

| **Screen** | **Key Streamlit Components & Logic** |
|----|----|
| Landing / Upload | st.file_uploader for car and wheel photos; Submit button triggers POST /jobs |
| Processing View | st.progress + st.spinner; polling loop with time.sleep(2) + st.rerun(); estimated time display from job metadata |
| Result View | st.image for output render; st.download_button for JPEG/PNG; share link; 'Try another wheel' resets session state |
| Account / Usage | Job history via st.dataframe; API key management panel for B2B tier; usage meter with quota remaining |
| B2B Widget Demo | Embed code snippet display with st.code; live preview iframe; API key copy button with st.clipboard |

## **5.3 Non-Blocking Polling Pattern**

| **Recommended Implementation** |
|----|
| 1\. On submit: call POST /jobs -\> store job_id in st.session_state\['job_id'\] |
| 2\. Set st.session_state\['view'\] = 'processing', call st.rerun() |
| 3\. In processing view: call GET /jobs/{job_id}, check status |
| 4\. If still processing: time.sleep(2), st.rerun() to refresh |
| 5\. If completed: store result_url, set view = 'result', st.rerun() |
| 6\. If failed: display error_code with user-friendly message + Retry button |
|  |
| Warning: avoid blocking sleep() \> 3s — it locks the Streamlit thread |
| Warning: store JWT in st.session_state only, never in st.secrets |

## **5.4 Scalability Ceiling & Migration Path**

Streamlit is single-threaded per user session. For production scale beyond approximately 50 concurrent users, the recommended migration path is:

- Phase 1 MVP: Streamlit on Cloud Run, auto-scale instances, suitable for validation

- Phase 2 scale: Migrate to React / Next.js frontend calling the same FastAPI backend — no backend changes required

- The FastAPI backend is designed to be frontend-agnostic from day one

**Communication Pattern Evolution:**

Phase 1 (MVP — 0–500 users): Streamlit frontend, short polling with adaptive 1–5s intervals. Sufficient for validation and early adopters. Low infrastructure complexity.

Phase 2 (Scale — 500–5,000 users): Migrate to Next.js frontend. Implement SSE for real-time updates. FastAPI backend unchanged — add /stream endpoints only. Load balancer with sticky sessions required.

Phase 3 (Enterprise — 5,000+ users): Consider WebSocket for bidirectional features. Redis pub/sub for multi-instance SSE coordination. Separate WebSocket service if bidirectional communication needed.

# **6. Security & Data Handling**

| **Concern** | **Design Decision** |
|----|----|
| Image upload validation | Check MIME type + magic bytes server-side; max 10MB per image; strip EXIF metadata before S3 storage |
| Storage access control | All S3/GCS buckets are private; access only via pre-signed URLs (TTL: 1h uploads, 24h outputs) |
| API key storage | Keys stored as bcrypt hash in database; plaintext shown to user exactly once at creation |
| JWT security | RS256 signing; access token TTL 15 minutes; refresh token TTL 30 days with rotation on use |
| User image privacy | Car photos never used for model training without explicit opt-in; stated clearly in ToS |
| GDPR compliance | EU-region deployment option; right-to-deletion endpoint; data retention policy enforced via expiry jobs |
| AI API credentials | Stored in GCP Secret Manager or AWS Secrets Manager; injected via environment at runtime; never in code or DB |
| Application security | Rate limiting per IP + per user; input sanitization; SQL injection prevention via ORM; CORS origin whitelist |
| Secrets rotation | API keys and model credentials rotatable without downtime via versioned secrets |
| **SSE security** | JWT passed as query param (SSE cannot set custom headers in browser): GET /jobs/{id}/stream?token={jwt}. Max 3 concurrent SSE connections per user. Connection auto-timeout at 5 minutes; heartbeat every 30s. Graceful degradation to polling if SSE unavailable. |

# **7. Development Phases & Milestones**

## **Phase 0 — Proof of Concept (2 weeks)**

Goal: validate that AI compositing produces acceptable quality before investing in full infrastructure.

1.  Set up minimal chats with Gemini 3 Pro and Reve v1.1 models using LLMArena.

2.  Prepare 10 manually curated car + wheel image pairs as a test set.

3.  Run compositing tests, compare Gemini vs. Reve v1.1 output quality side-by-side

4.  Define and score acceptance criteria: realism, edge blending, processing time, cost per image

5.  Decision gate: proceed with chosen primary model, or pivot approach before any backend work begins

## Phase 1 — MVP Backend + Pipeline (4-6 weeks)

6.  FastAPI project scaffold with Docker Compose: PostgreSQL, Redis, Celery worker

7.  Image upload endpoint + S3/GCS integration with pre-signed URLs

8.  AI pipeline worker: Stage 1 (wheel detection) + Stage 3 (compositing) — minimum viable pipeline

9.  Job queue and status polling endpoints

10. Basic JWT authentication (register, login, refresh)

11. Streamlit UI: upload -\> processing -\> result flow

12. Deploy to staging environment (Cloud Run or equivalent)

## **Phase 1 — MVP Backend + Pipeline (4-6 weeks)**

13. FastAPI project scaffold with Docker Compose: PostgreSQL, Redis, Celery worker

14. Image upload endpoint + S3/GCS integration with pre-signed URLs

15. AI pipeline worker: Stage 1 (wheel detection) + Stage 3 (compositing) — minimum viable pipeline

16. Job queue and status polling endpoints

17. Basic JWT authentication (register, login, refresh)

18. Streamlit UI: upload -\> processing -\> result flow

19. Deploy to staging environment (Cloud Run or equivalent)

## **Phase 2 — Quality & Robustness (3-4 weeks)**

20. Stage 2 perspective/geometry estimation research and integration

21. Stage 4 post-processing pipeline (shadow blending, color grading)

22. Full error handling, retry logic, and graceful failure messages for all failure modes

23. Wheel catalog management

24. Quality benchmarking on 200-image test set; iterate on prompt and pipeline

## **Phase 2.5 — Real-time Updates (Post-500 Users)**

**Trigger:** User metrics show \>500 DAU or feedback requests faster real-time updates.

**Backend tasks:** Add GET /jobs/{id}/stream SSE endpoint (FastAPI StreamingResponse). Add Redis pub/sub for job status broadcasting across instances. Load-test with 1,000+ concurrent SSE connections.

**Frontend tasks:** Replace adaptive_poll_job() with EventSource connection. Implement reconnection logic on drop. Add connection status indicator. Graceful fallback to polling if SSE unavailable.

**Infrastructure:** Sticky sessions on load balancer. Increase worker instance limits. Monitor SSE connection count and latency metrics.

**Timeline:** 1–2 week sprint, coordinated with Next.js frontend migration.

## **Phase 3 — B2B API & Monetization (3-4 weeks)**

25. API key management: creation, scoping, revocation, usage tracking

26. Rate limiting and usage metering per API key

27. B2B REST API endpoints with full OpenAPI documentation

28. White-label widget (embeddable iframe + JS postMessage API for result callbacks)

29. Stripe billing integration: per-image credits or monthly subscription tiers

30. Admin dashboard: job monitoring, user management, revenue metrics

## **Phase 4 — Scale & Product Maturity (ongoing)**

- Performance: async pipeline optimization, evaluate GPU self-hosting vs. API cost trade-off

- Quality: domain-specific fine-tuning on wheel/car dataset if API quality plateaus

- Mobile: responsive Streamlit or React Native wrapper for Phase 2 frontend migration

- Analytics: funnel tracking, A/B testing framework, conversion metrics per wheel and car segment

**7.1 Telegram MVP — 1-Week Sprint Plan**

This section defines the minimum viable product delivered as a Telegram bot within one week. The stack is intentionally stripped down: Reve API for image generation, Telegram Bot API for user interaction, FastAPI as the thin backend layer, Redis for the job queue and session state, and PostgreSQL for job and user persistence. No Streamlit frontend, no Celery, no SAM/YOLO wheel detection — the user provides both car and wheel images directly.

**7.1.1 Sprint Goal**

Ship a working Telegram bot that accepts a car photo and a wheel image from a user, generates a photorealistic composite via Reve v1.1, and returns the result — all within 60 seconds end-to-end. The bot identifies users by Telegram user_id (no registration required). Jobs and results are stored in PostgreSQL; Redis handles the async job queue between the bot handler and the FastAPI worker.

**7.1.2 MVP Tech Stack**

| **Component** | **Technology & Role in MVP** |
|----|----|
| **Telegram Bot API** | User-facing interface. python-telegram-bot (async). Handles /start, photo upload flow, job status polling, result delivery. User identity = Telegram user_id (no auth required). |
| **FastAPI** | Thin async backend. Two endpoints: POST /jobs (create job, push to Redis queue) and GET /jobs/{job_id} (status + result URL). No auth middleware in MVP — Telegram user_id passed as parameter. |
| **Redis** | Job queue (LIST data structure, RPUSH/BLPOP pattern). Session state cache: stores image file_ids during multi-step upload dialog (TTL 10 min). No Celery — FastAPI background worker polls queue directly. |
| **PostgreSQL** | Persistent storage: jobs table and users table (keyed by telegram_user_id). Minimal schema — no billing, no catalog, no API keys in MVP. |
| **Reve v1.1 API** | Image compositing engine. Image-to-image conditioning: car photo + wheel reference image → composite. No SAM/YOLO in MVP — wheel region is described via prompt only. |

**7.1.3 Bot User Flow**

| 1\. User sends /start → Bot replies with welcome + instructions |
|----|
| 2\. User sends photo of their car → Bot saves Telegram file_id to Redis session (TTL 10 min) |
| 3\. User sends wheel product photo → Bot saves file_id to Redis session |
| 4\. Bot calls POST /jobs → FastAPI creates job in PostgreSQL, pushes job_id to Redis queue |
| 5\. FastAPI worker picks up job → downloads images from Telegram, calls Reve v1.1 API |
| 6\. Reve v1.1 returns composite image → worker updates job status = completed in PostgreSQL |
| 7\. Bot polls GET /jobs/{job_id} every 3s → sends result image back to user in Telegram |

**7.1.4 Minimal Database Schema**

Two tables only. No migrations framework in week 1 — plain SQL init script.

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<thead>
<tr>
<th><p>-- users</p>
<p>id, telegram_user_id (UNIQUE), username, created_at, job_count</p>
<p>-- jobs</p>
<p>id, user_id (FK), status, car_image_url, wheel_image_url,</p>
<p>output_image_url, error_message, created_at, completed_at</p>
<p>-- job.status: queued | processing | completed | failed</p></th>
</tr>
</thead>
<tbody>
</tbody>
</table>

**7.1.5 FastAPI Endpoints (MVP)**

| **Method + Path** | **Auth** | **Description** |
|----|----|----|
| POST /jobs | None | Create job: accepts telegram_user_id, car_file_id, wheel_file_id. Downloads images from Telegram, stores to S3/GCS, pushes job_id to Redis queue. Returns {job_id, status: queued}. |
| GET /jobs/{job_id} | None | Poll job status. Returns {status, output_image_url} when completed. Bot uses this for result delivery. |
| GET /health | None | Uptime check for deployment health monitoring. |

**7.1.6 1-Week Development Timeline**

| **Day** | **Tasks** | **End-of-Day Deliverable** |
|----|----|----|
| **Day 1** | Repo setup (FastAPI + Docker Compose with PostgreSQL + Redis). DB init script. Reve v1.1 API credentials + first manual test call. Confirm image-to-image endpoint works with a real car + wheel photo pair. | **Reve API ✓ confirmed** |
| **Day 2** | FastAPI: POST /jobs + GET /jobs/{job_id}. Background worker (asyncio task) polling Redis queue, calling Reve API, updating PostgreSQL. GET /health endpoint. | **Backend pipeline ✓ end-to-end via curl** |
| **Day 3** | Telegram bot: /start handler, multi-step photo upload dialog (car → wheel), Redis session state. Bot registers user by telegram_user_id in PostgreSQL on first interaction. | **Bot accepts photos ✓** |
| **Day 4** | Connect bot to backend: POST /jobs call, polling loop, send result image back to user. Add “processing…” typing indicator while job runs. Error handling: failed job → user-friendly message + /retry. | **Full flow ✓ end-to-end in Telegram** |
| **Day 5** | Deploy to Cloud Run (bot + FastAPI as one service or two). Telegram webhook setup. Smoke test with real photos. Prompt tuning for Reve v1.1 based on first results. | **Deployed ✓ live on Cloud Run** |
| **Day 6–7** | Buffer: fix bugs from Day 5 smoke test. Prompt iteration on 10 real image pairs. Add /history command (last 5 results from PostgreSQL). Prepare demo script and test set for stakeholder review. | **MVP Demo-ready ✓** |

**7.1.7 Explicitly Out of Scope for Week 1**

- SAM 2 / YOLO wheel detection — user uploads both images manually; no auto-masking

- Celery — replaced by asyncio background task inside FastAPI process

- JWT authentication — identity via telegram_user_id only

- Wheel catalog — no catalog UI; user brings their own wheel photo

- Streamlit UI — all interaction via Telegram bot only

- Post-processing (Stage 3) — raw Reve v1.1 output delivered directly; shadow blending and color grading deferred to Phase 2

- Billing, rate limiting, B2B API — out of scope for demo sprint

# **8. Infrastructure & Deployment**

## **8.1 Recommended Stack**

| **Service** | **Recommended Option & Notes** |
|----|----|
| Cloud provider | GCP preferred (natural fit with Gemini API, unified billing) or AWS |
| API hosting | Cloud Run (serverless, auto-scale to zero) for MVP; GKE for high-scale production |
| Streamlit hosting | Cloud Run or App Engine; Streamlit Community Cloud acceptable for very early MVP |
| AI workers | Cloud Run Jobs or GKE node pool; add GPU node pool if self-hosting SAM or depth models |
| Database | Cloud SQL PostgreSQL managed instance (automatic backups, failover) |
| Cache / Queue | Cloud Memorystore for Redis (managed, no ops overhead) |
| Object storage | Google Cloud Storage (or AWS S3); enable lifecycle policies for auto-expiry |
| CDN | Cloudflare or GCP Cloud CDN for output image delivery to end users |
| CI/CD | GitHub Actions: lint -\> test -\> Docker build -\> push to Artifact Registry -\> deploy to Cloud Run |
| Secrets | GCP Secret Manager; inject into Cloud Run at deploy time via --set-secrets flag |
| Monitoring | GCP Cloud Monitoring + Sentry; Flower for Celery worker visibility; Uptime Checks for /health |

## **8.2 Estimated Monthly Costs (MVP — ~1,000 jobs/month)**

| **Line Item** | **Estimated Cost / Month** |
|----|----|
| Gemini 2.5 Pro API (1,000 compositing calls) | ~\$50-150 (varies by image token count) |
| Cloud Run — FastAPI + Streamlit | ~\$20-50 (scale to zero when idle) |
| Cloud SQL PostgreSQL (db-f1-micro) | ~\$25-40 |
| Cloud Memorystore Redis (basic 1GB) | ~\$30 |
| GCS storage (images, 30-day retention) | ~\$10-20 |
| Total MVP estimate | ~\$135-290 / month |

## **8.3 Open Questions for Dev Team Review**

| **Items Requiring Team Decision Before Phase 1** |
|----|
| 1\. GPU vs. API-only for Stage 1 (wheel detection): |
| Running SAM 2 locally requires a GPU worker node. API-only avoids infrastructure |
| complexity but adds latency and cost. Recommend profiling both in Phase 0. |
|  |
| 2\. Primary AI model — Gemini 3 Pro Image vs. Reve v1.1: |
| Define quantitative quality acceptance criteria in Phase 0 before committing. |
|  |
| 3\. Streamlit concurrency ceiling: |
| At what concurrent session count should we migrate to React frontend? |
| Recommend defining this threshold (suggested: \>50 concurrent sessions) before Phase 3. |
|  |
| 4\. Wheel catalog source: |
| Manual admin upload vs. automated supplier data feed (API or CSV import)? |
| Affects catalog schema design and Phase 1 scope significantly. |
|  |
| 5\. Perspective estimation approach: |
| Pure OpenCV (faster, simpler) vs. ML depth estimation (MiDaS / DepthPro)? |
| ML approach improves realism on difficult angles but adds pipeline complexity. |

# **9. Key Risks & Mitigations**

| **Risk** | **Likelihood** | **Mitigation Strategy** |
|----|----|----|
| AI output quality below user expectation on complex photos | High | Phase 0 PoC with strict quality gate; fallback manual mask adjustment UI |
| Gemini / Reve API pricing increases significantly | Medium | Design pipeline with model-agnostic adapter pattern; maintain swap-ready interface |
| Processing time exceeds 60 seconds per job | Medium | Optimize pipeline; offer async email notification; show live stage-by-stage progress |
| Streamlit hits concurrency limits under load | Medium | Plan and document React migration path from Phase 1; keep FastAPI backend frontend-agnostic |
| Users upload low-quality or unsuitable car photos | High | Add photo quality scoring before queue; guide users with examples; clear rejection messages |
| Wheel mask detection fails on complex or dark backgrounds | Medium | Fallback to manual mask drawing tool in Streamlit UI; collect failures for model improvement |
| Competitor launches equivalent product | Low-Med | Focus on B2B white-label and catalog integration as primary differentiation |

# **10. Recommended Next Steps**

The following actions are recommended to validate the most critical unknowns before committing to full development:

31. Start Phase 0 this week. Set up Gemini 2.5 Pro API credentials and run manual compositing tests on 20 image pairs. This single step validates the entire product premise.

32. Run model comparison. Test Gemini 2.5 Pro vs. Reve v1.1 on the same 20-image test set. Define a scoring rubric (realism, edge quality, geometry accuracy, processing time) before development begins.

33. Resolve the five open questions in Section 8.3. These decisions affect architecture, cost, and timeline significantly. Aim to resolve all before Phase 1 kickoff.

34. Assemble minimum viable team. This architecture requires three roles: (1) Backend/API developer (FastAPI, PostgreSQL, Redis/Celery), (2) ML/CV engineer (pipeline stages 1-4, model integration), (3) DevOps/Infrastructure (Docker, GCP, CI/CD).

35. Define SLA targets upfront. Recommended targets: processing time \< 30s at P90, output resolution \>= 1920px on long edge, quality acceptance rate \>= 85% on a diverse test set.

| **Document Status & Review Notes** |
|----|
| This document is a technical foundation intended for review and challenge by the dev team. |
| All architectural decisions should be treated as proposals, not mandates. |
| Sections most likely to require revision: Section 3 (AI pipeline stages), |
| Section 5 (Streamlit scalability), and Section 8 (infrastructure cost estimates). |
|  |
| Please annotate disagreements, alternative approaches, and missing considerations. |
| Version 1.0 \| February 2026 \| Confidential |
