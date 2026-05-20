# moesql Copyright (c) 2026, Ivan Reshetnikov - All rights reserved.
# 
# An small ORM abstraction written in Python 3 powered by SQLite 3 dialect of SQL.
#
# Features:
# - Define entities as Python classes
# - Create/save/update/delete entities
# - Simple one-to-many relationships
# - Automatic table creation
# - Absolutely no SQL injection concerns


import sqlite3
from typing import Any, Dict, List, Optional, Type



class Database:
    # NOTE(vanya): SQLite3-only database back-end.

    _connection = None


    @classmethod
    def connect(cls, path: str):
        cls._connection = sqlite3.connect(path)
        cls._connection.row_factory = sqlite3.Row


    @classmethod
    def execute(cls, query: str, params=()):
        cursor = cls._connection.cursor()
        cursor.execute(query, params)
        cls._connection.commit()
        return cursor


    @classmethod
    def create_tables(cls):
        for model in Model.__subclasses__():
            model._create_table()



class Field:
    sql_type = "TEXT"

    def __init__(self, default=None):
        self.name = None
        self.default = default

    def to_sql(self):
        return f"{self.name} {self.sql_type}"



class IntegerField(Field):
    sql_type = "INTEGER"



class StringField(Field):
    sql_type = "TEXT"



class ForeignKey(Field):
    sql_type = "INTEGER"



class ModelMeta(type):
    def __new__(cls, p_name, p_bases, p_attrs):
        fields = {}

        for base in p_bases:
            if hasattr(base, "_fields"):
                fields.update(base._fields)

        for key, value in list(p_attrs.items()):
            if isinstance(value, Field):
                value.name = key
                fields[key] = value

        p_attrs["_fields"] = fields

        return super().__new__(cls, p_name, p_bases, p_attrs)



class Model(metaclass=ModelMeta):
    id = IntegerField()

    def __init__(self, **kwargs):
        for field_name, field in self._fields.items():
            value = kwargs.get(field_name, field.default)
            setattr(self, field_name, value)


    @classmethod
    def table_name(cls):
        # NOTE(vanya): Get class table name

        return cls.__name__


    @classmethod
    def _create_table(cls) -> None:
        # NOTE(vanya): Create SQL-table for the passed class signature

        # NOTE(vanya): Mandate primary keys
        columns = ["id INTEGER PRIMARY KEY AUTOINCREMENT"]

        for field_name, field in cls._fields.items():
            if field_name == "id":
                continue

            columns.append(field.to_sql())

        sql = f"""
        CREATE TABLE IF NOT EXISTS {cls.table_name()} (
            {", ".join(columns)}
        )
        """

        Database.execute(sql)


    def save(self) -> None:
        # NOTE(vanya): Update row from instance attributes

        fields = [f for f in self._fields.keys() if f != "id"]

        values = [getattr(self, f) for f in fields]

        if getattr(self, "id", None):
            set_clause = ", ".join([f"{f}=?" for f in fields])

            sql = f"""
            UPDATE {self.table_name()}
                SET {set_clause}
                WHERE id=?
            """

            Database.execute(sql, (*values, self.id))

        else:
            # INSERT
            placeholders = ", ".join(["?"] * len(fields))

            sql = f"""
            INSERT INTO {self.table_name()}
                ({", ".join(fields)})
                VALUES ({placeholders})
            """

            cursor = Database.execute(sql, values)
            self.id = cursor.lastrowid


    def delete(self):
        # NOTE(vanya): Delete row from instance ID

        if not getattr(self, "id", None):
            return

        sql = f"DELETE FROM {self.table_name()} WHERE id=?"
        Database.execute(sql, (self.id,))

        self.id = None


    @classmethod
    def get(cls, entity_id: int):
        # NOTE(vanya): Delete row from instance ID
        # NOTE(vanya): No "advanced" SQL-query search is supported.

        sql = f"SELECT * FROM {cls.table_name()} WHERE id=?"

        row = Database.execute(sql, (entity_id,)).fetchone()

        if not row:
            return None

        return cls(**dict(row))


    @classmethod
    def all(cls):
        sql = f"SELECT * FROM {cls.table_name()}"

        rows = Database.execute(sql).fetchall()

        return [cls(**dict(row)) for row in rows]


    @classmethod
    def filter(cls, **kwargs):
        where = []
        values = []

        for key, value in kwargs.items():
            where.append(f"{key}=?")
            values.append(value)

        sql = f"""
        SELECT * FROM {cls.table_name()}
            WHERE {" AND ".join(where)}
        """

        rows = Database.execute(sql, values).fetchall()

        return [cls(**dict(row)) for row in rows]


    def __repr__(self):
        # NOTE(vanya): Pretty-print

        values = ", ".join(
            f"{k}={repr(getattr(self, k))}"
            for k in self._fields.keys()
        )

        return f"{self.__class__.__name__}({values})"

