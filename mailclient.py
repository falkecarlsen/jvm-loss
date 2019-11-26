from __future__ import print_function

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
from sqlite import create_db, insert_event, get_last_event, get_events
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://mail.google.com/']
DB_FILE_NAME = "jvm-loss.db"


# Sets up connection to gmail
def setup_gmail_connection():
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    return build('gmail', 'v1', credentials=creds)


# todo return tuple with mail body and id
def get_mails(gmail_con, search, max_results):
    inbox = gmail_con.users().messages().list(userId='me', q=search, maxResults=max_results).execute()

    if 0 < inbox["resultSizeEstimate"]:
        mails = [gmail_con.users().messages().get(userId="me", id=msg['id'], format="full").execute() for msg in
                 inbox["messages"]]

        ids = [mail['id'] for mail in mails]

        return [str(base64.urlsafe_b64decode(mails['payload']['parts'][0]['parts'][0]['body']['data'])) for mail in
                mails], ids


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
    return re.findall("(?<=;)[a-zA-Z é]*(?=&)", event)[0]


""" def wait_and_check_volume(drink, gmail_con):
    # Wait 2 hours
    time.sleep(7200)

    drink = check_menu(gmail_con)

    # todo gør så databasen har et table til fylde beholder
    # todo træk menu parametre ind i db, i det uendelige løkke
    # todo finally check her om der har været fyldt på en af disse items i de seneste 2 timer
    # todo lav et table med ingrediensbeholdning (et for hvert ting), og indsæt et nyt event hver gang denne ændres
"""


def check_clean_events():
    pass


def check_dispensed(gmail_con, db_conn):
    mails, ids = get_mails(gmail_con, 'label:jvm-dispenseddrinkevent is:unread', 20)

    for mail in mails:
        mail.split('\\n')
        # Add the DispensedDrinkEvent to db
        insert_event(db_conn, convert_formatted_timestamp(mail[1]), "DispensedDrinkEvent",
                     get_drink(mail[1]))

    return ids


def check_evadts():
    pass


def check_failures():
    pass


def check_ingredient_level(gmail_con):
    mail, id = get_mails(gmail_con, 'label:jvm-ingredientlevel  is:unread', 1)

    if 0 < len(mail):
        mail.split('\\n')

        drinks = []
        low_volumes = []
        for line in mail:
            if "is under threshold" not in line:
                continue
            elif datetime.datetime.now().isoweekday() + 1 is not datetime.datetime.fromtimestamp(
                    convert_formatted_timestamp(line)).isoweekday():
                continue
            elif re.findall("(?<=')[a-zA-Z ]+(?=\\\\)", line)[0] in drinks:
                continue
            else:
                drinks.append(re.findall("(?<=')[a-zA-Z ]+(?=\\\\)", line)[0])
                low_volumes.append(line)

        # Send a mail
        """ 
        if 0 < len(low_volumes):
        #   print("Ingredient level under threshold, sending mail")
        #   send_message(gmail_con, 'fklubjvmloss@gmail.com', 'mathiasmehlsoerensen@gmail.com',
        #                'Low volume',
        #                str(low_volumes).strip('[]').replace(",", "\n"))

        # todo
        # _thread.start_new_thread(wait_and_check_volume, (drinks, gmail_con))
        """
        return id
    else:
        print("Ingredient level above threshold")


def check_menu(gmail_con):
    inbox = gmail_con.users().messages().list(userId='me', q='label:jvm-menu  is:unread', maxResults=1).execute()
    if 0 < inbox["resultSizeEstimate"]:
        email = gmail_con.users().messages().get(userId='me', id=inbox["messages"][0]['id'], format='full').execute()
        lines = str(base64.urlsafe_b64decode(email['payload']['parts'][0]['parts'][0]['body']['data'])).split('\\n')

        # todo regex for at finde fylde beholder på drink i første linje
        if "Fylde beholder" in lines[1] and convert_formatted_timestamp(lines[1]):
            return re.findall("(?<=gr)[a-zA-Z ]+(?=\")", lines[1])[0]


def check_safety():
    pass


def check_for_mails(gmail_con, db_conn):
    mark_mail_unread = []

    print("Checking for new clean events")
    mark_mail_unread.append(check_clean_events())
    print("Done checking for new clean events")

    print("Checking for new dispensed")
    mark_mail_unread.append(check_dispensed(gmail_con, db_conn))
    print("Done checking for new dispensed")

    print("Checking for new EVADTS")
    mark_mail_unread.append(check_evadts())
    print("Done checking for new EVADTS")

    print("Checking for new failures")
    mark_mail_unread.append(check_failures())
    print("Done checking for new failures")

    print("Checking for new ingredient level")
    mark_mail_unread.append(check_ingredient_level(gmail_con))
    print("Done checking for ingredient level")

    print("Checking for new menu events")
    mark_mail_unread.append(check_menu(gmail_con))
    print("Done checking for new menu events")

    print("Checking for new safety mails")
    mark_mail_unread.append(check_safety())
    print("Done checking for new safety mails")

    if 0 < len(mark_mail_unread):
        gmail_con.users().messages().batchModify(userId='me', body={'removeLabelIds': ['UNREAD'], 'addLabelIds': [],
                                                                    'ids': mark_mail_unread}).execute()


def main():
    gmail_con = setup_gmail_connection()

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
        print("Database does not exist on disk, creating a new one")
        db_conn = sqlite3.connect('jvm-loss.db')
        create_db(db_conn, True, True)

    while True:
        current_hour = datetime.datetime.now().hour
        current_day = datetime.datetime.now().isoweekday()

        print(f"Hour: {current_hour}, day: {calendar.day_name[current_day - 1]}")

        # During working hours, check every 5 minutes, else wait an hour and check again
        if (7 <= current_hour <= 24) and (1 <= current_day <= 5):

            print("Checking for new mails")
            check_for_mails(gmail_con, db_conn)
            print("Done checking for mails")

            print("Sleeping for 5 minutes\n")
            time.sleep(300)
        else:
            print("Not within working hours, waiting for an hour\n")
            time.sleep(3600)


if __name__ == '__main__':
    main()
