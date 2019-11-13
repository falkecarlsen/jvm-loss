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


def add_new_events(gmail_con, db_conn, search):
    # Get all mails that match the search
    inbox = gmail_con.users().messages().list(userId='me', q=search, maxResults=20).execute()

    # Gets information from mails in "minimal" format, as only a snippet of the mail is needed
    # (recent event is in start of mail)
    if 0 < inbox["resultSizeEstimate"]:
        mails = [gmail_con.users().messages().get(userId="me", id=msg['id'], format="minimal").execute() for msg in
                 inbox["messages"]]

        # Array to hold ids of mails to remove "unread"- label
        idsToModify = []

        for mail in mails:
            # Add the DispensedDrinkEvent to db
            insert_event(db_conn, convert_formatted_timestamp(mail["snippet"]), "DispensedDrinkEvent",
                         get_drink(mail["snippet"]))

            # Append id to array
            idsToModify.append(mail['id'])

        # Remove "unread"- label on all mails in array
        gmail_con.users().messages().batchModify(userId='me',
                                                 body={'removeLabelIds': ['UNREAD'], 'addLabelIds': [],
                                                       'ids': idsToModify}).execute()
    else:
        print(f"No new '{search}' since last check")


def checkIngredientLevel(gmail_con):
    # TODO code looks a lot like 'addNewEvents' function, could perhaps abstract some logic
    inbox = gmail_con.users().messages().list(userId='me', q='label:jvm-ingredientlevel  is:unread',
                                              maxResults=1).execute()

    if 0 < inbox["resultSizeEstimate"]:
        body = gmail_con.users().messages().get(userId='me', id=inbox["messages"][0]['id'], format='raw').execute()

        text = str(base64.urlsafe_b64decode(body['raw'].encode('utf-8'))).split("\\n")

        lowVolumes = []
        drinks = []
        for temp in text:
            if "is under threshold" in temp:
                drink = re.findall("(?<=')[a-zA-Z ]+(?=\\\\)", temp)[0]
                if len(lowVolumes) == 0:
                    lowVolumes.append(temp.replace(' \\r', '').replace('\\', ''))
                    drinks.append(drink)
                if drink in drinks:
                    continue
                else:
                    lowVolumes.append(temp.replace(' \\r', '').replace('\\', ''))
                    drinks.append(drink)

    # TODO could perhaps just forward the mail, instead of creating a new one
    if 0 < len(lowVolumes):
        print("Ingredient level under threshold, sending mail")
        send_message(gmail_con, 'fklubjvmloss@gmail.com', 'mmsa17@student.aau.dk',
                     'Low volume',
                     str(lowVolumes).strip('[]').replace(",", "\n"))
        gmail_con.users().messages().modify(userId='me', id=inbox["messages"][0]['id'],
                                            body={'removeLabelIds': ['UNREAD'], 'addLabelIds': []}).execute()

    else:
        print("Ingredient level above threshold")


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

    search = 'label:jvm-dispenseddrinkevent is:unread'

    while True:
        current_hour = datetime.datetime.now().hour
        current_day = datetime.datetime.now().isoweekday()

        print(f"Hour: {current_hour}, day: {calendar.day_name[current_day - 1]}")

        # During working hours, check every 5 minutes, else wait an hour and check again
        if (7 <= current_hour <= 24) and (1 <= current_day <= 5):
            print(f"Checking for new '{search}'")
            add_new_events(gmail_con, db_conn, search)
<<<<<<< HEAD
            print(f"Done checking for new '{search}', sleeping for 5 minutes")
            # Check if any ingredient level is under threshold
            checkIngredientLevel(gmail_con)
=======
            print(f"Done checking for new '{search}'")

            print("Checking for low ingredients")
            checkIngredientLevel(gmail_con)
            print("Done checking for low ingredients, sleeping for 5 minutes\n")
>>>>>>> d7ca5d6f367afd02b6bdd0ec0b8fe1c05c3be4a8
            time.sleep(300)
        else:
            print("Not within working hours, waiting for an hour\n")
            time.sleep(3600)


if __name__ == '__main__':
    main()
