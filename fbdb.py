#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" fbdb.py

    This file is part of Flibrowser2.

    Flibrowser2 is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    Flibrowser2 is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with Flibrowser2.  If not, see <http://www.gnu.org/licenses/>."""


"""Базовые функции и классы для работы с БД sqlite3"""

from fbinpx import INPXFile
from fbsqlgenlist import import_genre_list_mysqldump
import sqlite3
import datetime


DB_DATE_FORMAT = '%Y-%m-%d'


class Database():
    """Тупая обёртка над sqlite3.Connection."""

    def __init__(self, dbfname):
        """Инициализация.
        dbfname - путь к файлу БД."""

        self.dbfilename = dbfname
        self.connection = None # будет присвоено из .connect()
        self.cursor = None # --//--

    def connect(self):
        """Соединение с БД"""
        if self.connection is None:
            self.connection = sqlite3.connect(self.dbfilename)
            self.cursor = self.connection.cursor()

    def disconnect(self):
        """Завершение соединения с БД.
        Желательно код между .connect() и .disconnect() засовывать
        в try..finally."""

        if self.connection is not None:
            self.connection.commit()
            self.connection.close()
            self.cursor = None
            self.connection = None


if __name__ == '__main__':
    print('[test]')
