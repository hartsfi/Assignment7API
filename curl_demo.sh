#!/usr/bin/env bash
# ================================================================
#  curl_demo.sh  –  Exercise all 10 Plant Nursery API endpoints
#  Usage: ./curl_demo.sh   (server must be running on :8000)
# ================================================================

BASE="http://127.0.0.1:8000"
GRN='\033[0;32m'; CYN='\033[0;36m'; NC='\033[0m'

hr()    { echo -e "\n${CYN}──────────────────────────────────────────────${NC}"; }
title() { echo -e "\n${GRN}▶ $1${NC}"; }
pp()    { python3 -m json.tool; }

# ── 1. GET /plants ──────────────────────────────────────────────
hr; title "1. GET /plants?category=tropical  (filter by category)"
curl -s "$BASE/plants?category=tropical" | pp

# ── 2. GET /plants/{id} ─────────────────────────────────────────
hr; title "2. GET /plants/p1  (single plant with embedded schedule)"
curl -s "$BASE/plants/p1" | pp

# ── 3. POST /plants ─────────────────────────────────────────────
hr; title "3. POST /plants  (add a Pothos to inventory)"
NEW_PLANT=$(curl -s -X POST "$BASE/plants" \
  -H "Content-Type: application/json" \
  -d '{
    "common_name": "Golden Pothos",
    "scientific_name": "Epipremnum aureum",
    "category": "tropical",
    "location": "Shelf D",
    "pot_size_cm": 18,
    "sunlight": "indirect",
    "stock": 15,
    "price_usd": 11.99,
    "notes": "Fast grower, great for beginners."
  }')
echo $NEW_PLANT | pp
PLANT_ID=$(echo $NEW_PLANT | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "  → New plant ID: $PLANT_ID"

# ── 4. POST /plants/{id}/water ──────────────────────────────────
hr; title "4. POST /plants/p3/water  (log a watering event)"
curl -s -X POST "$BASE/plants/p3/water" \
  -H "Content-Type: application/json" \
  -d '{"watered_by": "Jamie", "watered_at": "2026-03-15", "notes": "Soil was very dry"}' | pp

# ── 5. PUT /plants/{id} ─────────────────────────────────────────
hr; title "5. PUT /plants/p2  (full replace snake plant record)"
curl -s -X PUT "$BASE/plants/p2" \
  -H "Content-Type: application/json" \
  -d '{
    "common_name": "Snake Plant (Laurentii)",
    "scientific_name": "Sansevieria trifasciata laurentii",
    "category": "succulent",
    "location": "Display Window",
    "pot_size_cm": 20,
    "sunlight": "indirect",
    "stock": 18,
    "price_usd": 24.99
  }' | pp

# ── 6. PUT /care-schedules/{id} ─────────────────────────────────
hr; title "6. PUT /care-schedules/cs2  (full replace succulent schedule)"
curl -s -X PUT "$BASE/care-schedules/cs2" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Desert Succulent Pro",
    "watering_interval_days": 28,
    "fertilize_interval_days": 90,
    "misting": false,
    "repot_interval_months": 36,
    "preferred_temp_min_c": 10,
    "preferred_temp_max_c": 38,
    "notes": "Never let sit in standing water."
  }' | pp

# ── 7. PATCH /plants/{id} ───────────────────────────────────────
hr; title "7. PATCH /plants/p3  (mark bird of paradise as critical + attach schedule)"
curl -s -X PATCH "$BASE/plants/p3" \
  -H "Content-Type: application/json" \
  -d '{"health_status": "critical", "care_schedule_id": "cs1"}' | pp

# ── 8. PATCH /care-schedules/{id} ───────────────────────────────
hr; title "8. PATCH /care-schedules/cs1  (shorten watering interval for summer)"
curl -s -X PATCH "$BASE/care-schedules/cs1" \
  -H "Content-Type: application/json" \
  -d '{"watering_interval_days": 5, "notes": "Summer: water more frequently."}' | pp

# ── 9. DELETE /plants/{id} ──────────────────────────────────────
hr; title "9. DELETE /plants/$PLANT_ID  (remove the pothos we just added)"
curl -s -X DELETE "$BASE/plants/$PLANT_ID" | pp

# ── 10. DELETE /care-schedules/{id} ─────────────────────────────
hr; title "10. DELETE /care-schedules/cs1  (blocked — plants still assigned)"
curl -s -X DELETE "$BASE/care-schedules/cs1" | pp
echo ""
echo "  ↳ Expected 409: Monstera + Bird of Paradise are still using cs1"

hr; echo -e "\n${GRN}All 10 endpoints exercised. 🪴${NC}\n"
