import sqlite3
import time
import unittest
from pprint import pprint

DISPENSE_TABLE_NAME = "jvm_dispense_events"
INGREDIENT_LEVEL_TABLE_NAME = "jvm_ingredient_levels"
DISPENSE_EVENT = "DispensedDrinkEvent"
TEST_DB_PATH = "test-databases"


def create_db(conn: sqlite3.Connection, drop=False, create=False):
    cur = conn.cursor()
    if drop:
        cur.execute(f'DROP TABLE IF EXISTS {DISPENSE_TABLE_NAME}')
        cur.execute(f'DROP TABLE IF EXISTS {INGREDIENT_LEVEL_TABLE_NAME}')

    create_dispense_table_query = (f'CREATE TABLE {DISPENSE_TABLE_NAME} (\n'
                                   '                            timestamp INTEGER PRIMARY KEY,\n'
                                   '                            event_type TEXT NOT NULL,\n'
                                   '                            event_item TEXT NOT NULL)\n'
                                   '    ')

    create_ingredient_level_table_query = (f'CREATE TABLE {INGREDIENT_LEVEL_TABLE_NAME} (\n'
                                           '                            timestamp INTEGER PRIMARY KEY,\n'
                                           '                            coffee_level FLOAT NOT NULL ,\n'
                                           '                            milk_level FLOAT NOT NULL ,\n'
                                           '                            sugar_level FLOAT NOT NULL,\n'
                                           '                            cacao_item FLOAT NOT NULL)\n'
                                           '    ')

    if drop or create:
        cur.execute(create_dispense_table_query)
        cur.execute(create_ingredient_level_table_query)

    cur.close()
    conn.commit()


def insert_event(conn: sqlite3.Connection, time: int, type: str, item: str):
    cur = conn.cursor()
    insert_query = f'INSERT INTO {DISPENSE_TABLE_NAME} (timestamp, event_type, event_item) VALUES (?,?,?)'
    cur.execute(insert_query, (time, type, item))
    conn.commit()


def get_event(conn: sqlite3.Connection, time: int):
    cur = conn.cursor()
    select_event_query = f'SELECT * FROM {DISPENSE_TABLE_NAME} WHERE "timestamp"=?'
    # Note, parameters must be iterable
    cur.execute(select_event_query, (time,))
    return cur.fetchall()


def get_events_by_type(conn: sqlite3.Connection, type: str):
    cur = conn.cursor()
    select_event_query = f'SELECT * FROM {DISPENSE_TABLE_NAME} WHERE "event_type"=?'
    # Note, parameters must be iterable
    cur.execute(select_event_query, (type,))
    return cur.fetchall()


def get_events_by_type_newer_than(conn: sqlite3.Connection, type: str, time: int):
    cur = conn.cursor()
    select_event_query = f'SELECT * FROM {DISPENSE_TABLE_NAME} WHERE "event_type"=? AND "timestamp" >=?'
    # Note, parameters must be iterable
    cur.execute(select_event_query, (type, time))
    return cur.fetchall()


def get_events_by_type_in_range(conn: sqlite3.Connection, type: str, lower_time: int, upper_time: int):
    cur = conn.cursor()
    select_event_query = f'SELECT * FROM {DISPENSE_TABLE_NAME}' \
                         f' WHERE "event_type"=? AND "timestamp" >=? AND "timestamp" <=?'
    # Note, parameters must be iterable
    cur.execute(select_event_query, (type, lower_time, upper_time))
    return cur.fetchall()


def get_events_by_item(conn: sqlite3.Connection, item: str):
    cur = conn.cursor()
    select_event_query = f'SELECT * FROM {DISPENSE_TABLE_NAME} WHERE "event_item"=?'
    # Note, parameters must be iterable
    cur.execute(select_event_query, (item,))
    return cur.fetchall()


def get_events(conn: sqlite3.Connection):
    cur = conn.cursor()
    select_query = f'SELECT * FROM {DISPENSE_TABLE_NAME}'
    cur.execute(select_query)
    return cur.fetchall()


def get_last_event(conn: sqlite3.Connection):
    cur = conn.cursor()
    select_last_query = f'SELECT * FROM    {DISPENSE_TABLE_NAME} ' \
                        f'WHERE   timestamp = (SELECT MAX(timestamp)  FROM {DISPENSE_TABLE_NAME});'
    cur.execute(select_last_query)
    return cur.fetchall()


def get_last_event_by_type(conn: sqlite3.Connection, type: str):
    cur = conn.cursor()
    select_last_query_by_type = f'SELECT * FROM {DISPENSE_TABLE_NAME} ' \
                                f'WHERE "event_type"=? ORDER BY timestamp DESC LIMIT 1'
    cur.execute(select_last_query_by_type, (type,))
    return cur.fetchall()


def get_last_event_by_type_older_than(conn: sqlite3.Connection, type: str, upper_time: int):
    cur = conn.cursor()
    select_last_query_by_type_older_than = f'SELECT * FROM {DISPENSE_TABLE_NAME} ' \
                                           f'WHERE "event_type"=? AND "timestamp" <=? ORDER BY timestamp DESC LIMIT 1'
    cur.execute(select_last_query_by_type_older_than, (type, upper_time))
    return cur.fetchall()


def get_last_event_by_type_newer_than(conn: sqlite3.Connection, type: str, lower_time: int):
    cur = conn.cursor()
    select_last_query_by_type_older_than = f'SELECT * FROM {DISPENSE_TABLE_NAME} ' \
                                           f'WHERE "event_type"=? AND "timestamp" >=? ORDER BY timestamp DESC LIMIT 1'
    cur.execute(select_last_query_by_type_older_than, (type, lower_time))
    return cur.fetchall()


def get_events_ingredient(conn: sqlite3.Connection):
    cur = conn.cursor()
    select_query = f'SELECT * FROM {INGREDIENT_LEVEL_TABLE_NAME}'
    cur.execute(select_query)
    return cur.fetchall()


def insert_event_ingredient(conn: sqlite3.Connection, time: int, coffee: float, milk: float, sugar: float,
                            cacao: float):
    cur = conn.cursor()
    insert_query = f'INSERT INTO {INGREDIENT_LEVEL_TABLE_NAME} ' \
                   f'(timestamp, coffee_level, milk_level, sugar_level, cacao_item) VALUES (?,?,?,?,?)'
    cur.execute(insert_query, (time, coffee, milk, sugar, cacao))
    conn.commit()


def get_last_event_ingredient(conn: sqlite3.Connection):
    cur = conn.cursor()
    select_last_query = f'SELECT * FROM {INGREDIENT_LEVEL_TABLE_NAME} ' \
                        f'WHERE timestamp = (SELECT MAX(timestamp)  FROM {INGREDIENT_LEVEL_TABLE_NAME});'
    cur.execute(select_last_query)
    return cur.fetchall()


class TestDBFunctions(unittest.TestCase):
    def setUp(self) -> None:
        """
        Setup test-dir if it doesn't exist yet, for putting testing databases into
        :return:
        """
        import os
        if not os.path.exists(TEST_DB_PATH):
            os.makedirs(TEST_DB_PATH)

    def tearDown(self) -> None:
        """
        Removes all files in test-dir. FIXME; is fairly slow to execute
        :return:
        """
        import os
        for entry in os.scandir(TEST_DB_PATH):
            if not entry.name.startswith('.') and entry.is_file():
                os.remove(f"{TEST_DB_PATH}/{entry.name}")

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

    def test_database_get_item_events(self):
        db_conn = sqlite3.connect(f"{TEST_DB_PATH}/{self._testMethodName}.db")
        create_db(db_conn, True, True)
        timestamp = int(time.time())

        coffee_item = "Hot Coffee with Milk"
        water_item = "Hot Water without Milk"

        # Create entries, ensuring that primary key timestamp is unique
        for i in range(0, 20):
            insert_event(db_conn, timestamp + i, DISPENSE_EVENT, coffee_item)
            insert_event(db_conn, timestamp + i + 1000, DISPENSE_EVENT, water_item)

        # Assert that all coffee-items are as expected
        coffee_time = timestamp
        for item in get_events_by_item(db_conn, coffee_item):
            self.assertEqual(item[0], coffee_time)
            self.assertEqual(item[1], DISPENSE_EVENT)
            self.assertEqual(item[2], coffee_item)
            coffee_time += 1

        # Assert that all water-items are as expected
        water_time = timestamp + 1000
        for item in get_events_by_item(db_conn, water_item):
            self.assertEqual(item[0], water_time)
            self.assertEqual(item[1], DISPENSE_EVENT)
            self.assertEqual(item[2], water_item)
            water_time += 1

    def test_database_get_type_events(self):
        db_conn = sqlite3.connect(f"{TEST_DB_PATH}/{self._testMethodName}.db")
        create_db(db_conn, True, True)
        timestamp = int(time.time())

        ingredient_event = '"Ingredient \'Sugar\' is filled." Current grams: 2400 '
        cleaning_event = '"Manual rengøring" "Espresso Brewer"   "success" '

        ingredient_type = "IngredientLevel"
        cleaning_type = "Rengørrings begivenhed"

        # Create entries, ensuring that primary key timestamp is unique
        for i in range(0, 20):
            insert_event(db_conn, timestamp + i, ingredient_type, ingredient_event)
            insert_event(db_conn, timestamp + i + 1000, cleaning_type, cleaning_event)

        # Assert that all coffee-items are as expected
        ingredient_time = timestamp
        for item in get_events_by_type(db_conn, ingredient_type):
            self.assertEqual(item[0], ingredient_time)
            self.assertEqual(item[1], ingredient_type)
            self.assertEqual(item[2], ingredient_event)
            ingredient_time += 1

        # Assert that all water-items are as expected
        cleaning_time = timestamp + 1000
        for item in get_events_by_type(db_conn, cleaning_type):
            self.assertEqual(item[0], cleaning_time)
            self.assertEqual(item[1], cleaning_type)
            self.assertEqual(item[2], cleaning_event)
            cleaning_time += 1

    def test_database_get_type_events_newer_than(self):
        db_conn = sqlite3.connect(f"{TEST_DB_PATH}/{self._testMethodName}.db")
        create_db(db_conn, True, True)
        timestamp = int(time.time())

        ingredient_event = '"Ingredient \'Sugar\' is filled." Current grams: 2400 '
        cleaning_event = '"Manual rengøring" "Espresso Brewer"   "success" '

        ingredient_type = "IngredientLevel"
        cleaning_type = "Rengørrings begivenhed"

        # Insert same event at different times
        insert_event(db_conn, timestamp - 5, ingredient_type, ingredient_event)
        insert_event(db_conn, timestamp, ingredient_type, ingredient_event)
        insert_event(db_conn, timestamp + 5, ingredient_type, ingredient_event)

        # Insert differently typed event at different times
        insert_event(db_conn, timestamp - 4, cleaning_type, cleaning_event)
        insert_event(db_conn, timestamp + 1, cleaning_type, cleaning_event)
        insert_event(db_conn, timestamp + 6, cleaning_type, cleaning_event)

        # Assert that events were added
        self.assertEqual(len(get_events(db_conn)), 6)

        # Assert that three results are received when exactly within time-bounds
        self.assertEqual(len(get_events_by_type_newer_than(db_conn, ingredient_type, timestamp - 5)), 3)
        # Assert that no newer events exist
        self.assertEqual(get_events_by_type_newer_than(db_conn, ingredient_type, timestamp + 10), [])

    def test_database_get_type_events_in_range(self):
        db_conn = sqlite3.connect(f"{TEST_DB_PATH}/{self._testMethodName}.db")
        create_db(db_conn, True, True)
        timestamp = int(time.time())

        ingredient_event = '"Ingredient \'Sugar\' is filled." Current grams: 2400 '
        cleaning_event = '"Manual rengøring" "Espresso Brewer"   "success" '

        ingredient_type = "IngredientLevel"
        cleaning_type = "Rengørrings begivenhed"

        # Insert same event at different times
        insert_event(db_conn, timestamp - 5, ingredient_type, ingredient_event)
        insert_event(db_conn, timestamp - 2, ingredient_type, ingredient_event)
        insert_event(db_conn, timestamp, ingredient_type, ingredient_event)
        insert_event(db_conn, timestamp + 2, ingredient_type, ingredient_event)
        insert_event(db_conn, timestamp + 5, ingredient_type, ingredient_event)

        # Insert differently typed event at different times
        insert_event(db_conn, timestamp - 4, cleaning_type, cleaning_event)
        insert_event(db_conn, timestamp + 1, cleaning_type, cleaning_event)
        insert_event(db_conn, timestamp + 6, cleaning_type, cleaning_event)

        # Assert that events were added
        self.assertEqual(len(get_events(db_conn)), 8)

        # Assert that three results are received when exactly within time-bounds
        self.assertEqual(len(get_events_by_type_in_range(db_conn, ingredient_type, timestamp - 2, timestamp + 2)), 3)
        # Assert that no newer events exist
        self.assertEqual(get_events_by_type_newer_than(db_conn, ingredient_type, timestamp + 10), [])

    def test_database_get_last_event(self):
        db_conn = sqlite3.connect(f"{TEST_DB_PATH}/{self._testMethodName}.db")
        create_db(db_conn, True, True)
        timestamp = int(time.time())

        coffee_item = "Hot Coffee with Milk"

        for i in range(10):
            insert_event(db_conn, timestamp + i, DISPENSE_EVENT, coffee_item)

        last_event = get_last_event(db_conn)
        # Assert that timestamp is equal to last inserted event
        self.assertEqual(last_event[0][0], timestamp + 9)


if __name__ == '__main__':
    unittest.main()
