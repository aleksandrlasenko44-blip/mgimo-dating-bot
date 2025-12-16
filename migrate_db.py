#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Разовая миграция БД для DiplomatMatch.

Добавляет в таблицу users колонки:
- subscription_until TEXT
- auto_renew INTEGER DEFAULT 1
"""

import os
import sqlite3

DB_PATH = "mgimo_dating_bot.db"


def column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cur = conn.execute(f"PRAGMA table_info({table})")
    for row in cur.fetchall():
        # row[1] — имя колонки
        if row[1] == column:
            return True
    return False


def main() -> None:
    if not os.path.exists(DB_PATH):
        print(f"Файл БД {DB_PATH} не найден в текущей папке.")
        print("Убедись, что запускаешь скрипт из папки с ботом.")
        return

    conn = sqlite3.connect(DB_PATH)
    try:
        print(f"Открываю БД: {DB_PATH}")
        changed = False

        # subscription_until
        if not column_exists(conn, "users", "subscription_until"):
            print("Добавляю колонку users.subscription_until ...")
            conn.execute("ALTER TABLE users ADD COLUMN subscription_until TEXT;")
            changed = True
        else:
            print("Колонка users.subscription_until уже существует.")

        # auto_renew
        if not column_exists(conn, "users", "auto_renew"):
            print("Добавляю колонку users.auto_renew ...")
            conn.execute(
                "ALTER TABLE users ADD COLUMN auto_renew INTEGER DEFAULT 1;"
            )
            changed = True
        else:
            print("Колонка users.auto_renew уже существует.")

        if changed:
            conn.commit()
            print("✅ Миграция выполнена, изменения сохранены.")
        else:
            print("✅ Ничего делать не пришлось — структура уже новая.")

    finally:
        conn.close()
        print("Готово.")


if __name__ == "__main__":
    main()

