import requests
from bs4 import BeautifulSoup
import time
from telegram import Bot
import asyncio

URL = "https://www.billetterie-parismusees.paris.fr/selection/timeslotpass?productId=101972921593&gtmStepTracking=true"
STATS_NOTIFY_INTERVAL = 60 * 5 # seconds, every half hour
CHECK_INTERVAL = 15 # seconds

class StatisticsHandler:
    def __init__(self):
        self.total_error_count = {}
        self.previous_errors = []
        self.current_errors = []

        self.tries = 0
        self.timeslots_checked = 0
        self.pages_loaded = 0
        self.no_timeslots_found = 0
        
    def add_error(self, error):
        # Add the count of total errors
        if not error in self.total_error_count:
            self.total_error_count[error] = 1
        else:
            self.total_error_count[error] += 1

        # Add to current errors
        if not error in self.current_errors:
            self.current_errors.append(error)

    # Returns list of new errors
    def update_errors(self):
        new_errors = []
        for new_error in self.current_errors:
            if not new_error in self.previous_errors:
                new_errors.append(new_error)
        self.previous_errors = self.current_errors
        self.current_errors = []
        return new_errors
    
    def clear(self):
        self.total_error_count = {}
        self.previous_errors = []
        self.current_errors = []
        self.tries = 0
        self.timeslots_checked = 0
        self.pages_loaded = 0
        self.no_timeslots_found = 0

class Scraper:
    # Returns web page object, or None if failed
    def get_page(stats: StatisticsHandler):
        try:
            page = requests.get(URL)
            stats.pages_loaded += 1
            return page
        except requests.exceptions.ConnectionError:
            stats.add_error("No internet connection")
        except Exception as e:
            print("======= Oh no, time out maybe? " + str(e) + " of type: '" + str(type(e)) + "'")

    def get_timeslots_html(soup, stats: StatisticsHandler):
        timeslots_container = soup.find(id="timeSlotsContainer")
        
        try:
            timeslots_container_list = timeslots_container.find("ul")
        except AttributeError as e:
            stats.no_timeslots_found += 1
            return []

        if not timeslots_container_list:
            stats.no_timeslots_found += 1
            return []

        timeslots_list_items = timeslots_container_list.find_all("li")
        return timeslots_list_items

    def get_data_for_timeslot(timeslot):
        time = timeslot.find("div", class_="timeslot_time").text.strip()
        available_span = timeslot.find("span", class_="simple_availability")
        available = not "sold_out" in available_span.attrs["class"]
        return time, available

    def get_timeslots(stats: StatisticsHandler):
        page = Scraper.get_page(stats)
        if not page:
            stats.add_error("No page")
            return []
        
        soup = BeautifulSoup(page.content, "html.parser")
        html_timeslots = Scraper.get_timeslots_html(soup, stats)
        
        timeslots = {}

        for timeslot_html in html_timeslots:
            ts_time, ts_available = Scraper.get_data_for_timeslot(timeslot_html)

            if ts_time in timeslots:
                print("=========== Timeslot: " + ts_time + " already exists!")
            
            stats.timeslots_checked += 1

            timeslots[ts_time] = ts_available

        return timeslots

    def get_available_timeslots(stats: StatisticsHandler):
        timeslots = Scraper.get_timeslots(stats)
        available = [x for x in timeslots if timeslots[x]]
        return available

class TelegramHandler:
    def get_chat_ids():
        chats = []
        with open("database.txt", 'r') as file:
            for line in file:
                if not line.startswith('#'):
                    chats.append(int(line.strip()))
        return chats

    def get_token():
        with open("telegram_token", 'r') as file:
            token = file.readline().strip()
            return token

    async def broadcast_message_async(message):
        chats = TelegramHandler.get_chat_ids()
        token = TelegramHandler.get_token()

        bot = Bot(token)
        
        try:
            for id in chats:
                async with bot:
                    await bot.send_message(text=message, chat_id=id)
        except TimeoutError as e:
            print("======== Error here happened: " + str(e))

    def broadcast(message):
        asyncio.run(TelegramHandler.broadcast_message_async(message))

def main():
    stats = StatisticsHandler()

    previous_available_times = []

    TelegramHandler.broadcast("Started watching...")

    last_stats_notify = time.time()

    while True:
        stats.tries += 1
        available_timeslots = Scraper.get_available_timeslots(stats)

        # Handle any new errors:
        new_errors = stats.update_errors()
        if new_errors:
            TelegramHandler.broadcast("Received errors:" + str(new_errors))

        # Handle timeslot availabilities
        if available_timeslots:
            times = [x for x, _ in available_timeslots]
            if times != previous_available_times:
                TelegramHandler.broadcast("New timeslots available:" + str(times))
                previous_available_times = times

        time_since_last_stats_notification = time.time() - last_stats_notify
        if time_since_last_stats_notification > STATS_NOTIFY_INTERVAL:
            msg = "Since last update:\n"
            msg += "- Check tries: " + str(stats.tries) + "\n"
            msg += "- Pages fetched: " + str(stats.pages_loaded) + "\n"
            msg += "- Timeslots checked: " + str(stats.timeslots_checked) + "\n"
            msg += "- Pages without timeslots: " + str(stats.no_timeslots_found)
            TelegramHandler.broadcast(msg)

            last_stats_notify = time.time()
            stats.clear()

        stats.update_errors()

        time.sleep(5)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Exited due to keyboard")
    except Exception as e:
        print("Some other exception happened: " + str(e) + ", of type: '" + str(type(e)) + "'")
        TelegramHandler.broadcast("Unhandled exception ocurred: " + str(e) + ", of type: '" + str(type(e)) + "'")
    
    TelegramHandler.broadcast("Stopped watching")