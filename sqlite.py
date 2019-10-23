import sqlite3
from pprint import pprint

table_name = "jvm_dispense_events"


def create_db(conn: sqlite3.Connection, drop=False, create=False):
    cur = conn.cursor()
    if drop:
        cur.execute(f'DROP TABLE IF EXISTS {table_name}')

    create_table_query = (f'CREATE TABLE {table_name} (\n'
                          '                            timestamp INTEGER PRIMARY KEY,\n'
                          '                            event_type TEXT NOT NULL,\n'
                          '                            event_item TEXT NOT NULL)\n'
                          '    ')

    if drop or create:
        cur.execute(create_table_query)

    cur.close()
    conn.commit()


def insert_event(conn: sqlite3.Connection, time: int, type: str, item: str):
    cur = conn.cursor()
    insert_query = f'INSERT INTO {table_name} (timestamp, event_type, event_item) VALUES (?,?,?)'
    cur.execute(insert_query, (time, type, item))
    conn.commit()


def get_event(conn: sqlite3.Connection, time: int):
    cur = conn.cursor()
    select_event_query = f'SELECT * FROM {table_name} WHERE "timestamp"=?'
    # Note, parameters must be iterable
    cur.execute(select_event_query, (time,))
    return cur.fetchall()


def get_events(conn: sqlite3.Connection):
    cur = conn.cursor()
    select_query = f'SELECT * FROM {table_name}'
    cur.execute(select_query)
    return cur.fetchall()


db_conn = sqlite3.connect('jvm-loss.db')
create_db(db_conn, True, True)
for i in range(100):
    insert_event(db_conn, i, "DispensedDrinkEvent", "Coffee")
pprint(get_events(db_conn))
print("Selecting for time=42 event")
pprint(get_event(db_conn, 42))
