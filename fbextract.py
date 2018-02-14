#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" fbextract.py

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

"""Распаковка книг из архивов"""


import zipfile
import fblib
import fbenv
import os, os.path


INVALID_FN_CHARS = '<>:"/\|?*'

def validate_fname_charset(s):
    """Замена в имени файла недопустимых символов.
    Недопустимые символы заменяются на "_"."""

    return ''.join(map(lambda c: '_' if c < ' ' or c in INVALID_FN_CHARS else c, s))

def validate_dname_charset(s):
    """Замена в имени каталога недопустимых символов.
    Недопустимые символы заменяются на "_"."""

    return os.path.join(*map(validate_fname_charset, s.split(os.sep)))


class BookExtractor():
    def __init__(self, lib, env, cfg):
        """Инициализация.

        lib                 - экземпляр fblib.LibraryDB,
        env                 - экземпляр fbeng.Environment,
        cfg                 - экземпляр fbenv.Settings.

        Прочие параметры берутся из этих объектов."""

        self.lib = lib
        self.env = env
        self.cfg = cfg

    def extract(self, bookids, fntemplate=None, progress=None):
        """Извлекает книги.
        bookids         - список идентификаторов книг в БД
        fntemplate      - экземпляр fbfntemplate.Template для генерации имён файлов из значений в БД;
                          если генерируемые им имена файлов содержат разделители путей,
                          будут созданы соотв. подкаталоги в extractdir;
                          если None - будет использовано оригинальное имя файла;
                          внимание! в имя файла ВСЕГДА добавляется bookid, при использовании
                          шаблона тоже.
        progress        - (если не None) функция для отображения прогресса,
                          получает параметр fraction - вещественное число в диапазоне 0.0-1.0
        В случае успеха возвращает пустую строку или None, в случае ошибки
        (одну или несколько книг извлечь не удалось) - возвращает строку
        с сообщением об ошибке."""

        if not bookids:
            return None # ибо пустой список ошибкой не считаем

        extractdir = self.cfg.get_param(self.cfg.EXTRACT_TO_DIRECTORY)

        if not os.path.exists(extractdir):
            return 'Каталог для извлекаемых книг не найден.'

        packtozip = self.cfg.get_param(self.cfg.EXTRACT_PACK_ZIP)

        librarydir = self.cfg.get_param(self.cfg.LIBRARY_DIRECTORY)

        em = []

        extractedbooks = 0
        totalbooks = 0

        # выбираем книги и группируем по архивам (т.к. в одном архиве может быть несколько книг)
        xbundles = {}
        # при очень большом кол-ве книг (длинном списке bookids) может жрать память, но мне пока пофиг

        # какого хуя тут нельзя executemany?

        for bookid in bookids:
            cur = self.lib.cursor.execute('''SELECT bundles.filename
                FROM books INNER JOIN bundles ON bundles.bundleid=books.bundleid
                WHERE bookid=?;''', (bookid,))
            r = cur.fetchone()
            if r is None:
                em.append('Книга с id=%d отсутствует в БД. Что-то не то с программой...' % bookid)
                continue

            totalbooks += 1

            bundlefname = r[0]
            if bundlefname in xbundles:
                xbundles[bundlefname].append(bookid)
            else:
                xbundles[bundlefname] = [bookid]

        # а вот теперь уже пытаемся выковырять книги из архивов

        ixbook = 0
        createddirs = set() # дабы не пытаться создавать каталоги повторно

        for bundlefname in xbundles:
            bundlefpath = os.path.join(librarydir, bundlefname)

            if not os.path.exists(bundlefpath):
                em.append('Файл архива "%s" не найден.' % bundlefpath)
            else:
                try:
                    with zipfile.ZipFile(bundlefpath, 'r', allowZip64=True) as zf:
                        missingbooks = 0

                        znames = zf.namelist()

                        bundlebooks = xbundles[bundlefname]
                        for bookid in bundlebooks:
                            ixbook += 1

                            cur = self.lib.cursor.execute('''SELECT filename,filetype,books.title,seriesnames.title,serno,authornames.name
                                FROM books
                                INNER JOIN seriesnames ON seriesnames.serid=books.serid
                                INNER JOIN authornames ON authornames.authorid=books.authorid
                                WHERE bookid=?;''', (bookid,))

                            # 0 filename
                            # 1 filetype
                            # 2 books.title
                            # 3 seriesnames.title
                            # 4 serno
                            # 5 authornames.name

                            bookfname, bookftype, booktitle, seriestitle, serno, authorname = cur.fetchone()
                            # наличие книги с bookid уже проверено при заполнении xbundles!

                            zbookfname = '%s.%s' % (bookfname, bookftype)

                            if zbookfname not in znames:
                                missingbooks += 1
                            else:
                                try:
                                    znfo = zf.getinfo(zbookfname)
                                    if znfo.file_size == 0:
                                        em.append('Файл "%s" в архиве "%s" имеет нулевой размер. Нечего распаковывать.' %\
                                            (bookfname, bundlefpath))
                                        continue

                                    BLOCKSIZE = 1*1024*1024

                                    with zf.open(znfo, 'r') as srcf:
                                        if fntemplate:
                                            dstsubdir, dstfname = fntemplate.create_file_name(bookfname, booktitle,
                                                seriestitle, serno, authorname)
                                        else:
                                            dstsubdir = ''
                                            dstfname = bookfname

                                        # имя файла всегда содержит bookid - независимо от шаблона
                                        dstfname = validate_fname_charset('%d %s.%s' % (bookid, dstfname, bookftype))

                                        dstfpath = os.path.join(extractdir, validate_dname_charset(dstsubdir))

                                        if dstsubdir and dstsubdir not in createddirs:
                                            if not os.path.exists(dstfpath):
                                                print('создаю каталог "%s"' % dstsubdir)
                                                os.makedirs(dstfpath)

                                            createddirs.add(dstsubdir)

                                        print('создаю файл "%s"' % dstfname)
                                        dstfpath = os.path.join(dstfpath, dstfname)

                                        with open(dstfpath, 'wb+') as dstf:
                                            remain = znfo.file_size
                                            while remain > 0:
                                                iosize = BLOCKSIZE if remain >= BLOCKSIZE else remain
                                                dstf.write(srcf.read(iosize))
                                                remain -= iosize

                                        if packtozip:
                                            with zipfile.ZipFile(dstfpath + '.zip', 'w', zipfile.ZIP_DEFLATED) as dstarcf:
                                                dstarcf.write(dstfpath, dstfname)
                                            os.remove(dstfpath)

                                    extractedbooks += 1

                                except zipfile.BadZipfile as ex:
                                    em.append('Ошибка при извлечении файла "%s" из архива "%s" - %s.' % (bookfname, bundlefpath, str(ex)))

                            if callable(progress):
                                progress(float(ixbook) / totalbooks)

                        if missingbooks > 0:
                            em.append('В архиве "%s" не нашлось несколько файлов (%d из %d).' % (bundlefpath, missingbooks, len(bundlebooks)))

                except zipfile.BadZipfile as ex:
                    em.append('Ошибка при работе с архивом "%s" - %s.' % (bundlefpath, str(ex)))

        if extractedbooks < totalbooks:
            em.append('Не извлечено ни одной книги.' if extractedbooks == 0 else 'Извлечено книг: %d из %d.' % (extractedbooks, totalbooks))

        return u'\n'.join(em) if em else None


if __name__ == '__main__':
    print('[test]')

    print('f', validate_fname_charset('опа/хопа:муу'))
    print('d', validate_dname_charset('опа/хопа:муу'))
    exit(0)


    import fbenv
    import fblib

    import fbfntemplate

    env = fbenv.Environment()
    cfg = fbenv.Settings(env)
    cfg.load()

    lib = fblib.LibraryDB(env.libraryFilePath)
    lib.connect()
    try:
        extractor = BookExtractor(lib, env, cfg)

        cur = lib.cursor.execute('''select bookid from books limit 30;''')
        r = cur.fetchall()
        if r is None:
            print('No books in library')
            exit()

        em = extractor.extract(map(lambda v: v[0], r), fbfntemplate.AuthorDirTitleSeriesTemplate())
        if em:
            print(em)
    finally:
        lib.disconnect()
