# Plant Nursery & Care Tracker API
# ----------------------------------
# A simple REST API built with Python's built-in http.server module.
# No third-party libraries needed — just run: python3 main.py
#
# Endpoints:
#   GET    /plants                  - list all plants (with optional filters)
#   GET    /plants/{id}             - get one plant by ID
#   POST   /plants                  - add a new plant
#   POST   /plants/{id}/water       - log that a plant was watered
#   PUT    /plants/{id}             - replace all fields on a plant
#   PUT    /care-schedules/{id}     - replace all fields on a care schedule
#   PATCH  /plants/{id}             - update only some fields on a plant
#   PATCH  /care-schedules/{id}     - update only some fields on a care schedule
#   DELETE /plants/{id}             - remove a plant
#   DELETE /care-schedules/{id}     - remove a care schedule

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime, date
import json
import uuid
import re


# ---------------------------------------------------------------------------
# Data — stored in memory (resets when the server restarts)
# ---------------------------------------------------------------------------

# Each plant is a dictionary stored under its ID key
plants_db = {
    "p1": {
        "id": "p1",
        "common_name": "Monstera",
        "scientific_name": "Monstera deliciosa",
        "category": "tropical",
        "location": "Greenhouse A",
        "pot_size_cm": 30,
        "health_status": "healthy",
        "sunlight": "indirect",
        "stock": 12,
        "price_usd": 34.99,
        "last_watered": "2026-03-13",
        "care_schedule_id": "cs1",
        "added_date": "2025-11-01",
        "notes": "Popular seller, repot annually.",
    },
    "p2": {
        "id": "p2",
        "common_name": "Snake Plant",
        "scientific_name": "Sansevieria trifasciata",
        "category": "succulent",
        "location": "Shelf B",
        "pot_size_cm": 15,
        "health_status": "healthy",
        "sunlight": "indirect",
        "stock": 25,
        "price_usd": 18.50,
        "last_watered": "2026-03-10",
        "care_schedule_id": "cs2",
        "added_date": "2025-09-15",
        "notes": "Very low maintenance.",
    },
    "p3": {
        "id": "p3",
        "common_name": "Bird of Paradise",
        "scientific_name": "Strelitzia reginae",
        "category": "tropical",
        "location": "Greenhouse A",
        "pot_size_cm": 40,
        "health_status": "needs_attention",
        "sunlight": "direct",
        "stock": 4,
        "price_usd": 89.00,
        "last_watered": "2026-03-08",
        "care_schedule_id": None,
        "added_date": "2026-01-20",
        "notes": "Yellowing on lower leaves — check drainage.",
    },
}

# Care schedules define how often to water, feed, and repot a plant type
schedules_db = {
    "cs1": {
        "id": "cs1",
        "name": "Tropical Standard",
        "watering_interval_days": 7,
        "fertilize_interval_days": 30,
        "misting": True,
        "repot_interval_months": 12,
        "preferred_temp_min_c": 18,
        "preferred_temp_max_c": 27,
        "notes": "Wipe leaves monthly to remove dust.",
        "created_at": "2025-11-01T00:00:00Z",
    },
    "cs2": {
        "id": "cs2",
        "name": "Succulent Care",
        "watering_interval_days": 21,
        "fertilize_interval_days": 60,
        "misting": False,
        "repot_interval_months": 24,
        "preferred_temp_min_c": 15,
        "preferred_temp_max_c": 32,
        "notes": "Allow soil to fully dry between waterings.",
        "created_at": "2025-09-01T00:00:00Z",
    },
}

# Every time a plant is watered, a record gets added here
watering_log = []

# Allowed values for certain fields
VALID_HEALTH_VALUES   = ["healthy", "needs_attention", "critical", "dormant"]
VALID_SUNLIGHT_VALUES = ["direct", "indirect", "shade"]
VALID_CATEGORY_VALUES = ["tropical", "succulent", "herb", "fern", "cactus", "flowering", "tree", "other"]


# ---------------------------------------------------------------------------
# Small utility functions
# ---------------------------------------------------------------------------

def make_id(prefix):
    # Creates a unique ID like "plt-a3f9c12b"
    return prefix + "-" + uuid.uuid4().hex[:8]

def current_timestamp():
    # Returns the current UTC time as a string
    return datetime.utcnow().isoformat() + "Z"

def current_date():
    # Returns today's date as a string like "2026-03-15"
    return date.today().isoformat()

def send_response(handler, status_code, data):
    # Converts data to JSON and sends it back to the client
    body = json.dumps(data, indent=2).encode()
    handler.send_response(status_code)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)

def read_request_body(handler):
    # Reads and parses the JSON body sent with a POST/PUT/PATCH request
    content_length = int(handler.headers.get("Content-Length", 0))
    if content_length == 0:
        return {}
    raw = handler.rfile.read(content_length)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None  # signals bad JSON


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def validate_plant_fields(data, require_all_fields):
    # Checks that plant data is valid before saving it.
    # Returns (clean_data, error_message) — error is None if everything is fine.
    errors = []
    clean = {}

    # --- Required fields (always checked on POST/PUT; optional on PATCH) ---

    if require_all_fields or "common_name" in data:
        value = data.get("common_name", "")
        if isinstance(value, str) and value.strip():
            clean["common_name"] = value.strip()
        else:
            errors.append("'common_name' must be a non-empty string")

    if require_all_fields or "scientific_name" in data:
        value = data.get("scientific_name", "")
        if isinstance(value, str) and value.strip():
            clean["scientific_name"] = value.strip()
        else:
            errors.append("'scientific_name' must be a non-empty string")

    if require_all_fields or "category" in data:
        value = data.get("category", "")
        if value in VALID_CATEGORY_VALUES:
            clean["category"] = value
        else:
            errors.append("'category' must be one of: " + ", ".join(VALID_CATEGORY_VALUES))

    if require_all_fields or "location" in data:
        value = data.get("location", "")
        if isinstance(value, str) and value.strip():
            clean["location"] = value.strip()
        else:
            errors.append("'location' must be a non-empty string")

    if require_all_fields or "pot_size_cm" in data:
        value = data.get("pot_size_cm")
        if isinstance(value, (int, float)) and value > 0:
            clean["pot_size_cm"] = value
        else:
            errors.append("'pot_size_cm' must be a positive number")

    if require_all_fields or "sunlight" in data:
        value = data.get("sunlight", "")
        if value in VALID_SUNLIGHT_VALUES:
            clean["sunlight"] = value
        else:
            errors.append("'sunlight' must be one of: " + ", ".join(VALID_SUNLIGHT_VALUES))

    if require_all_fields or "stock" in data:
        value = data.get("stock", 0)
        if isinstance(value, int) and value >= 0:
            clean["stock"] = value
        else:
            errors.append("'stock' must be a whole number, 0 or more")

    if require_all_fields or "price_usd" in data:
        value = data.get("price_usd")
        if isinstance(value, (int, float)) and value >= 0:
            clean["price_usd"] = round(float(value), 2)
        else:
            errors.append("'price_usd' must be a positive number")

    # --- Optional fields (validated only if they were actually sent) ---

    if "health_status" in data:
        value = data.get("health_status")
        if value in VALID_HEALTH_VALUES:
            clean["health_status"] = value
        else:
            errors.append("'health_status' must be one of: " + ", ".join(VALID_HEALTH_VALUES))

    if "notes" in data:
        clean["notes"] = str(data["notes"])

    if "care_schedule_id" in data:
        value = data.get("care_schedule_id")
        if value is None or isinstance(value, str):
            clean["care_schedule_id"] = value
        else:
            errors.append("'care_schedule_id' must be a string ID or null")

    if errors:
        return None, "; ".join(errors)
    return clean, None


def validate_schedule_fields(data, require_all_fields):
    # Same idea as validate_plant_fields, but for care schedules.
    errors = []
    clean = {}

    if require_all_fields or "name" in data:
        value = data.get("name", "")
        if isinstance(value, str) and value.strip():
            clean["name"] = value.strip()
        else:
            errors.append("'name' must be a non-empty string")

    if require_all_fields or "watering_interval_days" in data:
        value = data.get("watering_interval_days")
        if isinstance(value, int) and value > 0:
            clean["watering_interval_days"] = value
        else:
            errors.append("'watering_interval_days' must be a positive whole number")

    if require_all_fields or "fertilize_interval_days" in data:
        value = data.get("fertilize_interval_days")
        if isinstance(value, int) and value > 0:
            clean["fertilize_interval_days"] = value
        else:
            errors.append("'fertilize_interval_days' must be a positive whole number")

    if require_all_fields or "misting" in data:
        value = data.get("misting")
        if isinstance(value, bool):
            clean["misting"] = value
        else:
            errors.append("'misting' must be true or false")

    if require_all_fields or "repot_interval_months" in data:
        value = data.get("repot_interval_months")
        if isinstance(value, int) and value > 0:
            clean["repot_interval_months"] = value
        else:
            errors.append("'repot_interval_months' must be a positive whole number")

    if require_all_fields or "preferred_temp_min_c" in data:
        value = data.get("preferred_temp_min_c")
        if isinstance(value, (int, float)):
            clean["preferred_temp_min_c"] = value
        else:
            errors.append("'preferred_temp_min_c' must be a number")

    if require_all_fields or "preferred_temp_max_c" in data:
        value = data.get("preferred_temp_max_c")
        if isinstance(value, (int, float)):
            clean["preferred_temp_max_c"] = value
        else:
            errors.append("'preferred_temp_max_c' must be a number")

    if "notes" in data:
        clean["notes"] = str(data["notes"])

    if errors:
        return None, "; ".join(errors)
    return clean, None


# ---------------------------------------------------------------------------
# Route registry — maps (method, URL pattern) to a handler function
# ---------------------------------------------------------------------------

# ROUTES holds tuples of (HTTP method, compiled URL regex, handler function)
ROUTES = []

def route(method, url_pattern):
    # This is a decorator. It registers a function as the handler for a route.
    # Example: @route("GET", r"/plants") means "call this function for GET /plants"
    def decorator(fn):
        compiled_pattern = re.compile("^" + url_pattern + "$")
        ROUTES.append((method, compiled_pattern, fn))
        return fn
    return decorator


# ---------------------------------------------------------------------------
# Route handlers — one function per endpoint
# ---------------------------------------------------------------------------

@route("GET", r"/plants")
def list_plants(handler, match, query_params, body):
    # Returns all plants, with optional query string filters.
    # Example: GET /plants?category=tropical&available=true
    results = []
    for plant in plants_db.values():
        results.append(plant)

    # Apply filters if they were passed in the URL
    category_filter  = query_params.get("category",  [None])[0]
    location_filter  = query_params.get("location",  [None])[0]
    health_filter    = query_params.get("health",    [None])[0]
    sunlight_filter  = query_params.get("sunlight",  [None])[0]
    available_filter = query_params.get("available", [None])[0]

    if category_filter:
        filtered = []
        for plant in results:
            if plant["category"].lower() == category_filter.lower():
                filtered.append(plant)
        results = filtered

    if location_filter:
        filtered = []
        for plant in results:
            if location_filter.lower() in plant["location"].lower():
                filtered.append(plant)
        results = filtered

    if health_filter:
        filtered = []
        for plant in results:
            if plant["health_status"].lower() == health_filter.lower():
                filtered.append(plant)
        results = filtered

    if sunlight_filter:
        filtered = []
        for plant in results:
            if plant["sunlight"].lower() == sunlight_filter.lower():
                filtered.append(plant)
        results = filtered

    if available_filter == "true":
        filtered = []
        for plant in results:
            if plant["stock"] > 0:
                filtered.append(plant)
        results = filtered
    elif available_filter == "false":
        filtered = []
        for plant in results:
            if plant["stock"] == 0:
                filtered.append(plant)
        results = filtered

    send_response(handler, 200, {"total": len(results), "plants": results})


@route("GET", r"/plants/(?P<id>[^/]+)")
def get_plant(handler, match, query_params, body):
    # Returns a single plant by ID.
    # If the plant has a care schedule attached, it's included in the response.
    plant_id = match.group("id")
    plant = plants_db.get(plant_id)

    if not plant:
        send_response(handler, 404, {"error": "Plant '" + plant_id + "' not found."})
        return

    # Build the response — start with a copy of the plant data
    response = {}
    for key in plant:
        response[key] = plant[key]

    # Attach the care schedule if one is linked
    if plant.get("care_schedule_id"):
        schedule = schedules_db.get(plant["care_schedule_id"])
        if schedule:
            response["care_schedule"] = schedule

    send_response(handler, 200, response)


@route("POST", r"/plants")
def create_plant(handler, match, query_params, body):
    # Adds a new plant to the database.
    if body is None:
        send_response(handler, 400, {"error": "Could not read request body. Is it valid JSON?"})
        return

    clean_data, error = validate_plant_fields(body, require_all_fields=True)
    if error:
        send_response(handler, 422, {"error": error})
        return

    plant_id = make_id("plt")
    new_plant = {
        "id": plant_id,
        "common_name": clean_data["common_name"],
        "scientific_name": clean_data["scientific_name"],
        "category": clean_data["category"],
        "location": clean_data["location"],
        "pot_size_cm": clean_data["pot_size_cm"],
        "sunlight": clean_data["sunlight"],
        "stock": clean_data["stock"],
        "price_usd": clean_data["price_usd"],
        "health_status": clean_data.get("health_status", "healthy"),
        "care_schedule_id": clean_data.get("care_schedule_id"),
        "notes": clean_data.get("notes", ""),
        "last_watered": None,
        "added_date": current_date(),
    }

    plants_db[plant_id] = new_plant
    send_response(handler, 201, new_plant)


@route("POST", r"/plants/(?P<id>[^/]+)/water")
def water_plant(handler, match, query_params, body):
    # Logs a watering event for a plant.
    # Optionally accepts: watered_by, watered_at, notes
    plant_id = match.group("id")
    plant = plants_db.get(plant_id)

    if not plant:
        send_response(handler, 404, {"error": "Plant '" + plant_id + "' not found."})
        return

    if body is None:
        send_response(handler, 400, {"error": "Could not read request body."})
        return

    # Read optional fields from the request, using sensible defaults
    watered_by   = str(body.get("watered_by", "staff")).strip() or "staff"
    watered_at   = body.get("watered_at", current_date())
    entry_notes  = str(body.get("notes", "")).strip()

    # Make sure the date is in YYYY-MM-DD format
    try:
        datetime.strptime(watered_at, "%Y-%m-%d")
    except ValueError:
        send_response(handler, 422, {"error": "'watered_at' must be in YYYY-MM-DD format, e.g. 2026-03-15"})
        return

    # Build the log entry and save it
    log_entry = {
        "id": make_id("wl"),
        "plant_id": plant_id,
        "watered_at": watered_at,
        "watered_by": watered_by,
        "notes": entry_notes,
        "logged_at": current_timestamp(),
    }
    watering_log.append(log_entry)

    # Update the plant's last_watered field
    plant["last_watered"] = watered_at

    # If the plant was in critical condition, watering bumps it up to needs_attention
    if plant["health_status"] == "critical":
        plant["health_status"] = "needs_attention"

    send_response(handler, 200, {
        "message": "Watering logged for '" + plant["common_name"] + "'.",
        "log_entry": log_entry,
        "plant_last_watered": plant["last_watered"],
    })


@route("PUT", r"/plants/(?P<id>[^/]+)")
def replace_plant(handler, match, query_params, body):
    # Fully replaces a plant record. All required fields must be included.
    # Good for when you want to update many fields at once.
    plant_id = match.group("id")
    existing = plants_db.get(plant_id)

    if not existing:
        send_response(handler, 404, {"error": "Plant '" + plant_id + "' not found."})
        return

    if body is None:
        send_response(handler, 400, {"error": "Could not read request body."})
        return

    clean_data, error = validate_plant_fields(body, require_all_fields=True)
    if error:
        send_response(handler, 422, {"error": error})
        return

    # Build the updated record, keeping a few fields from the original
    updated_plant = {
        "id": plant_id,
        "common_name": clean_data["common_name"],
        "scientific_name": clean_data["scientific_name"],
        "category": clean_data["category"],
        "location": clean_data["location"],
        "pot_size_cm": clean_data["pot_size_cm"],
        "sunlight": clean_data["sunlight"],
        "stock": clean_data["stock"],
        "price_usd": clean_data["price_usd"],
        "health_status": clean_data.get("health_status", existing["health_status"]),
        "care_schedule_id": clean_data.get("care_schedule_id", existing.get("care_schedule_id")),
        "notes": clean_data.get("notes", ""),
        "last_watered": existing["last_watered"],  # preserve watering history
        "added_date": existing["added_date"],       # preserve original add date
        "updated_at": current_timestamp(),
    }

    plants_db[plant_id] = updated_plant
    send_response(handler, 200, updated_plant)


@route("PUT", r"/care-schedules/(?P<id>[^/]+)")
def replace_schedule(handler, match, query_params, body):
    # Fully replaces a care schedule. All fields required.
    schedule_id = match.group("id")
    existing = schedules_db.get(schedule_id)

    if not existing:
        send_response(handler, 404, {"error": "Care schedule '" + schedule_id + "' not found."})
        return

    if body is None:
        send_response(handler, 400, {"error": "Could not read request body."})
        return

    clean_data, error = validate_schedule_fields(body, require_all_fields=True)
    if error:
        send_response(handler, 422, {"error": error})
        return

    updated_schedule = {
        "id": schedule_id,
        "name": clean_data["name"],
        "watering_interval_days": clean_data["watering_interval_days"],
        "fertilize_interval_days": clean_data["fertilize_interval_days"],
        "misting": clean_data["misting"],
        "repot_interval_months": clean_data["repot_interval_months"],
        "preferred_temp_min_c": clean_data["preferred_temp_min_c"],
        "preferred_temp_max_c": clean_data["preferred_temp_max_c"],
        "notes": clean_data.get("notes", ""),
        "created_at": existing["created_at"],  # preserve original creation date
        "updated_at": current_timestamp(),
    }

    schedules_db[schedule_id] = updated_schedule
    send_response(handler, 200, updated_schedule)


@route("PATCH", r"/plants/(?P<id>[^/]+)")
def update_plant(handler, match, query_params, body):
    # Updates only the fields you send — everything else stays the same.
    # Useful for small changes like updating stock or changing health status.
    plant_id = match.group("id")
    plant = plants_db.get(plant_id)

    if not plant:
        send_response(handler, 404, {"error": "Plant '" + plant_id + "' not found."})
        return

    if body is None:
        send_response(handler, 400, {"error": "Could not read request body."})
        return

    if len(body) == 0:
        send_response(handler, 422, {"error": "No fields were provided. Send at least one field to update."})
        return

    clean_data, error = validate_plant_fields(body, require_all_fields=False)
    if error:
        send_response(handler, 422, {"error": error})
        return

    # Merge the new values into the existing plant
    for key in clean_data:
        plant[key] = clean_data[key]

    plant["updated_at"] = current_timestamp()
    send_response(handler, 200, plant)


@route("PATCH", r"/care-schedules/(?P<id>[^/]+)")
def update_schedule(handler, match, query_params, body):
    # Updates only the fields you send on a care schedule.
    schedule_id = match.group("id")
    schedule = schedules_db.get(schedule_id)

    if not schedule:
        send_response(handler, 404, {"error": "Care schedule '" + schedule_id + "' not found."})
        return

    if body is None:
        send_response(handler, 400, {"error": "Could not read request body."})
        return

    if len(body) == 0:
        send_response(handler, 422, {"error": "No fields were provided. Send at least one field to update."})
        return

    clean_data, error = validate_schedule_fields(body, require_all_fields=False)
    if error:
        send_response(handler, 422, {"error": error})
        return

    for key in clean_data:
        schedule[key] = clean_data[key]

    schedule["updated_at"] = current_timestamp()
    send_response(handler, 200, schedule)


@route("DELETE", r"/plants/(?P<id>[^/]+)")
def delete_plant(handler, match, query_params, body):
    # Removes a plant from the database.
    # If the plant has a watering history, you must add ?force=true to confirm deletion.
    plant_id = match.group("id")
    plant = plants_db.get(plant_id)

    if not plant:
        send_response(handler, 404, {"error": "Plant '" + plant_id + "' not found."})
        return

    # Check if this plant has any watering log entries
    history = []
    for entry in watering_log:
        if entry["plant_id"] == plant_id:
            history.append(entry)

    # Block deletion if there's a history, unless ?force=true was passed
    force = query_params.get("force", [None])[0] == "true"
    if len(history) > 0 and not force:
        send_response(handler, 409, {
            "error": "This plant has " + str(len(history)) + " watering log entries. "
                     "Add ?force=true to the URL if you still want to delete it.",
            "watering_entries": len(history),
        })
        return

    del plants_db[plant_id]
    send_response(handler, 200, {
        "message": plant["common_name"] + " (ID: " + plant_id + ") has been removed from inventory.",
        "watering_logs_orphaned": len(history),
    })


@route("DELETE", r"/care-schedules/(?P<id>[^/]+)")
def delete_schedule(handler, match, query_params, body):
    # Removes a care schedule.
    # Blocked if any plants are still using this schedule.
    schedule_id = match.group("id")
    schedule = schedules_db.get(schedule_id)

    if not schedule:
        send_response(handler, 404, {"error": "Care schedule '" + schedule_id + "' not found."})
        return

    # Find any plants that reference this schedule
    assigned_plants = []
    for plant in plants_db.values():
        if plant.get("care_schedule_id") == schedule_id:
            assigned_plants.append({"id": plant["id"], "name": plant["common_name"]})

    if len(assigned_plants) > 0:
        send_response(handler, 409, {
            "error": str(len(assigned_plants)) + " plant(s) are still using this schedule. "
                     "Reassign or remove them first.",
            "assigned_plants": assigned_plants,
        })
        return

    del schedules_db[schedule_id]
    send_response(handler, 200, {"message": "Care schedule '" + schedule["name"] + "' has been deleted."})


# ---------------------------------------------------------------------------
# HTTP request handler — receives every request and routes it
# ---------------------------------------------------------------------------

class RequestHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        # Custom log format so the terminal output is easier to read
        print("  [" + self.command + "] " + self.path + " -> " + args[1])

    def dispatch(self):
        # Parse the URL into its path and query string parts
        parsed_url  = urlparse(self.path)
        path        = parsed_url.path.rstrip("/") or "/"
        query_params = parse_qs(parsed_url.query)

        # Only read a body for requests that typically have one
        if self.command in ("POST", "PUT", "PATCH"):
            body = read_request_body(self)
        else:
            body = {}

        # Try each registered route until we find a match
        for method, pattern, handler_fn in ROUTES:
            if method != self.command:
                continue
            match = pattern.match(path)
            if match:
                handler_fn(self, match, query_params, body)
                return

        # Nothing matched
        send_response(self, 404, {"error": "Route not found: " + self.command + " " + path})

    # Python's http.server calls these methods based on the HTTP verb
    def do_GET(self):    self.dispatch()
    def do_POST(self):   self.dispatch()
    def do_PUT(self):    self.dispatch()
    def do_PATCH(self):  self.dispatch()
    def do_DELETE(self): self.dispatch()


# ---------------------------------------------------------------------------
# Start the server
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    HOST = "127.0.0.1"
    PORT = 8000

    server = HTTPServer((HOST, PORT), RequestHandler)

    print("")
    print("  Plant Nursery & Care Tracker API")
    print("  Running at http://" + HOST + ":" + str(PORT))
    print("")
    print("  Endpoints:")
    print("    GET    /plants                  list all plants")
    print("    GET    /plants/{id}             get one plant")
    print("    POST   /plants                  add a plant")
    print("    POST   /plants/{id}/water       log a watering")
    print("    PUT    /plants/{id}             replace a plant")
    print("    PUT    /care-schedules/{id}     replace a schedule")
    print("    PATCH  /plants/{id}             update some fields")
    print("    PATCH  /care-schedules/{id}     update some fields")
    print("    DELETE /plants/{id}             remove a plant")
    print("    DELETE /care-schedules/{id}     remove a schedule")
    print("")
    print("  Seeded data: plants p1 p2 p3 | schedules cs1 cs2")
    print("  Press Ctrl+C to stop.")
    print("")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Server stopped.")
