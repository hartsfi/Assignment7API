# test_api.py
# -----------
# Tests for the Plant Nursery & Care Tracker API.
# Uses only Python's built-in unittest and urllib — no installs needed.
#
# Run with: python3 test_api.py

import unittest
import json
import threading
import urllib.request
import urllib.error
import sys
import os

# Import our app so the tests can share the same in-memory database
sys.path.insert(0, os.path.dirname(__file__))
import main
from main import RequestHandler, plants_db, schedules_db, watering_log

BASE_URL = "http://127.0.0.1:18766"


# ---------------------------------------------------------------------------
# Helper functions used across all tests
# ---------------------------------------------------------------------------

def make_request(method, path, body=None):
    """Send an HTTP request and return (status_code, response_data)."""
    url = BASE_URL + path
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def reset_database():
    """Restore all data to the original seeded state before each test."""
    plants_db.clear()
    plants_db.update({
        "p1": {"id":"p1","common_name":"Monstera","scientific_name":"Monstera deliciosa","category":"tropical","location":"Greenhouse A","pot_size_cm":30,"health_status":"healthy","sunlight":"indirect","stock":12,"price_usd":34.99,"last_watered":"2026-03-13","care_schedule_id":"cs1","added_date":"2025-11-01","notes":"Popular seller."},
        "p2": {"id":"p2","common_name":"Snake Plant","scientific_name":"Sansevieria trifasciata","category":"succulent","location":"Shelf B","pot_size_cm":15,"health_status":"healthy","sunlight":"indirect","stock":25,"price_usd":18.50,"last_watered":"2026-03-10","care_schedule_id":"cs2","added_date":"2025-09-15","notes":"Low maintenance."},
        "p3": {"id":"p3","common_name":"Bird of Paradise","scientific_name":"Strelitzia reginae","category":"tropical","location":"Greenhouse A","pot_size_cm":40,"health_status":"needs_attention","sunlight":"direct","stock":4,"price_usd":89.00,"last_watered":"2026-03-08","care_schedule_id":None,"added_date":"2026-01-20","notes":"Check drainage."},
    })
    schedules_db.clear()
    schedules_db.update({
        "cs1": {"id":"cs1","name":"Tropical Standard","watering_interval_days":7,"fertilize_interval_days":30,"misting":True,"repot_interval_months":12,"preferred_temp_min_c":18,"preferred_temp_max_c":27,"notes":"Wipe leaves monthly.","created_at":"2025-11-01T00:00:00Z"},
        "cs2": {"id":"cs2","name":"Succulent Care","watering_interval_days":21,"fertilize_interval_days":60,"misting":False,"repot_interval_months":24,"preferred_temp_min_c":15,"preferred_temp_max_c":32,"notes":"Allow soil to dry.","created_at":"2025-09-01T00:00:00Z"},
    })
    watering_log.clear()


# A valid plant payload we can reuse across tests
VALID_PLANT = {
    "common_name": "Golden Pothos",
    "scientific_name": "Epipremnum aureum",
    "category": "tropical",
    "location": "Shelf C",
    "pot_size_cm": 18,
    "sunlight": "indirect",
    "stock": 10,
    "price_usd": 12.99,
}

# A valid schedule payload we can reuse across tests
VALID_SCHEDULE = {
    "name": "General Tropical",
    "watering_interval_days": 7,
    "fertilize_interval_days": 30,
    "misting": True,
    "repot_interval_months": 12,
    "preferred_temp_min_c": 18,
    "preferred_temp_max_c": 28,
}


# ---------------------------------------------------------------------------
# 1. GET /plants
# ---------------------------------------------------------------------------

class Test01_ListPlants(unittest.TestCase):

    def setUp(self):
        reset_database()

    def test_returns_all_plants(self):
        status, data = make_request("GET", "/plants")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(data["total"], 3)

    def test_filter_by_category(self):
        status, data = make_request("GET", "/plants?category=tropical")
        self.assertEqual(status, 200)
        for plant in data["plants"]:
            self.assertEqual(plant["category"], "tropical")

    def test_filter_by_health(self):
        status, data = make_request("GET", "/plants?health=needs_attention")
        self.assertEqual(status, 200)
        for plant in data["plants"]:
            self.assertEqual(plant["health_status"], "needs_attention")

    def test_filter_by_sunlight(self):
        status, data = make_request("GET", "/plants?sunlight=indirect")
        self.assertEqual(status, 200)
        for plant in data["plants"]:
            self.assertEqual(plant["sunlight"], "indirect")

    def test_filter_available_only(self):
        plants_db["p3"]["stock"] = 0
        status, data = make_request("GET", "/plants?available=true")
        self.assertEqual(status, 200)
        for plant in data["plants"]:
            self.assertGreater(plant["stock"], 0)

    def test_filter_by_location(self):
        status, data = make_request("GET", "/plants?location=greenhouse")
        self.assertEqual(status, 200)
        for plant in data["plants"]:
            self.assertIn("greenhouse", plant["location"].lower())


# ---------------------------------------------------------------------------
# 2. GET /plants/{id}
# ---------------------------------------------------------------------------

class Test02_GetSinglePlant(unittest.TestCase):

    def setUp(self):
        reset_database()

    def test_returns_correct_plant(self):
        status, data = make_request("GET", "/plants/p1")
        self.assertEqual(status, 200)
        self.assertEqual(data["common_name"], "Monstera")

    def test_includes_care_schedule_when_linked(self):
        status, data = make_request("GET", "/plants/p1")
        self.assertEqual(status, 200)
        self.assertIn("care_schedule", data)
        self.assertEqual(data["care_schedule"]["name"], "Tropical Standard")

    def test_no_schedule_when_none_linked(self):
        status, data = make_request("GET", "/plants/p3")
        self.assertEqual(status, 200)
        self.assertNotIn("care_schedule", data)

    def test_returns_404_for_unknown_id(self):
        status, data = make_request("GET", "/plants/does-not-exist")
        self.assertEqual(status, 404)


# ---------------------------------------------------------------------------
# 3. POST /plants
# ---------------------------------------------------------------------------

class Test03_CreatePlant(unittest.TestCase):

    def setUp(self):
        reset_database()

    def test_creates_plant_successfully(self):
        status, data = make_request("POST", "/plants", VALID_PLANT)
        self.assertEqual(status, 201)
        self.assertEqual(data["common_name"], "Golden Pothos")
        self.assertTrue(data["id"].startswith("plt-"))

    def test_health_defaults_to_healthy(self):
        status, data = make_request("POST", "/plants", VALID_PLANT)
        self.assertEqual(status, 201)
        self.assertEqual(data["health_status"], "healthy")

    def test_can_set_health_on_create(self):
        payload = dict(VALID_PLANT)
        payload["health_status"] = "dormant"
        status, data = make_request("POST", "/plants", payload)
        self.assertEqual(status, 201)
        self.assertEqual(data["health_status"], "dormant")

    def test_missing_required_field_returns_422(self):
        status, data = make_request("POST", "/plants", {"common_name": "Lonely Plant"})
        self.assertEqual(status, 422)

    def test_invalid_category_returns_422(self):
        payload = dict(VALID_PLANT)
        payload["category"] = "moonplant"
        status, data = make_request("POST", "/plants", payload)
        self.assertEqual(status, 422)

    def test_negative_price_returns_422(self):
        payload = dict(VALID_PLANT)
        payload["price_usd"] = -10
        status, data = make_request("POST", "/plants", payload)
        self.assertEqual(status, 422)

    def test_invalid_sunlight_returns_422(self):
        payload = dict(VALID_PLANT)
        payload["sunlight"] = "moonlight"
        status, data = make_request("POST", "/plants", payload)
        self.assertEqual(status, 422)


# ---------------------------------------------------------------------------
# 4. POST /plants/{id}/water
# ---------------------------------------------------------------------------

class Test04_WaterPlant(unittest.TestCase):

    def setUp(self):
        reset_database()

    def test_logs_watering_event(self):
        status, data = make_request("POST", "/plants/p1/water", {"watered_at": "2026-03-15"})
        self.assertEqual(status, 200)
        self.assertIn("Watering logged", data["message"])

    def test_updates_last_watered_on_plant(self):
        make_request("POST", "/plants/p1/water", {"watered_at": "2026-03-15"})
        status, plant = make_request("GET", "/plants/p1")
        self.assertEqual(plant["last_watered"], "2026-03-15")

    def test_critical_plant_improves_to_needs_attention(self):
        plants_db["p3"]["health_status"] = "critical"
        make_request("POST", "/plants/p3/water", {"watered_at": "2026-03-15"})
        status, plant = make_request("GET", "/plants/p3")
        self.assertEqual(plant["health_status"], "needs_attention")

    def test_watered_by_defaults_to_staff(self):
        status, data = make_request("POST", "/plants/p1/water", {"watered_at": "2026-03-15"})
        self.assertEqual(data["log_entry"]["watered_by"], "staff")

    def test_returns_404_for_unknown_plant(self):
        status, data = make_request("POST", "/plants/ghost/water", {"watered_at": "2026-03-15"})
        self.assertEqual(status, 404)

    def test_bad_date_format_returns_422(self):
        status, data = make_request("POST", "/plants/p1/water", {"watered_at": "March 15"})
        self.assertEqual(status, 422)


# ---------------------------------------------------------------------------
# 5. PUT /plants/{id}
# ---------------------------------------------------------------------------

class Test05_ReplacePlant(unittest.TestCase):

    def setUp(self):
        reset_database()

    def test_replaces_all_fields(self):
        status, data = make_request("PUT", "/plants/p1", VALID_PLANT)
        self.assertEqual(status, 200)
        self.assertEqual(data["common_name"], "Golden Pothos")
        self.assertEqual(data["location"], "Shelf C")

    def test_preserves_id_and_added_date(self):
        status, data = make_request("PUT", "/plants/p1", VALID_PLANT)
        self.assertEqual(data["id"], "p1")
        self.assertEqual(data["added_date"], "2025-11-01")

    def test_returns_404_for_unknown_plant(self):
        status, data = make_request("PUT", "/plants/ghost", VALID_PLANT)
        self.assertEqual(status, 404)

    def test_missing_field_returns_422(self):
        status, data = make_request("PUT", "/plants/p1", {"common_name": "Incomplete"})
        self.assertEqual(status, 422)


# ---------------------------------------------------------------------------
# 6. PUT /care-schedules/{id}
# ---------------------------------------------------------------------------

class Test06_ReplaceSchedule(unittest.TestCase):

    def setUp(self):
        reset_database()

    def test_replaces_all_fields(self):
        status, data = make_request("PUT", "/care-schedules/cs1", VALID_SCHEDULE)
        self.assertEqual(status, 200)
        self.assertEqual(data["name"], "General Tropical")
        self.assertEqual(data["watering_interval_days"], 7)

    def test_preserves_id_and_created_at(self):
        status, data = make_request("PUT", "/care-schedules/cs1", VALID_SCHEDULE)
        self.assertEqual(data["id"], "cs1")
        self.assertEqual(data["created_at"], "2025-11-01T00:00:00Z")

    def test_returns_404_for_unknown_schedule(self):
        status, data = make_request("PUT", "/care-schedules/ghost", VALID_SCHEDULE)
        self.assertEqual(status, 404)

    def test_misting_must_be_boolean(self):
        payload = dict(VALID_SCHEDULE)
        payload["misting"] = "yes"
        status, data = make_request("PUT", "/care-schedules/cs1", payload)
        self.assertEqual(status, 422)


# ---------------------------------------------------------------------------
# 7. PATCH /plants/{id}
# ---------------------------------------------------------------------------

class Test07_UpdatePlant(unittest.TestCase):

    def setUp(self):
        reset_database()

    def test_updates_only_stock(self):
        status, data = make_request("PATCH", "/plants/p1", {"stock": 99})
        self.assertEqual(status, 200)
        self.assertEqual(data["stock"], 99)
        self.assertEqual(data["common_name"], "Monstera")  # unchanged

    def test_updates_multiple_fields(self):
        status, data = make_request("PATCH", "/plants/p1", {"location": "Outdoor", "stock": 5})
        self.assertEqual(status, 200)
        self.assertEqual(data["location"], "Outdoor")
        self.assertEqual(data["stock"], 5)

    def test_can_attach_a_care_schedule(self):
        status, data = make_request("PATCH", "/plants/p3", {"care_schedule_id": "cs1"})
        self.assertEqual(status, 200)
        self.assertEqual(data["care_schedule_id"], "cs1")

    def test_empty_body_returns_422(self):
        status, data = make_request("PATCH", "/plants/p1", {})
        self.assertEqual(status, 422)

    def test_invalid_health_value_returns_422(self):
        status, data = make_request("PATCH", "/plants/p1", {"health_status": "thriving"})
        self.assertEqual(status, 422)

    def test_returns_404_for_unknown_plant(self):
        status, data = make_request("PATCH", "/plants/ghost", {"stock": 1})
        self.assertEqual(status, 404)


# ---------------------------------------------------------------------------
# 8. PATCH /care-schedules/{id}
# ---------------------------------------------------------------------------

class Test08_UpdateSchedule(unittest.TestCase):

    def setUp(self):
        reset_database()

    def test_updates_watering_interval(self):
        status, data = make_request("PATCH", "/care-schedules/cs1", {"watering_interval_days": 5})
        self.assertEqual(status, 200)
        self.assertEqual(data["watering_interval_days"], 5)
        self.assertEqual(data["name"], "Tropical Standard")  # unchanged

    def test_can_toggle_misting_off(self):
        status, data = make_request("PATCH", "/care-schedules/cs1", {"misting": False})
        self.assertEqual(status, 200)
        self.assertFalse(data["misting"])

    def test_can_update_temperature_range(self):
        status, data = make_request("PATCH", "/care-schedules/cs2", {
            "preferred_temp_min_c": 10,
            "preferred_temp_max_c": 38
        })
        self.assertEqual(status, 200)
        self.assertEqual(data["preferred_temp_min_c"], 10)
        self.assertEqual(data["preferred_temp_max_c"], 38)

    def test_empty_body_returns_422(self):
        status, data = make_request("PATCH", "/care-schedules/cs1", {})
        self.assertEqual(status, 422)

    def test_returns_404_for_unknown_schedule(self):
        status, data = make_request("PATCH", "/care-schedules/ghost", {"misting": True})
        self.assertEqual(status, 404)


# ---------------------------------------------------------------------------
# 9. DELETE /plants/{id}
# ---------------------------------------------------------------------------

class Test09_DeletePlant(unittest.TestCase):

    def setUp(self):
        reset_database()

    def test_deletes_plant_with_no_watering_history(self):
        # First create a temporary plant to delete
        status, new_plant = make_request("POST", "/plants", VALID_PLANT)
        plant_id = new_plant["id"]

        # Now delete it
        status, data = make_request("DELETE", "/plants/" + plant_id)
        self.assertEqual(status, 200)
        self.assertIn("removed", data["message"].lower())

        # Confirm it's gone
        status, data = make_request("GET", "/plants/" + plant_id)
        self.assertEqual(status, 404)

    def test_blocks_deletion_when_watering_history_exists(self):
        make_request("POST", "/plants/p1/water", {"watered_at": "2026-03-15"})
        status, data = make_request("DELETE", "/plants/p1")
        self.assertEqual(status, 409)
        self.assertIn("watering_entries", data)

    def test_force_delete_works_despite_history(self):
        make_request("POST", "/plants/p2/water", {"watered_at": "2026-03-14"})
        status, data = make_request("DELETE", "/plants/p2?force=true")
        self.assertEqual(status, 200)
        self.assertEqual(data["watering_logs_orphaned"], 1)

    def test_returns_404_for_unknown_plant(self):
        status, data = make_request("DELETE", "/plants/ghost")
        self.assertEqual(status, 404)


# ---------------------------------------------------------------------------
# 10. DELETE /care-schedules/{id}
# ---------------------------------------------------------------------------

class Test10_DeleteSchedule(unittest.TestCase):

    def setUp(self):
        reset_database()

    def test_deletes_schedule_not_in_use(self):
        # Add a standalone schedule that no plant is using
        schedules_db["cs_tmp"] = {
            "id": "cs_tmp",
            "name": "Temporary Schedule",
            "watering_interval_days": 14,
            "fertilize_interval_days": 30,
            "misting": False,
            "repot_interval_months": 12,
            "preferred_temp_min_c": 15,
            "preferred_temp_max_c": 25,
            "notes": "",
            "created_at": "2026-01-01T00:00:00Z",
        }
        status, data = make_request("DELETE", "/care-schedules/cs_tmp")
        self.assertEqual(status, 200)
        self.assertIn("deleted", data["message"].lower())

    def test_blocks_deletion_when_plants_are_assigned(self):
        # cs1 is used by p1, so deleting it should be blocked
        status, data = make_request("DELETE", "/care-schedules/cs1")
        self.assertEqual(status, 409)
        self.assertIn("assigned_plants", data)
        self.assertGreater(len(data["assigned_plants"]), 0)

    def test_returns_404_for_unknown_schedule(self):
        status, data = make_request("DELETE", "/care-schedules/ghost")
        self.assertEqual(status, 404)

    def test_becomes_deletable_after_plants_reassigned(self):
        # Create an isolated schedule, assign a plant to it, then unassign
        schedules_db["cs_solo"] = {
            "id": "cs_solo", "name": "Solo", "watering_interval_days": 10,
            "fertilize_interval_days": 45, "misting": True, "repot_interval_months": 6,
            "preferred_temp_min_c": 16, "preferred_temp_max_c": 28,
            "notes": "", "created_at": "2026-01-01T00:00:00Z",
        }
        plants_db["p3"]["care_schedule_id"] = "cs_solo"

        # Unassign the plant by setting its schedule to null
        make_request("PATCH", "/plants/p3", {"care_schedule_id": None})

        # Now the schedule should be deletable
        status, data = make_request("DELETE", "/care-schedules/cs_solo")
        self.assertEqual(status, 200)


# ---------------------------------------------------------------------------
# Run all tests
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Start the server on a test port
    server = main.HTTPServer(("127.0.0.1", 18766), RequestHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    # Collect and run all test classes in order
    loader = unittest.TestLoader()
    loader.sortTestMethodsUsing = None
    suite = unittest.TestSuite()

    test_classes = [
        Test01_ListPlants,
        Test02_GetSinglePlant,
        Test03_CreatePlant,
        Test04_WaterPlant,
        Test05_ReplacePlant,
        Test06_ReplaceSchedule,
        Test07_UpdatePlant,
        Test08_UpdateSchedule,
        Test09_DeletePlant,
        Test10_DeleteSchedule,
    ]

    for test_class in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(test_class))

    result = unittest.TextTestRunner(verbosity=2).run(suite)
    server.shutdown()
    exit(0 if result.wasSuccessful() else 1)
