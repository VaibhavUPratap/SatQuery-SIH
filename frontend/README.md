# TerraPulse AI Dashboard

## Run the current GitHub version

From a fresh clone, use the `main` branch and start both services from the
repository root:

```bash
git clone https://github.com/VaibhavUPratap/SatQuery-SIH.git
cd SatQuery-SIH
git checkout main
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 -m uvicorn backend.api.main:app --reload --host 127.0.0.1 --port 8000
```

In a second terminal:

```bash
cd SatQuery-SIH/frontend
npm install
npm run dev
```

Open the Vite URL shown in the terminal, authenticate with the
environment-configured prototype credentials, and choose **Open Bengaluru
NISAR case study**. The upgraded page is the **Temporal backscatter
workspace**.

The frontend alone is not sufficient: the case-study catalog, candidate
GeoJSON, processed previews, job status, trace, and PDF result are served by
FastAPI. If the API uses another host or port, set
`VITE_API_URL=http://<host>:<port>/api/v1` before starting Vite. When a friend
is using a different computer, `127.0.0.1` refers to their computer, not the
developer's computer; both services must run on their machine or the API must
be deployed and configured with `VITE_API_URL`.

For an existing checkout, refresh the exact pushed release with:

```bash
git fetch origin
git checkout main
git pull --ff-only origin main
```
