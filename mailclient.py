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
import argparse

from dictionaries import coffee_beans_usage, sugar_usage, milk_powder_usage, chocolate_usage, MAX_COFFEE, MAX_MILK, \
    MAX_SUGAR, MAX_CHOCOLATE
from sqlite import create_db, insert_event, get_last_event, get_events, get_last_event_ingredient, \
    insert_event_ingredient
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://mail.google.com/']
DB_FILE_NAME = "jvm-loss.db"

# todo multithread to see if under threshold has been fixed
# TODO make universal get mails function that returns a dict of all useful information, instead of multiple functions

MAINTAINER_MAILS = 'mmsa17@student.aau.dk, fvejlb17@student.aau.dk'
BACKUP_MAINTAINER_MAILS = ''

parser = argparse.ArgumentParser(description="jvm-loss, track and monitor usage of networked Wittenburg 9100")
parser.add_argument('mode', type=str, default="prod", nargs='?', choices={"prod", "test"}, help='set mode')
# Parse some args
args = parser.parse_args()

# Set internal mode
MODE = args.mode

if MODE == "test":
    JVM_MAIL = 'fklubjvmloss@gmail.com'
elif MODE == "prod":
    JVM_MAIL = 'fklubjvmlosstest@gmail.com'
else:
    exit(1)  # Exit early, as unknown mode

print(f"Running JVM-loss in mode: {MODE}")


# Sets up connection to gmail
def setup_gmail_connection():
    if MODE == 'test':
        token_pickle = 'token_test.pickle'
        credentials = 'credentials_test.json'
    elif MODE == 'prod':
        token_pickle = 'token.pickle'
        credentials = 'credentials.json'
    else:
        exit(1)

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


'''Returns body of mails (only the text part) and the id of mails'''


# Fixme very ugly, there are better solutions we can use, I plan to use
#  https://github.com/abhishekchhibber/Gmail-Api-through-Python/blob/master/gmail_read.py
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


'''Connects to gmail, and uses a search term, such as is:unread or label:jvm-dispenseddrinkevent, finds a max number of results
This function returns the email of the sender, as well as the id of the mails. Used to send back replies to queries'''


def get_mails_sender_email(gmail_con, search, max_results):
    inbox = gmail_con.users().messages().list(userId='me', q=search, maxResults=max_results).execute()

    if 0 < inbox["resultSizeEstimate"]:
        mails = [gmail_con.users().messages().get(userId="me", id=msg['id'], format="full").execute() for msg in
                 inbox["messages"]]

        ids = [mail['id'] for mail in mails]

        return [str(mail['payload']['headers'][6]['value']).replace("<", "").replace(">", "")
                for mail in mails], ids

    else:
        return [], []


'''Connects to gmail, and uses a search term, such as is:unread or label:jvm-dispenseddrinkevent and keeps looping 
until no more mails is found. The loop is necessary, as a max of 100 max can be returned using the API, 
and there might be more. This could potentially take a long time, if all mails are marked unread (many minutes, 
up-to an hour depending on number of mails) Marks the mails returned as read.
Returns just the mails'''


def get_all_mails_by_search(gmail_con, search):
    all_mails = []

    while True:
        mails, ids = get_mails_body(gmail_con, search, 100)
        if 0 < len(mails):
            all_mails.extend(mail for mail in mails)
            mark_mails_read(gmail_con, ids)
        else:
            return all_mails


def setup_database():
    db_conn = sqlite3.connect('jvm-loss.db')
    create_db(db_conn, True, True)
    insert_event_ingredient(db_conn, 0, MAX_COFFEE, MAX_MILK, MAX_SUGAR, MAX_CHOCOLATE)

    return db_conn


'''Marks all mails in gmail as read, given their IDs'''


def mark_mails_read(gmail_con, ids):
    if 0 < len(ids):
        gmail_con.users().messages().batchModify(userId='me', body={'removeLabelIds': ['UNREAD'], 'addLabelIds': [],
                                                                    'ids': ids}).execute()


'''Deletes all mails from gmail, given their IDs'''


def batch_delete_mails(gmail_con, ids):
    if 0 < len(ids):
        gmail_con.users().messages().batchDelete(userId='me', body={'ids': ids}).execute()


'''Constructs a mail given the parameters, and sends it'''


def send_message(gmail_con, sender, to, subject, message_text):
    message = MIMEText(message_text)
    message['to'] = to
    message['from'] = sender
    message['subject'] = subject
    message = {'raw': base64.urlsafe_b64encode(message.as_string().encode()).decode()}

    gmail_con.users().messages().send(userId='me', body=message).execute()


'''Converts the timestamp in mail for dispenseEvent to unix timestamp'''


def convert_formatted_timestamp(time):
    # Get all numbers from the snippet
    array = list(map(int, re.findall(r'[0-9]+', time)))

    # Convert to unix timestamp in correct order. Might be a better solution.
    # (mail is in DD/MM/YY, function is in (YY/MM/DD, therefore the weird indexes)
    return int(datetime.datetime(array[2], array[1], array[0], array[3], array[4], array[5], array[6]).timestamp())


'''Specific convert_formatted_timestamp function for mails with "failure" label. These mails for some reason idiotic 
reason has a different format than all other mails. Is MM/DD/YY HH:MM, and not 2020, but just 20 for year, 
and not seconds or ms as ALL THE OTHER MAILS HAVE, totally BS'''


def convert_formatted_timestamp_failure(time):
    # Get all numbers from the snippet
    array = list(map(int, re.findall(r'[0-9]+', time)))
    # Convert to unix timestamp in correct order. Might be a better solution.
    # (mail is in DD/MM/YY, function is in (YY/MM/DD, therefore the weird indexes)
    return int(datetime.datetime(array[2] + 2000, array[1], array[0], array[3], array[4]).timestamp())


'''Return the name of the first drink found in the given line from a mail'''


def get_drink(line):
    return re.findall("(?<=\")[a-zA-Z é]*(?=\" \")", line)[0]


""" def wait_and_check_volume(drink, gmail_con):
    # Wait 2 hours
    time.sleep(7200)
"""

'''Updates the ingredient level in DB by some amount. New ingredient level is ceiled by the max capacity. 
Other ingredients are not updated'''


def update_ingredient_level(db_conn, timestamp, ingredient, amount: float):
    # Gets last ingredient status from DB, contains information about all 4 ingredients
    status = get_last_event_ingredient(db_conn)[0]

    if ingredient == "coffee":
        insert_event_ingredient(db_conn, timestamp, min(status[1] + amount, MAX_COFFEE), status[2], status[3],
                                status[4])
    elif ingredient == "milk":
        insert_event_ingredient(db_conn, timestamp, status[2], min(status[2] + amount, MAX_MILK), status[3], status[4])
    elif ingredient == "sugar":
        insert_event_ingredient(db_conn, timestamp, status[1], status[2], min(status[3] + amount, MAX_SUGAR), status[4])
    elif ingredient == "chocolate":
        insert_event_ingredient(db_conn, timestamp, status[1], status[2], status[3],
                                min(status[4] + amount, MAX_CHOCOLATE))


'''Updates ingredient status in DB, by a single dispensed drink event'''


def update_ingredient_level_by_dispense_event(db_conn, timestamp, drink):
    # Gets the most recent ingredient status from DB
    status = get_last_event_ingredient(db_conn)[0]

    # Inserts new ingredient status to DB, using existing status, and extracting amounts according to the drink
    # dispensed, see dictionaries for usages.
    insert_event_ingredient(db_conn, timestamp, status[1] - coffee_beans_usage[drink],
                            status[2] - milk_powder_usage[drink], status[3] - sugar_usage[drink],
                            status[4] - chocolate_usage[drink])


'''Called by the check_for_mails function called every 5 mins. Will update ingredient levels, if any mails that 
contains information about ingredient level has been received '''


def update_ingredient_levels(db_conn, mails):
    # Get all first lines from the mails, as the first lines is the most recent event, iterating through all mails,
    # therefore gets all events with no duplicates
    first_lines = [mail.split("\n")[1] for mail in mails]

    # Sort these lines based on the timestamp in the mails, oldest mails first, as it makes sense to go
    # chronologically through the events and act upon these
    first_lines.sort(key=lambda x: convert_formatted_timestamp(x))

    # Go through each line, and act depending on type of mail. Currently these are with keywords in the line
    # "DispensedDrinkEvent" - a drink has been dispensed, and a couple of grams of ingredients is subtracted from
    # latest ingredient status in DB,

    # "Menu parametre" - can technically be all changes in menu, such as changing settings and drinks. Here we only
    # look for coffee beans added to "beholder", if this change is less than max, which we handle in ingredientlevel
    # mails, add amount to ingredient status in DB.

    # FIXME should probably also add logic for other ingredients here,
    #  but it is only very rarely we do not fill these to capacity, which again, is handled in IngredientLevel mails

    # "IngredientLevel - an ingredient is at max capacity, and ingredient status is set to this in DB"
    for first_line in first_lines:
        timestamp = convert_formatted_timestamp(first_line)
        if "DispensedDrinkEvent" in first_line:
            drink = get_drink(first_line)

            update_ingredient_level_by_dispense_event(db_conn, timestamp, drink)
        elif "Menu parametre" in first_line and re.findall("(?<=beholder).[0-9]*(?=grCoffee Beans)", first_line):
            amount_filled = int(re.findall("(?<=beholder).[0-9]*(?=grCoffee Beans)", first_line)[0])
            if 0 < amount_filled < 2400:
                update_ingredient_level(db_conn, timestamp, "coffee", float(amount_filled))
        elif "IngredientLevel" in first_line:
            if "Coffee Beans\' is filled." in first_line:
                update_ingredient_level(db_conn, timestamp, "coffee", MAX_COFFEE)
            if "Chocolate\' is filled." in first_line:
                update_ingredient_level(db_conn, timestamp, "chocolate", MAX_CHOCOLATE)
            if "Sugar\' is filled." in first_line:
                update_ingredient_level(db_conn, timestamp, "sugar", MAX_SUGAR)
            if "Milk product\' is filled." in first_line:
                update_ingredient_level(db_conn, timestamp, "milk", MAX_MILK)


'''Gets all unread "clean" mails, and adds most recent event to DB (the first line in the mail). Example is the 
weekly cleaning '''


def check_clean_events(gmail_con, db_conn):
    mails = get_all_mails_by_search(gmail_con, search='label:jvm-clean is:unread')

    for mail in mails:
        # Extracts and inputs just the first line into the DB, as the next lines in the mails are previous events
        first_line = mail.split("\n")[1]
        insert_event(db_conn, convert_formatted_timestamp(first_line), "Clean", first_line)
    return len(mails)


'''Gets all unread "dispenseddrinkevent" mails, and adds most recent event to DB (the first line in the mail). This 
is NOT updating ingredient levels, just adding information that a certain drink has been dispensed '''


def check_dispensed(gmail_con, db_conn):
    mails = get_all_mails_by_search(gmail_con, search='label:jvm-dispenseddrinkevent is:unread')

    for mail in mails:
        first_line = mail.split("\n")[1]

        # Add the DispensedDrinkEvent to db
        insert_event(db_conn, convert_formatted_timestamp(first_line), "DispensedDrinkEvent", get_drink(first_line))
    # returns the actual mails, as these will be used later to update ingredient level
    # TODO could do optimisation, and just return the first lines of each mail, as these are later extracted again in the
    #  update_ingredient_levels function
    return mails


# TODO Add logic to extract info from evadts mail to DB
def check_evadts(gmail_con, db_conn):
    return 0


'''Gets all unread "failure" mails, and adds most recent event to DB (the first line in the mail). Example is missing 
"drypbakke" '''


def check_failures(gmail_con, db_conn):
    mails = get_all_mails_by_search(gmail_con, search='label:jvm-failures is:unread')

    # FIXME Offset needed because seconds are not present in failure mail,
    #  and a failure can be resolved the same minute that it appears, therefore the timestamp which is used as primary key
    #  will not be unique. Should be fixed in the database design.
    offset = 0
    for mail in mails:
        # Extracts and inputs just the first line into the DB, as the next lines in the mails are previous events
        first_line = mail.split("\n")[1]
        insert_event(db_conn, convert_formatted_timestamp_failure(first_line) + offset, "Failure", first_line)
        offset += 1
    return len(mails)


'''Gets all unread "IngredientLevel" mails. Example is ingredient level is under threshold, or ingredient is filled. 
If an ingredient is under threshold, sends a mail to maintainers, currently adds nothing to DB, probably should. 
Should extend to also check if the mail to maintainer is acted upon (e.g the maintainer filled the ingredient after 
it was under threshold) '''


def check_ingredient_level(gmail_con):
    # todo add mail to DB
    mails = get_all_mails_by_search(gmail_con, search='label:jvm-ingredientlevel  is:unread')

    ingredients_under_threshold = []

    for mail in mails:
        # First line is most recent event
        line = mail.split('\n')[1]

        # If the line contains information about some ingredient under threshold, is from today, and is not an
        # ingredient that has already been found as under threshold, append to array
        if "is under threshold" in line and \
                time.time() - convert_formatted_timestamp(line) < 86400 and \
                re.findall("(?<= ')[ a-zA-Z]+(?=' )", line)[0] not in ingredients_under_threshold:
            ingredients_under_threshold.append(re.findall("(?<= ')[ a-zA-Z]+(?=' )", line)[0])

    # If at least one ingredient found to be under threshold, send mail to maintainers
    if 0 < len(ingredients_under_threshold):
        print("Ingredient level under threshold, sending mail")

        # Add all ingredients found to be under threshold to mail
        message = "Ingredients are under threshold: \n" \
                  "%s " % (str(ingredients_under_threshold).strip('[]'))

        send_message(gmail_con, JVM_MAIL, MAINTAINER_MAILS,
                     'Low volume', message)

    # todo check if maintainer fixed ingredient under threshold
    # _thread.start_new_thread(wait_and_check_volume, (ingredients_under_threshold, gmail_con))

    return mails


'''Gets all unread "menu" mails, and adds most recent event to DB (the first line in the mail). Example is settings 
changed, or added coffee beans '''


def check_menu(gmail_con, db_conn):
    mails = get_all_mails_by_search(gmail_con, search='label:jvm-menu is:unread')

    # Extracts and inputs just the first line into the DB, as the next lines in the mails are previous events
    for mail in mails:
        first_line = mail.split("\n")[1]
        insert_event(db_conn, convert_formatted_timestamp(first_line), "Menu", first_line)
    # returns the actual mails, as these will be used later to update ingredient level
    # TODO could do optimisation, and just return the first lines of each mail, as these are later extracted again in the
    #  update_ingredient_levels function
    return mails


# TODO add logic for extracting information for safety mails
def check_safety():
    return 0


'''Has one function for each type of mail that can be sent from the coffee machine. Labels are given in gmail 
to different types of mails, these functions check for these labels, corresponding to the function name'''


def check_for_mails(gmail_con, db_conn):
    # Counts how many mails have been read
    mails_read = 0

    # Collects all mails that changes the ingredient level. Will be sent to update_ingredient_level function to
    # update DB
    mails_changing_ingredient_level = []

    print("Checking for new clean events")
    mails_read += check_clean_events(gmail_con, db_conn)
    print("Done checking for new clean events")

    print("Checking for new dispensed")
    mails_changing_ingredient_level += check_dispensed(gmail_con, db_conn)
    print("Done checking for new dispensed")

    print("Checking for new EVADTS")
    mails_read += check_evadts(gmail_con, db_conn)
    print("Done checking for new EVADTS")

    # FIXME can result in error, due to unique timestamp
    # print("Checking for new failures")
    # mails_read += check_failures(gmail_con, db_conn)
    # print("Done checking for new failures")

    print("Checking for new ingredient level")
    mails_changing_ingredient_level += (check_ingredient_level(gmail_con))
    print("Done checking for ingredient level")

    print("Checking for new menu events")
    mails_changing_ingredient_level += (check_menu(gmail_con, db_conn))
    print("Done checking for new menu events")

    print("Checking for new safety mails")
    mails_read += check_safety()
    print("Done checking for new safety mails")

    # Update ingredient level
    print("Updating ingredient levels")
    if 0 < len(mails_changing_ingredient_level):
        update_ingredient_levels(db_conn, mails_changing_ingredient_level)
    print("Done updating ingredient levels")

    # Add number of mails that has changed ingredient level to total number of mails read
    mails_read += len(mails_changing_ingredient_level)

    return mails_read


'''If any mails has been received with label "queries" (currently as of 11-03-2020 only ingredient level queries 
pr mail is supported) send back a mail to each email that sent the query, containing the current (as of reading the mail)
 last ingredient level contained in the DB'''


def check_queries(gmail_con, db_conn):
    # FIXME currently query mail is deleted, a prettier solution would be to check if the mail was received today, or
    #  perhaps just mark it read. This would however spam everyone who has ever queried the DB, if all mails
    #  are marked unread (which could happen in the case that we want to hard reset DB and read every mail
    received_from_email, mail_ids = get_mails_sender_email(gmail_con, 'label:queries   is:unread', 100)

    if 0 < len(received_from_email):

        # Gets last ingredient level
        ingredient_status = get_last_event_ingredient(db_conn)[0]

        # Construct a pretty-ish mail to be sent to the email that queried
        # index 1 is current coffee level, 2 is milk etc. Return the level in grams, and in capacity %
        message = "Status on ingredients: \n" \
                  "Coffee: %.1fg (%.1f%%)\n" \
                  "Milk: %.1fg (%.1f%%)\n" \
                  "Sugar: %.1fg (%.1f%%)\n" \
                  "Chocolate: %.1fg (%.1f%%)\n" % (
                      ingredient_status[1],
                      (ingredient_status[1] / MAX_COFFEE) * 100.0,
                      ingredient_status[2],
                      (ingredient_status[2] / MAX_MILK) * 100.0,
                      ingredient_status[3],
                      (ingredient_status[3] / MAX_SUGAR) * 100.0,
                      ingredient_status[4],
                      (ingredient_status[4] / MAX_CHOCOLATE) * 100.0)

        # Send this email to all emails that queried
        for email in received_from_email:
            send_message(gmail_con, JVM_MAIL, email, 'Ingredient-status', message)

        # Delete the query mail
        batch_delete_mails(gmail_con, mail_ids)

    return len(mail_ids)


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
        db_conn = setup_database()

    while True:
        current_hour = datetime.datetime.now().hour
        current_day = datetime.datetime.now().isoweekday()

        print(f"Hour: {current_hour}, day: {calendar.day_name[current_day - 1]}")

        # During working hours, check every 5 minutes, else wait an hour and check again. Omit check if testing
        if MODE == "test" or ((7 <= current_hour <= 17) and (1 <= current_day <= 5)):

            # Checks all types of mails that can be sent from the coffee machine
            print("Checking for new mails from JVM")
            mails_read = check_for_mails(gmail_con, db_conn)
            print(f"Done checking for new mails from JVM, mails read: {mails_read}")

            # Checks queries from users to get ingredient levels. Currently only type of query supported.
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
