import os
import re
import base64
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, auth
from firebase_admin.exceptions import FirebaseError

# --- Configuration ---
ROOT_DIR = "enrollment_data"

# --- Initialize Firebase ---
firebase_key = os.getenv("FIREBASE_KEY")
if not firebase_key:
    print("[FATAL ERROR] FIREBASE_KEY not set.")
    exit()

try:
    cred = credentials.Certificate(json.loads(firebase_key))
    firebase_admin.initialize_app(cred)
    print("[INFO] Firebase Admin SDK initialized successfully.")
except FirebaseError as e:
    print(f"[FATAL ERROR] Firebase init failed: {e}")
    exit()

# --- Initialize Flask ---
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

if not os.path.exists(ROOT_DIR):
    os.makedirs(ROOT_DIR)

def get_usn_from_email(email):
    match = re.search(r'([a-z]{2})(\d{3})@nmamit\.in', email)
    if match:
        branch = match.group(1).upper()
        number = match.group(2)
        return branch, f"{branch}_{number}"
    else:
        return "UNKNOWN", email.split('@')[0].replace('.', '_')

@app.route('/enroll', methods=['POST'])
def enroll():
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"status": "error", "message": "Missing auth token"}), 401

        token = auth_header.split(' ')[1]
        decoded_token = auth.verify_id_token(token)
        email = decoded_token.get('email')
        if not email:
            return jsonify({"status": "error", "message": "No email in token"}), 401
    except Exception as e:
        return jsonify({"status": "error", "message": f"Auth failed: {e}"}), 401

    branch, usn_folder = get_usn_from_email(email)
    print(f"[INFO] Enrollment request from {email} -> {branch}/{usn_folder}")

    branch_dir = os.path.join(ROOT_DIR, branch)
    person_dir = os.path.join(branch_dir, usn_folder)
    os.makedirs(person_dir, exist_ok=True)

    try:
        data = request.get_json()
        if not data or 'images' not in data:
            return jsonify({"status": "error", "message": "'images' missing"}), 400

        imgs = data['images']
        if len(imgs) != 5:
            return jsonify({"status": "error", "message": f"Expected 5 images, got {len(imgs)}"}), 400

        angles = ["frontal", "left", "right", "up", "down"]
        for i, durl in enumerate(imgs):
            encoded = durl.split(",", 1)[1] if "," in durl else durl
            binary = base64.b64decode(encoded)
            path = os.path.join(person_dir, f"{angles[i]}.jpg")
            with open(path, "wb") as f:
                f.write(binary)
        print(f"[SUCCESS] Saved 5 images for {usn_folder}")
        return jsonify({"status": "success", "message": "Images saved"}), 200
    except Exception as e:
        print(f"[ERROR] {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    print("[INFO] Server running on 0.0.0.0:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
