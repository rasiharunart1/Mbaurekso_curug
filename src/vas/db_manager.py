import pymysql
import json
from .config import DB_CONFIG

SCHEMA_PERSON_COUNTS = """
CREATE TABLE IF NOT EXISTS vas_person_counts (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    occupancy INT NOT NULL,
    note VARCHAR(255) NULL
) ENGINE=InnoDB;
"""

class DBManager:
    def __init__(self, status_callback=None):
        self.cfg = DB_CONFIG
        self.conn = None
        self.status_callback = status_callback
        if self.cfg.get("enable"):
            self.connect()

    def connect(self):
        try:
            self.conn = pymysql.connect(
                host=self.cfg["host"],
                port=int(self.cfg["port"]),
                user=self.cfg["user"],
                password=self.cfg["password"],
                database=self.cfg["name"],
                autocommit=True,
                charset="utf8mb4"
            )
            self._init_tables()
            if self.status_callback:
                self.status_callback(True)
        except Exception:
            self.conn = None
            if self.status_callback:
                self.status_callback(False)

    def _init_tables(self):
        if not self.conn:
            return
        cur = self.conn.cursor()
        cur.execute(SCHEMA_PERSON_COUNTS)

    def is_connected(self):
        return self.conn is not None

    def insert_person_snapshot(self, occupancy: int, note: str = None):
        if not self.cfg.get("enable"):
            return False
        if not self.conn:
            self.connect()
        if not self.conn:
            return False
        try:
            cur = self.conn.cursor()
            cur.execute(
                "INSERT INTO vas_person_counts (occupancy, note) VALUES (%s,%s)",
                (occupancy, note)
            )
            return True
        except Exception:
            return False

    def close(self):
        try:
            if self.conn:
                self.conn.close()
        except Exception:
            pass
        self.conn = None