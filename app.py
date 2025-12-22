from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS


app = Flask(__name__)
CORS(app)   # ✅ THIS LINE FIXES FLUTTER CONNECTION
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

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


class Location(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    floor = db.Column(db.String(50))
    place_id = db.Column(db.Integer)


class Route(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    from_location_id = db.Column(db.Integer)
    to_location_id = db.Column(db.Integer)
    floor = db.Column(db.String(50))

class Place(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True)

class RouteStep(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    route_id = db.Column(db.Integer)
    step_order = db.Column(db.Integer)
    action = db.Column(db.String(50))   # walk, left, right, stairs_up
    distance = db.Column(db.Float)      # meters


# ---------------- AUTH APIs ----------------

@app.route('/admin/login', methods=['POST'])
def admin_login():
    data = request.json
    if data['email'] == ADMIN_EMAIL and data['password'] == ADMIN_PASSWORD:
        return jsonify({"role": "admin"})
    return jsonify({"error": "Invalid admin"}), 401


@app.route('/user/signup', methods=['POST'])
def user_signup():
    data = request.json
    user = User(
        name=data['name'],
        email=data['email'],
        password=generate_password_hash(data['password'])
    )
    db.session.add(user)
    db.session.commit()
    return jsonify({"message": "User created"})


@app.route('/user/login', methods=['POST'])
def user_login():
    data = request.json
    user = User.query.filter_by(email=data['email']).first()
    if user and check_password_hash(user.password, data['password']):
        return jsonify({"user_id": user.id})
    return jsonify({"error": "Invalid login"}), 401


# ---------------- LOCATIONS ----------------

@app.route('/admin/location', methods=['POST'])
def add_location():
    data = request.json
    loc = Location(name=data['name'], floor=data['floor'])
    db.session.add(loc)
    db.session.commit()
    return jsonify({"message": "Location saved"})


@app.route('/locations', methods=['GET'])
def get_locations():
    return jsonify([
        {"id": l.id, "name": l.name, "floor": l.floor}
        for l in Location.query.all()
    ])


# ---------------- ROUTE RECORDING ----------------

@app.route('/admin/route/start', methods=['POST'])
def start_route():
    data = request.json
    route = Route(
        from_location_id=data['from_id'],
        to_location_id=data['to_id'],
        floor=data['floor']
    )
    db.session.add(route)
    db.session.commit()
    return jsonify({"route_id": route.id})


@app.route('/admin/route/step', methods=['POST'])
def save_route_step():
    data = request.json
    step = RouteStep(
        route_id=data['route_id'],
        step_order=data['order'],
        action=data['action'],
        distance=data['distance']
    )
    db.session.add(step)
    db.session.commit()
    return jsonify({"message": "Step saved"})


@app.route('/admin/route/stop', methods=['POST'])
def stop_route():
    return jsonify({"message": "Route completed"})


# ---------------- USER NAVIGATION ----------------

@app.route('/navigate', methods=['GET'])
def navigate():
    from_id = request.args.get('from')
    to_id = request.args.get('to')

    route = Route.query.filter_by(
        from_location_id=from_id,
        to_location_id=to_id
    ).first()

    if not route:
        return jsonify({"error": "Route not found"}), 404

    steps = RouteStep.query.filter_by(
        route_id=route.id
    ).order_by(RouteStep.step_order).all()

    return jsonify([
        {"action": s.action, "distance": s.distance}
        for s in steps
    ])

@app.route('/admin/place', methods=['POST'])
def add_place():
    data = request.json
    place = Place(name=data['name'])
    db.session.add(place)
    db.session.commit()
    return jsonify({"place_id": place.id})

@app.route('/locations/<int:place_id>', methods=['GET'])
def get_locations_by_place(place_id):
    return jsonify([
        {"id": l.id, "name": l.name}
        for l in Location.query.filter_by(place_id=place_id).all()
    ])

import os

# ---------------- RUN ----------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)