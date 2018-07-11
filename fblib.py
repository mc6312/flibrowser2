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
from collections import namedtuple


def kilobytes_str(n):
    return u'%gk' % round(n / 1024.0, 1)


class LibraryDB(Database):
    TABLE_FAVORITE_AUTHORS = 'favorite_authors'
    TABLE_FAVORITE_SERIES = 'favorite_series'

    __FAVORITE_FIELDS = (Database.coldef('name', 'TEXT PRIMARY KEY'),)

    favorite_params = namedtuple('favorite_params', 'favtablename libtablename libtablecolname')
    """favtablename     - имя таблицы favorite_* БД,
    libtablename        - имя таблицы БД, по которой выполняется запрос (authornames или seriesnames),
    libtablecolname     - имя столбца вышеуказанной таблицы, по которому выполняется запрос;
                          Внимание! В таблице favorite_* соотв. столбец в любом случае называется name."""

    FAVORITE_AUTHORS_PARAMS = favorite_params(TABLE_FAVORITE_AUTHORS,
        'authornames', 'name')

    FAVORITE_SERIES_PARAMS = favorite_params(TABLE_FAVORITE_SERIES,
        'seriesnames', 'title')

    __SQL_CLEANUP_FAVORITE = lambda par: 'DELETE FROM %s WHERE %s.name NOT IN (SELECT %s.%s FROM %s);' % \
        (par.favtablename, par.favtablename,
         par.libtablename, par.libtablecolname, par.libtablename)

    SQL_CLEANUP_FAVORITES = '\n'.join(map(__SQL_CLEANUP_FAVORITE, (FAVORITE_AUTHORS_PARAMS, FAVORITE_SERIES_PARAMS)))

    DB_VERSION = 1

    TABLES = (# главная таблица - список книг
        Database.tabdef('books',
            (Database.coldef('bookid', 'INTEGER PRIMARY KEY'),
            Database.coldef('authorid', 'INTEGER'),
            Database.coldef('title', 'VARCHAR(100)'),
            Database.coldef('serid', 'INTEGER'),
            Database.coldef('serno', 'INTEGER'),
            Database.coldef('filename', 'VARCHAR(256)'),
            Database.coldef('filetype', 'VARCHAR(16)'),
            Database.coldef('filesize', 'INTEGER'),
            Database.coldef('date', 'VARCHAR(10)'),
            Database.coldef('language', 'VARCHAR(2)'),
            Database.coldef('keywords', 'VARCHAR(128)'),
            Database.coldef('bundleid', 'INTEGER')),
            False),
        # таблица имён авторов
        Database.tabdef('authornames',
            (Database.coldef('authorid', 'INTEGER PRIMARY KEY'),
            Database.coldef('alpha', 'VARCHAR(1)'),
            Database.coldef('name', 'VARCHAR(100)')),
            False),
        # первые символы имён авторов
        Database.tabdef('authornamealpha',
            (Database.coldef('alpha', 'VARCHAR(1) PRIMARY KEY'),),
            False),
        # таблица названий циклов/сериалов
        Database.tabdef('seriesnames',
            (Database.coldef('serid', 'INTEGER PRIMARY KEY'),
            Database.coldef('alpha', 'VARCHAR(1)'),
            Database.coldef('title', 'VARCHAR(100)')),
            False),
        # первые символы названий циклов/сериалов
        Database.tabdef('seriesnamealpha',
            (Database.coldef('alpha', 'VARCHAR(1) PRIMARY KEY'),),
            False),
        # таблица тэгов
        Database.tabdef('genretags',
            (Database.coldef('genreid', 'INTEGER PRIMARY KEY'),
            Database.coldef('tag', 'VARCHAR(64)')),
            False),
        # таблица соответствий жанровых тэгов книжкам
        # таблица genres - БЕЗ primary key!
        Database.tabdef('genres',
            (Database.coldef('genreid', 'INTEGER'),
            Database.coldef('bookid', 'INTEGER')),
            False),
        # таблица человекочитаемых названий для тэгов
        Database.tabdef('genrenames',
            (Database.coldef('tag', 'VARCHAR(64)'),
            Database.coldef('name', 'VARCHAR(128)'),
            Database.coldef('category', 'VARCHAR(128)')),
            False),
        # таблица имён файлов архивов с книгами
        Database.tabdef('bundles',
            (Database.coldef('bundleid', 'INTEGER PRIMARY KEY'),
            Database.coldef('filename', 'VARCHAR(256)')),
            False),
        #
        # "нестираемые" таблицы - не очищаются при импорте библиотеки
        #
        # таблица имён избранных авторов
        Database.tabdef(TABLE_FAVORITE_AUTHORS, __FAVORITE_FIELDS, True),
        # таблица названий избранных циклов/сериалов
        Database.tabdef(TABLE_FAVORITE_SERIES, __FAVORITE_FIELDS, True),
        )

    def sqlite_quote(self, s):
        """Приводит строку s к виду, пригодному для добавления в строку
        SQL-запроса с помощью питоньего символа подстановки параметров
        (в отличие от sqlite placeholders, которые не везде применимы).
        Возвращает преобразованную строку."""

        self.cursor.execute('select quote(?);', (s,))
        r = self.cursor.fetchone()
        return None if r is None else r[0]

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

    def add_favorite(self, tablename, favname):
        """Добавление имени favname в таблицу tablename
        (TABLE_FAVORITE_*.)."""

        self.cursor.execute('INSERT OR REPLACE INTO %s(name) VALUES (?);' % tablename, (favname,))

    def remove_favorite(self, tablename, favname):
        """Удаление имени favname из таблицы tablename
        (TABLE_FAVORITE_*.)."""

        self.cursor.execute('DELETE FROM %s WHERE name=?;' % tablename, (favname,))

    def get_favorite_where_param(self, favparams, value):
        """Возвращает условие для параметра WHERE SQL-запроса.

        favparams - экземпляр favorite_params,
        value - значение столбца из таблицы FAVORITE_TABLE_NAME."""

        return '%s.%s=%s' % (favparams.libtablename,
            favparams.libtablecolname,
            self.sqlite_quote(value))

    def cleanup_favorites(self):
        """Очистка списков избранного от имен, отсутствующих в БД
        (например, после очередного импорта)."""

        self.cursor.executescript(self.SQL_CLEANUP_FAVORITES);


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
                query = 'INSERT INTO %s (%s) VALUES (%s);' % (tablename,
                    ','.join(colnames), ','.join('?' * (len(colvalues) + 1)))

                self.library.cursor.execute(query, [valkey] + colvalues)

            return valkey

        # seriesnames
        seriestitle = record[INPXFile.REC_SERIES]

        if seriestitle:
            # в алфавитный индекс попадут только книги с названием цикла
            stitlealpha = self.library.get_name_first_letter(seriestitle)
            self.library.cursor.execute('''INSERT OR REPLACE INTO seriesnamealpha (alpha) VALUES (?);''', (stitlealpha,))
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

        self.library.cursor.execute('''INSERT OR REPLACE INTO authornamealpha (alpha) VALUES (?);''', (anamealpha,))

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
            self.library.cursor.execute('''INSERT INTO genres (genreid, bookid) VALUES (?,?);''',
                (genreid, bookid))

        # насчет 'insert or replace' см. выше в комментарии к методу!
        self.library.cursor.execute('''INSERT OR REPLACE INTO books(bookid, authorid,
title, serid, serno,
filename, filetype, filesize,
date, language, keywords, bundleid) VALUES (?,?,?,?,?,?,?,?,?,?,?,?);''',
            (bookid, authorid,
            record[INPXFile.REC_TITLE],
            serid, record[INPXFile.REC_SERNO],
            record[INPXFile.REC_FILE], record[INPXFile.REC_EXT], record[INPXFile.REC_SIZE],
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
    def show_progress(fraction):
        print('%d%%\x0d' % int(fraction * 100), end='')

    print('Initializing DB (%s)...' % lib.dbfilename)
    lib.reset_tables()

    print('Importing INPX file "%s"...' % inpxFileName)
    importer = INPXImporter(lib, cfg)
    importer.import_inpx_file(inpxFileName, show_progress)
    print()

    #print('Importing genre name list "%s"...' % genreNamesFile)
    #import_genre_names_list(lib, genreNamesFile)

    lib.connection.commit()

    """lib.cursor.execute('SELECT * FROM books;')
    while True:
        r = lib.cursor.fetchone()
        if r is None:
            break

        print(r)"""

def __test_book_list(lib):
    """ ебучие тормоза, неприменимые нахрен """
    q = '''SELECT
        books.title, group_concat(genretags.tag)
        FROM books
        INNER JOIN genretags ON genreid IN (SELECT genreid FROM genres WHERE genres.bookid=books.bookid)
        GROUP BY books.bookid
        LIMIT 30;'''

    c = lib.cursor.execute('SELECT bookid FROM books;')
    r = c.fetchall()

    q = '''SELECT group_concat(tag, ',')
        FROM genretags WHERE genreid
            IN (SELECT genreid FROM genres WHERE bookid=?)
        LIMIT 300;'''

    if r is not None:
        for v in r:
            cur = lib.cursor.execute(q, v)
            r = cur.fetchall()
            print(r)
    return

    if cur:
        while True:
            r = cur.fetchone()
            if r is None:
                break

            print(r)


def __test_genre_list(lib):
    q = '''SELECT genrenames.name FROM genrenames
        INNER JOIN genretags ON genretags.tag=genrenames.tag;'''

    cur = lib.cursor.execute(q)
    if cur:
        while True:
            r = cur.fetchone()
            if r is None:
                break

            print(r)


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
        #__test_inpx_import(lib, cfg, inpxFileName)#, genreNamesFile)
        #__test_book_list(lib)
        #__test_genre_list(lib)
        pass
    finally:
        lib.disconnect()
