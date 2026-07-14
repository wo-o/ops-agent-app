import http.server
import json
import logging
import os
import socketserver
import time

import psycopg2

logging.basicConfig(
    filename="/var/log/app/app.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

CFG = dict(
    host=os.environ["DB_HOST"],
    dbname=os.environ["DB_NAME"],
    user=os.environ["DB_USER"],
    password=os.environ["DB_PASSWORD"],
    connect_timeout=5,
)
_leaks = []  # /troublemaker가 닫지 않고 쌓는 커넥션(누수)


def db():
    return psycopg2.connect(**CFG)


def init_db():
    for _ in range(30):
        try:
            with db() as c, c.cursor() as cur:
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS items(id serial primary key, name text, created_at timestamptz default now())"
                )
                c.commit()
            logging.info("db ready")
            return
        except Exception as e:
            logging.info("waiting for db: %s", e)
            time.sleep(5)
    logging.error("db never became ready")


class H(http.server.BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="text/plain"):
        b = body if isinstance(body, bytes) else str(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, fmt, *a):
        logging.info("%s %s", self.command + " " + self.path, (fmt % a))

    def do_GET(self):
        if self.path.startswith("/healthz"):
            return self._send(200, "ok")
        if self.path.startswith("/troublemaker"):
            # 사전 장애: 커넥션 누수 + CPU 태우기 + ERROR 로그 → 500
            try:
                for _ in range(20):
                    _leaks.append(db())  # 닫지 않음 → 커넥션 증가
                end = time.time() + 8
                while time.time() < end:  # CPU 태우기
                    _ = sum(i * i for i in range(10000))
                logging.error(
                    "troublemaker triggered: leaked %d db connections + burned cpu",
                    len(_leaks),
                )
                return self._send(500, "internal error: resource exhaustion")
            except Exception as e:
                logging.error("troublemaker db error: %s", e)
                return self._send(500, "internal error")
        if self.path.startswith("/items"):
            try:
                with db() as c, c.cursor() as cur:
                    cur.execute(
                        "SELECT id, name, created_at FROM items ORDER BY id DESC LIMIT 50"
                    )
                    rows = [
                        {"id": r[0], "name": r[1], "created_at": str(r[2])}
                        for r in cur.fetchall()
                    ]
                return self._send(200, json.dumps(rows), "application/json")
            except Exception as e:
                logging.error("items query failed: %s", e)
                return self._send(500, "db error")
        # GET /
        try:
            with db() as c, c.cursor() as cur:
                cur.execute("SELECT count(*) FROM items")
                n = cur.fetchone()[0]
            return self._send(200, "A-service OK — items=%d, db=connected" % n)
        except Exception as e:
            logging.error("root db check failed: %s", e)
            return self._send(200, "A-service OK — db=UNREACHABLE")

    def do_POST(self):
        if self.path.startswith("/items"):
            n = int(self.headers.get("Content-Length", 0))
            name = (self.rfile.read(n).decode() or "unnamed").strip()[:100]
            try:
                with db() as c, c.cursor() as cur:
                    cur.execute(
                        "INSERT INTO items(name) VALUES(%s) RETURNING id", (name,)
                    )
                    new_id = cur.fetchone()[0]
                    c.commit()
                return self._send(
                    201, json.dumps({"id": new_id, "name": name}), "application/json"
                )
            except Exception as e:
                logging.error("insert failed: %s", e)
                return self._send(500, "db error")
        return self._send(404, "not found")


init_db()
socketserver.ThreadingTCPServer.allow_reuse_address = True
with socketserver.ThreadingTCPServer(("0.0.0.0", 8080), H) as s:
    s.serve_forever()
