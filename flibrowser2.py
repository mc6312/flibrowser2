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

from gi.repository import Gtk, Gdk, GObject, Pango
from gi.repository.GdkPixbuf import Pixbuf
from gi.repository.GLib import markup_escape_text

from fbcommon import *
from fbenv import *
from fblib import *
from fbextract import *
import fbfntemplate
from fbabout import AboutDialog
from fbsetup import SetupDialog
from fbchoosers import *

from collections import namedtuple

import os.path
import datetime

from time import time, sleep
from random import randrange


class MainWnd():
    """Основное междумордие"""

    # индексы столбцов в Gtk.ListStore списка книг
    COL_BOOK_ID, COL_BOOK_AUTHOR, COL_BOOK_TITLE, \
    COL_BOOK_SERNO, COL_BOOK_SERIES, \
    COL_BOOK_DATE, COL_BOOK_AGEICON, \
    COL_BOOK_FILESIZE, COL_BOOK_FILETYPE = range(9)

    CPAGE_AUTHORS, CPAGE_SERIES, CPAGE_SEARCH = range(3)
    PAGE_NAMES = ('authors', 'series', 'search')

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

    def set_widgets_sensitive(self, wgtlst, v):
        for widget in wgtlst:
            widget.set_sensitive(v)

    def task_begin(self, msg):
        self.set_widgets_sensitive(self.tasksensitivewidgets, False)
        self.task_msg(msg)

    def task_msg(self, msg):
        self.labmsg.set_text(msg)
        self.task_events()

    def task_end(self, msg=''):
        self.labmsg.set_text(msg)
        self.progressbar.set_fraction(0.0)
        self.set_widgets_sensitive(self.tasksensitivewidgets, True)

    def task_progress(self, fraction):
        self.progressbar.set_fraction(fraction)
        self.task_events()

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
        headerbar.set_subtitle('v%s' % VERSION)

        self.resldr = get_resource_loader(self.env)

        self.window.set_titlebar(headerbar)

        #self.window.set_title(TITLE_VERSION)

        self.window.set_size_request(100 * WIDGET_BASE_UNIT, 76 * WIDGET_BASE_UNIT)
        self.window.set_border_width(WIDGET_SPACING)

        self.resldr = get_resource_loader(self.env)

        self.dlgabout = AboutDialog(self.window, self.resldr)
        self.dlgsetup = SetupDialog(self.window, self.env, self.cfg)

        self.window.set_default_icon(self.dlgabout.windowicon)
        self.window.set_icon(self.dlgabout.windowicon)

        #
        # начинаем напихивать виджеты
        #

        rootvbox = Gtk.VBox(spacing=WIDGET_SPACING)
        self.window.add(rootvbox)

        self.tasksensitivewidgets = []
        # список виджетов, которые должны блокироваться между вызовами task_begin/task_end

        # всё, кроме прогрессбара, кладём сюда, чтоб блокировать разом
        self.ctlvbox = Gtk.VBox(spacing=WIDGET_SPACING)
        rootvbox.pack_start(self.ctlvbox, True, True, 0)

        self.tasksensitivewidgets.append(self.ctlvbox)

        #
        # меню
        #

        # костыль для виндового порта GTK 3
        # задолбали гномеры всё подряд deprecated объявлять!
        #Gtk.Settings.get_default().props.gtk_menu_images = True

        #
        # плевал я, что deprecated.
        # Gtk.Builder и уёбищным говноблёвом под названием Glade пользоваться не буду
        #

        actions = Gtk.ActionGroup('ui')
        actions.add_actions(
            # action-name,stock-id,label,accel,toltip,callback
            (('file', None, 'Файл', None, None, None),
                ('fileAbout', Gtk.STOCK_ABOUT, 'О программе',
                    '<Alt>F1', 'Информация о программе', lambda b: self.dlgabout.run()),
                ('fileImport', Gtk.STOCK_REFRESH, 'Импорт библиотеки',
                    None, 'Импорт индексного файла (INPX) библиотеки', lambda b: self.import_library(True)),
                ('fileSettings', Gtk.STOCK_PREFERENCES, 'Настройка',
                    None, 'Настройка программы', lambda b: self.change_settings()),
                ('fileExit', Gtk.STOCK_QUIT, 'Выход',
                    '<Control>q', 'Завершить программу', self.destroy),
            ('books', None, 'Книги', None, None, None),
                ('booksRandomChoice', None, 'Случайный выбор',
                    '<Control>r', 'Случайный выбор книги', lambda b: self.random_book_choice()),
                ('booksExtract', Gtk.STOCK_SAVE, 'Извлечь',
                    '<Control>e', 'Извлечь выбранные книги из библиотеки', lambda b: self.extract_books()),
                #
                ('booksSearch', Gtk.STOCK_FIND, 'Искать',
                    '<Control>f', 'Искать книги в библиотеке', lambda b: self.search_books()),
                ('booksFavoriteAuthors', None, 'Избранные авторы', None, None, None),
                ('booksFavoriteSeries', None, 'Избранные сериалы/циклы', None, None, None),
            ))

        uimgr = Gtk.UIManager()
        uimgr.insert_action_group(actions)
        uimgr.add_ui_from_string(u'''<ui>
            <menubar>
                <menu name="mnuFile" action="file">
                    <menuitem name="mnuFileAbout" action="fileAbout"/>
                    <menuitem name="mnuFileImport" action="fileImport"/>
                    <menuitem name="mnuFileSettings" action="fileSettings"/>
                    <separator />
                    <menuitem name="mnuFileExit" action="fileExit"/>
                </menu>
                <menu name="mnuBooks" action="books">
                    <menuitem name="mnuBooksSearch" action="booksSearch"/>
                    <menuitem name="mnuBooksRandomChoice" action="booksRandomChoice"/>
                    <menuitem name="mnuBooksExtract" action="booksExtract"/>
                    <separator />
                    <menu name="mnuBooksFavoriteAuthors" action="booksFavoriteAuthors" />
                    <menu name="mnuBooksFavoriteSeries" action="booksFavoriteSeries" />
                </menu>
            </menubar>
            </ui>''')

        #self.tasksensitivewidgets.append(mnu)

        mainmenu = uimgr.get_widget('/ui/menubar')
        headerbar.pack_start(mainmenu)

        self.window.add_accel_group(uimgr.get_accel_group())

        self.mnuitemExtractBooks = uimgr.get_widget('/ui/menubar/mnuBooks/mnuBooksExtract')
        self.mnuitemSearchBooks = uimgr.get_widget('/ui/menubar/mnuFile/mnuBooksSearch')

        self.mnuFavoriteAuthors = uimgr.get_widget('/ui/menubar/mnuBooks/mnuBooksFavoriteAuthors').get_submenu()
        self.mnuFavoriteSeries = uimgr.get_widget('/ui/menubar/mnuBooks/mnuBooksFavoriteSeries').get_submenu()

        #
        # морда будет из двух вертикальных панелей
        #

        self.roothpaned = Gtk.HPaned()
        self.roothpaned.set_wide_handle(True)
        self.roothpaned.connect('notify::position', self.roothpaned_moved)
        self.ctlvbox.pack_start(self.roothpaned, True, True, 0)

        self.booklist = None
        # а реальное значение сюда сунем потом.
        # ибо alphachooser будет дёргать MainWnd.update_books_*,
        # и на момент вызова поле MainWnd.booklist уже должно существовать

        # символы для мнемоник быстрого перехода к виджетам (Alt+N)
        fastlabel = iter('123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ')

        #
        # в левой панели - алфавитные списки авторов и циклов
        #

        fr, fl = create_labeled_frame('Выбор')
        self.roothpaned.pack1(fr, True, False)

        self.chooserpages = Gtk.Notebook()
        self.chooserpages.set_border_width(WIDGET_SPACING)
        self.chooserpages.set_size_request(WIDGET_BASE_UNIT*24, -1)
        self.chooserpages.set_show_border(False)

        fr.add(self.chooserpages)
        fl.set_mnemonic_widget(self.chooserpages)

        # все "выбиральники"
        self.choosers = []
        # только те, которые можно использовать для случайного выбора
        self.rndchoosers = []

        __chsrs = (AuthorAlphaListChooser,
            SeriesAlphaListChooser,
            SearchFilterChooser)

        for chooserclass in __chsrs:
            chooser = chooserclass(self.lib, self.update_books_by_chooser)

            self.choosers.append(chooser)
            if chooser.RANDOM:
                self.rndchoosers.append(chooser)

            lab = Gtk.Label('_%s: %s' % (fastlabel.__next__(), chooserclass.LABEL))
            lab.set_use_underline(True)

            self.chooserpages.append_page(chooser.box, lab)

        self.selectWhere = None # None или строка с условиями для параметра WHERE
        # SQL-запроса в методе self.update_books()

        self.choosers[self.CPAGE_AUTHORS].onfavoriteclicked = self.update_favorite_authors
        self.choosers[self.CPAGE_SERIES].onfavoriteclicked = self.update_favorite_series

        self.curChooser = None
        self.chooserpages.connect('switch-page', self.chooser_page_switched)

        #
        # в правой панели - список книг соотв. автора и управление распаковкой
        #

        self.bookcount = Gtk.Label('0')
        bookframe, bl = create_labeled_frame('_%s. Книги:' % fastlabel.__next__(), self.bookcount)
        self.roothpaned.pack2(bookframe, True, False)

        bpanel = Gtk.VBox(spacing=WIDGET_SPACING)
        bpanel.set_size_request(WIDGET_BASE_UNIT * 30, -1) #!!!
        bpanel.set_border_width(WIDGET_SPACING)
        bookframe.add(bpanel)

        self.bookageicons = BookAgeIcons(Gtk.IconSize.MENU)

        # список книг
        self.booklist = TreeViewer(
            (GObject.TYPE_INT,      # bookid
                GObject.TYPE_STRING,# author
                GObject.TYPE_STRING,# title
                GObject.TYPE_STRING,# series
                GObject.TYPE_STRING,# serno
                GObject.TYPE_STRING,# date
                Pixbuf,             # иконка "свежести" книги
                GObject.TYPE_STRING,# filesize
                GObject.TYPE_STRING,# filetype
                ),
            (TreeViewer.ColDef(self.COL_BOOK_AUTHOR, 'Автор', False, True, markup=True, tooltip=self.COL_BOOK_AUTHOR),
                TreeViewer.ColDef(self.COL_BOOK_TITLE, 'Название', False, True, markup=True, tooltip=self.COL_BOOK_TITLE),
                TreeViewer.ColDef(self.COL_BOOK_SERNO, '#', False, False, 1.0, tooltip=self.COL_BOOK_SERIES),
                TreeViewer.ColDef(self.COL_BOOK_SERIES, 'Цикл', False, True, markup=True),
                TreeViewer.ColDef(self.COL_BOOK_FILESIZE, 'Размер', False, False, 1.0, tooltip=self.COL_BOOK_SERIES),
                TreeViewer.ColDef(self.COL_BOOK_FILETYPE, 'Тип', False, False, tooltip=self.COL_BOOK_SERIES),
                (TreeViewer.ColDef(self.COL_BOOK_AGEICON, 'Дата', tooltip=self.COL_BOOK_SERIES),
                 TreeViewer.ColDef(self.COL_BOOK_DATE))
                 )
            )

        bl.set_mnemonic_widget(self.booklist.view)

        #print(self.booklist.colmap)

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

        self.selbookcount = Gtk.Label('0')
        extractframe, efl = create_labeled_frame('_%s. Выбрано книг:' % fastlabel.__next__(), self.selbookcount)

        xfbox = Gtk.HBox(spacing=WIDGET_SPACING)
        xfbox.set_border_width(WIDGET_SPACING)
        extractframe.add(xfbox)

        self.ctlvbox.pack_start(extractframe, False, False, 0)

        # внезапно, кнопка
        self.btnextract = Gtk.Button('Извлечь')
        self.btnextract.connect('clicked', lambda b: self.extract_books())
        xfbox.pack_start(self.btnextract, False, False, 0)

        # выбор каталога
        xfbox.pack_start(Gtk.Label('в каталог'), False, False, 0)
        self.destdirchooser = Gtk.FileChooserButton.new('Выбор каталога для извлечения книг', Gtk.FileChooserAction.SELECT_FOLDER)

        #!!!!
        efl.set_mnemonic_widget(self.destdirchooser)

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
        self.cfg.lock()
        #print('calling __create_ui()')
        self.__create_ui()
        #print('__create_ui() is called')
        self.cfg.unlock()

        #print('check_startup_environment()')
        self.check_startup_environment()

        #print('update_choosers()')
        self.update_choosers()

        #print('update_favorite_authors()')
        self.update_favorite_authors()
        #print('update_favorite_series()')
        self.update_favorite_series()

        # выбор ранее запомненной страницы выбиральника
        npage = self.cfg.get_param_int(self.cfg.MAIN_WINDOW_CHOOSER_PAGE, 0)
        lastchooser = len(self.choosers) - 1
        if npage > lastchooser:
            npage = lastchooser
        self.chooserpages.set_current_page(npage)
        #print('__init__() end')

    def update_choosers(self):
        """Обновление потрохов экземпляров FilterChooser после обновления БД"""

        for chooser in self.choosers:
            chooser.update()

    def check_startup_environment(self):
        """Проверки:
        - на первый запуск и, при необходимости, первоначальная настройка;
        - на устарелость индексного файла (.inpx);
        - на соответствие версии БД в файле и текущей версии БД в программе;
        При необходимости - импорт индексного файла."""

        needImport = False

        if not self.cfg.has_required_settings():
            if self.dlgsetup.run('Первоначальная настройка') != Gtk.ResponseType.OK:
                msg_dialog(self.window, TITLE_VERSION, 'Не могу работать без настройки', Gtk.MessageType.ERROR)
                exit(1) #!!!
            else:
                needImport = True

        # создание (при необходимости) отсутствующих таблиц
        # которые есть и чего-то содержат - их не трогаем
        self.lib.init_tables()

        E_NON_ACTUAL = 'Импорт индексного файла отменён, работа с неактуальным содержимым БД недопустима.'

        # проверяем соответствие версий БД в файле и в программе
        if not needImport:
            needImport = self.lib.dbversion != self.lib.DB_VERSION

            if needImport:
                print('Версия БД изменена (в файле - %d, текущая - %d), необходим повторный импорт индексного файла библиотеки.' %\
                    (self.lib.dbversion, self.lib.DB_VERSION))

                if msg_dialog(self.window, 'Внимание!',
                        'Версия базы данных отличается от текущей.\nНеобходим повторный импорт индексного файла библиотеки.',
                        buttons=Gtk.ButtonsType.OK_CANCEL) != Gtk.ResponseType.OK:

                    print(E_NON_ACTUAL)
                    exit(1)

        # если на предыдущем шаге необходимость импорта не выявлена -
        # дополнительно проверяем наличие и mtime индексного файла
        if not needImport:
            inpxFileName = self.cfg.get_param(self.cfg.IMPORT_INPX_INDEX)
            inpxTStamp = get_file_timestamp(inpxFileName)

            if inpxTStamp != 0:
                inpxStoredTStamp = self.cfg.get_param_int(self.cfg.IMPORT_INPX_INDEX_TIMESTAMP, 0)

                if inpxStoredTStamp == 0 or inpxStoredTStamp != inpxTStamp:
                    print('Индексный файл библиотеки изменён, необходим его импорт.')

                    if msg_dialog(self.window, 'Внимание!',
                            'Индексный файл библиотеки ("%s") изменён.\nНеобходим его импорт.' %\
                            os.path.split(inpxFileName)[1],
                            buttons=Gtk.ButtonsType.OK_CANCEL) != Gtk.ResponseType.OK:
                        print(E_NON_ACTUAL)
                        exit(1)

                    needImport = True
            # если inpxTStamp == 0 - индексного файла попросту нет, нечего импортировать

        if needImport:
            self.import_library()

    def import_library(self, askconfirm=False, xtramsg=''):
        """Процедура импорта библиотеки.

        askconfirm  - спрашивать ли подтверждения
                      (через Gtk.MessageDialog),
                      если askconfirm=True;
        xtramsg     - строка с дополнительным сообщением
                      или пустая строка."""

        S_IMPORT = 'Импорт библиотеки'

        if askconfirm:
            if msg_dialog(self.window, S_IMPORT,
                '%sИмпорт библиотеки может быть долгим.\nПродолжить?' %\
                    ('' if not xtramsg else '%s\n\n' % xtramsg),
                buttons=Gtk.ButtonsType.YES_NO) != Gtk.ResponseType.YES:
                    return

        try:
            self.task_begin(S_IMPORT)
            try:
                self.lib.cursor.executescript('''CREATE TEMPORARY TABLE oldbookids(bookid INTEGER PRIMARY KEY);
                    CREATE TEMPORARY TABLE oldauthorids(authorid INTEGER PRIMARY KEY);''')
                try:
                    # список books.bookid ДО импорта
                    self.lib.cursor.executescript('''INSERT OR REPLACE INTO oldbookids(bookid) SELECT bookid FROM books;
                        INSERT OR REPLACE INTO oldauthorids(authorid) SELECT authorid FROM authornames;''')

                    print('Инициализация БД (%s)...' % self.env.libraryFilePath)
                    self.task_msg('Инициализация БД')
                    self.lib.reset_tables()

                    inpxFileName = self.cfg.get_param(self.cfg.IMPORT_INPX_INDEX)
                    print('Импорт индекса библиотеки "%s"...' % inpxFileName)
                    self.task_msg('Импорт индекса библиотеки')

                    importer = INPXImporter(self.lib, self.cfg)
                    importer.import_inpx_file(inpxFileName, self.task_progress)

                    # импорт успешен, ничего не упало, можно дальше изгаляться
                    # а если выскочило исключение, то один фиг нижеследующе не выполнится

                    # обновляем в БД настроек параметр с timestamp'ом индексного файла
                    self.cfg.set_param_int(self.cfg.IMPORT_INPX_INDEX_TIMESTAMP,
                        get_file_timestamp(inpxFileName))

                    # чистим списки избранного - лежавших там авторов и сериалов может не быть
                    # в свежей БД
                    __CLEANUP_FAVS = 'Удаление устаревших записей из списков избранного'
                    print(__CLEANUP_FAVS)
                    self.task_msg(__CLEANUP_FAVS)
                    self.lib.cleanup_favorites()
                    self.update_favorite_authors()
                    self.update_favorite_series()

                    # собираем некоторую статистику

                    # получаем количества новых и удалённых книг
                    booksTotal = self.get_total_book_count()
                    booksNew = self.lib.get_table_dif_count('books', 'oldbookids', 'bookid')
                    booksDeleted = self.lib.get_table_dif_count('oldbookids', 'books', 'bookid')

                    # получаем количество удалённых книг
                    authorsTotal = self.lib.get_table_count('authornames')
                    authorsNew = self.lib.get_table_dif_count('authornames', 'oldauthorids', 'authorid')
                    authorsDeleted = self.lib.get_table_dif_count('oldauthorids', 'authornames', 'authorid')

                    print('''Книги:  импортировано   %d
            добавлено новых %d
            удалено         %d
    Авторы: всего           %d
            добавлено       %d
            удалено         %d''' % (booksTotal,
                        booksNew, booksDeleted,
                        authorsTotal,
                        authorsNew, authorsDeleted))

                    if any((booksNew, booksDeleted, authorsNew, authorsDeleted)):
                        # если после импорта чего-то изменилось - показываем окно со статистикой
                        stgrid = LabeledGrid()

                        def add_counter(t, v):
                            stgrid.append_row(t)
                            stgrid.append_col(create_aligned_label('%d' % v, 1.0), True)

                        if booksNew:
                            add_counter('Добавлено книг:', booksNew)

                        if booksDeleted:
                            add_counter('Удалено книг:', booksDeleted)

                        if authorsNew:
                            add_counter('Добавлено авторов:', authorsNew)

                        if authorsDeleted:
                            add_counter('Удалено авторов:', authorsDeleted)

                        msg_dialog(self.window, 'Импорт библиотеки',
                            'Импорт библиотеки завершён.', Gtk.MessageType.OTHER,
                            widgets=(Gtk.HSeparator(), stgrid))

                finally:
                    self.lib.cursor.executescript('''DROP TABLE IF EXISTS oldbookids;
                        DROP TABLE IF EXISTS oldauthorids;''')

                self.update_choosers()

            finally:
                self.task_end()

        except Exception as ex:
            msg_dialog(self.window, 'Ошибка', str(ex), Gtk.MessageType.ERROR)
            raise ex

    def random_book_choice(self):
        """Случайный выбор книги"""

        # сначала выбираем случайный выбиральник

        npage = randrange(len(self.rndchoosers))
        self.chooserpages.set_current_page(npage)

        # выбираем случайный элемент в выбиральнике
        if self.choosers[npage].random_choice():
            # ...и случайную книгу в списке книг
            self.booklist.random_choice()

    def chooser_page_switched(self, nbook, page, pagenum):
        self.curChooser = self.choosers[pagenum]
        self.curChooser.do_on_choosed()

        self.cfg.set_param_int(self.cfg.MAIN_WINDOW_CHOOSER_PAGE, pagenum)

        self.window.set_default(self.curChooser.defaultWidget)

        if self.curChooser.firstWidget is not None:
            self.curChooser.firstWidget.grab_focus()

    def update_favorites_menu(self, menu, favparams, truncfunc):
        """Обновление содержимого меню избранного.

        menu        - экземпляр Gtk.Menu,
        favparams   - экземпляр LibraryDB.favorite_params,
        truncfunc   - функция со строковым параметром,
                      обрезающая слишком длинную строку."""

        clear_menu(menu)

        nitems = 0

        cur = self.lib.cursor.execute('SELECT name FROM %s ORDER BY name;' % favparams.favtablename)
        while True:
            r = cur.fetchone()
            if r is None:
                break

            nitems += 1

            item = Gtk.MenuItem.new_with_label(truncfunc(r[0]))
            item.connect('activate', self.select_favorite, (favparams, r[0]))
            menu.append(item)

        if nitems == 0:
            item = Gtk.MenuItem.new_with_label('<нет>')
            item.set_sensitive(False)
            menu.append(item)

        menu.show_all()

    def update_favorite_authors(self):
        self.update_favorites_menu(self.mnuFavoriteAuthors,
            LibraryDB.FAVORITE_AUTHORS_PARAMS,
            fbfntemplate.truncate_author_name)

    def update_favorite_series(self):
        self.update_favorites_menu(self.mnuFavoriteSeries,
            LibraryDB.FAVORITE_SERIES_PARAMS,
            fbfntemplate.truncate_str)

    def select_favorite(self, mnuitem, data):
        """Метод, вызываемый при выборе элемента меню избранного.

        Eго параметры такие же, как у обработчика сигнала "activate"
        Gtk.MenuItem, дополнительный параметр data -
        кортеж из двух элементов - экземпляра LibraryDB.favorite_params
        и значения primary key соответствующего элемента таблицы БД."""

        self.selectWhere = self.lib.get_favorite_where_param(*data)

        self.update_books()

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
            #print('tooltip column', mcolid)
            #print('columns', self.booklist.store.get_n_columns())

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

        self.set_widgets_sensitive((self.btnextract, self.mnuitemExtractBooks), nselbooks > 0)
        #
        self.selbookcount.set_text(str(nselbooks))

    def dest_dir_changed(self, chooser):
        self.cfg.set_param(self.cfg.EXTRACT_TO_DIRECTORY, chooser.get_filename())

    def extract_books(self):
        """Извлечение выбранных в списке книг"""
        if self.booksSelected:
            self.task_begin('Извлечение книг...')
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
                self.task_end()

    def get_total_book_count(self):
        """Возвращает общее количество книг в БД"""

        return self.lib.get_table_count('books')

    def search_books(self):
        """Поиск книг по нескольким полям."""

        self.chooserpages.set_current_page(self.CPAGE_SEARCH)

    def update_books_by_chooser(self):
        self.selectWhere = self.curChooser.selectWhere
        self.update_books()

    def update_books(self):
        """Обновление списка книг.

        idcolname   - имя столбца в таблице books для запроса к БД,
        idcolvalue  - значение столбца для запроса."""

        if self.booklist is None:
            return

        self.booklist.view.set_model(None)
        self.booklist.store.clear()

        ntotalbooks = self.get_total_book_count()
        stotalbooks = '%d' % ntotalbooks
        nbooks = 0

        if self.selectWhere is not None:
            # получаем список книг
            q = '''SELECT books.bookid,books.title,serno,seriesnames.title,date,authornames.name,filesize,filetype
                FROM books
                INNER JOIN seriesnames ON seriesnames.serid=books.serid
                INNER JOIN authornames ON authornames.authorid=books.authorid
                WHERE %s
                ORDER BY authornames.name, seriesnames.title, serno, books.title, date;'''\
                % self.selectWhere

            #print(q)
            cur = self.lib.cursor.execute(q)

            # для фильтрации по дате можно сделать втык в запрос подобного:
            #  and (date > "2014-01-01") and (date < "2016-12-31")
            # или вручную фильтровать ниже
            datenow = datetime.datetime.now()

            while True:
                r = cur.fetchone()
                if r is None:
                    break

                nbooks += 1

                # 0:bookid 1:title 2:serno 3:sername 4:date 5:authorname
                flds = filterfields(r[0], r[1], r[2], r[3],
                    # подразумеваятся, что в соотв. поле БД точно есть хоть какая-то дата
                    datetime.datetime.strptime(r[4], DB_DATE_FORMAT),
                    r[5], r[6], r[7])

                #
                # дальше работаем ТОЛЬКО с полями flds, про список r забываем
                #

                #
                # дополнительная фильтрация
                #
                if self.booklistTitlePattern:
                    if flds.title.lower().find(self.booklistTitlePattern) < 0 \
                        and flds.authorname.lower().find(self.booklistTitlePattern) < 0 \
                        and flds.sertitle.lower().find(self.booklistTitlePattern) < 0:
                        continue

                dateicon = self.bookageicons.get_book_age_icon(datenow, flds.date)
                datestr = flds.date.strftime(DISPLAY_DATE_FORMAT)

                self.booklist.store.append((flds.bookid,
                    markup_escape_text(flds.authorname, -1), # authornames.name
                    markup_escape_text(flds.title, -1), # books.title
                    str(flds.serno) if flds.serno > 0 else '', # serno
                    markup_escape_text(flds.sertitle, -1), # seriesnames.title
                    datestr, # date
                    dateicon, # age pixbuf
                    kilobytes_str(flds.filesize),
                    '?' if not flds.filetype else flds.filetype.upper()
                    ))

        self.booklist.view.set_model(self.booklist.store)
        self.booklist.view.set_search_column(self.COL_BOOK_TITLE)
        self.booklist.view.set_search_equal_func(self.booklist_search_func)

        self.bookcount.set_text('(%d из %s)' % (nbooks, stotalbooks))

    def booklist_search_func(self, model, column, key, _iter, data=None):
        """Штатная функция сравнивает key с началом строки в столбце column,
        а эта будет искать любое вхождение key в нескольких столбцах.
        Внимание! При успешном сравнении функция должна возвращать False!
        См. документацию по GTK."""

        key = key.upper()

        if model.get_value(_iter, self.COL_BOOK_AUTHOR).upper().find(key) >= 0:
            return False

        if model.get_value(_iter, self.COL_BOOK_TITLE).upper().find(key) >= 0:
            return False

        if model.get_value(_iter, self.COL_BOOK_SERIES).upper().find(key) >= 0:
            return False

        return True

    def main(self):
        Gtk.main()


def main():
    try:
        env = Environment()
        cfg = Settings(env)

        if os.path.exists(env.lockFilePath):
            raise EnvironmentError('Программа %s уже запущена' % TITLE)

        with open(env.lockFilePath, 'w+') as lockf:
            lockf.write('%s\n' % os.getpid())

        try:
            cfg.load()
            try:
                #inpxFileName = cfg.get_param(cfg.IMPORT_INPX_INDEX)
                #genreNamesFile = cfg.get_param(cfg.GENRE_NAMES_PATH)

                dbexists = os.path.exists(env.libraryFilePath)
                lib = LibraryDB(env.libraryFilePath)
                print('соединение с БД')
                lib.connect()
                try:
                    #if not dbexists:
                    #    lib.init_tables()

                    print('запуск UI')
                    mainwnd = MainWnd(lib, env, cfg)
                    mainwnd.main()
                finally:
                    lib.disconnect()
            finally:
                cfg.unload()
        finally:
            if os.path.exists(env.lockFilePath):
                os.remove(env.lockFilePath)
    except Exception as ex:
        msg_dialog(None, '%s: ошибка' % TITLE, str(ex), Gtk.MessageType.ERROR)
        raise ex

    return 0


if __name__ == '__main__':
    exit(main())
