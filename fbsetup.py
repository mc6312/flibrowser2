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
    def __init__(self, env, cfg, uibldr):
        """Инициализация.

        env - экземпляр fbenv.Environment,
        cfg - экземпляр fbenv.Settings,
        uibldr - экземпляр Gtk.Builder."""

        self.env = env
        self.cfg = cfg

        self.settingsChanged = False

        self.dialog = uibldr.get_object('dlgSetup')

        # за каким-то фигом Glade именно это не умеет
        self.dialog.set_default_response(Gtk.ResponseType.OK)

        #
        # временное хранение настроек. в БД настроек они будут занесены только
        # в случае нажатия кнопки "ОК" и правильности всех настроек!
        #
        self.libraryDirectory = self.cfg.get_param(self.cfg.LIBRARY_DIRECTORY, os.path.expanduser('~'))
        self.libraryIndexFile = self.cfg.get_param(self.cfg.IMPORT_INPX_INDEX, os.path.expanduser('~'))

        self.libraryLanguages = self.cfg.get_param_set(self.cfg.IMPORT_LANGUAGES, self.cfg.DEFAULT_IMPORT_LANGUAGES)
        self.libraryLanguages.update(self.cfg.DEFAULT_IMPORT_LANGUAGES)
        # всегда добавляется множество (set) языков, приколоченных гвоздями

        #
        #
        #

        self.libdirchooser = uibldr.get_object('libdirchooser')
        self.libdirchooser.set_filename(self.libraryDirectory)
        #self.libdirchooser.connect('selection-changed', self.lib_dir_changed)

        #
        #
        #
        self.libindexchooser = uibldr.get_object('libindexchooser')
        self.libindexchooser.set_filename(self.libraryIndexFile)

        #
        #
        #
        self.liblanguagesentry = uibldr.get_object('liblanguagesentry')
        self.liblanguagesentry.set_text(' '.join(self.libraryLanguages))

    def get_data(self):
        """Забирает значения из виджетов.
        Возвращает None или пустую строку в случае правильных значений,
        иначе возвращает строку с сообщением об ошибке."""

        self.settingsChanged = False

        #
        v = self.libdirchooser.get_filename()
        if not v:
            return 'Не указан каталог библиотеки'

        if not os.path.isdir(v):
            return 'Каталог библиотеки указан неправильно'

        if v != self.libraryDirectory:
            self.libraryDirectory = v
            self.settingsChanged = True

        #
        v = self.libindexchooser.get_filename()
        if not v:
            return 'Не указан файл индекса библиотеки'

        if not os.path.isfile(v):
            return 'Неправильно указан файл индекса библиотеки'

        if v != self.libraryIndexFile:
            self.libraryIndexFile = v
            self.settingsChanged = True

        #
        v = set(self.liblanguagesentry.get_text().lower().split(None))
        v.update(self.cfg.DEFAULT_IMPORT_LANGUAGES)
        # всегда добавляется множество (set) языков, приколоченных гвоздями

        if v != self.libraryLanguages:
            self.libraryLanguages = v
            self.settingsChanged = True

        return None

    def flush_settings(self):
        """"Наконец-то складываем настройки в БД настроек."""

        self.cfg.set_param(self.cfg.LIBRARY_DIRECTORY, self.libraryDirectory)
        self.cfg.set_param(self.cfg.IMPORT_INPX_INDEX, self.libraryIndexFile)
        self.cfg.set_param_set(self.cfg.IMPORT_LANGUAGES, self.libraryLanguages)

    def run(self, title=None):
        """Запуск диалога.

        run - строка заголовка или None."""

        if title:
            self.dialog.set_title(title)
        self.dialog.show_all()

        while True:
            r = self.dialog.run()

            if r == Gtk.ResponseType.OK:
                e = self.get_data()
                if e:
                    msg_dialog(self.dialog, 'Ошибка', e, Gtk.MessageType.ERROR)
                else:
                    if self.settingsChanged:
                        self.flush_settings()
                    break
            elif r in (Gtk.ResponseType.CANCEL, Gtk.ResponseType.DELETE_EVENT):
                break

        self.dialog.hide()

        return r


if __name__ == '__main__':
    print('[debugging %s]' % __file__)

    import fbenv

    env = fbenv.Environment()
    cfg = fbenv.Settings(env)
    cfg.load()
    ldr = get_resource_loader(env)
    uibldr = ldr.load_gtk_builder('flibrowser2.ui')
    try:
        dlg = SetupDialog(env, cfg, uibldr)
        print(dlg.run())
    finally:
        cfg.unload()
