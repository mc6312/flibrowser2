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

from gi.repository import Gtk, GLib
from gi.repository.GdkPixbuf import Pixbuf

from fbgtk import *


LOGO_SIZE = WIDGET_WIDTH_UNIT*8


class AboutDialog():
    ICONNAME = 'flibrowser2.svg'

    def __init__(self, parentwnd, env):
        """Создание и первоначальная настройка.

        parentwnd   - экземпляр Gtk.Window или None,
        env         - экземпляр fbenv.Environment."""

        self.dlgabout = Gtk.AboutDialog(parent=parentwnd)

        ldr = get_resource_loader(env)
        try:
            logo = ldr.load_bytes(self.ICONNAME)

            logotype = ldr.pixbuf_from_bytes(logo, LOGO_SIZE, LOGO_SIZE)

            rok, rw, rh = Gtk.IconSize.lookup(Gtk.IconSize.DIALOG)
            # проверять rok == True не буду - если ф-я на стандартное значение
            # не вернет соотв. размер, то поломат либо gtk, либо gobject, и пошло всё в жопу

            self.windowicon = ldr.pixbuf_from_bytes(logo, rw, rh)

        except Exception as ex:
            print('Не удалось загрузить файл изображения "%s" - %s' % (self.ICONNAME, str(ex)))
            logotype = self.dlgabout.render_icon_pixbuf('gtk-find', Gtk.IconSize.DIALOG)
            self.windowicon = logotype

        self.dlgabout.set_icon(self.windowicon)

        self.dlgabout.set_size_request(WIDGET_WIDTH_UNIT*24, WIDGET_WIDTH_UNIT*32)
        self.dlgabout.set_copyright(COPYRIGHT)
        self.dlgabout.set_version('версия %s' % VERSION)
        self.dlgabout.set_program_name(TITLE)
        self.dlgabout.set_logo(logotype)

        try:
            slicense = str(ldr.load('COPYING'), 'utf-8')
        except:
            slicense = None

        #self.dlgabout.set_license_type(Gtk.License.GPL_3_0_ONLY)
        self.dlgabout.set_license_type(Gtk.License.GPL_3_0) #???
        self.dlgabout.set_license(slicense if slicense else 'Файл с текстом GPL не найден.\nЧитайте https://www.gnu.org/licenses/gpl.html')

        self.dlgabout.set_website(URL)
        self.dlgabout.set_website_label(URL)

        self.dlgabout.add_credit_section('Сляпано во славу', ['Азатота', 'Йог-Сотота', 'Ктулху', 'Шаб-Ниггурат', 'и прочей кодлы Великих Древних'])
        self.dlgabout.add_credit_section('Особая благодарность', ['Левой ноге автора'])

    def run(self):
        self.dlgabout.show_all()
        self.dlgabout.run()
        self.dlgabout.hide()


def main():
    print('[%s test]' % __file__)

    import fbenv

    AboutDialog(None, fbenv.Environment()).run()

if __name__ == '__main__':
    exit(main())
