#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" fblib.py

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


"""Основной набор классов и функций библиотеки"""


from fbinpx import INPXFile
#from fbsqlgenlist import import_genre_list_mysqldump
from fbdb import *
import sqlite3
import datetime
import zipfile
import os.path


class LibraryDB(Database):
    __TABLES = (# главная таблица - список книг
        ('books', '''bookid integer primary key,
authorid integer,
title varchar(100), serid integer, serno integer,
filename varchar(256), filetype varchar(16),
date varchar(10), language varchar(2), keywords varchar(128),
bundleid integer'''),
        # таблица имён авторов
        ('authornames', '''authorid integer primary key, name varchar(100)'''),
        # таблица индекса по первым символам имён авторов
        ('authornamealpharefs', '''alpha varchar(1), authorid integer'''),
        # первые символы имён авторов
        ('authornamealpha', '''alpha varchar(1) primary key'''),
        # таблица названий циклов/сериалов
        ('seriesnames', '''serid integer primary key, title varchar(100)'''),
        # таблица тэгов
        ('genretags', '''genreid integer primary key, tag varchar(64)'''),
        # таблица соответствий жанровых тэгов книжкам
        # таблица genres - БЕЗ primary key!
        ('genres', '''genreid integer, bookid integer'''),
        # таблица человекочитаемых названий для тэгов
        ('genrenames', '''tag varchar(64), name varchar(128), category varchar(128)'''),
        # таблица имён файлов архивов с книгами
        ('bundles', '''bundleid integer primary key, filename varchar(256)'''))

    def __init__(self, dbfname):
        super().__init__(dbfname)

        self.vacuumOnInit = False # потом когда-нито будет меняться из настроек

    def check_db(self):
        """Проверка и создание таблиц БД"""

        for dbname, dbflds in self.__TABLES:
            self.cursor.execute('''create table if not exists %s(%s)''' % (dbname, dbflds))

    def reset_db(self):
        """Создание таблиц в БД.
        Сносится всё под корень!"""

        for dbname, dbflds in self.__TABLES:
            self.cursor.execute('''drop table if exists %s;''' % dbname)

        if self.vacuumOnInit:
            self.connection.execute('vacuum;')

        self.check_db()

    def get_name_first_letter(self, name):
        """Возвращает первый буквенно-цифровой символ из строки name,
        приведённый к верхнему регистру.
        Если строка не содержит таких символов, возвращает символ "#"."""

        for c in name:
            if c.isalnum():
                c = c.upper()
                # грязный хакЪ, дабы не тащить вагон внешних
                # зависимостей для полноценного Unicode Collation
                if c == 'Ё':
                    c = 'Е'

                return c

        # для всех прочих символов
        return '#'


class StrHashIdDict():
    """Обёртка над словарём, где ключи - хэши строк,
    а значения - уникальные (в пределах словаря) целые числа.
    Используется для генерации primary keys."""

    def __init__(self):
        self.items = dict()
        self.lastid = 1

    def str_hash(self, s):
        return hash(s)

    def is_unical(self, s):
        """Проверяет, есть ли хэш от строки в словаре.
        Возвращает кортеж из двух элементов:
        1й: булевское значение - уникальное ли значение хэша
        2й: целое число - unical id."""

        h = self.str_hash(s)
        if h in self.items:
            return (False, self.items[h])
        else:
            v = self.lastid
            self.lastid += 1
            self.items[h] = v
            return (True, v)


class NormStrHashIdDict(StrHashIdDict):
    """То же самое, что StrHashIdDict, только хэши считаются от
    нормализованных строк."""

    def str_hash(self, s):
        return hash(s.lower())


class INPXImporter(INPXFile):
    """Класс-обёртка для импорта INPX в БД sqlite3"""

    def str_hash(self, s):
        return hash(s.lower())

    def __init__(self, lib):
        """Инициализация.
        lib - экземпляр LibraryDB"""

        super().__init__()
        self.library = lib

        # временные словари для создания вспомогательных таблиц
        # т.к. проверять повторы select'ами при добавлении записей,
        # а потом еще вытрясать из БД последний primary key -
        # адовы тормоза

        self.seriesnames = NormStrHashIdDict()
        self.bundles = StrHashIdDict()
        self.authornames = NormStrHashIdDict()
        self.genretags = NormStrHashIdDict()

    def get_last_insert_rowid(self):
        """Возвращает ROWID (или соотв. integer primary key)
        записи, добавленной последним вызовом INSERT.
        На ошибки пока проверять не будем..."""

        self.library.cursor.execute('select last_insert_rowid();')
        return self.library.cursor.fetchone()[0]

    def is_allowed_language(self, lang):
        # временная заглушка!
        return lang == 'ru'

    def flush_record(self, record):
        """Метод для спихивания разобранной записи с нормализованными полями
        в БД sqlite3.

        record - список полей в том же порядке, в каком они перечислены
        в описании записи файла INPX, плюс дополнительные поля:
        REC_AUTHOR  - имя автора (строка, см. parse_author_name)
        REC_GENRE   - список тэгов (строк в нижнем регистре)
        REC_TITLE   - название книги (строка)
        REC_SERIES  - название цикла/сериала (строка)
        REC_SERNO   - порядковый номер в сериале (целое)
        REC_FILE    - имя файла (строка)
        REC_SIZE    - размер файла (целое)
        REC_LIBID   - id книги (целое)
        REC_DEL     - флаг удаления (булевское)
        REC_EXT     - тип файла (строка)
        REC_DATE    - дата добавления книги в библиотеку (datetime.date)
        REC_LANG    - язык (строка в нижнем регистре)
        REC_KEYWORDS- ключевые слова (строка в нижнем регистре)
        REC_BUNDLE  - имя файла архива (без каталога), содержащего файл книги.

        Т.к. содержимое INPX импортируется "по порядку", то "новые" записи должны
        замещать "старые" (т.е. если в БД есть запись с неким LIBID, то
        следующая запись с тем же LIBID должна ее заменить)."""

        # я так и не знаю, что значит флаг 'удалено' -
        # то ли книжка физически удалена, то ли "удалена" по требованию
        # правообглодателя
        if record[INPXFile.REC_DEL]:
            return

        #
        # сначала добавляем данные в таблицы, на которые могут ссылаться
        # записи из таблицы books
        #

        def __add_table_unic_rec(unicdict, tablename, valstr, keycolname, valcolname):
            """Добавление уникального значения в таблицу БД.
            Используется ТОЛЬКО для таблиц с двумя столбцами вида "primary key; строка".

            unicdict    - экземпляр класса [Norm]StrHashIdDict,
            tablename   - имя таблицы в БД,
            valstr      - значение помещаемого в таблицу поля,
            keycolname  - имя столбца БД, в котором хранится primary key,
            valcolname  - имя столбца БД для значения.

            Возвращает primary key соотв. таблицы."""

            isunic, valkey = unicdict.is_unical(valstr)
            if isunic:
                self.library.cursor.execute('''insert into %s (%s, %s) values (?,?);''' %\
                    (tablename, keycolname, valcolname),
                    (valkey, valstr))

            return valkey

        # seriesnames
        serid = __add_table_unic_rec(self.seriesnames, 'seriesnames', record[INPXFile.REC_SERIES], 'serid', 'title')

        # bundles
        bundleid = __add_table_unic_rec(self.bundles, 'bundles', record[INPXFile.REC_BUNDLE], 'bundleid', 'filename')

        # authornames
        authorname = record[INPXFile.REC_AUTHOR]
        authorid = __add_table_unic_rec(self.authornames, 'authornames', authorname, 'authorid', 'name')

        # authornamealpharefs
        aname1l = self.library.get_name_first_letter(authorname)
        self.library.cursor.execute('''insert or replace into authornamealpha (alpha) values (?);''', aname1l)
        self.library.cursor.execute('''insert into authornamealpharefs (alpha, authorid) values (?,?);''',
            (aname1l, authorid))

        # genresnames: genreid, name (str)
        # genres: genreid, bookid (int!)

        genreids = set()
        for genrename in record[INPXFile.REC_GENRE]:
            if genrename:
                genreids.add(__add_table_unic_rec(self.genretags, 'genretags', genrename, 'genreid', 'tag'))

        bookid = record[INPXFile.REC_LIBID]

        for genreid in genreids:
            self.library.cursor.execute('''insert into genres (genreid, bookid) values (?,?);''',
                (genreid, bookid))

        # насчет 'insert or replace' см. выше в комментарии к методу!
        self.library.cursor.execute('''insert or replace into books(bookid, authorid,
title, serid, serno,
filename, filetype, date, language, keywords, bundleid) values (?,?,?,?,?,?,?,?,?,?,?);''',
            (bookid, authorid,
            record[INPXFile.REC_TITLE],
            serid, record[INPXFile.REC_SERNO],
            record[INPXFile.REC_FILE], record[INPXFile.REC_EXT],
            record[INPXFile.REC_DATE].strftime(DB_DATE_FORMAT),
            record[INPXFile.REC_LANG], record[INPXFile.REC_KEYWORDS],
            bundleid))


'''Отключено, на время или совсем.
def import_genre_names_list(lib, fname):
    """Импорт Импорт списка жанров (тэгов) из SQL-файла
    в таблицу genrenames БД.

    lib     - экземпляр LibraryDB,
    fname   - имя файла SQL-дампа.

    В случае ошибок генерирует исключения."""

    gdict = import_genre_list_mysqldump(fname)

    for tag in gdict:
        lib.cursor.execute('insert into genrenames (tag, name, category) values (?, ?, ?)',
            (tag, *gdict[tag]))'''


def __test_inpx_import(lib, inpxFileName, genreNamesFile):
    class TestImporter(INPXImporter):
        PROGRESS_DELAY = 1000

        def __init__(self, lib):
            super().__init__(lib)

            self.progressdelay = self.PROGRESS_DELAY

        def show_progress(self, fraction):
            if self.progressdelay > 0:
                self.progressdelay -= 1
            else:
                self.progressdelay = self.PROGRESS_DELAY
                print('%d%%\x0d' % int(fraction * 100), end='')

    print('Initializing DB (%s)...' % lib.dbfilename)
    lib.reset_db()

    print('Importing INPX file "%s"...' % inpxFileName)
    importer = TestImporter(lib)
    importer.import_inpx_file(inpxFileName, importer.show_progress)
    print()

    print('Importing genre name list "%s"...' % genreNamesFile)
    import_genre_names_list(lib, genreNamesFile)

    lib.connection.commit()

    """lib.cursor.execute('select * from books;')
    while True:
        r = lib.cursor.fetchone()
        if r is None:
            break

        print(r)"""


def __test_alpha_authornames_index(lib):
    from time import time

    t0 = time()
    aindex = lib.get_author_alphabet_dict()
    t1 = time() - t0
    print('%d letters in index; %g sec.' % (len(aindex), t1))

    #return

    for l1 in sorted(aindex.keys()):
        print('%s:' % l1)

        for aid, aname in aindex[l1]:
            print('  %.6d  %s' % (aid, aname))


if __name__ == '__main__':
    print('[test]')

    from fbenv import *

    env = Environment()
    cfg = Settings(env)
    cfg.load()

    inpxFileName = cfg.get_param(cfg.INPX_INDEX)
    genreNamesFile = cfg.get_param(cfg.GENRE_NAMES_PATH)

    lib = LibraryDB(env.libraryFilePath)
    lib.connect()
    try:
        #__test_inpx_import(lib, inpxFileName, genreNamesFile)
        #__test_alpha_authornames_index(lib)
        pass
    finally:
        lib.disconnect()
