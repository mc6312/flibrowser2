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

import os.path

from time import time, sleep


class MainWnd():
    """Основное междумордие"""

    COL_AUTHALPHA_L1 = 0

    COL_AUTH_ID, COL_AUTH_NAME = range(2)

    COL_BOOK_ID, COL_BOOK_TITLE, COL_BOOK_SERNO, COL_BOOK_SERIES, \
    COL_BOOK_DATE, COL_BOOK_LANG = range(6)

    def destroy(self, widget, data=None):
        #self.update_ui_state(ctrls=True) # только состояние кнопок - потому что размер окна здесь уже неправильный
        #self.save_ui_state()
        Gtk.main_quit()

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

    def __create_ui(self):
        #!!!self.uistate = MainWndSettings(os.path.join(library.cfgDir, u'uistate'))

        self.window = Gtk.ApplicationWindow(Gtk.WindowType.TOPLEVEL)
        #self.window.connect('configure_event', self.wnd_configure_event)
        #self.window.connect('window_state_event', self.wnd_state_event)
        #self.window.connect('size-allocate', self.wnd_size_allocate)
        self.window.connect('destroy', self.destroy)

        self.window.set_title(TITLE_VERSION)

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
        hbtb = Gtk.HBox(spacing=WIDGET_SPACING)
        self.ctlvbox.pack_start(hbtb, False, False, 0)

        # title, pack_end, handler
        tbitems = (('Настройка', False, lambda b: self.change_settings()),
            ('Импорт библиотеки', False, lambda b: self.import_library()),
            ('О программе', True, lambda b: self.dlgabout.run()),)

        for label, toend, handler in tbitems:
            btn = Gtk.Button(label)
            btn.connect('clicked', handler)

            (hbtb.pack_end if toend else hbtb.pack_start)(btn, False, False, 0)

        #
        # морда будет из двух вертикальных панелей
        #

        roothbox = Gtk.HBox(spacing=WIDGET_SPACING) # потом, возможно, будет Gtk.HPaned
        self.ctlvbox.pack_start(roothbox, True, True, 0)

        #
        # в левой панели - алфавитный список авторов
        # (из двух отдельных виджетов Gtk.TreeView)
        #
        fr = Gtk.Frame.new('Авторы')
        roothbox.pack_start(fr, False, False, 0)

        apanel = Gtk.VBox(spacing=WIDGET_SPACING)
        apanel.set_border_width(WIDGET_SPACING)
        apanel.set_size_request(384, -1) #!!!
        fr.add(apanel)

        ahbox = Gtk.HBox(spacing=WIDGET_SPACING)
        apanel.pack_start(ahbox, True, True, 0)

        # первые буквы имён авторов
        self.authalphalist = TreeViewer((GObject.TYPE_STRING,),
            (TreeViewer.ColDef(self.COL_AUTHALPHA_L1, '', False, True),))

        self.authalphalist.view.set_headers_visible(False)
        self.authalphalist.view.set_enable_search(True)
        ahbox.pack_start(self.authalphalist.window, False, False, 0)

        #self.authalphalist.selection.set_mode(Gtk.SelectionMode.SINGLE)
        self.authalphalist.selection.connect('changed', self.authalphalist_selected)

        # имена авторов
        self.authlist = TreeViewer(
            # authorid, name
            (GObject.TYPE_INT, GObject.TYPE_STRING),
            (TreeViewer.ColDef(self.COL_AUTH_NAME, '', False, True),))

        self.authlist.view.set_headers_visible(False)
        self.authlist.view.set_enable_search(True)

        self.authlist.view.set_tooltip_column(self.COL_AUTH_NAME)

        self.authlist.selection.connect('changed', self.authlist_selected)

        ahbox.pack_end(self.authlist.window, True, True, 0)

        ahpanel = Gtk.HBox(spacing=WIDGET_SPACING)
        apanel.pack_end(ahpanel, False, False, 0)

        create_labeled_entry(ahpanel, 'Имя:', self.authornameentry_changed, True)

        #
        # в правой панели - список книг соотв. автора и управление распаковкой
        #

        fr = Gtk.Frame.new('Книги')
        roothbox.pack_end(fr, True, True, 0)

        bpanel = Gtk.VBox(spacing=WIDGET_SPACING)
        bpanel.set_border_width(WIDGET_SPACING)
        fr.add(bpanel)

        # список книг

        self.booklist = TreeViewer(
            (GObject.TYPE_INT,      # bookid
                GObject.TYPE_STRING,# title
                GObject.TYPE_STRING,# series
                GObject.TYPE_STRING,# serno
                GObject.TYPE_STRING,# date
                GObject.TYPE_STRING),# language
            (TreeViewer.ColDef(self.COL_BOOK_TITLE, 'Название', False, True),
                TreeViewer.ColDef(self.COL_BOOK_SERNO, '#', False, False, 1.0),
                TreeViewer.ColDef(self.COL_BOOK_SERIES, 'Цикл', False, True),
                TreeViewer.ColDef(self.COL_BOOK_DATE, 'Дата'),
                TreeViewer.ColDef(self.COL_BOOK_LANG, 'Яз.')))

        self.booklist.view.connect('motion-notify-event', self.booklist_mouse_moved)

        self.booklist.selection.set_mode(Gtk.SelectionMode.MULTIPLE)
        self.booklist.selection.connect('changed', self.booklist_selected)

        bpanel.pack_start(self.booklist.window, True, True, 0)

        # фильтрация списка книг по названию книги и названию цикла
        blhbox = Gtk.HBox(spacing=WIDGET_SPACING)
        bpanel.pack_start(blhbox, False, False, 0)

        create_labeled_entry(blhbox, 'Название:', self.booklisttitlepattern_changed, True)

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

        self.update_authors_alpha()

        self.window.show_all()

        #self.load_ui_state()

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
        self.authorNamePattern = '' # строка для фильтрации списка авторов
        self.booklistTitlePattern = ''

        self.selectedAuthorAlpha = None # присваивается при выборе первой буквы автора в списке
        self.selectedAuthorId = 0 # присваивается при выборе автора в списке

        # создаём междумордие
        self.__create_ui()

        self.check_1st_run()

    def check_1st_run(self):
        """Проверка на первый запуск и, при необходимости, первоначальная настройка."""

        if not self.cfg.has_required_settings():
            if self.dlgsetup.run('Первоначальная настройка') != Gtk.ResponseType.OK:
                msg_dialog(self.window, TITLE_VERSION, 'Не могу работать без настройки', Gtk.MessageType.ERROR)
                exit(1) #!!!
            else:
                self.import_library()

    def import_library(self):
        self.begin_task('Импорт библиотеки')
        try:
            print('Инициализация БД (%s)...' % self.env.libraryFilePath)
            self.task_msg('Инициализация БД')
            self.lib.init_db()

            inpxFileName = self.cfg.get_param(self.cfg.INPX_INDEX)
            print('Импорт индекса библиотеки "%s"...' % inpxFileName)
            self.task_msg('Импорт индекса библиотеки')
            importer = INPXImporter(self.lib)
            importer.import_inpx_file(inpxFileName, self.task_progress)

            self.update_authors_alpha()

        finally:
            self.end_task()

    def change_settings(self):
        self.dlgsetup.run()

    def extractfntemplatecb_changed(self, cb, data=None):
        self.extractTemplateIndex = cb.get_active()
        if self.extractTemplateIndex < 0:
            self.extractTemplateIndex = 0

        self.cfg.set_param(self.cfg.EXTRACT_FILE_NAMING_SCHEME,
            fbfntemplate.templates[self.extractTemplateIndex].NAME)

    def extracttozipbtn_clicked(self, cb, data=None):
        self.cfg.set_param_bool(self.cfg.EXTRACT_PACK_ZIP, cb.get_active())

    def authornameentry_changed(self, entry, data=None):
        self.authorNamePattern = entry.get_text().strip().lower()
        self.update_authors()

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

    def update_authors_alpha(self):
        """Обновление списка авторов"""

        # первые буквы имён авторов
        self.authalphalist.view.set_model(None)
        self.authalphalist.store.clear()

        cur = self.lib.cursor.execute('''select alpha from authornamealpha order by alpha;''')
        while True:
            r = cur.fetchone()
            if r is None:
                break

            self.authalphalist.store.append((r[0],))

        self.authalphalist.view.set_model(self.authalphalist.store)
        self.authalphalist.view.set_search_column(self.COL_AUTHALPHA_L1)

    def get_list_column(self, listview, column):
        #listview.get_value(self.booklist.get_iter(ix), 0)
        pass

    def authalphalist_selected(self, sel, data=None):
        """Обработка события выбора элемента(ов) в списке первых букв имён авторов"""

        rows = self.authalphalist.selection.get_selected_rows()[1]
        if rows:
            self.selectedAuthorAlpha = self.authalphalist.store.get_value(self.authalphalist.store.get_iter(rows[0]), self.COL_AUTHALPHA_L1)
        else:
            self.selectedAuthorAlpha = None

        self.update_authors()

    def update_authors(self):
        self.authlist.view.set_model(None)
        self.authlist.store.clear()

        if self.selectedAuthorAlpha:
            cur = self.lib.cursor.execute('''select authorid,name from authornames where authorid in
                (select authorid from authornamealpharefs where alpha=?) order by name;''', (self.selectedAuthorAlpha,))

            while True:
                r = cur.fetchone()
                if r is None:
                    break

                # фильтрация по начальным буквам имени автора.
                # вручную, ибо лень прикручивать collation к sqlite3

                if self.authorNamePattern and not r[1].lower().startswith(self.authorNamePattern):
                    continue

                self.authlist.store.append((r[0], r[1]))

        self.authlist.view.set_model(self.authlist.store)
        self.authlist.view.set_search_column(self.COL_AUTH_NAME)

    def authlist_selected(self, sel, data=None):
        """Обработка события выбора элемента(ов) в списке имён авторов"""

        rows = self.authlist.selection.get_selected_rows()[1]

        if rows:
            self.selectedAuthorId = self.authlist.store.get_value(self.authlist.store.get_iter(rows[0]), self.COL_AUTH_ID)
        else:
            self.selectedAuthorId = None

        self.update_books()

    def update_books(self):
        self.booklist.view.set_model(None)
        self.booklist.store.clear()

        # куда-то сюда присобачить выковыр названия цикла!
        cur = self.lib.cursor.execute('''select bookid,books.title,serno,seriesnames.title,date,language
            from books inner join seriesnames on seriesnames.serid=books.serid
            where authorid=?
            order by seriesnames.title, serno, books.title, date;''', (self.selectedAuthorId,))
        # для фильтрации по дате сделать втык в запрос подобного:
        #  and (date > "2014-01-01") and (date < "2016-12-31")

        while True:
            r = cur.fetchone()
            if r is None:
                break

            # поля, которые могут потребовать доп. телодвижений
            title = r[1]
            seriestitle = r[3]

            # подразумеваятся, что в соотв. поле БД точно есть хоть какая-то дата
            date = datetime.datetime.strptime(r[4], DB_DATE_FORMAT)
            # тут, возможно, будет код для показа соответствия "дата - цвет 'свежести' книги"
            # и/или фильтрация по дате
            datestr = date.strftime(DISPLAY_DATE_FORMAT)

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
                r[5], # language
                ))

        self.booklist.view.set_model(self.booklist.store)
        self.booklist.view.set_search_column(self.COL_BOOK_TITLE)
        self.booklist.view.set_search_equal_func(self.booklist_search_func)

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
        #inpxFileName = cfg.get_param(cfg.INPX_INDEX)
        #genreNamesFile = cfg.get_param(cfg.GENRE_NAMES_PATH)

        lib = LibraryDB(env.libraryFilePath)
        lib.connect()
        try:
            mainwnd = MainWnd(lib, env, cfg)
            mainwnd.main()
        finally:
            lib.disconnect()
    finally:
        cfg.unload()

    return 0


if __name__ == '__main__':
    exit(main())
