import requests
from bs4 import BeautifulSoup
import time

URL = "https://www.billetterie-parismusees.paris.fr/selection/timeslotpass?productId=101972921593&gtmStepTracking=true"

def get_page():
    try:
        return requests.get(URL)
    except:
        print("Failed to retreive html. Are you connected?")

def get_timeslots_html(soup):
    timeslots_container = soup.find(id="timeSlotsContainer")
    timeslots_container_list = timeslots_container.find("ul")
    timeslots_list_items = timeslots_container_list.find_all("li")
    return timeslots_list_items

def get_data_for_timeslot(timeslot):
    time = timeslot.find("div", class_="timeslot_time").text.strip()
    available_span = timeslot.find("span", class_="simple_availability")
    available = not "sold_out" in available_span.attrs["class"]
    return time, available

def get_timeslots():
    page = get_page()
    if not page:
        return []
    soup = BeautifulSoup(page.content, "html.parser")
    html_timeslots = get_timeslots_html(soup)
    
    timeslots = {}

    for timeslot_html in html_timeslots:
        ts_time, ts_available = get_data_for_timeslot(timeslot_html)

        if ts_time in timeslots:
            print("Timeslot: " + ts_time + " already exists!")
        
        timeslots[ts_time] = ts_available

    return timeslots


def get_available_timeslots():
    timeslots = get_timeslots()
    available = [x for x in timeslots if timeslots[x]]
    return available


def wait_for_availability():
    while True:
        available_timeslots = get_available_timeslots()

        if available_timeslots:
            print("Available timeslots!")
        else:
            print(".")

        time.sleep(10)

try:
    wait_for_availability()
except KeyboardInterrupt:
    print("Exited due to keyboard")