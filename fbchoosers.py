#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" fbchoosers.py

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


"""Классы для выбора по авторам/циклам/..."""


from fbgtk import *

from gi.repository import Gtk, Gdk, GObject, Pango, GLib
from gi.repository.GdkPixbuf import Pixbuf

from random import randrange


class FilterChooser():
    """Базовый класс для обёртки над виджетами фильтрации"""

    LABEL = ''

    def __init__(self, lib, onchoosed):
        """Инициализация.
        Этот конструктор должен быть перекрыт в классе-потомке
        с помощью super().

        Параметры:
        lib         - экземпляр fblib.LibraryDB,
        onchoosed   - функция или метод, обрабатывающие событие
                      "выбран элемент в списке";
                      функция должна принимать один параметр -
                      значение primary key выбранной сущности.

        Поля:
        LABEL       - строка для отображения в UI,
        box         - виджет, доступный "снаружи" для вставки в UI,
        selectedId  - primary key выбранной сущности;
                      значение присваивается из потрохов класса-потомка."""

        if not callable(onchoosed):
            raise ValueError('%s.__init__(): onchoose is not callable' % self.__class__.__name__)

        self.lib = lib
        self.onchoosed = onchoosed
        self.box = None
        self.selectedId = None

    def do_on_choosed(self):
        """Вызов self.onchoosed "снаружи"."""

        self.onchoosed(self.selectedId)

    def random_choice(self):
        """Случайный выбор элемента списка.
        Метод ДОЛЖЕН быть перекрыт классом-потомком."""

        raise NotImplementedError('%s.random_choice() must be implemented' % self.__class__.__name__)

    def update(self):
        """Обновление содержимого виджетов из БД (self.lib).
        Метод ДОЛЖЕН быть перекрыт классом-потомком."""

        raise NotImplementedError('%s.update() must be implemented' % self.__class__.__name__)


class AlphaListChooser(FilterChooser):
    """Обёртка над двумя таблицами - алфавитным списком, содержащим
    столбец alpha (см. далее colAlpha), и списком имён, содержащим
    столбцы id, alpha, name (название столбца alpha должно совпадать
    в обеих таблицах) и двумя Gtk.TreeView,
    в первом из которых - алфавитный список,
    во втором - список имён (например, первые буквы имён авторов
    и имена авторов)."""

    # эти поля должны быть перекрыты в классе-потомке!
    ALPHATABLENAME      = None # имя таблицы в БД для списка имён
    NAMETABLENAME       = None # имя таблицы в БД для алфавитного списка
    COLNAMEID           = None # имя столбца с primary key в таблице имён
    COLALPHA            = None # имя столбца с 1й буквой (alpha) в таблицах alphatable и nametable
    COLNAMETEXT         = None # имя столбца с отображаемым текстом в nametable
    EMPTYALPHATEXT      = None # значение, отображаемое в alphalist, если alpha==''

    ENTRYLABEL = '' # текст метки поля ввода

    # столбцы алфавитного списка
    COL_ALPHA_VALUE, COL_ALPHA_DISPLAY = range(2)

    # столбцы списка имён
    COL_NAME_ID, COL_NAME_TEXT = range(2)

    def __init__(self, lib, onchoosed):
        """Инициализация объекта и создание виджетов."""

        super().__init__(lib, onchoosed)

        # буква, выбранная в self.alphalist
        self.selectedAlpha = None

        # строка для фильтрации self.namelist
        self.namePattern = ''

        #
        self.box = Gtk.VBox(spacing=WIDGET_SPACING)

        hbox = Gtk.HBox(spacing=WIDGET_SPACING)
        self.box.pack_start(hbox, True, True, 0)

        # алфавитный список
        self.alphalist = TreeViewer((GObject.TYPE_STRING, GObject.TYPE_STRING),
            (TreeViewer.ColDef(self.COL_ALPHA_DISPLAY, '', False, True),))

        self.alphalist.window.set_size_request(WIDGET_WIDTH_UNIT*3, -1)

        self.alphalist.view.set_headers_visible(False)
        self.alphalist.view.set_enable_search(True)
        hbox.pack_start(self.alphalist.window, False, False, 0)

        self.alphalist.selection.set_mode(Gtk.SelectionMode.SINGLE)
        self.alphalist.selection.connect('changed', self.alphalist_selected)

        # список имён
        self.namelist = TreeViewer(
            # id, name
            (GObject.TYPE_INT, GObject.TYPE_STRING),
            (TreeViewer.ColDef(self.COL_NAME_TEXT, '', False, True),))

        self.namelist.view.set_headers_visible(False)
        self.namelist.view.set_enable_search(True)
        self.namelist.view.set_tooltip_column(self.COL_NAME_TEXT)

        self.namelist.selection.connect('changed', self.namelist_selected)

        hbox.pack_end(self.namelist.window, True, True, 0)

        hpanel = Gtk.HBox(spacing=WIDGET_SPACING)
        self.box.pack_end(hpanel, False, False, 0)

        entry = create_labeled_entry(hpanel, self.ENTRYLABEL, self.nameentry_changed, True)
        entry_setup_clear_icon(entry)

        #self.update_alphalist() #?

    def update(self):
        """Обновление алфавитного списка"""

        # первые буквы имён авторов
        self.alphalist.view.set_model(None)
        self.alphalist.store.clear()

        q = 'select %s from %s order by %s;' %\
            (self.COLALPHA, self.ALPHATABLENAME,
            self.COLALPHA)
        #print(q)
        cur = self.lib.cursor.execute(q)

        while True:
            r = cur.fetchone()
            if r is None:
                break

            s = r[0]
            self.alphalist.store.append((s, s if s else self.EMPTYALPHATEXT))

        self.alphalist.view.set_model(self.alphalist.store)
        self.alphalist.view.set_search_column(self.COL_ALPHA_DISPLAY)

    def update_namelist(self):
        """Обновление списка имён"""

        self.namelist.view.set_model(None)
        self.namelist.store.clear()

        if self.selectedAlpha is not None:
            cur = self.lib.cursor.execute('select %s,%s from %s where %s="%s" order by %s;' %\
                (self.COLNAMEID, self.COLNAMETEXT,
                self.NAMETABLENAME,
                self.COLALPHA, self.selectedAlpha,
                self.COLNAMETEXT))

            while True:
                r = cur.fetchone()
                if r is None:
                    break

                # фильтрация по начальным буквам имени автора.
                # вручную, ибо лень прикручивать collation к sqlite3

                if self.namePattern and not r[1].lower().startswith(self.namePattern):
                    continue

                self.namelist.store.append((r[0], r[1]))

        self.namelist.view.set_model(self.namelist.store)
        self.namelist.view.set_search_column(self.COL_NAME_TEXT)

    def alphalist_selected(self, sel, data=None):
        """Обработка события выбора элемента(ов) в списке первых букв имён"""

        rows = self.alphalist.selection.get_selected_rows()[1]
        if rows:
            self.selectedAlpha = self.alphalist.store.get_value(self.alphalist.store.get_iter(rows[0]), self.COL_ALPHA_VALUE)
        else:
            self.selectedAlpha = None

        #print('"%s"' % self.selectedAlpha)

        self.update_namelist()

    def namelist_selected(self, sel, data=None):
        """Обработка события выбора элемента(ов) в списке имён"""

        rows = self.namelist.selection.get_selected_rows()[1]

        if rows:
            self.selectedId = self.namelist.store.get_value(self.namelist.store.get_iter(rows[0]), self.COL_NAME_ID)
        else:
            self.selectedId = None

        self.do_on_choosed()

    def nameentry_changed(self, entry, data=None):
        self.namePattern = entry.get_text().strip().lower()
        self.update_namelist()

    def random_choice(self):
        """Выбор случайных элементов в алфавитном и именном списках.
        Возвращает True в случае успеха и False, если не из чего выбирать."""

        if self.alphalist.random_choice():
            return self.namelist.random_choice()
        else:
            return False


class AuthorAlphaListChooser(AlphaListChooser):
    LABEL = 'Авторы'

    ALPHATABLENAME = 'authornamealpha'  # имя таблицы в БД для списка имён
    NAMETABLENAME = 'authornames'       # имя таблицы в БД для алфавитного списка
    COLNAMEID = 'authorid'              # имя столбца с primary key в таблице имён
    COLALPHA = 'alpha'                  # имя столбца с 1й буквой (alpha) в таблицах alphatable и nametable
    COLNAMETEXT = 'name'                # имя столбца с отображаемым текстом в nametable
    EMPTYALPHATEXT = '<>'               # значение, отображаемое в alphalist, если alpha==''

    ENTRYLABEL = 'Имя:'


class SeriesAlphaListChooser(AlphaListChooser):
    LABEL = 'Циклы/сериалы'

    ALPHATABLENAME = 'seriesnamealpha'  # имя таблицы в БД для списка имён
    NAMETABLENAME = 'seriesnames'       # имя таблицы в БД для алфавитного списка
    COLNAMEID = 'serid'                 # имя столбца с primary key в таблице имён
    COLALPHA = 'alpha'                  # имя столбца с 1й буквой (alpha) в таблицах alphatable и nametable
    COLNAMETEXT = 'title'               # имя столбца с отображаемым текстом в nametable
    EMPTYALPHATEXT = '<>'               # значение, отображаемое в alphalist, если alpha==''

    ENTRYLABEL = 'Название:'
