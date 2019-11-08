import sqlite3
import time
import unittest

TABLE_NAME = "jvm_dispense_events"
DISPENSE_EVENT = "DispensedDrinkEvent"
TEST_DB_PATH = "test-databases"


def create_db(conn: sqlite3.Connection, drop=False, create=False):
    cur = conn.cursor()
    if drop:
        cur.execute(f'DROP TABLE IF EXISTS {TABLE_NAME}')

    create_table_query = (f'CREATE TABLE {TABLE_NAME} (\n'
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
    insert_query = f'INSERT INTO {TABLE_NAME} (timestamp, event_type, event_item) VALUES (?,?,?)'
    cur.execute(insert_query, (time, type, item))
    conn.commit()


def get_event(conn: sqlite3.Connection, time: int):
    cur = conn.cursor()
    select_event_query = f'SELECT * FROM {TABLE_NAME} WHERE "timestamp"=?'
    # Note, parameters must be iterable
    cur.execute(select_event_query, (time,))
    return cur.fetchall()


def get_events_by_type(conn: sqlite3.Connection, type: str):
    cur = conn.cursor()
    select_event_query = f'SELECT * FROM {TABLE_NAME} WHERE "event_type"=?'
    # Note, parameters must be iterable
    cur.execute(select_event_query, (type,))
    return cur.fetchall()


def get_events(conn: sqlite3.Connection):
    cur = conn.cursor()
    select_query = f'SELECT * FROM {TABLE_NAME}'
    cur.execute(select_query)
    return cur.fetchall()


class TestDBFunctions(unittest.TestCase):
    def setUp(self):
        """
        Setup test-dir if it doesn't exist yet, for putting testing databases into
        :return:
        """
        import os
        if not os.path.exists(TEST_DB_PATH):
            os.makedirs(TEST_DB_PATH)

    def test_database_creation(self):
        """
        Test that a database can be setup and that it is empty
        :return:
        """
        db_conn = sqlite3.connect(f"{TEST_DB_PATH}/{self._testMethodName}.db")
        create_db(db_conn, True, True)
        # Assert empty list returned when getting all events
        self.assertEqual(get_events(db_conn), [])

    def test_database_insert_and_get(self):
        """
        Test that a single inserted event into an empty database functions as expected
        :return:
        """
        db_conn = sqlite3.connect(f"{TEST_DB_PATH}/{self._testMethodName}.db")
        create_db(db_conn, True, True)
        # Insert event and assert for existence
        event = "Strong Coffee with Milk"
        timestamp = int(time.time())
        insert_event(db_conn, timestamp, DISPENSE_EVENT, event)
        # Assert that every element is as expected
        self.assertEqual((get_event(db_conn, timestamp))[0][0], timestamp)
        self.assertEqual((get_event(db_conn, timestamp))[0][1], DISPENSE_EVENT)
        self.assertEqual((get_event(db_conn, timestamp))[0][2], event)


if __name__ == '__main__':
    unittest.main()
