#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" flibrowser2.py

    Copyright 2018 MC-6312 <mc6312@gmail.com>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>."""


from fbgtk import *

from gi.repository import Gtk, Gdk, GObject, Pango, GLib
from gi.repository.GdkPixbuf import Pixbuf

from fbcommon import *
from fbenv import *
from fblib import *
from fbextract import *
import fbfntemplate
from fbabout import AboutDialog
from fbsetup import SetupDialog

from collections import namedtuple

import os.path
import datetime

from time import time, sleep


class AlphaListChooser():
    """Обёртка над двумя таблицами - алфавитным списком, содержащим
    столбец alpha (см. далее colAlpha), и списком имён, содержащим
    столбцы id, alpha, name (название столбца alpha должно совпадать
    в обеих таблицах) и двумя Gtk.TreeView,
    в первом из которых - алфавитный список,
    во втором - список имён (например, первые буквы имён авторов
    и имена авторов)."""

    tableparams = namedtuple('tableparams', 'alphatablename nametablename colnameid colalpha colnametext emptyalphatext onnameselected')
    """Параметры таблицы, с которой работает AlphaListChooser:

        alphatablename      - имя таблицы в БД для списка имён
        nametablename       - имя таблицы в БД для алфавитного списка
        colnameid           - имя столбца с primary key в таблице имён
        colalpha            - имя столбца с 1й буквой (alpha) в таблицах alphatable и nametable
        colnametext         - имя столбца с отображаемым текстом в nametable
        emptyalphatext      - значение, отображаемое в alphalist, если alpha==''
        onnameselected      - функция или метод, обрабатывающие событие
                              "выбран элемент в списке namelist"
                              функция должна принимать один параметр -
                              значение selectedNameId."""

    # столбцы алфавитного списка
    COL_ALPHA_VALUE, COL_ALPHA_DISPLAY = range(2)

    # столбцы списка имён
    COL_NAME_ID, COL_NAME_TEXT = range(2)

    def __init__(self, lib):
        """Инициализация объекта и создание виджетов.

        lib - экземпляр fblib.LibraryDB."""

        self.lib = lib

        self.tableParams = None # сюда будет присвоен экземпляр AlphaListChooser.tableparams

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

        # когда-нибудь потом переделать - вместо размеров иконки брать ширину шрифта, напр. 1em
        self.alphalist.window.set_size_request(Gtk.IconSize.lookup(Gtk.IconSize.MENU)[1]*2, -1)

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

        entry = create_labeled_entry(hpanel, 'Имя:', self.nameentry_changed, True)
        entry_setup_clear_icon(entry)

    def connect_db_table(self, params):
        """Настройка на таблицу БД.

        params - экземпляр AlphaListChooser.tableparams."""

        self.tableParams = params

        self.update_alphalist()

    def update_alphalist(self):
        """Обновление алфавитного списка"""

        if self.tableParams is None:
            return

        # первые буквы имён авторов
        self.alphalist.view.set_model(None)
        self.alphalist.store.clear()

        q = 'select %s from %s order by %s;' %\
            (self.tableParams.colalpha, self.tableParams.alphatablename,
            self.tableParams.colalpha)
        #print(q)
        cur = self.lib.cursor.execute(q)

        while True:
            r = cur.fetchone()
            if r is None:
                break

            s = r[0]
            self.alphalist.store.append((s, s if s else self.tableParams.emptyalphatext))

        self.alphalist.view.set_model(self.alphalist.store)
        self.alphalist.view.set_search_column(self.COL_ALPHA_DISPLAY)

    def update_namelist(self):
        """Обновление списка имён"""

        if self.tableParams is None:
            return

        self.namelist.view.set_model(None)
        self.namelist.store.clear()

        if self.selectedAlpha is not None:
            cur = self.lib.cursor.execute('select %s,%s from %s where %s="%s" order by %s;' %\
                (self.tableParams.colnameid, self.tableParams.colnametext,
                self.tableParams.nametablename,
                self.tableParams.colalpha, self.selectedAlpha,
                self.tableParams.colnametext))

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
            self.selectedNameId = self.namelist.store.get_value(self.namelist.store.get_iter(rows[0]), self.COL_NAME_ID)
        else:
            self.selectedNameId = None

        if callable(self.tableParams.onnameselected):
            self.tableParams.onnameselected(self.selectedNameId)

    def nameentry_changed(self, entry, data=None):
        self.namePattern = entry.get_text().strip().lower()
        self.update_names()


class MainWnd():
    """Основное междумордие"""

    COL_AUTHALPHA_L1 = 0

    COL_AUTH_ID, COL_AUTH_NAME = range(2)

    COL_BOOK_ID, COL_BOOK_TITLE, COL_BOOK_SERNO, COL_BOOK_SERIES, \
    COL_BOOK_DATE, COL_BOOK_LANG = range(6)

    def destroy(self, widget, data=None):
        Gtk.main_quit()

    def wnd_configure_event(self, wnd, event):
        """Сменились размер/положение окна"""

        if not self.windowMaximized:
            self.cfg.set_param(self.cfg.MAIN_WINDOW_X, event.x)
            self.cfg.set_param(self.cfg.MAIN_WINDOW_Y, event.y)

            self.cfg.set_param(self.cfg.MAIN_WINDOW_W, event.width)
            self.cfg.set_param(self.cfg.MAIN_WINDOW_H, event.height)

    def wnd_state_event(self, widget, event):
        """Сменилось состояние окна"""

        self.windowMaximized = bool(event.new_window_state & Gdk.WindowState.MAXIMIZED)
        self.cfg.set_param_bool(self.cfg.MAIN_WINDOW_MAXIMIZED, self.windowMaximized)

    def load_window_state(self):
        """Загрузка и установка размера и положения окна"""

        wx = self.cfg.get_param_int(self.cfg.MAIN_WINDOW_X, None)
        if wx is not None:
            wy = self.cfg.get_param_int(self.cfg.MAIN_WINDOW_Y, None)
            self.window.move(wx, wy)

            ww = self.cfg.get_param_int(self.cfg.MAIN_WINDOW_W, 0) # все равно GTK не даст меньше допустимого съёжить
            wh = self.cfg.get_param_int(self.cfg.MAIN_WINDOW_H, 0)

            self.window.resize(ww, wh)

        wm = self.cfg.get_param_bool(self.cfg.MAIN_WINDOW_MAXIMIZED, False)
        if wm:
            self.window.maximize()

        self.task_events() # грязный хакЪ, дабы окно смогло поменять размер,
        # без спросу пошевелить HPaned, и т.п.

        pp = self.cfg.get_param_int(self.cfg.MAIN_WINDOW_HPANED_POS, 0)
        #print('loaded paned pos=%d' % pp)
        self.roothpaned.set_position(pp)

        self.windowStateLoaded = True

    def task_events(self):
        # даем прочихаться междумордию
        while Gtk.events_pending():
            Gtk.main_iteration()

    def begin_task(self, msg):
        self.ctlvbox.set_sensitive(False)
        self.task_msg(msg)

    def task_msg(self, msg):
        self.labmsg.set_text(msg)
        self.task_events()

    def end_task(self, msg=''):
        self.labmsg.set_text(msg)
        self.progressbar.set_fraction(0.0)
        self.ctlvbox.set_sensitive(True)

    def task_progress(self, fraction):
        self.progressbar.set_fraction(fraction)
        self.task_events()

    def update_books_by_authorid(self, authorid):
        self.bookListUpdateColName = 'authorid'
        self.bookListUpdateColValue = authorid
        self.update_books()

    def update_books_by_serid(self, serid):
        self.bookListUpdateColName = 'serid'
        self.bookListUpdateColValue = serid
        self.update_books()

    def __create_ui(self):
        self.windowMaximized = False
        self.windowStateLoaded = False

        self.window = Gtk.ApplicationWindow(Gtk.WindowType.TOPLEVEL)
        self.window.connect('configure_event', self.wnd_configure_event)
        self.window.connect('window_state_event', self.wnd_state_event)
        self.window.connect('destroy', self.destroy)

        headerbar = Gtk.HeaderBar()
        headerbar.set_show_close_button(True)
        headerbar.set_decoration_layout('menu:minimize,maximize,close')
        headerbar.set_title(TITLE)
        headerbar.set_subtitle(VERSION)

        self.window.set_titlebar(headerbar)

        #self.window.set_title(TITLE_VERSION)

        self.window.set_size_request(1024, 768)
        self.window.set_border_width(WIDGET_SPACING)

        self.dlgabout = AboutDialog(self.window, self.env)
        self.window.set_icon(self.dlgabout.windowicon)

        self.dlgsetup = SetupDialog(self.window, self.env, self.cfg)

        #
        # начинаем напихивать виджеты
        #

        rootvbox = Gtk.VBox(spacing=WIDGET_SPACING)
        self.window.add(rootvbox)

        # всё, кроме прогрессбара, кладём сюда, чтоб блокировать разом
        self.ctlvbox = Gtk.VBox(spacing=WIDGET_SPACING)
        rootvbox.pack_start(self.ctlvbox, True, True, 0)

        #
        # меню или тулбар (потом окончательно решу)
        #

        # Gtk.Toolbar - фпень, он уродский; меню тоже - слишком жирно из-за 3х элементов городить
        # пока так, а там видно будет
        #hbtb = Gtk.HBox(spacing=WIDGET_SPACING)
        #self.ctlvbox.pack_start(hbtb, False, False, 0)
        hbtb = headerbar

        # title, pack_end, handler
        tbitems = (('Настройка', 'preferences-system', 'Настройка программы', False, lambda b: self.change_settings()),
            ('Импорт библиотеки', 'document-open', 'Импорт индекса библиотеки', False, lambda b: self.import_library()),
            ('О программе', 'help-about', 'Информация о программе', True, lambda b: self.dlgabout.run()),)

        for label, iconname, tooltip, toend, handler in tbitems:
            btn = Gtk.Button.new_from_icon_name(iconname, Gtk.IconSize.BUTTON)# (label)
            btn.set_tooltip_text(tooltip)
            btn.connect('clicked', handler)

            (hbtb.pack_end if toend else hbtb.pack_start)(btn)#, False, False, 0)

        #
        # морда будет из двух вертикальных панелей
        #

        self.roothpaned = Gtk.HPaned()
        self.roothpaned.connect('notify::position', self.roothpaned_moved)
        self.ctlvbox.pack_start(self.roothpaned, True, True, 0)

        self.booklist = None
        # а реальное значение сюда сунем потом.
        # ибо alphachooser будет дёргать MainWnd.update_books_*,
        # и на момент вызова поле MainWnd.booklist уже должно существовать

        #
        # в левой панели - алфавитный список авторов
        # (из двух отдельных виджетов Gtk.TreeView)
        #
        self.alphaChooserParamsByAuthorId = AlphaListChooser.tableparams(
            'authornamealpha', 'authornames',
            'authorid', 'alpha', 'name', '<>',
            self.update_books_by_authorid)
        self.alphaChooserParamsBySerId = AlphaListChooser.tableparams(
            'seriesnamealpha', 'seriesnames',
            'serid', 'alpha', 'title', '<>',
            self.update_books_by_serid)

        fr = Gtk.Frame.new()
        self.roothpaned.pack1(fr, True, False)

        avbox = Gtk.VBox(spacing=WIDGET_SPACING)
        avbox.set_border_width(WIDGET_SPACING)
        # минимальная ширина - пока меряем в иконках
        # (но надо бы относительно размеров шрифта)
        avbox.set_size_request(Gtk.IconSize.lookup(Gtk.IconSize.MENU)[1]*24, -1)
        fr.add(avbox)

        # переключатель поиска по авторам или циклам

        ahbox = Gtk.HBox(spacing=WIDGET_SPACING)
        avbox.pack_start(ahbox, False, False, 0)

        self.rbauthors = Gtk.RadioButton.new_with_label(None, 'Авторы')
        ahbox.pack_start(self.rbauthors, False, False, 0)

        self.rbseries = Gtk.RadioButton.new_with_label_from_widget(self.rbauthors, 'Циклы/сериалы')
        ahbox.pack_start(self.rbseries, False, False, 0)

        # алфавитный список авторов или циклов
        self.alphachooser = AlphaListChooser(self.lib)
        self.alphachooser.connect_db_table(self.alphaChooserParamsByAuthorId)
        avbox.pack_end(self.alphachooser.box, True, True, 0)

        self.rbauthors.connect('toggled', self.switch_alphachooser, self.alphaChooserParamsByAuthorId)
        self.rbseries.connect('toggled', self.switch_alphachooser, self.alphaChooserParamsBySerId)
        self.rbauthors.set_active(True)

        #
        # в правой панели - список книг соотв. автора и управление распаковкой
        #

        self.bookframe = Gtk.Frame.new('Книги')
        self.roothpaned.pack2(self.bookframe, True, False)

        bpanel = Gtk.VBox(spacing=WIDGET_SPACING)
        bpanel.set_size_request(480, -1) #!!!
        bpanel.set_border_width(WIDGET_SPACING)
        self.bookframe.add(bpanel)

        # список книг

        self.booklist = TreeViewer(
            (GObject.TYPE_INT,      # bookid
                GObject.TYPE_STRING,# title
                GObject.TYPE_STRING,# series
                GObject.TYPE_STRING,# serno
                GObject.TYPE_STRING),# date
            (TreeViewer.ColDef(self.COL_BOOK_TITLE, 'Название', False, True),
                TreeViewer.ColDef(self.COL_BOOK_SERNO, '#', False, False, 1.0),
                TreeViewer.ColDef(self.COL_BOOK_SERIES, 'Цикл', False, True),
                TreeViewer.ColDef(self.COL_BOOK_DATE, 'Дата', markup=True)))

        self.booklist.view.connect('motion-notify-event', self.booklist_mouse_moved)

        self.booklist.selection.set_mode(Gtk.SelectionMode.MULTIPLE)
        self.booklist.selection.connect('changed', self.booklist_selected)

        bpanel.pack_start(self.booklist.window, True, True, 0)

        # фильтрация списка книг по названию книги и названию цикла
        blhbox = Gtk.HBox(spacing=WIDGET_SPACING)
        bpanel.pack_start(blhbox, False, False, 0)

        entry = create_labeled_entry(blhbox, 'Название:', self.booklisttitlepattern_changed, True)
        entry_setup_clear_icon(entry)

        #
        # панель с виджетами извлечения книг
        #

        self.extractframe = Gtk.Frame.new('Выбрано книг: 0')
        xfbox = Gtk.HBox(spacing=WIDGET_SPACING)
        xfbox.set_border_width(WIDGET_SPACING)
        self.extractframe.add(xfbox)
        self.ctlvbox.pack_start(self.extractframe, False, False, 0)

        # внезапно, кнопка
        self.btnextract = Gtk.Button('Извлечь')
        self.btnextract.connect('clicked', lambda b: self.extract_books())
        xfbox.pack_start(self.btnextract, False, False, 0)

        # выбор каталога
        xfbox.pack_start(Gtk.Label('в каталог'), False, False, 0)
        self.destdirchooser = Gtk.FileChooserButton.new('Выбор каталога для извлечения книг', Gtk.FileChooserAction.SELECT_FOLDER)

        self.destdirchooser.set_filename(self.cfg.get_param(self.cfg.EXTRACT_TO_DIRECTORY, os.path.expanduser('~')))
        self.destdirchooser.set_create_folders(True)
        self.destdirchooser.connect('selection-changed', self.dest_dir_changed)

        xfbox.pack_start(self.destdirchooser, True, True, 0)

        # как обзывать файлы
        xfbox.pack_start(Gtk.Label(', назвав файлы по образцу'), False, False, 0)

        self.extractfntemplatecb = Gtk.ComboBoxText()
        for fntplix, fntpl in enumerate(fbfntemplate.templates):
            self.extractfntemplatecb.append_text(fntpl.DISPLAY)

        self.extractfntemplatecb.set_active(self.extractTemplateIndex)
        self.extractfntemplatecb.connect('changed', self.extractfntemplatecb_changed)

        xfbox.pack_start(self.extractfntemplatecb, True, True, 0)

        self.extracttozipbtn = Gtk.CheckButton('и сжать ZIP')
        self.extracttozipbtn.set_active(self.cfg.get_param_bool(self.cfg.EXTRACT_PACK_ZIP, False))
        self.extracttozipbtn.connect('clicked', self.extracttozipbtn_clicked)

        xfbox.pack_start(self.extracttozipbtn, False, False, 0)

        #
        # прогрессбар (для распаковки и др.)
        #

        # потому как Gtk.ProgressBar со "своим" текстом в случае свежего GTK
        # и многих тем этот текст рисует слишком малозаметно
        self.labmsg = Gtk.Label()
        self.labmsg.set_ellipsize(Pango.EllipsizeMode.END)

        self.progressbar = Gtk.ProgressBar()
        rootvbox.pack_end(self.progressbar, False, False, 0)

        rootvbox.pack_end(self.labmsg, False, False, 0)
        #
        # заканчиваем напихивать виджеты
        #

        self.window.show_all()

        #print('loading window state')
        self.load_window_state()

    def __init__(self, lib, env, cfg):
        """Инициализация междумордия и загрузка настроек.
        lib, env, cfg - экземпляры LibraryDB, Environment и Settings соответственно."""

        self.lib = lib
        self.env = env
        self.cfg = cfg

        #
        # поддержка извлечения книг из архивов
        #
        self.extractor = BookExtractor(lib, env, cfg)

        extractTemplateName = self.cfg.get_param(self.cfg.EXTRACT_FILE_NAMING_SCHEME, 0)
        # если в БД настроек неправильное имя шаблона - не лаемся, а берем первый из списка
        if extractTemplateName in fbfntemplate.templatenames:
            self.extractTemplateIndex = fbfntemplate.templatenames[extractTemplateName]
        else:
            self.extractTemplateIndex = 0

        self.booksSelected = [] # список bookid, заполняется из self.booklist_selected

        #
        #
        #

        # поля для запроса в self.update_books(), заполняются из методов update_books_by_*
        self.bookListUpdateColName = None
        self.bookListUpdateColValue = None

        # строка для фильтрации booklist, заполняется из поля ввода
        self.booklistTitlePattern = ''

        # создаём междумордие
        self.__create_ui()

        self.check_1st_run()

        self.alphachooser.update_alphalist()

    def check_1st_run(self):
        """Проверка на первый запуск и, при необходимости, первоначальная настройка."""

        if not self.cfg.has_required_settings():
            if self.dlgsetup.run('Первоначальная настройка') != Gtk.ResponseType.OK:
                msg_dialog(self.window, TITLE_VERSION, 'Не могу работать без настройки', Gtk.MessageType.ERROR)
                exit(1) #!!!
            else:
                self.import_library()
        else:
            #print('check db')
            self.lib.init_tables()

    def import_library(self):
        self.begin_task('Импорт библиотеки')
        try:
            print('Инициализация БД (%s)...' % self.env.libraryFilePath)
            self.task_msg('Инициализация БД')
            self.lib.reset_tables()

            inpxFileName = self.cfg.get_param(self.cfg.IMPORT_INPX_INDEX)
            print('Импорт индекса библиотеки "%s"...' % inpxFileName)
            self.task_msg('Импорт индекса библиотеки')
            importer = INPXImporter(self.lib, self.cfg)
            importer.import_inpx_file(inpxFileName, self.task_progress)

            self.alphachooser.update_alphalist()

        finally:
            self.end_task()

    def switch_alphachooser(self, rbtn, tparams):
        if tparams is not None:
            self.alphachooser.connect_db_table(tparams)

    def roothpaned_moved(self, paned, data=None):
        pp = paned.get_position()
        #print('hpaned moved, wsl=%s, pos=%d' % (self.windowStateLoaded, pp))
        if self.windowStateLoaded:
            self.cfg.set_param_int(self.cfg.MAIN_WINDOW_HPANED_POS, pp)

    def change_settings(self):
        if self.dlgsetup.run() == Gtk.ResponseType.OK and self.dlgsetup.settingsChanged:
            self.import_library()

    def extractfntemplatecb_changed(self, cb, data=None):
        self.extractTemplateIndex = cb.get_active()
        if self.extractTemplateIndex < 0:
            self.extractTemplateIndex = 0

        self.cfg.set_param(self.cfg.EXTRACT_FILE_NAMING_SCHEME,
            fbfntemplate.templates[self.extractTemplateIndex].NAME)

    def extracttozipbtn_clicked(self, cb, data=None):
        self.cfg.set_param_bool(self.cfg.EXTRACT_PACK_ZIP, cb.get_active())

    def booklisttitlepattern_changed(self, entry, data=None):
        self.booklistTitlePattern = entry.get_text().strip().lower()
        self.update_books()

    def booklist_mouse_moved(self, lv, event):
        r = self.booklist.view.get_path_at_pos(event.x, event.y)
        if r is not None:
            mcolid = self.booklist.colmap[r[1]]

            if self.booklist.view.get_tooltip_column() != mcolid:
                self.booklist.view.set_tooltip_column(mcolid)

        return False

    def booklist_selected(self, sel, data=None):
        """Обработка события выбора элемента(ов) в списке книг"""

        rows = self.booklist.selection.get_selected_rows()[1]

        self.booksSelected.clear()

        if rows:
            for row in rows:
                self.booksSelected.append(self.booklist.store.get_value(self.booklist.store.get_iter(row), self.COL_BOOK_ID))

        nselbooks = len(self.booksSelected)
        self.btnextract.set_sensitive(nselbooks > 0)
        self.extractframe.set_label('Выбрано книг: %d' % nselbooks)

    def dest_dir_changed(self, chooser):
        self.cfg.set_param(self.cfg.EXTRACT_TO_DIRECTORY, chooser.get_filename())

    def extract_books(self):
        """Извлечение выбранных в списке книг"""
        self.begin_task('Извлечение книг...')
        try:
            em = ''
            ei = Gtk.MessageType.WARNING
            try:
                em = self.extractor.extract(self.booksSelected,
                    fbfntemplate.templates[self.extractTemplateIndex],
                    self.task_progress)

            except Exception as ex:
                if em:
                    em += '\n'
                elif em is None:
                    em = ''

                exs = str(ex)
                em += exs if exs else ex.__class__.__error__
                ei = Gtk.MessageType.ERROR

            if em:
                msg_dialog(self.window, 'Извлечение книг', em, ei)

        finally:
            self.end_task()

    def update_books(self):
        """Обновление списка книг.

        idcolname   - имя столбца в таблице books для запроса к БД,
        idcolvalue  - значение столбца для запроса."""

        if self.booklist is None:
            return

        self.booklist.view.set_model(None)
        self.booklist.store.clear()

        cur = self.lib.cursor.execute('select count(*) from books;')
        r = cur.fetchone()
        stotalbooks = '?' if r is None else '%d' % r[0]
        nbooks = 0

        if self.bookListUpdateColValue is not None:
            q = '''select bookid,books.title,serno,seriesnames.title,date,language
                from books inner join seriesnames on seriesnames.serid=books.serid
                where books.%s=?
                order by seriesnames.title, serno, books.title, date;''' % self.bookListUpdateColName
            #print(q)
            cur = self.lib.cursor.execute(q, (self.bookListUpdateColValue,))
            # для фильтрации по дате сделать втык в запрос подобного:
            #  and (date > "2014-01-01") and (date < "2016-12-31")

            datenow = datetime.datetime.now()

            while True:
                r = cur.fetchone()
                if r is None:
                    break

                nbooks += 1

                # поля, которые могут потребовать доп. телодвижений
                title = r[1]
                seriestitle = r[3]

                # подразумеваятся, что в соотв. поле БД точно есть хоть какая-то дата
                date = datetime.datetime.strptime(r[4], DB_DATE_FORMAT)
                # тут, возможно, будет код для показа соответствия "дата - цвет 'свежести' книги"
                # и/или фильтрация по дате
                datestr = '<span color="%s">⬛</span> %s' % (get_book_age_color(datenow, date), date.strftime(DISPLAY_DATE_FORMAT))

                # дополнительная фильтрация вручную, т.к. sqlite3 "из коробки"
                # не умеет в collation, и вообще что-то проще сделать не через запросы SQL

                if self.booklistTitlePattern:
                    if title.lower().find(self.booklistTitlePattern) < 0 \
                        and seriestitle.lower().find(self.booklistTitlePattern) < 0:
                        continue

                serno = r[2]

                self.booklist.store.append((r[0], # bookid
                    title, # books.title
                    str(serno) if serno > 0 else '', # serno
                    seriestitle, # seriesnames.title
                    datestr, # date
                    ))

        self.booklist.view.set_model(self.booklist.store)
        self.booklist.view.set_search_column(self.COL_BOOK_TITLE)
        self.booklist.view.set_search_equal_func(self.booklist_search_func)

        self.bookframe.set_label('Книги (%d из %s)' % (nbooks, stotalbooks))

    def booklist_search_func(self, model, column, key, _iter, data=None):
        """Штатная функция сравнивает key с началом строки в столбце column,
        а эта будет искать любое вхождение key в нескольких столбцах.
        Внимание! При успешном сравнении функция должна возвращать False!
        См. документацию по GTK."""

        key = key.upper()

        if model.get_value(_iter, self.COL_BOOK_TITLE).upper().find(key) >= 0:
            return False

        if model.get_value(_iter, self.COL_BOOK_SERIES).upper().find(key) >= 0:
            return False

        return True

    def main(self):
        Gtk.main()


def main():
    env = Environment()
    cfg = Settings(env)

    cfg.load()
    try:
        #inpxFileName = cfg.get_param(cfg.IMPORT_INPX_INDEX)
        #genreNamesFile = cfg.get_param(cfg.GENRE_NAMES_PATH)

        dbexists = os.path.exists(env.libraryFilePath)
        lib = LibraryDB(env.libraryFilePath)
        lib.connect()
        try:
            if not dbexists:
                lib.init_tables()

            mainwnd = MainWnd(lib, env, cfg)
            mainwnd.main()
        finally:
            lib.disconnect()
    finally:
        cfg.unload()

    return 0


if __name__ == '__main__':
    exit(main())
