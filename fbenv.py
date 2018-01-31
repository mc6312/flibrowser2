#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" fbenv.py

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


"""Определение расположения файлов настроек и данных Flibrowser2.
Загрузка и сохранение настроек."""


import os, os.path
import sys
from platform import system as system_name
from zipfile import is_zipfile

from fbdb import *


class Environment():
    """Класс, определяющий и хранящий пути к файлам данных и настроек."""

    CONFIG_FILE_NAME = 'settings.sqlite3'
    LIBRARY_FILE_NAME = 'library.sqlite3'
    SUBDIR_NAME = 'flibrowser2'

    def __init__(self, useappdir=False):
        """Определение путей.

        Если useappdir==True, то каталог приложения будет принудительно
        использован в качестве каталога для всех файлов приложения."""

        # путь к самому приложению (flibrowser2[.py|.pyz])
        self.appFilePath = os.path.abspath(sys.argv[0])

        # мы в жо... в зипе?
        self.appIsZIP = is_zipfile(self.appFilePath)

        # каталог самого поделия
        self.appDir = os.path.split(self.appFilePath)[0]

        # пытаемся определить, из откудова работать

        # сначала ищем рядом с самой софтиной
        self.configFilePath = os.path.join(self.appDir, self.CONFIG_FILE_NAME)
        if useappdir or os.path.exists(self.configFilePath):
            # нашелся или указан принидительно - считаем, что там и есть
            # рабочий каталог, и библиотека должна лежать там же

            self.dataDir = self.appDir
            self.configDir = self.appDir

        else:
            # иначе ищем (или создаём) каталоги в недрах $HOME

            sysname = system_name()
            if sysname == 'Windows':
                self.configDir = os.path.join(os.environ['APPDATA'], self.SUBDIR_NAME)
                self.dataDir = self.configDir
                # валим конфиг и библиотеку в один каталог
                # вообще _как бы_ полагается не совсем так, но у M$ линия партии очень уж извилиста,
                # и работа flibrowser2 под виндой у меня далеко не на первом месте
            else:
                if sysname != 'Linux':
                    print('Warning! Unsupported platform!', file=sys.stderr)

                # как это будет (если будет) работать под MacOS или *BSD - меня не колышет
                # теоретически, под Linux надо бы каталоги узнавать через
                # функции поддержки XDG, но это лишняя зависимость
                # и один фиг в массовых дистрибутивах это ~/.config/ и ~/.local/share/
                self.configDir = os.path.expanduser('~/.config/%s' % self.SUBDIR_NAME)
                self.dataDir = os.path.expanduser('~/.local/share/%s' % self.SUBDIR_NAME)

            # теперь создаём каталоги, если их нет
            if not os.path.exists(self.configDir):
                os.makedirs(self.configDir)

            if not os.path.exists(self.dataDir):
                os.makedirs(self.dataDir)

            self.configFilePath = os.path.join(self.configDir, self.CONFIG_FILE_NAME)

        # определяем пути к файлам
        # (точнее, self.configFilePath уже известен)
        self.libraryFilePath = os.path.join(self.dataDir, self.LIBRARY_FILE_NAME)

    def __str__(self):
        """Отображение для отладки"""

        return '''%s:
  appIsZIP=%s,
  appFilePath="%s",
  appDir="%s"
  dataDir="%s"
  configDir="%s"
  configFilePath="%s"
  libraryFilePath="%s"''' % (self.__class__.__name__,
    self.appIsZIP, self.appFilePath,
    self.appDir, self.dataDir, self.configDir,
    self.configFilePath, self.libraryFilePath)


class Settings(Database):
    """Работа с БД настроек"""

    def __init__(self, env):
        """Инициализация.

        env - экземпляр Environment."""

        super().__init__(env.configFilePath)

    LIBRARY_DIRECTORY = 'inpx_directory'
    INPX_INDEX = 'inpx_index'
    GENRE_NAMES_PATH = 'genre_names_path'
    EXTRACT_TO_DIRECTORY = 'extract_to_directory'
    EXTRACT_FILE_NAMING_SCHEME = 'extract_file_naming_scheme'
    EXTRACT_PACK_ZIP = 'extract_pack_zip'

    def init_tables(self):
        """Создание таблицы для хранения настроек"""

        self.cursor.execute('create table if not exists settings(name text primary key, value text);')

    def reset_tables(self):
        """Полная очистка настроек"""

        self.cursor.execute('drop table if exists settings;')
        self.init_tables()

    def load(self):
        self.connect()
        self.init_tables()

    def unload(self):
        self.disconnect()

    def get_param(self, vname, defvalue=''):
        """Получение параметра из БД настроек.

        vname       - имя параметра,
        defvalue    - None или значение по умолчанию, которое ф-я вернет,
                      если параметра нет в БД, или у него пустое значение;
                      defvalue = None - функция генерирует исключение."""

        self.cursor.execute('select value from settings where name=? limit 1;',
            (vname,))

        r = self.cursor.fetchone()
        if r is None:
            if defvalue is None:
                raise KeyError('Отсутствует значение параметра "%s" в таблице "settings" файла "%s"' % (vname, self.dbfilename))
            else:
                return defvalue
        else:
            return r[0]

    def get_param_int(self, vname, defvalue=None):
        """Получение цельночисленного параметра из БД настроек.
        В случае ошибки генерирует исключение."""

        return int(self.get_param(vname, defvalue))

    def get_param_bool(self, vname, defvalue=None):
        """Получение булевского параметра из БД настроек.
        В случае ошибки генерирует исключение."""

        return self.get_param_int(vname, defvalue) != 0

    def set_param(self, vname, vvalue):
        """Установка параметра в БД настроек.

        vname   - имя параметра,
        vvalue  - значение параметра."""

        self.cursor.execute('insert or replace into settings (name, value) values(?,?);',
            (vname, vvalue))

    def set_param_int(self, vname, vvalue):
        """Установка цельночисленного параметра в БД настроек."""

        self.set_param(vname, str(vvalue))

    def set_param_bool(self, vname, vvalue):
        """Установка булевского параметра в БД настроек."""

        self.set_param(vname, str(int(vvalue))) # булевские хранятся как целые числа!

    def __str__(self):
        """Для отладки"""

        ret = ['%s:' % self.__class__.__name__]

        if not self.cursor:
            ret.append('  <database is not connected>')
        else:
            self.cursor.execute('select name,value from settings;')

            while True:
                r = self.cursor.fetchone()
                if r is None:
                    break

                ret.append('  %s = "%s"' % r)

            return '\n'.join(ret)


if __name__ == '__main__':
    print('[test]')

    env = Environment()
    print(env)

    cfg = Settings(env)

    cfg.load()
    try:
        #cfg.set_param('test', 'somevalue')
        #print(cfg.get_param('test', None))

        #cfg.set_param(cfg.LIBRARY_DIRECTORY, './')
        #cfg.set_param(cfg.INPX_INDEX, './flibusta_fb2_local.inpx')
        #cfg.set_param(cfg.GENRE_NAMES_PATH, './lib.libgenrelist.sql')
        cfg.set_param_bool(cfg.EXTRACT_PACK_ZIP, False)

        print(cfg)
        #print(cfg.get_param(cfg.LIBRARY_DIRECTORY, '?'))
        print(type(cfg.get_param_bool(cfg.EXTRACT_PACK_ZIP)))
    finally:
        cfg.unload()
