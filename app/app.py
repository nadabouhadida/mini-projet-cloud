from flask import Flask, jsonify, request
import psycopg2
import redis
import os
import time
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)

r = redis.from_url(os.environ.get('REDIS_URL', 'redis://localhost:6379'))

# Métriques Prometheus
REQUEST_COUNT = Counter('request_count', 'Nombre de requêtes', ['method', 'endpoint'])

def get_db():
    conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
    return conn

def init_db():
    for i in range(10):
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    id SERIAL PRIMARY KEY,
                    title VARCHAR(200) NOT NULL
                )
            ''')
            conn.commit()
            cur.close()
            conn.close()
            print("✅ Base de données connectée !")
            return
        except Exception as e:
            print(f"⏳ Attente PostgreSQL... ({i+1}/10)")
            time.sleep(3)

@app.route('/tasks', methods=['GET'])
def get_tasks():
    REQUEST_COUNT.labels(method='GET', endpoint='/tasks').inc()
    visits = r.incr('visits')
    print(f"👀 Nombre de visites : {visits}")
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT * FROM tasks')
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify([{"id": row[0], "title": row[1]} for row in rows])

@app.route('/tasks', methods=['POST'])
def create_task():
    REQUEST_COUNT.labels(method='POST', endpoint='/tasks').inc()
    data = request.get_json()
    conn = get_db()
    cur = conn.cursor()
    cur.execute('INSERT INTO tasks (title) VALUES (%s) RETURNING id', (data['title'],))
    task_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"id": task_id, "title": data['title']}), 201

@app.route('/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    REQUEST_COUNT.labels(method='DELETE', endpoint='/tasks').inc()
    conn = get_db()
    cur = conn.cursor()
    cur.execute('DELETE FROM tasks WHERE id = %s', (task_id,))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"message": "supprimé"}), 200

@app.route('/visits', methods=['GET'])
def get_visits():
    visits = r.get('visits')
    return jsonify({"visits": int(visits) if visits else 0})

@app.route('/metrics')
def metrics():
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)