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
#from fbsqlgenlist import import_genre_list_mysqldump
import sqlite3
import datetime


DB_DATE_FORMAT = '%Y-%m-%d'


def sqlite_ulower(s):
    return s.lower()


class Database():
    """Тупая обёртка над sqlite3.Connection.

    TABLES  - список или кортеж, содержащий описания таблиц БД -
              кортежи из двух или трёх элементов вида
              ('имя таблицы', 'типы столбцов'[, dontreset]),
              где 'типы столбцов' - строка с перечислением типов
              столбцов в синтаксисе sqlite3,
              а dontreset - булевское значение, влияющее на работу
              метода reset_tables().
              Это поле используется методами init_tables()
              и reset_tables(), и должно быть перекрыто классом-потомком."""

    TABLES = ()

    def __init__(self, dbfname):
        """Инициализация.
        dbfname - путь к файлу БД."""

        self.dbfilename = dbfname
        self.connection = None # будет присвоено из .connect()
        self.cursor = None # --//--
        self.vacuumOnInit = False # потом когда-нито будет меняться из настроек, если понадобится

    def connect(self):
        """Соединение с БД.

        В нём применён не шибко быстрый костыль для регистронезависимого
        сравнения строковых значений в SELECT'ах.
        Т.е. в запросах д.б. "WHERE ulower(field)=value"
        и value тоже должно быть приведено к нижнему регистру"""

        if self.connection is None:
            self.connection = sqlite3.connect(self.dbfilename)
            self.cursor = self.connection.cursor()

            self.connection.create_function('ulower', 1, sqlite_ulower)

    def disconnect(self):
        """Завершение соединения с БД.
        Желательно код между .connect() и .disconnect() засовывать
        в try..finally."""

        if self.connection is not None:
            self.connection.commit()
            self.connection.close()
            self.cursor = None
            self.connection = None

    def init_tables(self):
        """Создание таблиц в БД, если они не существуют.
        Если поле TABLES не содержит описаний столбцов,
        метод не делает ничего."""

        if self.connection is None:
            raise Exception('%s.init_tables(): БД не подключена!' % self.__class__.__name__)
        else:
            for ixp, dbparms in enumerate(self.TABLES):
                if len(dbparms) not in (2, 3):
                    raise ValueError('%s.init_tables(): неправильное количество элементов списка параметров таблицы #%d' % (self.__class__.__name__, ixp))

                dbname, dbflds = dbparms[:2]

                self.cursor.execute('''CREATE TABLE IF NOT EXISTS %s(%s)''' % (dbname, dbflds))

    def reset_tables(self):
        """Удаление и пересоздание таблиц в БД.
        Если поле TABLES не содержит описаний столбцов,
        метод не делает ничего."""

        if self.connection is None:
            raise Exception('%s.init_tables(): БД не подключена!' % self.__class__.__name__)
        else:
            for ixp, dbparms in enumerate(self.TABLES):
                nparms = len(dbparms)
                if nparms not in (2, 3):
                    raise ValueError('%s.init_tables(): неправильное количество элементов списка параметров таблицы #%d' % (self.__class__.__name__, ixp))

                if nparms > 2 and nparms[2] == True:
                    # таблица, не подлежащая изничтожению
                    continue

                self.cursor.execute('''DROP TABLE IF EXISTS %s;''' % dbparms[0])

            if self.vacuumOnInit:
                self.connection.execute('VACUUM;')

        self.init_tables()


if __name__ == '__main__':
    print('[test]')
