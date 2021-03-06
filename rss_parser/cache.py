import sqlite3
from abc import ABC, abstractmethod
from typing import Optional, Dict, Tuple


class Cache(ABC):

    DB = "feeds_cache.db"

    @staticmethod
    @abstractmethod
    def init() -> None:
        pass

    @classmethod
    @abstractmethod
    def recover_from_cache(cls, id_: str) -> Optional[Dict[str, str]]:
        pass

    @staticmethod
    @abstractmethod
    def prune(max_entries: int) -> None:
        pass

    @classmethod
    @abstractmethod
    def flush_cache(cls) -> None:
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

    @classmethod
    def _truncate_table(cls, table: str) -> None:
        connection = sqlite3.connect(cls.DB)
        connection.execute("DELETE FROM '%s'" % table)
        connection.commit()
        connection.close()
