#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" flibrowser2.py

    Copyright 2018-2020 MC-6312 <mc6312@gmail.com>

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
import subprocess
import datetime
from time import time

from time import time, sleep
from random import randrange


class MainWnd():
    """Основное междумордие"""

    # индексы столбцов в Gtk.ListStore списка книг
    COL_BOOK_ID, COL_BOOK_AUTHOR, COL_BOOK_TITLE, \
    COL_BOOK_SERNO, COL_BOOK_SERIES, \
    COL_BOOK_DATE, COL_BOOK_AGEICON, \
    COL_BOOK_FILESIZE, COL_BOOK_ID_STR, COL_BOOK_FILETYPE = range(10)

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

    def mnuFileAbout_activate(self, wgt):
        self.dlgabout.run()

    def mnuFileImport_activate(self, wgt):
        self.import_library(True)

    def mnuFileSettings_activate(self, wgt):
        self.change_settings()

    def mnuBooksRandomChoice_activate(self, wgt):
        self.random_book_choice()

    def mnuBooksExtract_activate(self, wgt):
        self.extract_books()

    def mnuBooksSearch_activate(self, wgt):
        self.search_books()

    def mnuBooksSearchAuthor_activate(self, wgt):
        self.search_this_author()

    def mnuBooksSearchTitle_activate(self, wgt):
        self.search_this_title()

    def mnuBooksSearchSeries_activate(self, wgt):
        self.search_this_series()

    def __copy_col_to_clipboard(self, col):
        v = self.get_selected_column_value(col)
        if v:
            self.clipboard.set_text(v, -1)

    def mnuBooksCopyAuthorName_activate(self, wgt):
        self.__copy_col_to_clipboard(self.COL_BOOK_AUTHOR)

    def mnuBooksCopyBookTitle_activate(self, wgt):
        self.__copy_col_to_clipboard(self.COL_BOOK_TITLE)

    def mnuBooksCopySeriesName_activate(self, wgt):
        self.__copy_col_to_clipboard(self.COL_BOOK_SERIES)

    def btnextract_clicked(self, btn):
        self.extract_books()

    def extractopenfmbtn_clicked(self, btn):
        self.open_destination_dir()

    def __create_ui(self):
        self.windowMaximized = False
        self.windowStateLoaded = False

        self.resldr = get_resource_loader(self.env)
        uibldr = self.resldr.load_gtk_builder('flibrowser2.ui')

        self.window = uibldr.get_object('wndMain')

        headerbar = uibldr.get_object('headerBar')
        headerbar.set_title(TITLE)
        headerbar.set_subtitle('v%s' % VERSION)

        self.dlgabout = AboutDialog(self.resldr, uibldr)

        self.dlgsetup = SetupDialog(self.env, self.cfg, uibldr)

        self.window.set_default_icon(self.dlgabout.windowicon)
        self.window.set_icon(self.dlgabout.windowicon)

        # список виджетов, которые должны блокироваться между вызовами task_begin/task_end
        self.tasksensitivewidgets = []

        # всё, кроме прогрессбара, кладём сюда, чтоб блокировать разом
        self.ctlvbox = uibldr.get_object('ctlvbox')
        self.tasksensitivewidgets.append(self.ctlvbox)

        #
        # меню
        #

        mainmenu = uibldr.get_object('mnuMain')
        self.tasksensitivewidgets.append(mainmenu)

        self.mnuitemExtractBooks = uibldr.get_object('mnuBooksExtract')
        self.mnuitemSearchBooks = uibldr.get_object('mnuBooksSearch')

        self.mnuFavoriteAuthors = uibldr.get_object('mnuBooksFavoriteAuthorsSubmenu')
        self.mnuFavoriteSeries = uibldr.get_object('mnuBooksFavoriteSeriesSubmenu')

        # контекстное меню поиска по полям из списка найденных книг
        self.mnuBooksContextMenu = uibldr.get_object('mnuBooksContextMenuSubmenu')

        #
        # морда будет из двух вертикальных панелей
        #

        self.roothpaned = uibldr.get_object('roothpaned')

        self.booklist = None
        # а реальное значение сюда сунем потом.
        # ибо alphachooser будет дёргать MainWnd.update_books_*,
        # и на момент вызова поле MainWnd.booklist уже должно существовать

        #-----------------------------------------------------------#
        # начинаем напихивать динамически создаваемые виджеты,      #
        # которые по разным причинам нельзя было нарисовать в Glade #
        #-----------------------------------------------------------#

        #
        # в левой панели - алфавитные списки авторов и циклов
        #

        self.chooserpages = uibldr.get_object('chooserpages')

        # все "выбиральники"
        self.choosers = []

        # только те, которые можно использовать для случайного выбора
        self.rndchoosers = []

        __chsrs = (AuthorAlphaListChooser,
            SeriesAlphaListChooser,
            SearchFilterChooser)

        for chooserix, chooserclass in enumerate(__chsrs, 1):
            chooser = chooserclass(self.lib, self.update_books_by_chooser)

            self.choosers.append(chooser)
            if chooser.RANDOM:
                self.rndchoosers.append(chooser)

            # chooserix - номер для кнопки-акселератора
            lab = Gtk.Label.new('_%d: %s' % (chooserix, chooserclass.LABEL))
            lab.set_use_underline(True)

            self.chooserpages.append_page(chooser.box, lab)

        self.selectWhere = None # None или строка с условиями для параметра WHERE
        # SQL-запроса в методе self.update_books()

        self.choosers[self.CPAGE_AUTHORS].onfavoriteclicked = self.update_favorite_authors
        self.choosers[self.CPAGE_SERIES].onfavoriteclicked = self.update_favorite_series

        self.curChooser = None
        self.chooserChanged = False


        #
        # в правой панели - список книг соотв. автора и управление распаковкой
        #

        self.bookcount = uibldr.get_object('bookcount')

        self.bookageicons = BookAgeIcons(Gtk.IconSize.MENU)

        #TODO переделать booklist под Gtk.Builder
        # TreeView и прочее пока создаём "вручную"

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
                GObject.TYPE_STRING,# bookid as str
                GObject.TYPE_STRING,# filetype
                ),
            (TreeViewer.ColDef(self.COL_BOOK_AUTHOR, 'Автор', False, True, tooltip=self.COL_BOOK_AUTHOR),
                TreeViewer.ColDef(self.COL_BOOK_TITLE, 'Название', False, True, tooltip=self.COL_BOOK_TITLE),
                TreeViewer.ColDef(self.COL_BOOK_SERNO, '#', False, False, 1.0, tooltip=self.COL_BOOK_SERIES),
                TreeViewer.ColDef(self.COL_BOOK_SERIES, 'Цикл', False, True),
                TreeViewer.ColDef(self.COL_BOOK_FILESIZE, 'Размер', False, False, 1.0, tooltip=self.COL_BOOK_SERIES),
                TreeViewer.ColDef(self.COL_BOOK_ID_STR, 'Id', False, False, tooltip=self.COL_BOOK_SERIES),
                TreeViewer.ColDef(self.COL_BOOK_FILETYPE, 'Тип', False, False, tooltip=self.COL_BOOK_SERIES),
                (TreeViewer.ColDef(self.COL_BOOK_AGEICON, 'Дата', tooltip=self.COL_BOOK_SERIES),
                 TreeViewer.ColDef(self.COL_BOOK_DATE))
                 )
            )

        booklistbox = uibldr.get_object('booklistbox')
        booklistbox.pack_start(self.booklist.window, True, True, 0)

        uibldr.get_object('booklistlabel').set_mnemonic_widget(self.booklist.view)

        # для всплывающих подсказок, зависящих от столбца
        self.booklist.view.connect('motion-notify-event', self.booklist_mouse_moved)
        # для контекстного меню
        self.booklist.view.connect('button-press-event', self.booklist_button_pressed)
        self.booklist.view.connect('key-press-event', self.booklist_key_pressed)

        self.booklist.selection.set_mode(Gtk.SelectionMode.MULTIPLE)
        self.booklist.selection.connect('changed', self.booklist_selected)

        # фильтрация списка книг по названию книги и названию цикла
        booksearchentry = uibldr.get_object('booksearchentry')
        entry_setup_clear_icon(booksearchentry)

        #
        # панель с виджетами извлечения книг
        #

        self.selbookcount = uibldr.get_object('selbookcount')
        self.btnextract = uibldr.get_object('btnextract')

        # выбор каталога
        self.destdirchooser = uibldr.get_object('destdirchooser')

        self.destdirchooser.set_filename(self.cfg.get_param(self.cfg.EXTRACT_TO_DIRECTORY, os.path.expanduser('~')))

        # комбо-бокс шаблонов переименования
        self.extractfntemplatecb = uibldr.get_object('extractfntemplatecb')
        for fntplix, fntpl in enumerate(fbfntemplate.templates):
            self.extractfntemplatecb.append_text(fntpl.DISPLAY)

        self.extractfntemplatecb.set_active(self.extractTemplateIndex)

        # чекбокс "сжать zip"
        self.extracttozipbtn = uibldr.get_object('extracttozipbtn')
        self.extracttozipbtn.set_active(self.cfg.get_param_bool(self.cfg.EXTRACT_PACK_ZIP, False))

        # кнопка открытия каталога распаковки
        # доступна, только если программа знает, какой в ОС файловый менеджер!
        uibldr.get_object('extractopenfmbtn').set_sensitive(self.env.fileManager is not None)

        # чекбокс "затем открыть каталог"
        self.extractopenfmchkbtn = uibldr.get_object('extractopenfmchkbtn')
        self.extractopenfmchkbtn.set_active(self.cfg.get_param_bool(self.cfg.EXTRACT_OPEN_DIRECTORY, False))

        #
        # прогрессбар (для распаковки и др.)
        #

        # потому как Gtk.ProgressBar со "своим" текстом в случае свежего GTK
        # и многих тем этот текст рисует слишком малозаметно
        self.labmsg = uibldr.get_object('labmsg')
        self.progressbar = uibldr.get_object('progressbar')

        #
        # заканчиваем напихивать виджеты
        #

        self.window.show_all()

        self.clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)

        #print('loading window state')
        self.load_window_state()
        uibldr.connect_signals(self)

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

        # счетчик блокировок вызовов update_books()
        self.lockUpdateBooks = 0

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

        self.lock_update_books()

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

        self.set_chooser_page(npage)

        self.unlock_update_books()
        #print('__init__() end')

    def lock_update_books(self):
        self.lockUpdateBooks += 1

    def unlock_update_books(self):
        if self.lockUpdateBooks > 0:
            self.lockUpdateBooks -= 1

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

                #if msg_dialog(self.window, 'Внимание!',
                #        'Версия базы данных отличается от текущей.\nНеобходим повторный импорт индексного файла библиотеки.',
                #        buttons=Gtk.ButtonsType.OK_CANCEL) != Gtk.ResponseType.OK:

                #    print(E_NON_ACTUAL)
                #    exit(1)

        # если на предыдущем шаге необходимость импорта не выявлена -
        # дополнительно проверяем наличие и mtime индексного файла
        if not needImport:
            inpxFileName = self.cfg.get_param(self.cfg.IMPORT_INPX_INDEX)
            inpxTStamp = get_file_timestamp(inpxFileName)

            if inpxTStamp != 0:
                inpxStoredTStamp = self.cfg.get_param_int(self.cfg.IMPORT_INPX_INDEX_TIMESTAMP, 0)

                if inpxStoredTStamp == 0 or inpxStoredTStamp != inpxTStamp:
                    print('Индексный файл библиотеки изменён, необходим его импорт.')

                    """if msg_dialog(self.window, 'Внимание!',
                            '''Индексный файл библиотеки ("%s") изменён.
Необходим его импорт.
"OK"\t- импортировать индексный файл,
"Отмена"\t- завершить работу программы''' %\
                            os.path.split(inpxFileName)[1],
                            buttons=Gtk.ButtonsType.OK_CANCEL) != Gtk.ResponseType.OK:
                        print(E_NON_ACTUAL)
                        exit(1)"""

                    needImport = True
            # если inpxTStamp == 0 - индексного файла попросту нет, нечего импортировать

        if needImport:
            self.import_library(False) # в этой ситуации всегда импортируем без спросу

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
                '%sИмпорт библиотеки может быть долгим.\n"Да"\t- импортировать библиотеку,\n"Нет"\t- завершить работу.' %\
                    ('' if not xtramsg else '%s\n\n' % xtramsg),
                buttons=Gtk.ButtonsType.YES_NO) != Gtk.ResponseType.YES:
                    return

        self.task_begin(S_IMPORT)
        try:
            time0 = time()

            self.lib.cursor.executescript('''CREATE TEMPORARY TABLE oldbookids(bookid INTEGER PRIMARY KEY);
                CREATE TEMPORARY TABLE oldauthorids(authorid INTEGER PRIMARY KEY);
                CREATE TEMPORARY TABLE newbooks(bookid INTEGER PRIMARY KEY, favauthor INTEGER);''')
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
                time1 = time() - time0

                secs = time1 % 60
                mins = time1 // 60
                print('  затрачено времени: %d:%.2d' % (mins, secs))

                # получаем количества новых и удалённых книг
                booksTotal = self.get_total_book_count()

                self.lib.cursor.execute('''INSERT OR REPLACE INTO newbooks(bookid)
                    %s''' % self.lib.get_table_difference_query('books', 'oldbookids', 'bookid',
                                                                retcols=('bookid',)))

                booksNew = self.lib.get_table_count('newbooks')
                booksFavAuthorsNew = 0

                if booksNew:
                    # пытаемся найти новые книги избранных авторов
                    self.lib.cursor.executescript('''CREATE TEMPORARY TABLE favauthorbooks(bookid INTEGER PRIMARY KEY);
                        INSERT OR REPLACE INTO favauthorbooks(bookid)
                            SELECT bookid FROM books
                                INNER JOIN authornames ON authornames.authorid=books.authorid
                                INNER JOIN favorite_authors ON favorite_authors.name=authornames.name;
                        UPDATE newbooks SET favauthor=0;
                        UPDATE newbooks SET favauthor=1
                            WHERE newbooks.bookid IN (SELECT bookid FROM favauthorbooks);
                        DROP TABLE IF EXISTS favauthorbooks;''')

                    booksFavAuthorsNew = self.lib.get_table_count('newbooks', 'favauthor=1')

                booksDeleted = self.lib.get_table_dif_count('oldbookids', 'books', 'bookid')

                # получаем количество новых и удалённых авторов
                authorsTotal = self.lib.get_table_count('authornames')
                authorsNew = self.lib.get_table_dif_count('authornames', 'oldauthorids', 'authorid')
                authorsDeleted = self.lib.get_table_dif_count('oldauthorids', 'authornames', 'authorid')

                print('''Книги:  импортировано           %d
        добавлено новых всего   %d
        от избранных авторов    %d
        удалено                 %d
Авторы: всего                   %d
        добавлено               %d
        удалено                 %d''' % (booksTotal,
                    booksNew, booksFavAuthorsNew, booksDeleted,
                    authorsTotal,
                    authorsNew, authorsDeleted))

                if any((booksNew, booksDeleted, authorsNew, authorsDeleted)):
                    # если после импорта чего-то изменилось - показываем окно со статистикой
                    stgrid = LabeledGrid()

                    def add_counter(labtxt, value, withcb=False):
                        """Добавляет строку со значением в сетку stgrid.
                        labtxt  - текст метки в первом столбце;
                        value   - целое значение для второго столбца;
                        withcb  - булевское значение:
                                  True, если нужно в третий столбец
                                  поместить чекбокс.
                        Возвращает None, если withcb==False, иначе -
                        экземпляр Gtk.CheckButton."""

                        stgrid.append_row(labtxt)
                        stgrid.append_col(create_aligned_label('%d' % value, 1.0, stgrid.label_yalign), True)

                        if withcb:
                            cbox = Gtk.CheckButton.new_with_label('показать')
                            stgrid.append_col(cbox, False)
                        else:
                            cbox = None

                        return cbox

                    cboxBooksNew = None
                    cboxBooksNewFromFavAuthors = None

                    if booksNew:
                        cboxBooksNew = add_counter('Добавлено книг:', booksNew, True)

                        if booksFavAuthorsNew:
                            cboxBooksNewFromFavAuthors = add_counter('...в т.ч. от избранных авторов:', booksFavAuthorsNew, True)

                    if booksDeleted:
                        add_counter('Удалено книг:', booksDeleted)

                    if authorsNew:
                        add_counter('Добавлено авторов:', authorsNew)

                    if authorsDeleted:
                        add_counter('Удалено авторов:', authorsDeleted)

                    msg_dialog(self.window, 'Импорт библиотеки',
                        'Импорт библиотеки завершён.', Gtk.MessageType.OTHER,
                        widgets=(Gtk.HSeparator(), stgrid))

                    # если нажат чекбокс избранных авторов - показываем их новые книги,
                    # игнорируя чекбокс "все новые книги"
                    query = None
                    if cboxBooksNewFromFavAuthors is not None and cboxBooksNewFromFavAuthors.get_active():
                        query = 'books.bookid IN (SELECT bookid FROM newbooks WHERE newbooks.favauthor=1)'
                    # иначе, если нажат чекбокс новых книг - показываем ВСЕ новые книги
                    elif cboxBooksNew is not None and cboxBooksNew.get_active():
                        query = 'books.bookid IN (SELECT bookid FROM newbooks)'

                    if query:
                        self.selectWhere = query
                        self.update_books()

            finally:
                self.lib.cursor.executescript('''DROP TABLE IF EXISTS oldbookids;
                    DROP TABLE IF EXISTS oldauthorids;
                    DROP TABLE IF EXISTS newbooks;''')

            self.lock_update_books() # дабы не дёргали update_books()
            self.update_choosers()
            self.unlock_update_books()

        finally:
            self.task_end()

    def random_book_choice(self):
        """Случайный выбор книги"""

        # сначала выбираем случайный выбиральник

        npage = randrange(len(self.rndchoosers))
        self.set_chooser_page(npage)

        # выбираем случайный элемент в выбиральнике
        if self.choosers[npage].random_choice():
            # ...и случайную книгу в списке книг
            self.booklist.random_choice()

    def __chooser_changed(self, pagenum):
        self.curChooser = self.choosers[pagenum]
        self.curChooser.do_on_choosed()

        self.cfg.set_param_int(self.cfg.MAIN_WINDOW_CHOOSER_PAGE, pagenum)

    def set_chooser_page(self, pagenum):
        self.chooserpages.set_current_page(pagenum)

        if self.curChooser is None:
            self.__chooser_changed(pagenum)

        self.window.set_default(self.curChooser.defaultWidget)

        if self.curChooser.firstWidget is not None:
            self.curChooser.firstWidget.grab_focus()

    def search_books(self):
        """Поиск книг по нескольким полям."""

        self.set_chooser_page(self.CPAGE_SEARCH)

    def chooser_page_switched(self, nbook, page, pagenum):
        self.__chooser_changed(pagenum)

        # переключение фокуса на firstWidget на вкладке перенесено в set_chooser_page()

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

    def extracttozipbtn_clicked(self, cb):
        self.cfg.set_param_bool(self.cfg.EXTRACT_PACK_ZIP, cb.get_active())

    def extractopenfmchkbtn_toggled(self, cb):
        self.cfg.set_param_bool(self.cfg.EXTRACT_OPEN_DIRECTORY, cb.get_active())

    def booklisttitlepattern_changed(self, entry, data=None):
        self.booklistTitlePattern = entry.get_text().strip().lower()
        self.update_books()

    def booklist_context_menu(self, event):
        # вываливаем контекстное меню только при непустом списке найденных книг
        # и при условии, что хотя бы один элемент списка выбран
        if self.booklist.store.iter_n_children(None) > 0 and self.booklist.selection.get_selected_rows()[1]:
            self.mnuBooksContextMenu.popup_at_pointer(event)

    def booklist_button_pressed(self, widget, event):
        if event.button == 3: # правая кнопка мыша
            self.booklist_context_menu(event)
            return True

        return False

    def booklist_key_pressed(self, widget, event):
        if event.keyval == Gdk.KEY_Menu:
            self.booklist_context_menu(event)
            return True

        return False

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

        self.mnuBooksContextMenu.set_sensitive(nselbooks > 0)

        self.set_widgets_sensitive((self.btnextract, self.mnuitemExtractBooks), nselbooks > 0)
        #
        self.selbookcount.set_text(str(nselbooks))

    def dest_dir_changed(self, chooser):
        self.cfg.set_param(self.cfg.EXTRACT_TO_DIRECTORY, chooser.get_filename())

    def open_destination_dir(self):
        if self.env.fileManager is None:
            return

        et = 'Открытие каталога'

        extractdir, em = self.extractor.get_extraction_dir()
        if em:
            msg_dialog(self.window, et, em)
            return

        cmd = [self.env.fileManager] + self.env.fileManagerPrefixArgs
        cmd.append(extractdir)
        cmd += self.env.fileManagerSuffixArgs

        #print('running', ' '.join(cmd))
        try:
            subprocess.Popen(cmd)
        except Exception as ex:
            msg_dialog(self.window, et,
                'При запуске файлового менеджера произошла ошибка:\n%s' % (str(ex)))

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

            if self.extractopenfmchkbtn.get_active():
                self.open_destination_dir()

    def get_total_book_count(self):
        """Возвращает общее количество книг в БД"""

        return self.lib.get_table_count('books')

    def get_selected_column_value(self, col):
        """Получение значения из столбца в строке TreeView,
        на которой находится курсор.
        Если ничего не выбрано - возвращает пустую строку или None."""

        # выясняем строку в списке, на который курсор, а не просто выбранную (т.к. м.б. множественный выбор)
        path = self.booklist.view.get_cursor()[0]
        if path is not None:
            return self.booklist.store.get_value(self.booklist.store.get_iter(path), col)

    def search_by_selected_column(self, liststorecol, entryfldid):
        """Заполнение поля ввода с номером entryfldid
        (SearchFilterChooser.FLD_xxx) содержимым столбца
        из booklist.store с номером liststorecol и переключение
        на панель поиска по текстовым полям."""

        fldv = self.get_selected_column_value(liststorecol)
        if fldv:
            entry = self.choosers[self.CPAGE_SEARCH].entries[entryfldid].entry

            entry.set_text(fldv)
            self.set_chooser_page(self.CPAGE_SEARCH)
            # принудительно переключаем фокус на конкретное поле, т.к.
            # set_chooser_page() переключает на первое
            entry.grab_focus()

    def search_this_author(self):
        """Поиск книг с тем же именем автора"""

        self.search_by_selected_column(self.COL_BOOK_AUTHOR, SearchFilterChooser.FLD_AUTHORNAME)

    def search_this_title(self):
        """Поиск книг с тем же названием книги"""

        self.search_by_selected_column(self.COL_BOOK_TITLE, SearchFilterChooser.FLD_BOOKTITLE)

    def search_this_series(self):
        """Поиск книг с тем же названием цикла/сериала"""

        self.search_by_selected_column(self.COL_BOOK_SERIES, SearchFilterChooser.FLD_SERTITLE)

    def update_books_by_chooser(self):
        if self.curChooser is not None:
            self.selectWhere = self.curChooser.selectWhere
            self.update_books()

    def update_books(self):
        """Обновление списка книг."""

        if self.booklist is None:
            return

        if self.lockUpdateBooks:
            return

        self.booklist.view.set_model(None)
        self.booklist.store.clear()

        ntotalbooks = self.get_total_book_count()
        stotalbooks = '%d' % ntotalbooks
        nbooks = 0

        #print('%s  update_books(selectWhere is empty: %s)' % (datetime.datetime.now().strftime('%H:%M:%S'), self.selectWhere is None))

        if self.selectWhere is not None:
            # получаем список книг
            q = '''SELECT books.bookid,books.title,serno,seriesnames.title,date,authornames.name,filesize,filetype
                FROM books
                INNER JOIN seriesnames ON seriesnames.serid=books.serid
                INNER JOIN authornames ON authornames.authorid=books.authorid
                WHERE %s
                ORDER BY authornames.name, seriesnames.title, serno, books.title, date;'''\
                % self.selectWhere

            #print('update_books() query:', q)
            cur = self.lib.cursor.execute(q)

            # для фильтрации по дате можно сделать втык в запрос подобного:
            #  and (date > "2014-01-01") and (date < "2016-12-31")
            # или вручную фильтровать ниже
            datenow = datetime.datetime.now()

            for r in cur:
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
                    flds.authorname, # authornames.name
                    flds.title, # books.title
                    str(flds.serno) if flds.serno > 0 else '', # serno
                    flds.sertitle, # seriesnames.title
                    datestr, # date
                    dateicon, # age pixbuf
                    kilobytes_str(flds.filesize),
                    str(flds.bookid),
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
    env = None
    locked = False

    def remove_lock_file():
        if env and locked and os.path.exists(env.lockFilePath):
            os.remove(env.lockFilePath)

    def handle_unhandled(exc_type, exc_value, exc_traceback):
        # дабы не зациклиться, если че рухнет в этом обработчике
        sys.excepthook = sys.__excepthook__

        # логгер у нас тут недоступен - пишем в куда получится

        snfo = format_exception(exc_type, exc_value, exc_traceback)

        print('** Unhandled exception - %s' % exc_type.__name__)
        for s in snfo:
            print(s, file=sys.stderr)

        expander = Gtk.Expander.new_with_mnemonic('Подробнее')
        etxt = Gtk.Label.new('\n'.join(snfo))
        expander.add(etxt)

        msg_dialog(None, '%s: ошибка' % TITLE_VERSION,
            str(exc_value),
            widgets=(expander,))

        remove_lock_file()
        sys.exit(255)

    env = Environment()
    cfg = Settings(env)

    sys.excepthook = handle_unhandled

    if os.path.exists(env.lockFilePath):
        raise EnvironmentError('Программа %s уже запущена' % TITLE)

    with open(env.lockFilePath, 'w+') as lockf:
        lockf.write('%s\n' % os.getpid())
        locked = True

    try:
        cfg.load()
        try:
            #inpxFileName = cfg.get_param(cfg.IMPORT_INPX_INDEX)
            #genreNamesFile = cfg.get_param(cfg.GENRE_NAMES_PATH)

            dbexists = os.path.exists(env.libraryFilePath)
            lib = LibraryDB(env.libraryFilePath)
            print('соединение с БД')
            lib.connect()
            """FIXME когда-нибудь прикрутить проверки на наличие таблиц в БД,
            дабы не лаялось исключениями на отсутствующие таблицы в ситуациях, когда БД только что
            создана и ещё не содержит таблиц."""
            """FIXME переделать проверку на необходимость импорта индекса при пустой БД."""
            try:
                if not dbexists:
                    lib.init_tables()

                print('запуск UI')
                mainwnd = MainWnd(lib, env, cfg)
                mainwnd.main()
            finally:
                lib.disconnect()
        finally:
            cfg.unload()
    finally:
        remove_lock_file()

    return 0


if __name__ == '__main__':
    exit(main())
