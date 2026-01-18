from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import os

from routes.lesson_origin import lesson_origin_bp

load_dotenv()

app = Flask(__name__)
CORS(app, origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","))
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev")

app.register_blueprint(lesson_origin_bp, url_prefix="/api/lesson-origin")


@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy", "service": "lesson-origin-api"}), 200


if __name__ == "__main__":
    app.run(debug=True, port=5000)
