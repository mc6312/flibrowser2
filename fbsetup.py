#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" fbsetup.py

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


"""Диалоговое окно настройки и сопутствующая хрень"""


import os.path

from fbcommon import *

from gi.repository import Gtk, GLib
from gi.repository.GdkPixbuf import Pixbuf

from fbgtk import *


class SetupDialog():
    def __init__(self, wparent, env, cfg):
        """Инициализация.

        env - экземпляр fbenv.Environment,
        cfg - экземпляр fbenv.Settings."""

        self.env = env
        self.cfg = cfg

        self.dialog = Gtk.Dialog(parent=wparent, title='Настройки')

        #self.dialog.set_size_request(800, 600)
        self.dialog.add_buttons('gtk-ok', Gtk.ResponseType.OK, 'gtk-cancel', Gtk.ResponseType.CANCEL)
        self.dialog.set_default_response(Gtk.ResponseType.OK)

        box = self.dialog.get_content_area()

        grid = LabeledGrid()
        box.pack_start(grid, True, True, 0)

        #
        # временное хранение настроек. в БД настроек они будут занесены только
        # в случае нажатия кнопки "ОК" и правильности всех настроек!
        #
        self.libraryDirectory = self.cfg.get_param(self.cfg.LIBRARY_DIRECTORY, os.path.expanduser('~'))
        self.libraryIndexFile = self.cfg.get_param(self.cfg.INPX_INDEX, os.path.expanduser('~'))

        #
        #
        #
        grid.append_row('Каталог, где расположены архивы с книгами:')

        self.libdirchooser = Gtk.FileChooserButton.new('Выбор каталога библиотеки', Gtk.FileChooserAction.SELECT_FOLDER)

        self.libdirchooser.set_filename(self.libraryDirectory)
        self.libdirchooser.set_create_folders(False)
        #self.libdirchooser.connect('selection-changed', self.lib_dir_changed)

        grid.append_col(self.libdirchooser, True)

        #
        #
        #
        grid.append_row('Файл индекса библиотеки:')
        self.libindexchooser = Gtk.FileChooserButton.new('Выбор файла индекса библиотеки', Gtk.FileChooserAction.OPEN)
        self.libindexchooser.set_create_folders(False)
        self.libindexchooser.set_filename(self.libraryIndexFile)

        inpxfiles = Gtk.FileFilter()
        inpxfiles.set_name('Файлы индекса (.INPX)')
        for ptn in ('*.INPX', '*.inpx'):
            inpxfiles.add_pattern(ptn)
        self.libindexchooser.add_filter(inpxfiles)

        grid.append_col(self.libindexchooser, True)

    def get_data(self):
        """Забирает значения из виджетов.
        Возвращает None или пустую строку в случае правильных значений,
        иначе возвращает строку с сообщением об ошибке."""

        self.libraryDirectory = self.libdirchooser.get_filename()
        if not self.libraryDirectory:
            return 'Не указан каталог библиотеки'

        if not os.path.isdir(self.libraryDirectory):
            return 'Каталог библиотеки указан неправильно'

        self.libraryIndexFile = self.libindexchooser.get_filename()
        if not self.libraryIndexFile:
            return 'Не указан файл индекса библиотеки'

        if not os.path.isfile(self.libraryIndexFile):
            return 'Неправильно указан файл индекса библиотеки'

        return None

    def flush_settings(self):
        """"Наконец-то складываем настройки в БД настроек."""

        self.cfg.set_param(self.cfg.LIBRARY_DIRECTORY, self.libraryDirectory)
        self.cfg.set_param(self.cfg.INPX_INDEX, self.libraryIndexFile)

    def run(self):
        self.dialog.show_all()

        while True:
            r = self.dialog.run()

            if r == Gtk.ResponseType.OK:
                e = self.get_data()
                if e:
                    msg_dialog(self.dialog, 'Ошибка', e, Gtk.MessageType.ERROR)
                else:
                    self.flush_settings()
                    break
            elif r == Gtk.ResponseType.CANCEL:
                break

        self.dialog.hide()

        return r


if __name__ == '__main__':
    print('[test]')

    import fbenv

    env = fbenv.Environment()
    cfg = fbenv.Settings(env)
    cfg.load()
    try:
        dlg = SetupDialog(None, env, cfg)
        print(dlg.run())
    finally:
        cfg.unload()
