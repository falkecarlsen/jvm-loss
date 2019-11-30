from __future__ import print_function

import pprint
from email.mime.text import MIMEText
import base64
import pickle
import os.path
import sqlite3
import datetime
import re
import time
import calendar
import _thread
import sys
from sqlite import create_db, insert_event, get_last_event, get_events, get_last_event_by_type
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://mail.google.com/']
DB_FILE_NAME = "jvm-loss.db"

# todo add more tables, or insert all kind of mails into existing table when mail is read
# todo multithread to see if under threshold has been fixed
# todo add ingrediens level to db, and insert event each time an ingredient level is changed, either by dispenseddrink event, or other
# todo query by sending mail to jvmloss or do slack bot
# TODO make universal get mails function that returns a dict of all useful information, instead of multiple functions


# Todo QA this list, both with names (i think too many are added here, and with incorrect translations) and number
coffee_beans_usage = {"Café choco": 8,
                      "Cappuccino": 8,
                      "Café au lait sugar": 8,
                      "Choco lux": 8,
                      "Chocolate": 0,
                      "Coffee": 8,
                      "Coffee with sugar": 8,
                      "Espresso": 8,
                      "Filter kaffe": 8,
                      "Filter coffee milk": 8,
                      "Hot water": 8,
                      "Wiener melange": 8,

                      # todo check if these is correct
                      "Lungo": 8,
                      "Lungo with sugar": 8,
                      "Lungo with milk": 8,
                      "Lungo with sugar and milk": 8,
                      "Espresso with sugar": 8,
                      "Cappuccino with sugar": 8,
                      "Espresso with milk": 8,
                      "hot cacao": 8,
                      "Café au lait": 8,
                      "Latte macchiato": 8,
                      "Espresso with sugar and milk": 8,
                      "Hot cacao with milk": 8,
                      "Café au lait with sugar": 8,
                      "Latte macchiato with sugar": 8,
                      "Coffee with milk": 8,
                      "Coffee with sugar and milk": 8}

milk_powder_usage = {"Café choco": 8,
                     "Cappuccino": 8,
                     "Coffee with sugar": 8,
                     "Café au lait sugar": 8,
                     "Coffee": 8,
                     "Choco lux": 8,
                     "Chocolate": 0,
                     "Hot water": 8,
                     "Filter kaffe": 8,
                     "Filter coffee milk": 8,
                     "Wiener melange": 8}

cacao_powder_usage = {"Café choco": 8,
                      "Cappuccino": 8,
                      "Coffee with sugar": 8,
                      "Café au lait sugar": 8,
                      "Coffee": 8,
                      "Choco lux": 8,
                      "Chocolate": 0,
                      "Hot water": 8,
                      "Filter kaffe": 8,
                      "Filter coffee milk": 8,
                      "Wiener melange": 8}

sugar_usage = {"Café choco": 8,
               "Cappuccino": 8,
               "Coffee with sugar": 8,
               "Café au lait sugar": 8,
               "Coffee": 8,
               "Choco lux": 8,
               "Chocolate": 0,
               "Hot water": 8,
               "Filter kaffe": 8,
               "Filter coffee milk": 8,
               "Wiener melange": 8}


# Sets up connection to gmail
def setup_gmail_connection():
    if 1 < len(sys.argv) and sys.argv[1] == 'test':
        token_pickle = 'token_test.pickle'
        credentials = 'credentials_test.json'
    else:
        token_pickle = 'token.pickle'
        credentials = 'credentials.json'

    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists(token_pickle):
        with open(token_pickle, 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials, SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(token_pickle, 'wb') as token:
            pickle.dump(creds, token)

    return build('gmail', 'v1', credentials=creds)


# Returns body of mails (only the text part) and the id of mails
def get_mails_body(gmail_con, search, max_results):
    inbox = gmail_con.users().messages().list(userId='me', q=search, maxResults=max_results).execute()

    if 0 < inbox["resultSizeEstimate"]:
        mails = [gmail_con.users().messages().get(userId="me", id=msg['id'], format="full").execute() for msg in
                 inbox["messages"]]

        ids = [mail['id'] for mail in mails]

        return [str(base64.urlsafe_b64decode(mail['payload']['parts'][0]['parts'][0]['body']['data']).decode('utf-8'))
                for mail in mails], ids
    else:
        return [], []


def get_mails_sender(gmail_con, search, max_results):
    inbox = gmail_con.users().messages().list(userId='me', q=search, maxResults=max_results).execute()

    if 0 < inbox["resultSizeEstimate"]:
        mails = [gmail_con.users().messages().get(userId="me", id=msg['id'], format="full").execute() for msg in
                 inbox["messages"]]

        ids = [mail['id'] for mail in mails]

        return [str(mail['payload']['headers'][6]['value']).replace("<", "").replace(">", "")
                for mail in mails], ids
        # return str(mails[0]['payload']['headers'][6]['value']).replace("<", "").replace(">", "")

    else:
        return [], []


def mark_mails_unread(gmail_con, ids):
    if 0 < len(ids):
        gmail_con.users().messages().batchModify(userId='me', body={'removeLabelIds': ['UNREAD'], 'addLabelIds': [],
                                                                    'ids': ids}).execute()


def send_message(gmail_con, sender, to, subject, message_text):
    message = MIMEText(message_text)
    message['to'] = to
    message['from'] = sender
    message['subject'] = subject
    message = {'raw': base64.urlsafe_b64encode(message.as_string().encode()).decode()}

    gmail_con.users().messages().send(userId='me', body=message).execute()


# Converts the timestamp in mail for dispenseEvent to unix timestamp
def convert_formatted_timestamp(time):
    # Get all numbers from the snippet
    array = list(map(int, re.findall(r'[0-9]+', time)))

    # Convert to unix timestamp in correct order. Might be a better solution.
    # (mail is in DD/MM/YY, function is in (YY/MM/DD, therefore the weird indexes)
    return int(datetime.datetime(array[2], array[1], array[0], array[3], array[4], array[5]).timestamp())


# Return the name of the first drink
def get_drink(event):
    return re.findall("(?<=\")[a-zA-Z é]*(?=\" \")", event)[0]


""" def wait_and_check_volume(drink, gmail_con):
    # Wait 2 hours
    time.sleep(7200)
"""


def check_clean_events():
    pass


def check_dispensed(gmail_con, db_conn):
    mails, ids = get_mails_body(gmail_con, 'label:jvm-dispenseddrinkevent is:unread', 20)

    if 0 < len(mails):
        for mail in mails:
            lines = mail.split("\n")

            # Add the DispensedDrinkEvent to db
            insert_event(db_conn, convert_formatted_timestamp(lines[1]), "DispensedDrinkEvent",
                         get_drink(lines[1]))

            if get_last_event_by_type(db_conn, "Coffee_level"):
                new_coffee_level = str(
                    int(get_last_event_by_type(db_conn, "Coffee_level")[0][2]) - coffee_beans_usage[
                        get_drink(lines[1])])
            else:
                new_coffee_level = "0"

            # Insert new amount of coffee beans left
            insert_event(db_conn, convert_formatted_timestamp(lines[1]) + 1, "Coffee_level", new_coffee_level)

            # print(get_last_event_by_type(db_conn, "Coffee_level"))

        # Return the ids from mails read
        return ids
    else:
        # Return empty list if no mails was read
        return []


def check_evadts():
    pass


def check_failures():
    pass


def check_ingredient_level(gmail_con):
    mails, ids = get_mails_body(gmail_con, 'label:jvm-ingredientlevel  is:unread', 5)

    # Find all lines in the mails which are "under threshold" and from today
    # Send all such lines (no duplicates) as an email to the maintainers of JVM
    if 0 < len(mails):
        drinks = []
        low_volumes = []
        for mail in mails:
            lines = mail.split('\n')
            for line in lines:
                if "is under threshold" not in line:
                    continue
                elif datetime.datetime.now().isoweekday() is not datetime.datetime.fromtimestamp(
                        convert_formatted_timestamp(line)).isoweekday():
                    continue
                elif re.findall("(?<=')[a-zA-Z ]+(?=')", line) in drinks:
                    continue
                else:
                    drinks.append(re.findall("(?<=')[a-zA-Z ]+(?=')", line))
                    low_volumes.append(line)

        # Send a mail with low volumes
        # if 0 < len(low_volumes):
        #   print("Ingredient level under threshold, sending mail")
        #   send_message(gmail_con, 'fklubjvmloss@gmail.com', 'mmsa17@student.aau.dk, fvejlb17@student.aau.dk',
        #               'Low volume', str(low_volumes).strip('[]'))

        # todo
        # _thread.start_new_thread(wait_and_check_volume, (drinks, gmail_con))

        return ids
    else:
        return []


def check_menu():
    pass


def check_safety():
    pass


def check_for_mails(gmail_con, db_conn):
    mails_read = []
    """
    print("Checking for new clean events")
    ids = check_clean_events()
    if 0 < len(ids):
        mails_read.extend(ids)
    print("Done checking for new clean events")
    """
    # print("Checking for new dispensed")
    # ids = check_dispensed(gmail_con, db_conn)
    # if 0 < len(ids):
    #    mails_read.extend(ids)
    # print("Done checking for new dispensed")
    """
    print("Checking for new EVADTS")
    ids = check_evadts()
    if 0 < len(ids):
        mails_read.extend(ids)
    print("Done checking for new EVADTS")

    print("Checking for new failures")
    ids = check_failures()
    if 0 < len(ids):
        mails_read.extend(ids)
    print("Done checking for new failures")
    """
    # print("Checking for new ingredient level")
    # ids = check_ingredient_level(gmail_con)
    # if 0 < len(ids):
    #    mails_read.extend(ids)
    # print("Done checking for ingredient level")
    """
    print("Checking for new menu events")
    ids = check_menu()
    if 0 < len(ids):
        mails_read.extend(ids)
    print("Done checking for new menu events")

    print("Checking for new safety mails")
    ids = check_safety()
    if 0 < len(ids):
        mails_read.extend(ids)
    print("Done checking for new safety mails")    
    """

    # Mark all read mails as unread
    mark_mails_unread(gmail_con, mails_read)

    return len(mails_read)


def check_queries(gmail_con, db_conn):
    senders, ids = get_mails_sender(gmail_con, 'label:queries   is:unread', 5)

    if 0 < len(senders):

        message = "Status on ingredients: \n" \
                  "Coffee: %sg \n" \
                  "Milk: %sg \n" \
                  "Sugar: %sg \n" \
                  "Cacao: %sg \n" % (
                      get_last_event_by_type(db_conn, "Coffee_level")[0][2],
                      get_last_event_by_type(db_conn, "Milk_level")[0][2],
                      get_last_event_by_type(db_conn, "Sugar_level")[0][2],
                      get_last_event_by_type(db_conn, "Cacao_level")[0][2])

        for sender in senders:
            send_message(gmail_con, 'fklubjvmloss@gmail.com', sender, 'Ingredient-status', message)

        mark_mails_unread(gmail_con, ids)

    return len(ids)


def main():
    gmail_con = setup_gmail_connection()
    """
    # Check whether to resume using db or create a new one
    if os.path.exists(DB_FILE_NAME):
        db_conn = sqlite3.connect('jvm-loss.db')
        # Get last event for status message
        last_event = get_last_event(db_conn)
        # Check that last event is not empty
        if len(last_event) > 0:
            print(f"UTC timestamp of last event in db: "
                  f"{datetime.datetime.utcfromtimestamp(last_event[0][0]).strftime('%Y-%m-%d %H:%M:%S')}. "
                  f"Total number of events: {len(get_events(db_conn))}")
    else:
        print("Database does not exist on disk, creating a new one")"""
    db_conn = sqlite3.connect('jvm-loss.db')
    create_db(db_conn, True, True)

    while True:
        current_hour = datetime.datetime.now().hour
        current_day = datetime.datetime.now().isoweekday()

        print(f"Hour: {current_hour}, day: {calendar.day_name[current_day - 1]}")

        # During working hours, check every 5 minutes, else wait an hour and check again
        if (7 <= current_hour <= 17) and (1 <= current_day <= 5):

            print("Checking for new mails from JVM")
            mails_read = check_for_mails(gmail_con, db_conn)
            print(f"Done checking for new mails from JVM, mails read: {mails_read}")
            pprint.pprint(get_events(db_conn))

            print("Checking for new queries")
            mails_read = check_queries(gmail_con, db_conn)
            print(f"Done checking for new queries, queries processed: {mails_read}")

            print("Sleeping for 5 minutes\n")
            time.sleep(300)
        else:
            print("Not within working hours, waiting for an hour\n")
            time.sleep(3600)


if __name__ == '__main__':
    main()
