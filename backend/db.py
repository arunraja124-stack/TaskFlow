from contextlib import contextmanager

import mysql.connector

from config import Config


@contextmanager
def get_connection():
    connection = mysql.connector.connect(**Config.DB_CONFIG)
    try:
        yield connection
    finally:
        if connection.is_connected():
            connection.close()
