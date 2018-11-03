import sqlite3


class PriceviewDB:
    def __init__(self, store_id, timestamp):
        self.store_id = store_id
        self.ts = int(timestamp)
        self.conn = sqlite3.connect('priceview.sqlite3', )

        # создание таблиц
        self.conn.execute(
            'CREATE TABLE IF NOT EXISTS groups (sid INTEGER, pid INTEGER, id INTEGER, name TEXT, link TEXT,'
            'PRIMARY KEY (sid, pid, id),'
            'UNIQUE (sid, id))')

        self.conn.execute(
            'CREATE TABLE IF NOT EXISTS prods (sid INTEGER, id TEXT, active INTEGER, price REAL, name TEXT, category TEXT, vendor TEXT, link TEXT,'
            'PRIMARY KEY(sid, id))')

        self.conn.execute(
            'CREATE TABLE IF NOT EXISTS price_hist (sid INTEGER, prod TEXT, datetime INTEGER, price REAL,'
            'PRIMARY KEY(sid, prod, datetime))')

        self.conn.execute(
            'CREATE TABLE IF NOT EXISTS joins (sid INTEGER, prod TEXT, grp INTEGER,'
            'PRIMARY KEY(sid, prod, grp))')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx1 ON joins (sid, grp, prod)')

    def prepare_table_before_insert(self):
        # подготовка таблиц
        self.conn.execute('DELETE FROM groups WHERE sid = :id', {"id": self.store_id})
        self.conn.execute('DELETE FROM joins WHERE sid = :id', {"id": self.store_id})
        self.conn.execute('UPDATE prods SET active = 0 WHERE sid = :id', {"id": self.store_id})

    def commit(self):
        self.conn.commit()

    def insert_data_group(self, group):
        self.conn.execute("""
            INSERT INTO groups (sid, pid, id, name, link)
            VALUES (:sid, :pid, :id, :name, :link)
            """, group)
        self.conn.commit()

    def insert_prods(self, prods, joins):

        self.conn.executemany("""
            INSERT OR REPLACE
            INTO prods (sid, id, active, price, name, category, vendor, link)
            VALUES (:sid, :id, 1, :price, :name, :category, :vendor, :link)
            """, prods)

        self.conn.executemany("""
            INSERT INTO price_hist (sid, prod, datetime, price)
            SELECT :sid, :id, {0}, :price
            WHERE :price != coalesce((
                select price
                from price_hist
                where sid = :sid
                  and prod = :id
                  and datetime <= {0}
                order by datetime desc
                limit 1
            ), 0)
            """.format(self.ts), prods)

        self.conn.executemany("""
            INSERT OR REPLACE
            INTO joins (sid, prod, grp)
            VALUES (:sid, :prod, :grp)
            """, joins)

        self.conn.commit()
