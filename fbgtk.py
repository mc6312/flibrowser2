#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" fbgtk.py

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


GTK_VERSION = '3.0'
from gi import require_version
require_version('Gtk', GTK_VERSION) # извращенцы

from gi.repository import Gtk, Gdk, GObject, Pango, GLib, Gio
from gi.repository.GdkPixbuf import Pixbuf

import cairo

import os.path
import zipfile
from sys import stderr
from random import randrange
from math import pi

# отступы между виджетами, дабы не вырвало от пионерского вида гуя

__pangoContext = Gdk.pango_context_get()

WIDGET_BASE_UNIT = int(__pangoContext.get_metrics(__pangoContext.get_font_description(),
    None).get_approximate_char_width() / Pango.SCALE)

WIDGET_SPACING = WIDGET_BASE_UNIT // 2
if WIDGET_SPACING < 4:
    WIDGET_SPACING = 4

# Вынимание! GTK желает юникода!
UI_ENCODING = 'utf-8'


def create_scwindow():
    """Создает и возвращает экземпляр Gtk.ScrolledWindow"""

    scwindow = Gtk.ScrolledWindow()
    scwindow.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
    scwindow.set_shadow_type(Gtk.ShadowType.IN)

    return scwindow


def create_labeled_frame(txt, *widgets):
    """Создаёт экземпляры Gtk.Frame и Gtk.Label.

    txt     - текст для заголовка Frame,
    widgets - необязательный произвольный список доп. виджетов,
              добавляемых в заголовок.

    Возвращает Frame и Label."""

    hbox = Gtk.HBox(spacing=WIDGET_SPACING)

    lab = Gtk.Label(txt)
    lab.set_use_underline(True)
    hbox.pack_start(lab, False, False, 0)

    for wgt in widgets:
        hbox.pack_start(wgt, False, False, 0)

    fr = Gtk.Frame()
    fr.set_label_widget(hbox)

    return fr, lab


def create_aligned_label(title, halign=0.0, valign=0.0):
    label = Gtk.Label(title)
    label.set_alignment(halign, valign)
    #label.set_justify(Gtk.Justification.LEFT)
    return label


def create_labeled_entry(box, labtext, eventhandler, expand=False):
    """Создаёт в контейнере box виджеты Gtk.Label(labtext)
    и Gtk.Entry.
    expand - режим расположения entry в box.
    Возврашает экземпляр Gtk.Entry"""

    box.pack_start(Gtk.Label(labtext), False, False, 0)

    entry = Gtk.Entry()
    entry.connect('changed', eventhandler)

    box.pack_start(entry, expand, expand, 0)

    return entry


class TreeViewer():
    """Класс-костыль для создания Gtk.Tree|ListView и сопутствующих
    объектов."""

    class ColDef():
        """Класс для параметров создания Gtk.TreeViewColumn"""

        def __init__(self, index, title='', editable=False,
            expand=False, align=0.0, markup=False, tooltip=None):
            """index    - номер столбца в List|TreeStore,
            title       - отображаемое в заголовке название,
            editable    - (булевское) запрет/разрешение редактирования ячейки,
            expand      - (булевское) фиксированная/автоматическая ширина,
            align       - (0.0..1.0) выравнивание содержимого ячейки,
            markup      - (булевское) для столбцов типа GObject.TYPE_STRING:
                          True - использовать Pango Markup при отображении столбца,
                          False - отображать как простой текст,
            tooltip     - если не None, то целое - индекс столбца в *Store,
                          который должен использоваться для отображения
                          tooltips (всплывающих подсказок);
                          если None - для подсказки будет использован
                          столбец index."""

            self.index = index
            self.title = title
            self.editable = editable
            self.expand = expand
            self.align = align
            self.markup = markup
            self.tooltip = tooltip if tooltip is not None else index

    def __init__(self, coltypes, coldefs, islist=True):
        """Создает объекты.

        Параметры:
            coltypes    - список типов данных для столбцов *Store
                          (GObject.TYPE_*),
            coldefs     - список параметров столбцов, где элементы списка
                          либо экземпляры TreeViewer.ColDef,
                          либо списки/кортежи экземпляров TreeViewer.ColDef,
                          в последнем случае в одном столбце размещается
                          несколько Gtk.CellRenderer'ов, а значения title,
                          expand и tooltip для TreeViewColumn берётся
                          из первого элемента списка
            islist      - если True - создаётся ListStore, иначе TreeStore

        Поля:
            view        - экземпляр Gtk.TreeView
            store       - экземпляр Gtk.Tree|ListStore
            selection   - экземпляр Gtk.TreeViewSelection
            window      - экземпляр Gtk.ScrolledWindow
            columns     - список экземпляров Gtk.TreeViewColumn
            renderers   - список экземпляров Gtk.CellRenderer*
            colmap      - словарь, где ключи - экземпляры Gtk.TreeViewColumn,
                          а значения - индексы соотв. столбцов в store
                          (для динамического присвоения tooltip column и т.п.)."""

        self.store = (Gtk.ListStore if islist else Gtk.TreeStore)(*coltypes)

        self.view = Gtk.TreeView(self.store)
        self.view.set_border_width(WIDGET_SPACING)

        self.view.set_rules_hint(True)

        self.selection = self.view.get_selection()

        self.window = create_scwindow()
        self.window.add(self.view)

        self.renderers = []
        self.columns = []
        self.colmap = {}

        def __pack_col(col, coldef):
            ctype = coltypes[coldef.index]

            if ctype == GObject.TYPE_BOOLEAN:
                crt = Gtk.CellRendererToggle()
                crtpar = 'active'
            elif ctype == GObject.TYPE_STRING:
                crt = Gtk.CellRendererText() #!!!
                crt.props.xalign = coldef.align
                crt.props.ellipsize = Pango.EllipsizeMode.END \
                    if coldef.expand \
                    else Pango.EllipsizeMode.NONE
                crt.props.editable = coldef.editable
                crtpar = 'text' if not coldef.markup else 'markup'
            elif ctype == Pixbuf:
                crt = Gtk.CellRendererPixbuf()
                crt.props.xalign = coldef.align
                crtpar = 'pixbuf'
            else:
                raise ValueError('%s.__init__: неподдерживаемый тип данных столбца Gtk.ListStore' % self.__class__.__name__)

            self.renderers.append(crt)
            col.pack_start(crt, coldef.expand)
            col.add_attribute(crt, crtpar, coldef.index)

        for coldef in coldefs:
            col = Gtk.TreeViewColumn.new()
            self.columns.append(col)

            if isinstance(coldef, (list, tuple)):
                for subcoldef in coldef:
                    __pack_col(col, subcoldef)
                params = coldef[0]
            else:
                __pack_col(col, coldef)
                params = coldef

            self.view.append_column(col)
            col.set_title(params.title)
            col.set_sizing(Gtk.TreeViewColumnSizing.GROW_ONLY)
            col.set_resizable(params.expand)
            col.set_expand(params.expand)
            self.colmap[col] = params.tooltip

    def select_item_ix(self, ix):
        """Выбор в списке элемента с номером ix"""

        path = Gtk.TreePath.new_from_indices((ix,))
        self.selection.select_path(path)
        self.view.scroll_to_cell(path, None, True, True, False)

    def random_choice(self):
        """Выбор случайного элемента в списке.

        Возвращает True в случае успеха,
        False в случае пустого списка."""

        nitems = self.store.iter_n_children()
        if nitems <= 0:
            return False

        self.select_item_ix(randrange(nitems))

        return True


def msg_dialog(parent, title, msg, msgtype=Gtk.MessageType.WARNING, buttons=Gtk.ButtonsType.OK):
    dlg = Gtk.MessageDialog(parent, 0, msgtype, buttons, msg,
        #use_header_bar=True, # странно ведёт себя в GNOME, кто б мог подумать?
        flags=Gtk.DialogFlags.MODAL|Gtk.DialogFlags.DESTROY_WITH_PARENT)
    dlg.set_title(title)
    r = dlg.run()
    dlg.destroy()
    return r


class BookAgeIcons():
    """Класс, создающий и хранящий список GdkPixbuf для отображения
    "свежести" книг в виде цветовых меток."""

    # потом когда-нибудь надо будет присобачить загрузку палитры из файла

    BOOK_AGE_COLORS = ('#00FF00',
        '#A8FF00',
        '#B8FF00',
        '#FFFF00',
        '#FFF400',
        '#FFD700',
        '#FFB900',
        '#FF9C00',
        '#FF7A00',
        '#FF5A00',
        '#FF3A00',
        '#FF1B00',
        '#EE2D1A',
        '#E03C2F',
        '#D34A43',
        '#C55958',
        '#B8676D',
        '#AA7681',
        '#9D8496',
        '#8F93AA')

    BOOK_AGE_MAX = len(BOOK_AGE_COLORS) - 1

    def __init__(self, iconSize):
        """Создание списка икон (экземпляров GdkPixbuf.Pixbuf).

        iconSize - константа Gtk.IconSize.*."""

        _ok, self.iconSizePx, ih = Gtk.IconSize.lookup(iconSize)
        # прочие возвращённые значения фпень - у нас тут иконки строго квадратные

        self.icons = []

        for color in self.BOOK_AGE_COLORS:
            self.icons.append(self.__create_icon(color))

    def __create_icon(self, color):
        """Создаёт и возвращает экземпляр GdkPixbuf.Pixbuf заданного цвета.

        color - значение цвета в виде строки "#RRGGBB"."""

        _ok, gclr = Gdk.Color.parse(color)
        gclr = gclr.to_floats()

        csurf = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.iconSizePx, self.iconSizePx)

        cc = cairo.Context(csurf)
        #cc.scale(iconSize, iconSize)

        center = self.iconSizePx / 2.0
        radius = center * 0.7
        circle = 2 * pi

        cc.set_source(cairo.SolidPattern(0.0, 0.0, 0.0))

        cc.arc(center, center, radius, 0.0, circle)
        cc.fill()

        radius1 = radius - 1.0

        cc.set_source(cairo.SolidPattern(*gclr))
        cc.arc(center, center, radius1, 0.0, circle)
        cc.fill()

        return Gdk.pixbuf_get_from_surface(csurf, 0, 0, self.iconSizePx, self.iconSizePx)

    def __get_book_age_index(self, nowdate, bookdate):
        """Возвращает индекс в диапазоне 0..BOOK_AGE_MAX, соответствующий
        "свежести" книги.
        Готовой функции, считающей в месяцах, в стандартной библиотеке нет,
        возиться с точными вычислениями, учитывающими месяцы разной длины
        и високосные года, а также обвешивать софтину зависимостями на
        сторонние библиотеки мне влом, а потому "свежесть" считается
        в четырёхнедельных промежутках от текущей даты (nowdate).

        nowdate, bookdate - экземпляры dateitme.date или dateitme.datetime."""

        delta = (nowdate - bookdate).days // 28

        if delta < 0:
            # нет гарантии, что в БД лежала правильная дата
            delta = 0
        elif delta > self.BOOK_AGE_MAX:
            delta = self.BOOK_AGE_MAX

        return delta

    def get_book_age_color(self, nowdate, bookdate):
        """Возвращает цвет в виде "#RRGGBB", соответствующий "свежести" книги.

        nowdate, bookdate - экземпляры dateitme.date или dateitme.datetime."""

        return self.BOOK_AGE_COLORS[self.__get_book_age_index(nowdate, bookdate)]

    def get_book_age_icon(self, nowdate, bookdate):
        """Возвращает экземпляр GdkPixbuf.Pixbuf, соответствующий "свежести" книги.

        nowdate, bookdate - экземпляры dateitme.date или dateitme.datetime."""

        return self.icons[self.__get_book_age_index(nowdate, bookdate)]


class LabeledGrid(Gtk.Grid):
    """Виджет для таблиц с несколькими столбцами (Label и что-то еще)"""

    def __init__(self):
        Gtk.Grid.__init__(self)

        self.set_row_spacing(WIDGET_SPACING)
        self.set_column_spacing(WIDGET_SPACING)
        self.set_border_width(WIDGET_SPACING)

        self.currow = None # 1й виджет в строке
        self.curcol = None # последний виджет в строке

        self.label_xalign = 0.0
        self.label_yalign = 0.5

    def append_row(self, labtxt):
        """Добавление строки с виджетами.
        labtxt - текст для Label в левом столбце;
        Возвращает экземпляр Label, дабы можно было его скормить grid.attach_next_to()."""

        lbl = Gtk.Label(labtxt)
        lbl.set_alignment(self.label_xalign, self.label_yalign)
        lbl.set_use_underline(True)

        self.attach_next_to(lbl, self.currow, Gtk.PositionType.BOTTOM, 1, 1)
        self.currow = lbl
        self.curcol = lbl

        return lbl

    def append_col(self, widget, expand=False, cols=1, rows=1):
        """Добавляет widget в столбец справа от текущего"""

        widget.props.hexpand = expand
        self.attach_next_to(widget, self.curcol, Gtk.PositionType.RIGHT, cols, rows)
        self.curcol = widget


def __clear_entry_by_icon(entry, iconpos, event):
    if iconpos == Gtk.EntryIconPosition.SECONDARY:
        entry.set_text('')


def entry_setup_clear_icon(entry):
    """Включение правой иконки в Gtk.Entry и назначение обработчика её нажатия."""

    entry.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, 'edit-clear')
    entry.set_icon_activatable(Gtk.EntryIconPosition.SECONDARY, True)
    entry.set_icon_tooltip_text(Gtk.EntryIconPosition.SECONDARY, 'Очистить')
    entry.connect('icon-press', __clear_entry_by_icon)


def get_resource_loader(env):
    """Возвращает экземпляр класса FileResourceLoader
    или ZipFileResourceLoader, в зависимости от значения env.appIsZIP.

    env     - экземпляр класса fbenv.Environment."""

    return ZipFileResourceLoader(env) if env.appIsZIP else FileResourceLoader(env);


class FileResourceLoader():
    """Загрузчик файлов ресурсов.

    Внимание! Методы этого класса в случае ошибок генерируют исключения."""

    def __init__(self, env):
        """Инициализация.

        env     - экземпляр класса fbenv.Environment."""

        self.env = env

    def load(self, filename):
        """Загружает файл filename в память и возвращает в виде
        bytestring.

        filename - относительный путь к файлу."""

        filename = os.path.join(self.env.appDir, filename)

        if not os.path.exists(filename):
            raise ValueError('Файл "%s" не найден' % filename)

        try:
            self.error = None
            with open(filename, 'rb') as f:
                return f.read()
        except Exception as ex:
            # для более внятных сообщений
            self.error = 'Не удалось загрузить файл "%s" - %s' % (filename, str(ex))

    def load_bytes(self, filename):
        """Загружает файл filename в память и возвращает в виде
        экземпляра GLib.Bytes.

        filename - относительный путь к файлу."""

        return GLib.Bytes.new(self.load(filename))

    def load_memory_stream(self, filename):
        """Загружает файл в память и возвращает в виде экземпляра Gio.MemoryInputStream."""

        return Gio.MemoryInputStream.new_from_bytes(self.load_bytes(filename))

    @staticmethod
    def pixbuf_from_bytes(b, width, height):
        """Создаёт и возвращает Gdk.Pixbuf из b - экземпляра GLib.Bytes.

        width, height - размеры создаваемого изображения в пикселах."""

        return Pixbuf.new_from_stream_at_scale(Gio.MemoryInputStream.new_from_bytes(b),
            width, height, True)

    def load_pixbuf(self, filename, width, height, fallback=None):
        """Загружает файл в память и возвращает экземпляр Gdk.Pixbuf.

        filename        - имя файла (см. load_bytes),
        width, height   - размеры создаваемого изображения в пикселах,
        fallback        - имя стандартной иконки, которая будет загружена,
                          если не удалось загрузить файл filename;
                          если fallback=None - генерируется исключение."""

        try:
            return self.pixbuf_from_bytes(self.load_bytes(filename),
                width, height)
        except Exception as ex:
            print('Не удалось загрузить файл изображения "%s" - %s' % (filename, str(ex)), file=stderr)
            if fallback is None:
                raise ex
            else:
                print('Загружаю стандартное изображение "%s"' % fallback, file=stderr)
                return Gtk.IconTheme.get_default().load_icon(fallback, height, Gtk.IconLookupFlags.FORCE_SIZE)



class ZipFileResourceLoader(FileResourceLoader):
    """Загрузчик файлов ресурсов из архива ZIP.
    Архив - сам файл flibrowser2 в случае, когда он
    представляет собой python zip application."""

    def load(self, filename):
        """Аналогично FileResourceLoader.load(), загружает файл
        filename в память и возвращает в виде экземпляра bytestring.

        filename - путь к файлу внутри архива."""

        if not zipfile.is_zipfile(self.env.appFilePath):
            raise TypeError('Файл "%s" не является архивом ZIP' % self.env.appFilePath)

        with zipfile.ZipFile(self.env.appFilePath, allowZip64=True) as zfile:
            try:
                with zfile.open(filename, 'r') as f:
                    return f.read()
            except Exception as ex:
                raise Exception('Не удалось загрузить файл "%s" - %s' % (filename, str(ex)))


if __name__ == '__main__':
    print('[test]')

    import fbenv

    clrs = BookAgeIcons(Gtk.IconSize.MENU)
    #msg_dialog(None, 'Проверка', 'Проверка диалога')
    exit(0)

    env = fbenv.Environment()
    ldr = get_resource_loader(env)
    print('loader type:', type(ldr))

    b = ldr.load_pixbuf('flibrowser-2.svg', 64, 64, 'gtk-find')
    print('loaded:', b)
