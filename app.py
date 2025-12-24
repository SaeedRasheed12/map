from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///app.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# ---------------- ADMIN (HARDCODED) ----------------
ADMIN_EMAIL = "saeedrasheed"
ADMIN_PASSWORD = "saeed1122"

# ---------------- MODELS ----------------

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(120), unique=True)
    password = db.Column(db.String(200))


class Place(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True)


class Location(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    floor = db.Column(db.String(50))
    place_id = db.Column(db.Integer, db.ForeignKey("place.id"))


# ✅ NEW: Recorded route (map-based)
class RecordedRoute(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    place_id = db.Column(db.Integer, nullable=False)
    from_location_id = db.Column(db.Integer, nullable=False)
    to_location_id = db.Column(db.Integer, nullable=False)
    floor = db.Column(db.String(50), default="Ground")
    location_name = db.Column(db.String(100), default="")  # optional label


# ✅ NEW: Route points (x,y list)
class RoutePoint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    route_id = db.Column(db.Integer, db.ForeignKey("recorded_route.id"), nullable=False)
    x = db.Column(db.Float, nullable=False)
    y = db.Column(db.Float, nullable=False)
    point_order = db.Column(db.Integer, nullable=False)


# ---------------- AUTH ----------------

@app.route("/admin/login", methods=["POST"])
def admin_login():
    data = request.json or {}
    if data.get("email") == ADMIN_EMAIL and data.get("password") == ADMIN_PASSWORD:
        return jsonify({"role": "admin"})
    return jsonify({"error": "Invalid admin"}), 401


@app.route("/user/signup", methods=["POST"])
def user_signup():
    data = request.json or {}
    if not data.get("name") or not data.get("email") or not data.get("password"):
        return jsonify({"error": "Missing fields"}), 400

    # prevent duplicate email crash
    if User.query.filter_by(email=data["email"]).first():
        return jsonify({"error": "Email already exists"}), 409

    user = User(
        name=data["name"],
        email=data["email"],
        password=generate_password_hash(data["password"]),
    )
    db.session.add(user)
    db.session.commit()
    return jsonify({"message": "User created"})


@app.route("/user/login", methods=["POST"])
def user_login():
    data = request.json or {}
    user = User.query.filter_by(email=data.get("email")).first()
    if user and check_password_hash(user.password, data.get("password", "")):
        return jsonify({"user_id": user.id})
    return jsonify({"error": "Invalid login"}), 401


# ---------------- PLACES ----------------

@app.route("/admin/place", methods=["POST"])
def add_place():
    data = request.json or {}
    if not data.get("name"):
        return jsonify({"error": "Place name required"}), 400

    if Place.query.filter_by(name=data["name"]).first():
        return jsonify({"error": "Place already exists"}), 409

    place = Place(name=data["name"])
    db.session.add(place)
    db.session.commit()
    return jsonify({"id": place.id, "name": place.name})


@app.route("/places", methods=["GET"])
def get_places():
    return jsonify([{"id": p.id, "name": p.name} for p in Place.query.all()])


# ---------------- LOCATIONS ----------------

@app.route("/admin/location", methods=["POST"])
def add_location():
    data = request.json or {}
    if not data.get("name") or not data.get("floor") or not data.get("place_id"):
        return jsonify({"error": "Missing fields"}), 400

    loc = Location(
        name=data["name"],
        floor=data["floor"],
        place_id=int(data["place_id"]),
    )
    db.session.add(loc)
    db.session.commit()
    return jsonify({"id": loc.id, "message": "Location saved"})


@app.route("/locations/<int:place_id>", methods=["GET"])
def get_locations_by_place(place_id):
    return jsonify(
        [{"id": l.id, "name": l.name, "floor": l.floor} for l in Location.query.filter_by(place_id=place_id).all()]
    )


# ---------------- LIVE MAP ROUTE SAVE (ADMIN) ----------------
# Flutter sends:
# {
#   "place_id": 1,
#   "from_id": 2,
#   "to_id": 5,
#   "floor": "Ground",
#   "location_name": "Exit",
#   "path": [{"x":120.3,"y":330.1}, ...]
# }

@app.route("/admin/route/save", methods=["POST"])
def save_live_route():
    data = request.json or {}

    required = ["place_id", "from_id", "to_id", "path"]
    for k in required:
        if k not in data:
            return jsonify({"error": f"Missing field: {k}"}), 400

    path = data.get("path") or []
    if not isinstance(path, list) or len(path) < 2:
        return jsonify({"error": "Path must be a list with at least 2 points"}), 400

    route = RecordedRoute(
        place_id=int(data["place_id"]),
        from_location_id=int(data["from_id"]),
        to_location_id=int(data["to_id"]),
        floor=data.get("floor", "Ground"),
        location_name=data.get("location_name", ""),
    )
    db.session.add(route)
    db.session.commit()

    for i, p in enumerate(path):
        if "x" not in p or "y" not in p:
            return jsonify({"error": "Each path point must have x and y"}), 400
        rp = RoutePoint(
            route_id=route.id,
            x=float(p["x"]),
            y=float(p["y"]),
            point_order=i,
        )
        db.session.add(rp)

    db.session.commit()
    return jsonify({"route_id": route.id, "message": "Live route saved"})


# ---------------- USER NAVIGATION (MAP-BASED) ----------------
# GET /navigate/map?place_id=1&from=2&to=5

@app.route("/navigate/map", methods=["GET"])
def navigate_map():
    place_id = request.args.get("place_id")
    from_id = request.args.get("from")
    to_id = request.args.get("to")

    if not place_id or not from_id or not to_id:
        return jsonify({"error": "place_id, from, to are required"}), 400

    route = RecordedRoute.query.filter_by(
        place_id=int(place_id),
        from_location_id=int(from_id),
        to_location_id=int(to_id),
    ).first()

    if not route:
        return jsonify({"error": "Route not found"}), 404

    points = RoutePoint.query.filter_by(route_id=route.id).order_by(RoutePoint.point_order).all()

    from_loc = Location.query.get(route.from_location_id)
    to_loc = Location.query.get(route.to_location_id)

    return jsonify(
        {
            "route_id": route.id,
            "floor": route.floor,
            "location_name": route.location_name,
            "from_name": from_loc.name if from_loc else "",
            "to_name": to_loc.name if to_loc else "",
            "path": [{"x": p.x, "y": p.y} for p in points],
        }
    )


# ---------------- OPTIONAL: LIST ALL ROUTES FOR A PLACE ----------------
# Useful for admin testing in Postman
@app.route("/admin/routes/<int:place_id>", methods=["GET"])
def list_routes(place_id):
    routes = RecordedRoute.query.filter_by(place_id=place_id).all()
    return jsonify(
        [
            {
                "route_id": r.id,
                "from_id": r.from_location_id,
                "to_id": r.to_location_id,
                "floor": r.floor,
                "location_name": r.location_name,
            }
            for r in routes
        ]
    )


# ---------------- RUN ----------------

if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)