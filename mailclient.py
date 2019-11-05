from __future__ import print_function
import pprint
import pickle
import os.path
import sqlite3
import datetime
from pprint import pprint
import re

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# If modifying these scopes, delete the file token.pickle.
from sqlite import create_db, insert_event, get_event, get_events

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']


# TODO hvad hvis folk kommer til at købe noget, standse ved en fejl, og så tage den igen. Det tæller som 2 køb, men gælder faktisk kun for 1.

# Converts the timestamp in mail for dispenseEvent to unix timestamp
def getUnixTime(time):
    array = list(map(int, re.findall(r'[0-9]+', time)))
    return int(datetime.datetime(array[2], array[1], array[0], array[3], array[4], array[5]).timestamp())


def getDrink(event):
    return re.findall("(?<=;)[a-zA-Z ]*(?=&)", event)[0]


def main():
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

    service = build('gmail', 'v1', credentials=creds)

    #TODO mark emails as unread. Or find better solution than to list all mails, perhaps also delete already-processed mails?
    inbox = service.users().messages().list(userId='me', q='label:dispenseddrinkevent is:unread', maxResults=10).execute()
    mails = [service.users().messages().get(userId="me", id=msg['id'], format="minimal").execute() for msg in
             inbox["messages"]]

    db_conn = sqlite3.connect('jvm-loss.db')
    create_db(db_conn, True, True)

    for m in mails:
        insert_event(db_conn, getUnixTime(m["snippet"]), "DispensedDrinkEvent", getDrink(m["snippet"]))

    pprint(get_events(db_conn))


if __name__ == '__main__':
    main()
