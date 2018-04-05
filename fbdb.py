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
from collections import namedtuple


DB_DATE_FORMAT = '%Y-%m-%d'


def sqlite_ulower(s):
    """Костыльная функция для кривой замены unicode collation"""

    return s.lower()


class Database():
    """Тупая обёртка над sqlite3.Connection.

    Поля класса:
    DB_VERSION  - целое, версия схемы БД;
                  Это поле должно быть перекрыто классом-потомком.
    TABLES      - список или кортеж, содержащий описания таблиц БД -
                  экземпляры Database.tabdef.
                  Это поле используется методами init_tables()
                  reset_tables() и is_structure_valid(),
                  и должно быть перекрыто классом-потомком.

    Поля экземпляра класса:
    dbfilename      - путь к файлу БД
    connection      - экземпляр sqlite3.connection (присваивается из .connect())
    cursor          - курсор
    vacuumOnInit    - булевское значение: сжимать ли БД при инициализации;
                      потом когда-нито будет меняться из настроек, если понадобится.
    dbversion       - целое, значение поля user_version из файла БД (см. описание
                      PRAGMA user_version в документации по Sqlite 3);
                      берется из БД при соединении с оной;
                      сохраняется в БД при вызове reset_tables()
                      или при вызове set_db_version(),
                      при обоих вызовах этому полю предварительно
                      присваивается значение поля класса DB_VERSION."""

    tabdef = namedtuple('tabdef', 'tname cols dontreset')
    """Описание таблицы.

    tname       - строка, имя таблицы,
    cols        - список или кортеж экземпляров Database.coldef,
    dontreset   - булевское значение, влияющее на работу метода reset_tables()."""

    coldef = namedtuple('coldef', 'cname ctype')
    """Описание столбца таблицы.

    cname    - строка, имя столбца,
    ctype    - строка, тип столбца в синтаксисе sqlite3
               (напр. "INTEGER PRIMARY KEY")."""

    DB_VERSION = 0
    TABLES = ()


    def __init__(self, dbfname):
        """Инициализация.
        dbfname - путь к файлу БД."""

        self.dbfilename = dbfname
        self.connection = None # будет присвоено из .connect()
        self.cursor = None # --//--
        self.vacuumOnInit = False # потом когда-нито будет меняться из настроек, если понадобится
        self.dbversion = 0 # будет изменено при вызове .connect()!

    def connect(self):
        """Соединение с БД.

        В нём применён не шибко быстрый костыль для регистронезависимого
        сравнения строковых значений в SELECT'ах.
        Т.е. в запросах д.б. "WHERE ulower(field)=value"
        и value тоже должно быть приведено к нижнему регистру."""

        if self.connection is None:
            self.connection = sqlite3.connect(self.dbfilename)
            self.cursor = self.connection.cursor()
            self.cursor.executescript('''PRAGMA synchronous=OFF;
                PRAGMA journal_mode=MEMORY;''')

            self.connection.create_function('ulower', 1, sqlite_ulower)

            r = self.cursor.execute('PRAGMA user_version;')
            if r is None:
                self.dbversion = 0
            else:
                self.dbversion = r.fetchone()[0]

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
            for tabparam in self.TABLES:
                dbflds = ','.join(map(lambda cd: '%s %s' % (cd.cname, cd.ctype), tabparam.cols))
                self.cursor.execute('''CREATE TABLE IF NOT EXISTS %s(%s)''' % (tabparam.tname, dbflds))

    def set_db_version(self):
        """Принудительная установка self.dbversion и сохранение значения в БД."""

        if self.connection is None:
            raise Exception('%s.set_db_version(): БД не подключена!' % self.__class__.__name__)
        else:
            self.dbversion = self.DB_VERSION
            self.cursor.execute('PRAGMA user_version=%d;' % self.dbversion)

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

                if nparms > 2 and dbparms[2] == True:
                    # таблица, не подлежащая изничтожению
                    continue

                self.cursor.execute('''DROP TABLE IF EXISTS %s;''' % dbparms[0])

            if self.vacuumOnInit:
                self.connection.execute('VACUUM;')

            self.set_db_version()

        self.init_tables()

    def get_table_count(self, tabname, whereparam=''):
        """Возвращает количество строк в таблице.

        whereparm - строка с условиями (параметры для WHERE)
                    или пустая строка."""

        q = 'SELECT count(*) FROM %s%s;' %\
            (tabname, '' if whereparam == '' else ' WHERE %s' % whereparam)
        cur = self.cursor.execute(q)

        r = cur.fetchone()
        return 0 if r is None else r[0]

    def get_table_dif_count(self, tabname1, tabname2, colname1, colname2=None):
        """Возвращает количество несовпадающих строк
        в таблицах table1 и table2.
        Проверка ведётся по столбцам tabname1.colname1 и tabname2.colname2.
        Если значение colname2 == None, то считается, что названия
        столбцов в таблицах совпадают."""

        if not colname2:
            colname2 = colname1

        return self.get_table_count(tabname1,
            '%s NOT IN (SELECT %s FROM %s)' % (colname1, colname2, tabname2))


if __name__ == '__main__':
    print('[test]')

    class TestDatabase(Database):
        TABLES = (Database.tabdef('moo', (Database.coldef('v', 'INTEGER PRIMARY KEY'),), False),
            Database.tabdef('boo', (Database.coldef('u', 'INTEGER PRIMARY KEY'),), False),
            )

    db = TestDatabase(':memory:')
    db.connect()
    try:
        db.init_tables()
        print('dbversion = %d (must be %d)' % (db.dbversion, db.DB_VERSION))

        db.cursor.executescript('''INSERT INTO moo(v) VALUES (1),(2);
            INSERT INTO boo(u) VALUES (2);''')

        print(db.get_table_count('moo'))
        print(db.get_table_dif_count('moo', 'boo', 'v', 'u'))

    finally:
        db.disconnect()
