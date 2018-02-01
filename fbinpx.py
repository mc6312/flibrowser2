#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" fbinpx.py

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


"""Поддержка чтения файлов в формате INPX (zip-архив с индексными файлами
.inp внутри)."""


import os, os.path
import zipfile
import datetime


"""Структура записи файла .inp (находящегося внутри zip-архива .inpx):

AUTHOR;GENRE;TITLE;SERIES;SERNO;FILE;SIZE;LIBID;DEL;EXT;DATE;LANG;KEYWORDS;<CR><LF>
Разделитель полей записи (вместо ';') - 0x04
Завершают запись символы <CR><LF> - 0x0D,0x0A
--------------------------------------------------------------------------

Все поля записи представлены в символьном виде. Поле может быть 'пустым',
т.е. иметь нулевую длину.

Поля записи файла inpx в порядке расположения в записи:

AUTHOR      [текст]         Один или несколько авторов книги в формате <Ф,И,О:> подряд без пробелов.
GENRE       [текст]         Один или несколько жанров в формате <genre_id:> подряд без пробелов.
TITLE       [текст]         Заголовок книги.
SERIES      [текст]         Название серии в которую входит книга.
SERNO       [целое]         Номер книги в серии.
FILE        [целое/текст]   Номер книги/имя файла в архиве ххх-хххх.zip
SIZE        [целое]         Размер файла в байтах
LIBID       [целое]         BookId
DEL         [целое]         флаг удаления:
                            Пустое поле - для существующей книги
                            1 - для удалённой книги.
EXT         [текст]         Тип файла - fb2, doc, pdf, ...
DATE        [текст]         YYYY-MM-DD. Дата занесения книги в библиотеку
LANG        [текст]         Язык книги - ru, en, ...
KEYWORDS    [текст]         ключевые слова в виде одной строки"""


class INPXFile():
    """Класс для импорта БД в формате INPX."""

    # кодировка файла .inpx - приколочена внутре гвоздями!
    INPX_INDEX_ENCODING = 'utf-8'
    INPX_REC_SEPARATOR = '\x04'

    # индексы полей в записях INPX
    REC_AUTHOR, REC_GENRE, REC_TITLE,\
    REC_SERIES, REC_SERNO, REC_FILE, REC_SIZE,\
    REC_LIBID, REC_DEL, REC_EXT, REC_DATE,\
    REC_LANG, REC_KEYWORDS, REC_BUNDLE = range(14)
    # Внимание! Поля с индексом REC_BUNDLE в записи INPX нет!
    # Это значение допустимо только для параметра record
    # метода flush_record()

    def inpx_date_to_date(self, s, defval):
        """Преобразование строки вида YYYY-MM-DD в datetime.date.
        Возвращает результат преобразования в случае успеха.
        Если строка не содержит правильной даты - возвращает значение defval."""

        try:
            return datetime.datetime.strptime(s, '%Y-%m-%d').date()
        except ValueError:
            return defval

    def normalize_author_name(self, rawname):
        """Нормализация имени автора (в т.ч. группового).

        rawname - исходная строка вида
        "Фамилия1[,Имя1,Отчество1]:...:ФамилияN[,ИмяN,ОтчествоN]:"

        Исходная строка разбирается на список подстрок "Фамилия Имя Отчество",
        список сортируется по алфавиту и объединяется в строку, разделённую
        запятыми."""

        names = []

        for rawnamestr in filter(None, rawname.split(':')):
            # потому что в индексных файлах м.б. кривожопь

            rawnamestr = ' '.join(filter(None, map(lambda s: s.strip(), rawnamestr.split(','))))
            if rawnamestr:
                names.append(rawnamestr)

        return ', '.join(sorted(names)) if names else '?'

    def flush_record(self, record):
        """Метод для спихивания разобранной записи с нормализованными полями
        в какую-то "нормальную" БД.
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
        REC_BUNDLE  - имя файла архива (без каталога), содержащего файл книги

        Т.к. содержимое INPX импортируется "по порядку", то "новые" записи должны
        замещать "старые" (т.е. если в БД есть запись с неким LIBID, то
        следующая запись с тем же LIBID должна ее заменить).

        Внимание! Этот метод ничего не делает и должен быть перекрыт
        в классе-потомке."""

        pass

    def import_inpx_file(self, fpath, show_progress=None):
        """Разбор файла .inpx.

        fpath           - путь к импортируемому файлу,
        show_progress   - None или функция для отображения прогресса;
                          получает один параметр - значение
                          в диапазоне 0.0-1.0."""

        try:
            with zipfile.ZipFile(fpath, 'r', allowZip64=True) as zf:
                indexFiles = []

                # сначала ищем все индексные файлы, кладем в список

                for nfo in zf.infolist():
                    if nfo.file_size != 0:
                        fname = os.path.splitext(nfo.filename)

                        if fname[1].lower() == '.inp':
                            bundle = fname[0] + '.zip'

                            indexFiles.append((bundle, nfo.filename))

                numindexes = len(indexFiles)

                # ...потому что дальше нужно работать с _отсортированным_ списком файлов: новое затирает старое

                rejected = 0
                ixindex = 0
                for book_bundle, inp_fname in sorted(indexFiles, key=lambda a: a[0]):
                    ixindex += 1

                    # book_bundle: REC_BUNDLE  - имя файла архива (без каталога), содержащего файл книги

                    znfo = zf.getinfo(inp_fname)
                    defdate = datetime.date(znfo.date_time[0], znfo.date_time[1], znfo.date_time[2])
                    # могли бы поганцы и константы для индексов сделать, или namedtuple

                    with zf.open(inp_fname, 'r') as f:
                        for recix, recstr in enumerate(f):
                            srcrec = ['<not yet parsed>']
                            try:
                                srcrec = recstr.decode(self.INPX_INDEX_ENCODING, 'replace').split(self.INPX_REC_SEPARATOR)

                                if not srcrec[self.REC_LIBID].isdigit():
                                    raise ValueError('Неправильное значение поля LIBID: "%s"' % srcrec[self.REC_LIBID])

                                # DEL     - флаг удаления (булевское)
                                book_deleted = srcrec[self.REC_DEL] == '1'
                                # ?

                                # LANG    - язык (строка в нижнем регистре)
                                book_language = srcrec[self.REC_LANG].lower()

                                # LIBID   - id книги (целое)
                                book_libid = int(srcrec[self.REC_LIBID])

                                # GENRE   - список тэгов (строк в нижнем регистре)
                                book_genre = list(map(lambda s: s.strip(), srcrec[self.REC_GENRE].lower().split(':')))

                                # TITLE   - название книги (строка)
                                book_title = srcrec[self.REC_TITLE].strip()

                                # AUTHOR  - список из кортежей (см. parse_author_name)
                                book_author = self.normalize_author_name(srcrec[self.REC_AUTHOR])

                                # GENRE   - список тэгов (строк в нижнем регистре)
                                book_taglist = list(filter(None, srcrec[self.REC_GENRE].lower().split(u':')))

                                # цикл/сериал
                                book_series = srcrec[self.REC_SERIES]
                                book_serno = int(srcrec[self.REC_SERNO]) if srcrec[self.REC_SERNO].isdigit() else 0

                                # SIZE - размер файла (целое), если подумать, нахрен не нужно, но пусть будет
                                book_fsize = int(srcrec[self.REC_SIZE]) if srcrec[self.REC_SIZE].isdigit() else 0

                                # FILE - имя файла (строка)
                                book_fname = srcrec[self.REC_FILE]

                                # EXT     - тип файла (строка)
                                book_ftype = srcrec[self.REC_EXT]

                                # DATE    - дата добавления книги в библиотеку (datetime.date)
                                book_date = self.inpx_date_to_date(srcrec[self.REC_DATE], defdate)

                                # KEYWORDS- ключевые слова (строка в нижнем регистре)
                                book_keywords = srcrec[self.REC_KEYWORDS].strip().lower()

                                self.flush_record((book_author, book_genre, book_title,
                                    book_series, book_serno, book_fname, book_fsize,
                                    book_libid, book_deleted, book_ftype, book_date,
                                    book_language, book_keywords, book_bundle))

                            except Exception as ex:
                                # вот ниибет, что квыво
                                raise Exception(u'Ошибка в записи #%d файла "%s" - %s\n* запись: %s' % (recix + 1, fname, str(ex), u';'.join(srcrec)))

                            if show_progress is not None:
                                show_progress(float(ixindex) / numindexes)

        except Exception as ex:
            raise Exception(u'Ошибка обработки файла "%s",\n%s' % (fpath, str(ex)))


"""    def print_exec_time(self, todo, *arg):
        t0 = time()
        r = todo(*arg)
        t0 = time() - t0
        self.__print_stat('время работы', '%.1f сек' % t0)
        return r"""


if __name__ == '__main__':
    print('[test]')

    class TestINPXFile(INPXFile):
        PROGRESS_DELAY = 1000

        def __init__(self):
            super().__init__()
            self.ids = dict()
            self.dups = []
            self.progressdelay = self.PROGRESS_DELAY

        def show_progress(self, fraction):
            if self.progressdelay > 0:
                self.progressdelay -= 1
            else:
                self.progressdelay = self.PROGRESS_DELAY
                print('%d%%\x0d' % int(fraction * 100), end='')

        def flush_record(self, record):
            recd = '(%s) %s - %s' % ('D' if record[self.REC_DEL] else 'A', record[self.REC_AUTHOR], record[self.REC_TITLE])
            libid = record[self.REC_LIBID]
            if libid not in self.ids:
                self.ids[libid] = recd
            else:
                self.dups.append('* duplicated record "%s" ("%s" with same id %d' % (recd, self.ids[libid], libid))

    inpx = TestINPXFile()
    inpx.import_inpx_file('flibusta_fb2_local.inpx', inpx.show_progress)
    #for d in inpx.dups:
    #    print(d)
