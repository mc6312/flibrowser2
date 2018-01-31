#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" fbfntemplate.py

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


"""Шаблоны имён файлов для распаковки книг.
Полноценных шаблонов, как в v1.х, пока (или совсем) не будет."""


from os.path import join as path_join


class Template():
    """Класс для генерации имён файлов на основе полей, полученных из БД.

    Поля (должны перекрываться классом-потомком):
        DISPLAY     - строка для отображения в UI выбора шаблона;
        NAME        - имя для файла настроек."""

    DISPLAY = 'Оригинальное имя файла'
    NAME = 'filename'

    def create_file_name(self, filename, title, seriestitle, serno, authorname):
        """Генерация имени каталога и имени файла (без расширения)
        на основе набора полей из БД.
        Метод должен быть перекрыт в классе-потомке.

        filename    - имя файла без расширения
        title       - название книги
        seriestitle - название цикла (или пустая строка)
        serno       - номер в цикле (целое, м.б. 0)
        authorname  - имя автора (авторов).

        Возвращает кортеж из двух элементов:
        1й - имя каталога или пустая строка;
        2й - имя файла без расширения.

        Метод Template.create_file_name() возвращает только имя файла
        без каталога."""

        return ('', filename)

    MAX_FIELD_LEN = 64
    ELLIPSIS = '…'

    def truncate_author_name(self, authorname):
        """Сокращение имени автора до ~MAX_FIELD_LEN символов.

        Т.к. в БД могут быть длинные "составные" имена вида
        "Автор1, Автор2, ...АвторN", то шаблоны, добавляющие имя автора
        в имя файла, должны использовать этот метод."""

        authors = list(map(lambda s: s.strip(), authorname.split(',')))
        numauthors = len(authors)

        authorname = ''

        ixauthor = 0
        for author in authors:
            ixauthor += 1

            if authorname:
                authorname += ', '

            authorname += author

            namelen = len(authorname)

            if namelen > self.MAX_FIELD_LEN:
                authorname = authorname[:self.MAX_FIELD_LEN] + self.ELLIPSIS
                break

        if ixauthor < numauthors:
            authorname += ' и еще %d' % (numauthors - ixauthor)

        return authorname

    def truncate_str(self, s):
        """Обрезает строку s до MAX_FIELD_LEN символов."""

        if len(s) > self.MAX_FIELD_LEN:
            s = s[:self.MAX_FIELD_LEN - 1] + self.ELLIPSIS

        return s


class TitleSeriesTemplate(Template):
    DISPLAY = 'Название книги (Название цикла - номер)'
    NAME = 'title-series'

    def create_file_name(self, filename, title, seriestitle, serno, authorname):
        """Создаёт имя файла на основе полей title, seriestitle, serno.
        Имя каталога не создаёт."""

        if seriestitle:
            seriestitle = '%s%s' % (self.truncate_str(seriestitle), '' if serno < 1 else ' - %d' % serno)

        return ('', '%s%s' % (self.truncate_str(title), '' if not seriestitle else ' (%s)' % seriestitle))


class AuthorDirTitleSeriesTemplate(TitleSeriesTemplate):
    DISPLAY = 'Имя автора/Название книги (Название цикла - номер)'
    NAME = 'authordir-title-series'

    def create_file_name(self, filename, title, seriestitle, serno, authorname):
        """Создаёт имя каталога на основе поля authorname.
        Имя файла создаётся так же, как в TitleSeriesTemplate.create_file_name()."""

        return (self.truncate_author_name(authorname),
            super().create_file_name(filename, title, seriestitle, serno, authorname)[1])


"""templates - список экземпляров классов шаблонов для UI"""

templates = [Template(), TitleSeriesTemplate(), AuthorDirTitleSeriesTemplate()]

"""templatenames - словарь, где ключи - имена шаблонов, а значения - номера элементов списка templates"""

templatenames = dict(map(lambda tc: (tc[1].NAME, tc[0]), enumerate(templates)))


if __name__ == '__main__':
    print('[test]')

    #print(templatenames)
    #exit(0)

    tpl = Template()

    names = ['Иванов Иван Иваныч, Вольдемар де Вульф де Мордехай де Акакий ибн Вольдемарыч Некрофекалоидов-оглы, Сидоров Сидор Сидорыч, Петров Пётр Петрович',
        'Волков Сергей Юрьевич, Галковский Дмитрий Евгеньевич, Зыкин Д, Кара-Мурза Сергей Георгиевич, Миронин Сигизмунд Сигизмундович, Скорынин Р, Федотова П']

    for name in names:
        ol = len(name)
        name = tpl.truncate_author_name(name)
        print('%d/%d, "%s"' % (ol, len(name), name))

    ttitle = 'Освежевание летающих и подвижных объектов подручным сельскохозяйственным инструментом в условиях средней полосы. Методы и приёмы.'
    tseriesname = 'Расчленение, освежевание и др. для чайников'

    tpl = TitleSeriesTemplate()
    print(tpl.create_file_name('13666', ttitle, tseriesname, 13, names[0]))

    tpl = AuthorDirTitleSeriesTemplate()
    print(tpl.create_file_name('13666', ttitle, tseriesname, 13, names[0]))
