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
    TABLES = (# главная таблица - список книг
        ('books', '''bookid integer primary key,
authorid integer,
title varchar(100), serid integer, serno integer,
filename varchar(256), filetype varchar(16),
date varchar(10), language varchar(2), keywords varchar(128),
bundleid integer'''),
        # таблица имён авторов
        ('authornames', '''authorid integer primary key, alpha varchar(1), name varchar(100)'''),
        # первые символы имён авторов
        ('authornamealpha', '''alpha varchar(1) primary key'''),
        # таблица названий циклов/сериалов
        ('seriesnames', '''serid integer primary key, alpha varchar(1), title varchar(100)'''),
        # первые символы названий циклов/сериалов
        ('seriesnamealpha', '''alpha varchar(1) primary key'''),
        # таблица тэгов
        ('genretags', '''genreid integer primary key, tag varchar(64)'''),
        # таблица соответствий жанровых тэгов книжкам
        # таблица genres - БЕЗ primary key!
        ('genres', '''genreid integer, bookid integer'''),
        # таблица человекочитаемых названий для тэгов
        ('genrenames', '''tag varchar(64), name varchar(128), category varchar(128)'''),
        # таблица имён файлов архивов с книгами
        ('bundles', '''bundleid integer primary key, filename varchar(256)'''))

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

    def __init__(self, lib, cfg):
        """Инициализация.
        lib - экземпляр LibraryDB,
        cfg - экземпляр fbenv.Settings."""

        super().__init__()
        self.library = lib
        self.cfg = cfg

        self.allowedLanguages = self.cfg.get_param_set(self.cfg.IMPORT_LANGUAGES,
            self.cfg.DEFAULT_IMPORT_LANGUAGES)

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

        # фильтрация по языкам
        if record[INPXFile.REC_LANG] not in self.allowedLanguages:
            return

        #
        # сначала добавляем данные в таблицы, на которые могут ссылаться
        # записи из таблицы books
        #

        def __add_table_unic_rec(unicdict, tablename, colnames, colvalues, ixuniccol):
            """Добавление уникального значения в таблицу БД.
            Используется ТОЛЬКО для таблиц, где 1й столбец - integer primary key!

            unicdict    - экземпляр класса [Norm]StrHashIdDict,
            tablename   - имя таблицы в БД,
            colnames    - список или кортеж строк - имён столбцов,
            colvalues   - список или кортеж значений столбцов, кроме primary key;
                          т.е. размер списка д.б. на 1 меньше, чем colnames:
                          при добавлении в таблицу значение для первого
                          столбца генерирует эта функция!
            ixuniccol   - номер поля в списке colvalues, по которому
                          проверяется уникальность.

            Возвращает primary key соотв. таблицы."""

            if isinstance(colvalues, tuple):
                colvalues = list(colvalues)

            isunic, valkey = unicdict.is_unical(colvalues[ixuniccol])

            if isunic:
                query = 'insert into %s (%s) values (%s);' % (tablename,
                    ','.join(colnames), ','.join('?' * (len(colvalues) + 1)))

                self.library.cursor.execute(query, [valkey] + colvalues)

            return valkey

        # seriesnames
        seriestitle = record[INPXFile.REC_SERIES]

        if seriestitle:
            # в алфавитный индекс попадут только книги с названием цикла
            stitlealpha = self.library.get_name_first_letter(seriestitle)
            self.library.cursor.execute('''insert or replace into seriesnamealpha (alpha) values (?);''', (stitlealpha,))
        else:
            stitlealpha = ''

        serid = __add_table_unic_rec(self.seriesnames, 'seriesnames',
            ('serid', 'alpha', 'title'),
            (stitlealpha, seriestitle),
            1)

        # bundles
        bundleid = __add_table_unic_rec(self.bundles, 'bundles',
            ('bundleid', 'filename'), (record[INPXFile.REC_BUNDLE],),
            0)

        # authornames
        authorname = record[INPXFile.REC_AUTHOR]
        anamealpha = self.library.get_name_first_letter(authorname)

        authorid = __add_table_unic_rec(self.authornames, 'authornames',
            ('authorid', 'alpha', 'name'),
            (anamealpha, authorname),
            1)

        self.library.cursor.execute('''insert or replace into authornamealpha (alpha) values (?);''', (anamealpha,))

        # genresnames: genreid, name (str)
        # genresnames: genreid, name (str)
        # genres: genreid, bookid (int!)

        genreids = set()
        for genrename in record[INPXFile.REC_GENRE]:
            if genrename:
                genreid = __add_table_unic_rec(self.genretags, 'genretags',
                    ('genreid', 'tag'),
                    (genrename,),
                    0)
                genreids.add(genreid)

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


def __test_inpx_import(lib, cfg, inpxFileName): #, genreNamesFile):
    class TestImporter(INPXImporter):
        PROGRESS_DELAY = 1000

        def __init__(self, lib, cfg):
            super().__init__(lib, cfg)

            self.progressdelay = self.PROGRESS_DELAY

        def show_progress(self, fraction):
            if self.progressdelay > 0:
                self.progressdelay -= 1
            else:
                self.progressdelay = self.PROGRESS_DELAY
                print('%d%%\x0d' % int(fraction * 100), end='')

    print('Initializing DB (%s)...' % lib.dbfilename)
    lib.reset_tables()

    print('Importing INPX file "%s"...' % inpxFileName)
    importer = TestImporter(lib, cfg)
    importer.import_inpx_file(inpxFileName, importer.show_progress)
    print()

    #print('Importing genre name list "%s"...' % genreNamesFile)
    #import_genre_names_list(lib, genreNamesFile)

    lib.connection.commit()

    """lib.cursor.execute('select * from books;')
    while True:
        r = lib.cursor.fetchone()
        if r is None:
            break

        print(r)"""


if __name__ == '__main__':
    print('[test]')

    from fbenv import *

    env = Environment()
    cfg = Settings(env)
    cfg.load()

    inpxFileName = cfg.get_param(cfg.IMPORT_INPX_INDEX)

    lib = LibraryDB(env.libraryFilePath)
    lib.connect()
    try:
        __test_inpx_import(lib, cfg, inpxFileName)#, genreNamesFile)
        #pass
    finally:
        lib.disconnect()
