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

from collections import namedtuple

from fbdb import DB_DATE_FORMAT
from fblib import LibraryDB


filterfields = namedtuple('filterfields', 'bookid title serno sertitle date authorname')
"""bookid   целое; идентификатор книги, primary key в таблице books
title       строка; название книги
serno       целое; номер в цикле/сериале
sertitle    строка; название цикла или сериала
date        datetime.date; дата добавления книги в библиотеку
authorname  строка; имя автора (авторов)."""

FILTER_FIELD_BOOKID, FILTER_FIELD_TITLE, FILTER_FIELD_SERNO, \
    FILTER_FIELD_SERTITLE, FILTER_FIELD_DATE, FILTER_FIELD_AUTHORNAME = range(6)

class FilterChooser():
    """Базовый класс для обёртки над виджетами фильтрации"""

    LABEL = ''
    RANDOM = False

    def __init__(self, lib, onchoosed):
        """Инициализация.
        Этот конструктор должен быть перекрыт в классе-потомке
        с помощью super().

        Параметры:
        lib         - экземпляр fblib.LibraryDB,
        onchoosed   - функция или метод без параметров, обрабатывающие
                      событие "выбран элемент в списке";
                      функцияя должна заполнить список книг,
                      используя chooser.selectWhere и вызывая
                      chooser.filter_books().

        Поля:
        LABEL       - строка для отображения в UI,
        RANDOM      - может ли использоваться для случайного выбора:
                      если False, то метод random_choice вызываться
                      не должен (или должен содержать заглушку,
                      ничего не делающую),
        box         - экземпляр Gtk.VBox, доступный "снаружи" для вставки
                      в UI; все виджеты chooser'а должны быть вложены
                      в него;
        selectWhere - строка параметров, подставляемых в SQL-запрос
                      после WHERE в flibrowser2.update_books();
                      значение присваивается из потрохов класса-потомка;
                      может быть None, если в chooser'е ничего не выбрано
                      и список книг должен быть пуст;
        firstWidget - None или экземпляр класса Gtk.Widget, который должен
                      получить фокус ввода при активации chooser'а;
        defaultWidget - None или экземпляр класса Gtk.Widget;
                      используется основным окном программы для вызовов
                      window.set_default() при активации/деактивации
                      панели chooser'а."""

        if not callable(onchoosed):
            raise ValueError('%s.__init__(): onchoose is not callable' % self.__class__.__name__)

        self.lib = lib
        self.onchoosed = onchoosed

        self.box = Gtk.VBox(spacing=WIDGET_SPACING)
        self.box.set_border_width(WIDGET_SPACING)
        # бордюр - потому что снаружи это будет всунуто в виде страницы в Gtk.Notebook

        self.selectWhere = None
        self.defaultWidget = None
        self.firstWidget = None

    def do_on_choosed(self):
        """Вызов self.onchoosed "снаружи".
        Вызывается в т.ч. при активации виджета
        выбора. Если немедленное обновление
        списка книг в основном окне не нужно,
        этот метод должен быть перекрыт заглушкой."""

        self.onchoosed()

    def random_choice(self):
        """Случайный выбор элемента списка.
        Метод ДОЛЖЕН быть перекрыт классом-потомком,
        если поле RANDOM == True."""

        if self.RANDOM:
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

    RANDOM = True

    # эти поля должны быть перекрыты в классе-потомке!
    ALPHATABLENAME      = None # имя таблицы в БД для списка имён
    NAMETABLENAME       = None # имя таблицы в БД для алфавитного списка
    COLNAMEID           = None # имя столбца с primary key в таблице имён
    COLALPHA            = None # имя столбца с 1й буквой (alpha) в таблицах alphatable и nametable
    COLNAMETEXT         = None # имя столбца с отображаемым текстом в nametable
    EMPTYALPHATEXT      = None # значение, отображаемое в alphalist, если alpha==''
    FAVORITEPARAMS      = None # экземпляр LibraryDB.favorite_params
                               # (см. FAVORITE_*_PARAMS в fblib.LibraryDB)

    ENTRYLABEL = '' # текст метки поля ввода

    # столбцы алфавитного списка
    COL_ALPHA_VALUE, COL_ALPHA_DISPLAY = range(2)

    # столбцы списка имён
    COL_NAME_ID, COL_NAME_FAVORITE, COL_NAME_TEXT = range(3)

    def __init__(self, lib, onchoosed):
        """Инициализация объекта и создание виджетов."""

        super().__init__(lib, onchoosed)

        self.onfavoriteclicked = None
        # метод или функция, вызываемые при нажатии "Enter" на строке
        # списка имён или при двойном клике на левом столбце строки списка;
        # функция не получает параметров

        # буква, выбранная в self.alphalist
        self.selectedAlpha = None

        # строка для фильтрации self.namelist
        self.namePattern = ''

        hbox = Gtk.HBox(spacing=WIDGET_SPACING)
        self.box.pack_start(hbox, True, True, 0)

        #
        # алфавитный список
        #
        self.alphalist = TreeViewer((GObject.TYPE_STRING, GObject.TYPE_STRING),
            (TreeViewer.ColDef(self.COL_ALPHA_DISPLAY, '', False, True),))

        #self.alphalist.window.set_size_request(WIDGET_BASE_UNIT * 6, -1)
        self.alphalist.window.set_min_content_width(WIDGET_BASE_UNIT * 3)

        self.alphalist.view.set_headers_visible(False)
        self.alphalist.view.set_enable_search(True)
        hbox.pack_start(self.alphalist.window, False, False, 0)

        self.alphalist.selection.set_mode(Gtk.SelectionMode.SINGLE)
        self.alphalist.selection.connect('changed', self.alphalist_selected)

        #
        # список имён
        #
        self.namelist = TreeViewer(
            # id, name
            (GObject.TYPE_INT, Pixbuf, GObject.TYPE_STRING),
            (TreeViewer.ColDef(self.COL_NAME_FAVORITE, '', False, False),
             TreeViewer.ColDef(self.COL_NAME_TEXT, '', False, True),)
            )
        self.namelist.columns[0].set_min_width(MENU_ICON_SIZE_PIXELS)

        self.namelist.view.set_headers_visible(False)
        self.namelist.view.set_enable_search(True)
        self.namelist.view.set_tooltip_column(self.COL_NAME_TEXT)

        self.namelist.selection.connect('changed', self.namelist_selected)
        self.namelist.view.connect('row-activated', self.namelist_clicked)

        hbox.pack_end(self.namelist.window, True, True, 0)

        hpanel = Gtk.HBox(spacing=WIDGET_SPACING)
        self.box.pack_end(hpanel, False, False, 0)

        entry = create_labeled_entry(hpanel, self.ENTRYLABEL, self.nameentry_changed, True)
        entry_setup_clear_icon(entry)

        self.firstWidget = self.alphalist.view

        #self.update_alphalist() #?

    def update(self):
        """Обновление алфавитного списка"""

        # первые буквы имён авторов
        self.alphalist.view.set_model(None)
        self.alphalist.store.clear()

        q = 'SELECT %s FROM %s ORDER BY %s;' %\
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

        F_FAVNAME, F_ID, F_TEXT = range(3)

        if self.selectedAlpha is not None:
            favnamecol = '%s.name' % self.FAVORITETABLENAME
            namecol = '%s.%s' % (self.NAMETABLENAME, self.COLNAMETEXT)

            q = '''SELECT %s,%s,%s
                FROM %s
                LEFT JOIN %s ON %s=%s
                WHERE %s="%s"
                ORDER BY %s;''' %\
                (favnamecol, self.COLNAMEID, namecol,
                self.NAMETABLENAME,
                self.FAVORITETABLENAME, namecol, favnamecol,
                self.COLALPHA, self.selectedAlpha,
                namecol)
            #print(q)

            cur = self.lib.cursor.execute(q)

            while True:
                r = cur.fetchone()
                if r is None:
                    break

                # фильтрация по начальным буквам имени автора.
                # вручную, ибо лень прикручивать collation к sqlite3

                if self.namePattern and not r[F_TEXT].lower().startswith(self.namePattern):
                    continue

                # 2й элемент - Pixbuf, иконка "избранное/неизбранное"
                self.namelist.store.append((r[F_ID],
                    iconStarred if r[F_FAVNAME] else None,
                    r[F_TEXT]))

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

    def namelist_clicked(self, view, path, col):
        """Обработка двойного клика или нажатия "Enter" на строке
        в списке имён.
        И, соответственно, добавление/удаление соотв. элемента в/из
        списка избранного."""

        col = self.namelist.colmap[col]
        storeiter = self.namelist.store.get_iter(path)

        icon, name = self.namelist.store.get(storeiter,
            self.COL_NAME_FAVORITE, self.COL_NAME_TEXT)

        if icon is None:
            self.lib.add_favorite(self.FAVORITETABLENAME, name)
            icon = iconStarred
        else:
            self.lib.remove_favorite(self.FAVORITETABLENAME, name)
            icon = None

        self.namelist.store.set_value(storeiter, self.COL_NAME_FAVORITE, icon)

        #print('onfavoriteclicked:', self.onfavoriteclicked)
        if callable(self.onfavoriteclicked):
            self.onfavoriteclicked()

    def namelist_selected(self, sel, data=None):
        """Обработка события выбора элемента(ов) в списке имён."""

        rows = self.namelist.selection.get_selected_rows()[1]

        if rows:
            self.selectWhere = 'books.%s=%s' % (self.COLNAMEID,
                self.lib.sqlite_quote(self.namelist.store.get_value(self.namelist.store.get_iter(rows[0]), self.COL_NAME_ID)))
        else:
            self.selectWhere = None

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
    FAVORITETABLENAME = LibraryDB.TABLE_FAVORITE_AUTHORS

    ENTRYLABEL = 'Имя:'


class SeriesAlphaListChooser(AlphaListChooser):
    LABEL = 'Циклы/сериалы'

    ALPHATABLENAME = 'seriesnamealpha'  # имя таблицы в БД для списка имён
    NAMETABLENAME = 'seriesnames'       # имя таблицы в БД для алфавитного списка
    COLNAMEID = 'serid'                 # имя столбца с primary key в таблице имён
    COLALPHA = 'alpha'                  # имя столбца с 1й буквой (alpha) в таблицах alphatable и nametable
    COLNAMETEXT = 'title'               # имя столбца с отображаемым текстом в nametable
    EMPTYALPHATEXT = '<>'               # значение, отображаемое в alphalist, если alpha==''
    FAVORITETABLENAME = LibraryDB.TABLE_FAVORITE_SERIES

    ENTRYLABEL = 'Название:'


class SearchFilterChooser(FilterChooser):
    """Фильтр поиска по произвольному тексту
    в нескольких полях."""

    LABEL = 'Поиск'
    RANDOM = False

    # индексы self.entries
    FLD_AUTHORNAME, FLD_BOOKTITLE, FLD_SERTITLE, FLD_BOOKID = range(4)

    # соответствие полей filterfields и self.values
    FLDMAP = {FLD_AUTHORNAME:FILTER_FIELD_AUTHORNAME,
        FLD_BOOKTITLE:FILTER_FIELD_AUTHORNAME,
        FLD_SERTITLE:FILTER_FIELD_SERTITLE,
        FLD_BOOKID:FILTER_FIELD_BOOKID}

    class SearchFilterStrEntry():
        def __init__(self, entry, colname, onchange):
            """Класс-обёртка для Gtk.Entry.

            entry       - экземпляр Gtk.Entry,
            colname     - имя столбца в БД,
            onchange    - функция, вызываемая после изменения содержимого."""

            self.entry = entry
            self.entry.connect('changed', self.entry_changed)

            self.colname = colname

            self.value = None

            self.onchange = onchange

        def clear(self):
            self.entry.set_text('')

        def entry_changed(self, entry):
            """Содержимое поля ввода изменилось."""

            self.value = self.validate_value(entry.get_text().strip())
            self.onchange()

        def validate_value(self, s):
            """Преобразование строки s в необходимый тип и проверка
            значения. В случае неправильного значения возвращает None,
            иначе возвращает значение.
            Для регистронезависимого сравнения строковых значений
            прикручен не шибко быстрый костыль в виде функции
            ulower() - см. в модуле fbdb, и соотв. её вызова
            при генерации куска запроса в get_where_param().
            Для полей с нестроковыми значениями метод должен быть
            перекрыт классом-потомком."""

            return s.lower()

        def get_where_param(self):
            """Возвращает параметр для WHERE-части SQL-запроса,
            или пустую строку, если self.value==None.

            Метод должен быть перекрыт классом-потомком для
            нестроковых значений."""

            if not self.value:
                return ''

            #v.lower()
            return 'ulower(%s) LIKE "%%%s%%"' % (self.colname, self.value)

    class SearchFilterIntEntry(SearchFilterStrEntry):
        def validate_value(self, s):
            try:
                v = int(s)
                if v <= 0:
                    return None
                else:
                    return v
            except ValueError:
                return None

        def get_where_param(self):
            return '' if not self.value else '%s=%d' % (self.colname, self.value)

    FLD_DEFS = (('Имя автора', 'authornames.name', -1, -1, True, SearchFilterStrEntry),
        ('Название книги', 'books.title', -1, -1, True, SearchFilterStrEntry),
        ('Название цикла/сериала', 'seriesnames.title', -1, -1, True, SearchFilterStrEntry),
        ('Id книги', 'books.bookid', 8, 12, False, SearchFilterIntEntry))

    def __init__(self, lib, onchoosed):
        """Инициализация."""

        super().__init__(lib, onchoosed)

        grid = LabeledGrid()
        self.box.pack_start(grid, False, False, 0)

        self.entries = []

        self.datefrom = None
        self.dateto = None

        #
        # поля ввода имени автора, названия книги и т.п.
        #
        for eix, (labtxt, colname, maxlen, cwidth, eexpand, eclass) in enumerate(self.FLD_DEFS):
            grid.append_row('%s:' % labtxt)

            entry = eclass(Gtk.Entry(), colname, self.values_changed)

            entry_setup_clear_icon(entry.entry)
            entry.entry.set_activates_default(True)

            if maxlen > 0:
                entry.entry.set_max_length(maxlen)

            if cwidth > 0:
                #entry.entry.set_max_width_chars(cwidth)
                entry.entry.set_width_chars(cwidth)

            self.entries.append(entry)
            grid.append_col(entry.entry, expand=eexpand)

        self.firstWidget = self.entries[0].entry

        #
        # кнопки (создаём заранее, т.к. кнопка "искать" должна уже
        # существовать на момент создания полей даты (ибо её дергает
        # обработчик событий изменения даты)
        #
        hbox = Gtk.HBox(spacing=WIDGET_SPACING)

        btnreset = Gtk.Button('Очистить')
        btnreset.connect('clicked', lambda b: self.reset_entries())
        hbox.pack_start(btnreset, False, False, 0)

        self.btnfind = Gtk.Button('Искать')
        self.btnfind.set_sensitive(False) # потом включится, после ввода значений
        self.btnfind.set_can_default(True)
        self.btnfind.connect('clicked', lambda b: self.do_search())

        hbox.pack_end(self.btnfind, False, False, 0)

        self.defaultWidget = self.btnfind

        self.box.pack_end(hbox, False, False, 0)
        self.box.pack_end(Gtk.HSeparator(), False, False, 0)

        #
        # выбор даты от/до
        #
        grid.append_row('Дата:')

        datehbox = Gtk.VBox()#spacing=WIDGET_SPACING)

        self.datefromchooser = DateChooser('не старше', ondatechanged=self.datefrom_changed)
        datehbox.pack_start(self.datefromchooser.container, False, False, 0)

        self.datetochooser = DateChooser('не новее', ondatechanged=self.dateto_changed)
        datehbox.pack_start(self.datetochooser.container, False, False, 0)

        grid.append_col(datehbox, True)

    def datefrom_changed(self, date):
        self.datefrom = date
        self.values_changed()

    def dateto_changed(self, date):
        self.dateto = date
        self.values_changed()

    def do_search(self):
        """Создаём параметр для запроса и пинаем главное окно"""

        # формируем параметры запроса
        where = []

        # для полей "имя автора" и подобных
        for entry in self.entries:
            v = entry.get_where_param()
            if v:
                where.append(v)

        # для полей даты от/до
        datefromoper = '>='
        datetooper = '<='

        if self.datefrom is not None and self.dateto is not None:
            if self.datefrom > self.dateto:
                # чтоб не вводить лишние проверки при обработке событий гуЯ
                # когда введены даты не в том порядке
                datefromoper = '<='
                datetooper = '>='

        def __add_date(date, cmpoper):
            if date is not None:
                where.append('date %s %s' % (cmpoper,
                    self.lib.sqlite_quote(date.strftime(DB_DATE_FORMAT))))

        __add_date(self.datefrom, datefromoper)
        __add_date(self.dateto, datetooper)

        # формируем параметры запроса
        self.selectWhere = ' AND '.join(where)
        #print(self.selectWhere)

        self.onchoosed()

    def reset_entries(self):
        for entry in self.entries:
            entry.clear()

        self.datefromchooser.checkbox.set_active(False)
        self.datetochooser.checkbox.set_active(False)

    def values_changed(self):
        n = len(self.entries)

        for entry in self.entries:
            if not entry.value:
                n -= 1

        if self.datefrom is not None:
            n += 1

        if self.dateto is not None:
            n += 1

        ne = n > 0 # хоть одно непустое значение

        self.btnfind.set_sensitive(ne)
        if ne:
            # на всякий случай
            self.btnfind.grab_default()

    def update(self):
        """Обновление содержимого виджетов из БД (self.lib).

        SearchFilterChooser этого не требует."""

        return

    def do_on_choosed(self):
        """Не нужен, ибо список книг должен обновляться только
        по кнопке на панели поиска.

        А кнопка сама вызовет self.onchoosed."""

        return


if __name__ == '__main__':
    print('[test]')

    def __onchoosed():
        print('__onchoosed() called, selectWhere="%s"' % chooser.selectWhere)

    import fbenv
    import fblib

    env = fbenv.Environment()
    lib = fblib.LibraryDB(env.libraryFilePath)
    lib.connect()
    try:
        window = Gtk.ApplicationWindow(Gtk.WindowType.TOPLEVEL)
        window.connect('destroy', lambda w: Gtk.main_quit())

        window.set_size_request(400, 800)

        def fav_clicked():
            print('fav_clicked')

        #chooser = AuthorAlphaListChooser(lib, __onchoosed)
        #chooser.onfavoriteclicked = fav_clicked
        #chooser.update()
        chooser = SearchFilterChooser(lib, __onchoosed)
        window.add(chooser.box)
        window.set_default(chooser.defaultWidget)

        window.show_all()
        Gtk.main()

    finally:
        lib.disconnect()
