import json
import datetime
import os
import pytz
import websockets
import asyncio
from collections import deque
from colorama import Fore, Style
from settings.config import ApiConfig

dhaka_tz = pytz.timezone('Asia/Dhaka')


class Logger:
    def __init__(self) -> None:
        # Create logs folder if it doesn't exist
        if not os.path.exists("logs"):
            os.makedirs("logs")

        # Create a new log file with UTF-8 encoding
        self.logging_file = f"logs/{datetime.datetime.now(dhaka_tz).strftime('%Y-%m-%d %H-%M-%S')}.log"
        self.file = open(self.logging_file, "w", encoding="utf-8")

    def log(self, message, level="INFO"):
        """Asynchronously log messages to the file and send them to WebSocket."""
        timestamp = datetime.datetime.now(dhaka_tz).strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] [{level}] {message}\n"
        if level == "INFO":
            log_color = Fore.LIGHTCYAN_EX
        elif level == "WARNING":
            log_color = Fore.YELLOW
        elif level == "ERROR":
            log_color = Fore.RED
        elif level == "CRITICAL":
            log_color = Fore.MAGENTA
        elif level == "DANGER":
            log_color = Fore.RED
        elif level == "SUCCESS":
            log_color = Fore.GREEN
        elif level == "DEBUG":
            log_color = Fore.GREEN
        else:
            log_color = Fore.WHITE

        print(f"{log_color}{log_entry}{Style.RESET_ALL}", end="")

        self.file.write(log_entry)
        self.file.flush()  # Ensure the log entry is written immediately

    def info(self, message):
        try:
            self.log(message, "INFO")
        except :
            pass

    def warning(self, message):
        try:
            self.log(message, "WARNING")
        except:
            pass

    def error(self, message):
        try:
            self.log(message, "ERROR")
        except:
            pass

    def close(self):
        self.file.write(f"Log file closed at {datetime.datetime.now(dhaka_tz)}\n")
        self.file.close()

    def critical(self, message):
        try:
            self.log(message, "CRITICAL")
        except:
            pass

    def danger(self, message):
        try:
            self.log(message, "DANGER")
        except:
            pass

    def debug(self, message):
        if ApiConfig.DEBUG:
            try:
                self.log(message, "DEBUG")
            except:
                pass

    def success(self, message):
        try:
            self.log(message, "SUCCESS")
        except:
            pass

logger = Logger()

