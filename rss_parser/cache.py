import sqlite3
from abc import ABC, abstractmethod
from typing import Optional, Dict, Tuple


class Cache(ABC):

    DB = "feeds_cache.db"

    @staticmethod
    @abstractmethod
    def init():
        pass

    @staticmethod
    def _save_to_cache(table: str, data: Tuple) -> None:
        connection = sqlite3.connect(Cache.DB)
        c = connection.cursor()
        data_placeholder = "(" + ", ".join(map(lambda x: "?", data)) + ")"
        command = f"""INSERT INTO {table} VALUES {data_placeholder}"""
        c.execute(command, data)
        connection.commit()
        connection.close()

    @staticmethod
    def _recover_from_cache(id_: str, table: str) -> Optional[Dict[str, str]]:
        connection = sqlite3.connect(Cache.DB)
        connection.row_factory = sqlite3.Row
        c = connection.cursor()

        c.execute("SELECT * FROM '%s' WHERE id=:id" % table, {"id": id_})
        element = c.fetchone()
        connection.close()

        if element:
            return dict(element)
        return element
