#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#  fbsqlgenlist.py

""" This file is part of Flibrowser2.

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


"""Поддержка импорта списка названий жанров из MySQL-дампа"""


from tempfile import TemporaryFile
import os.path
from gzip import open as gzip_open
import sqlparse


# 'lib.libgenrelist.sql.gz'


def import_genre_list_mysqldump(fname):
    """Импорт списка жанров (тэгов) из SQL-файла fname.

    Возвращает словарь, где ключи - имена тэгов,
    а значения - кортежи из двух строк вида
    ('название жанра', 'категория жанра').

    В случае ошибок генерирует исключения."""

    gdict = dict()

    LEVEL_NONE, LEVEL_INSERT, LEVEL_LIBGEN, LEVEL_VALUES = range(4)

    level = LEVEL_NONE

    def clean_string(s):
        if s.startswith('\'') or s.startswith('"'):
            s = s[1:-1]
        return s

    if not os.path.exists(fname):
        raise EnvironmentError('Файл "%s" отсутствует или недоступен' % fname)

    fext = os.path.splitext(fname)[1]

    if fext == u'.gz':
        file_open = gzip_open
        file_mode = 'rt'
    elif fext == u'.sql':
        file_open = open
        file_mode = 'r'
    else:
        raise ValueError('Формат файла "%s" не поддерживается' % fname)

    with file_open(fname, file_mode, encoding='utf-8') as srcf:
        for sr in srcf:
            parsed = sqlparse.parse(sr)

            # гавнина is beginning...
            for stmt in parsed:
                if stmt.get_type() == 'INSERT':
                    level = LEVEL_INSERT
                    for token in stmt.tokens:
                        if token.ttype == sqlparse.tokens.Token.Keyword:
                            if token.value == 'VALUES':
                                if level == LEVEL_LIBGEN:
                                    level = LEVEL_VALUES
                        elif token.ttype is None:
                            if level == LEVEL_INSERT:
                                if str(token.value) == '`libgenrelist`':
                                    level = LEVEL_LIBGEN
                            elif level == LEVEL_VALUES:
                                for t0 in token.tokens:
                                    if t0.ttype is None:
                                        l = list(map(lambda v: v.value, filter(lambda t: t.ttype != sqlparse.tokens.Token.Punctuation, t0.tokens)))[1:]
                                        if len(l) != 3:
                                            continue # влом полностью проверять

                                        gdict[clean_string(l[0])] = (clean_string(l[1]), clean_string(l[2]))

                else:
                    level = LEVEL_NONE

    return gdict


if __name__ == '__main__':
    print('[test]')

    print(import_genre_list_mysqldump('lib.libgenrelist.sql'))

