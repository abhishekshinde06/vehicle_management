# Vehicle Fuel & Mileage Tracking — Frontend

Responsive web application for the Vehicle Fuel & Mileage Tracking System, built for **tablet operators** (live GPS geofence verification, live camera photo capture, and fuel entry logging) and **mobile/desktop fleet owners** (entry inspection with OpenStreetMap visualization, approval/rejection workflow, and fleet management).

---

## Technology Stack & Purpose

- **React 18** (`react`, `react-dom`): Component-based SPA UI.
- **Vite 6** (`vite`, `@vitejs/plugin-react`): Fast development server and production bundler.
- **JavaScript (ES Modules)**: Simple, maintainable MVP codebase.
- **Tailwind CSS v4** (`tailwindcss`, `@tailwindcss/vite`): Responsive utility-first styling across mobile, tablet, and desktop.
- **Axios** (`axios`): Centralized HTTP client with JWT request headers and 401 session-expiry handling.
- **React Router v6** (`react-router-dom`): Role-based routing and protected route guards.
- **React Context API**: Centralized authentication and session state (`AuthContext`).
- **Browser Geolocation API** (`navigator.geolocation.getCurrentPosition`): High-accuracy live GPS capture with `maximumAge: 0`.
- **Browser MediaDevices API** (`navigator.mediaDevices.getUserMedia`): Live camera capture without gallery upload fallback.
- **Leaflet + OpenStreetMap** (`leaflet`): Free interactive map visualization with OpenStreetMap attribution.

---

## Folder Structure

```text
frontend/
├── index.html
├── package.json
├── vite.config.js
├── .env.example
├── README.md
└── src/
    ├── api/
    │   ├── auth.js            # OAuth2 login, /me, operator provisioning & listing
    │   ├── client.js          # Centralized Axios instance, JWT & 401 interceptors
    │   ├── fuelEntries.js     # Verify location, create, list, detail, approve/reject
    │   ├── petrolPumps.js     # List and register authorized petrol pumps
    │   ├── photoUpload.js     # Modular photo upload & retrieval adapter
    │   └── vehicles.js        # List and register fleet vehicles
    ├── components/
    │   ├── AlertBanner.jsx
    │   ├── CameraCaptureCard.jsx
    │   ├── EntryLocationMap.jsx
    │   ├── ProtectedRoute.jsx
    │   ├── PumpCoordinatePickerMap.jsx
    │   └── StatusBadge.jsx
    ├── context/
    │   └── AuthContext.jsx
    ├── hooks/
    │   └── useGeolocation.js
    ├── layouts/
    │   ├── OperatorLayout.jsx
    │   └── OwnerLayout.jsx
    ├── pages/
    │   ├── LoginPage.jsx
    │   ├── operator/
    │   │   ├── OperatorDashboardPage.jsx
    │   │   └── OperatorHistoryPage.jsx
    │   └── owner/
    │       ├── OwnerFuelEntriesPage.jsx
    │       ├── OwnerFuelEntryDetailPage.jsx
    │       ├── OwnerOperatorsPage.jsx
    │       ├── OwnerPetrolPumpsPage.jsx
    │       └── OwnerVehiclesPage.jsx
    ├── utils/
    │   ├── formatters.js
    │   ├── leafletSetup.js
    │   └── storage.js
    ├── App.jsx
    ├── index.css
    └── main.jsx
```

---

## Installation

Prerequisites:
- Node.js `v22.x` (tested with `v22.23.5`) and npm `10.x`
- Running FastAPI backend server

```bash
cd frontend
npm install
```

---

## Environment Configuration

Create `frontend/.env` from `.env.example`:

```bash
cp .env.example .env
```

Available variables:

- `VITE_API_BASE_URL` (default: `http://localhost:8000/api`)
  Base URL of the FastAPI backend API including the `/api` prefix.
- `VITE_ENABLE_DEV_PHOTO_UPLOAD` (default: `false`)
  Keep `false` while the production secure photo upload module is under development (disables final fuel entry submission with a clear dependency notice). Set to `true` only if you want local development testing against the existing `POST /api/fuel-entries/upload-photo` endpoint.

---

## Running Commands

### Run the Backend Server

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Run the Frontend Development Server

```bash
cd frontend
npm run dev
```

### Build & Preview Production Bundle

```bash
cd frontend
npm run build
npm run preview
```

---

## API Integration Details

| Feature | Method & Endpoint | Notes |
| :--- | :--- | :--- |
| Login | `POST /api/auth/login` | Sends OAuth2 form data (`application/x-www-form-urlencoded`) |
| Current User | `GET /api/auth/me` | Validates stored JWT on app startup |
| List Operators | `GET /api/auth/operators` | Owner only |
| Create Operator | `POST /api/auth/create-operator` | Owner only (`password` min 8 chars) |
| List Vehicles | `GET /api/vehicles/` | Authenticated (returns `latest_odometer`) |
| Add Vehicle | `POST /api/vehicles/` | Owner only |
| List Petrol Pumps | `GET /api/petrol-pumps/` | Authenticated |
| Register Petrol Pump | `POST /api/petrol-pumps/` | Owner only (`latitude`, `longitude`, `radius_meters`) |
| Verify GPS Location | `POST /api/fuel-entries/verify-location` | Operator/Owner (`petrol_pump_id`, `latitude`, `longitude`, `accuracy_m`) |
| Submit Fuel Entry | `POST /api/fuel-entries/` | Requires fresh GPS + 3 unique photo URLs (`PLATE`, `ODOMETER`, `RECEIPT`) |
| List Fuel Entries | `GET /api/fuel-entries/` | Supports `vehicle_id`, `petrol_pump_id`, `status`, `start_date`, `end_date` |
| Fuel Entry Details | `GET /api/fuel-entries/{id}` | Operator restricted to own entries |
| Approve / Reject | `PATCH /api/fuel-entries/{id}/verify` | Owner only; `rejection_reason` required for `REJECTED`; `409` if already reviewed |

All authenticated requests automatically attach `Authorization: Bearer <token>`. HTTP `401` responses (outside login) clear the stored session and prompt re-authentication.

---

## Mobile & Tablet Testing Instructions (HTTPS Requirement)

Browser security rules require a **secure context** (`https://` or `http://localhost`) for both:
- `navigator.geolocation.getCurrentPosition()`
- `navigator.mediaDevices.getUserMedia()`

When testing from a physical **tablet or mobile phone** over your local Wi-Fi network (`http://<LAN-IP>:5173`), browsers will **block camera and GPS access** over plain HTTP.

Recommended ways to test on mobile/tablet:
1. **HTTPS Tunnel (recommended for quick testing):** Expose your local Vite frontend and FastAPI backend over HTTPS using a local TLS reverse proxy (such as Caddy or mkcert) or a trusted tunnel.
2. **Android USB Debugging + Port Forwarding:** Connect the tablet via USB with Chrome DevTools port forwarding (`chrome://inspect`) so the tablet accesses `http://localhost:5173` and `http://localhost:8000` (which browsers treat as a secure context).

---

## Pending Backend Dependencies

1. **Secure Photo Upload & Retrieval Module (`src/api/photoUpload.js`)**
   - Production authenticated upload (e.g., S3 presigned URLs) and secure photo retrieval are still under development.
   - Until enabled, live camera capture, preview, and retake work locally in memory, and final submission is disabled with a clear dependency banner rather than generating fake photo URLs.
2. **Automated OCR Reading Verification**
   - Backend OCR integration for odometer and pump receipt verification is pending; no simulated or fake OCR results are displayed in the UI.
