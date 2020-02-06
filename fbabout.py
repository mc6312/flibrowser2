#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" fbabout.py

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


import os.path

from fbcommon import *
from fbgtk import *

from gi.repository import Gtk, GLib
from gi.repository.GdkPixbuf import Pixbuf

from sys import stderr


class AboutDialog():
    ICONNAME = 'images/flibrowser2.svg'

    def __init__(self, resldr, uibldr):
        """Создание и первоначальная настройка.

        resldr      - экземпляр fbgtk.ResourceLoader,
        uibldr      - экземпляр Gtk.Builder."""

        self.dlgabout = uibldr.get_object('dlgAbout')

        logoSize = Gtk.IconSize.lookup(Gtk.IconSize.DIALOG)[1] * 3

        self.windowicon = resldr.load_pixbuf(self.ICONNAME, logoSize, logoSize, 'gtk-find')

        #self.dlgabout.set_icon(self.windowicon)

        self.dlgabout.set_copyright(COPYRIGHT)
        self.dlgabout.set_version('версия %s' % VERSION)
        self.dlgabout.set_program_name(TITLE)
        self.dlgabout.set_logo(self.windowicon)

        try:
            slicense = str(resldr.load('COPYING'), 'utf-8')
        except:
            slicense = 'Файл с текстом GPL не найден.\nЧитайте https://www.gnu.org/licenses/gpl.html'

        #self.dlgabout.set_license_type(Gtk.License.GPL_3_0_ONLY)
        self.dlgabout.set_license_type(Gtk.License.GPL_3_0) #???
        self.dlgabout.set_license(slicense)

        self.dlgabout.set_website(URL)
        self.dlgabout.set_website_label(URL)

        self.dlgabout.add_credit_section('Сляпано во славу',
            ['Азатота', 'Йог-Сотота', 'Ктулху', 'Шаб-Ниггурат', 'Хастура', 'Тсаттоггуа', 'Гатаноа', 'Ран-Тегота', 'и прочих'])
        self.dlgabout.add_credit_section('Особая благодарность', ['Левой ноге автора'])

        #abcontentbox = uibldr.get_object('abcontentbox')

    def run(self):
        self.dlgabout.show_all()
        self.dlgabout.run()
        self.dlgabout.hide()


def main():
    print('[%s test]' % __file__)

    from fbenv import Environment
    ldr = get_resource_loader(Environment())
    uibldr = ldr.load_gtk_builder('flibrowser2.ui')
    AboutDialog(ldr, uibldr).run()

if __name__ == '__main__':
    exit(main())
