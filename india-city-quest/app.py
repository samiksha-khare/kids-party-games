from flask import Flask, request, jsonify, session, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
import pymysql
from db import get_connection
from config import SECRET_KEY
import os

app = Flask(__name__, static_folder='.')
app.secret_key = SECRET_KEY


# ── Static file serving ─────────────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')


# ── Auth ─────────────────────────────────────────────────────────────────────

@app.route('/api/signup', methods=['POST'])
def signup():
    data     = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM users WHERE username = %s', (username,))
            if cur.fetchone():
                return jsonify({'error': 'Username already taken'}), 409
            pw_hash = generate_password_hash(password)
            cur.execute(
                'INSERT INTO users (username, password_hash) VALUES (%s, %s)',
                (username, pw_hash)
            )
            conn.commit()
            user_id = cur.lastrowid
    finally:
        conn.close()

    session['user_id']  = user_id
    session['username'] = username
    return jsonify({'ok': True, 'username': username})


@app.route('/api/login', methods=['POST'])
def login():
    data     = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT id, username, password_hash FROM users WHERE username = %s',
                (username,)
            )
            user = cur.fetchone()
    finally:
        conn.close()

    if not user or not check_password_hash(user['password_hash'], password):
        return jsonify({'error': 'Invalid username or password'}), 401

    session['user_id']  = user['id']
    session['username'] = user['username']
    return jsonify({'ok': True, 'username': user['username']})


@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'ok': True})


@app.route('/api/me')
def me():
    if 'user_id' in session:
        return jsonify({'loggedIn': True, 'username': session['username']})
    return jsonify({'loggedIn': False})


# ── Scores ───────────────────────────────────────────────────────────────────

@app.route('/api/score', methods=['POST'])
def save_score():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    data         = request.get_json() or {}
    score        = int(data.get('score', 0))
    max_possible = int(data.get('max_possible', 2000))
    game_mode    = data.get('game_mode', 'completed')
    if game_mode not in ('completed', 'game_over'):
        game_mode = 'completed'

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'INSERT INTO scores (user_id, score, max_possible, game_mode) VALUES (%s, %s, %s, %s)',
                (session['user_id'], score, max_possible, game_mode)
            )
            conn.commit()
    finally:
        conn.close()

    return jsonify({'ok': True})


@app.route('/api/scores')
def get_scores():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                '''SELECT score, max_possible, game_mode, played_at
                   FROM scores
                   WHERE user_id = %s
                   ORDER BY played_at DESC
                   LIMIT 10''',
                (session['user_id'],)
            )
            rows = cur.fetchall()

            cur.execute(
                'SELECT MAX(score) AS best FROM scores WHERE user_id = %s',
                (session['user_id'],)
            )
            best_row = cur.fetchone()
    finally:
        conn.close()

    for row in rows:
        row['played_at'] = row['played_at'].strftime('%d %b %Y, %I:%M %p')

    return jsonify({
        'scores':     rows,
        'best_score': best_row['best'] or 0
    })


if __name__ == '__main__':
    app.run(debug=True, port=5000)
