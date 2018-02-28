# Flibrowser 2

Ржавый крюк для вытаскивания книг из в оффлайновых библиотек.

## ЧТО УМЕЕТ

Искать книги в своей БД (содержимое БД импортируется из MyHomeLib-совместимого
индексного файла в формате INPX), вытаскивать выбранные книги из архивов
библиотеки и, при необходимости, паковать в отдельные зиповские архивы
(одна книга - один архив) для читалок, умеющих жрать упакованные книги.

В данной версии (и, вероятно, навсегда) умеет импортировать только
библиотеки вида "куча зиповских архивов с книгами и индексный файл
в формате INPX".

В первую очередь предназначено для работы под Linux.

Работа под Windows обеспечивается только в виде "хоть как-то",
инсталлятора "поставить всё кучей" нет и не будет.

Работа под чем-то еще (MacOS X, *BSD, экзотические *nix'ы и т.п.)
теоретически возможна (при наличии в целевой ОС всего, перечисленного
в разделе "Что хочет"), но не проверялась, и в обозримом будущем автор
не намерен напрягаться ради этого.


## ЧТО ХОЧЕТ

1. Любой дистрибутив Linux с любым графическим окружением рабочего стола
   (лишь бы там имелось нижеперечисленное)
   или MS Windows XP/Vista/...
2. Python 3.3 или новее.
3. GTK+ 3.18 или новее.
4. PythonGObject/PyGI


## КАК УСТАНАВЛИВАТЬ

Сама программа установки не требует. Достаточно положить в отдельный каталог.

Установки хотят компоненты из п.п.2-4 раздела "Что хочет":

#### Под Linux

Всё указанное устанавливается из репозиториев штатными средствами ОС.

Имена необходимых пакетов (номера версий актуальны на февраль 2018 г.):

- Debian/Ubuntu и производные от них дистрибутивы:
  - python3
  - python3-gi
  - python3-gi-cairo
  - gir1.2-gdkpixbuf-2.0
  - gir1.2-gtk-3.0
  - gir1.2-pango-1.0

  Остальное притащится само за счет зависимостей указанных пакетов.

  Если в качестве DE установлен GNOME 3 или его производные, всё перечисленное,
  скорее всего, уже установлено.

- Fedora: см. выше про GNOME.
- прочие дистрибутивы: см. документацию по конкретному дистрибутиву.

#### Под Windows

Всё сложнее:

1. С <http://python.org> берется установщик Python 3.4.x (т.к. на момент написания
   этого документа Python версии 3.5 и новее не поддерживаются виндовым
   портом PyGObject)
2. PyGObject (с GTK 3.x в комплекте) ищется по ссылкам здесь:
   <http://pygobject.readthedocs.io/en/latest/guide/faq.html>
   где должен найтись установщик pygi-aio-3.*.exe версии 3.18 или новее.
   В нем при установке нужно указать установленную версию питона,
   выбрать в списках пакетов GDK-Pixbuf, GTK 3.x и Pango.
   Остальное (вроде бы) не требуется.
3. И, напоминаю, инсталлятора, который будет сам выполнять п.п.1..3 - нет и НЕ БУДЕТ.

#### Первый запуск после установки

При первом запуске (или после удаления БД настроек) программа вываливает окно
первоначальной настройки, и, в случае успешной настройки, пытается
импортировать индексный файл библиотеки.

## КАК ЗАПУСКАТЬ

### Под Linux

- просто запустить команду "python3 [каталог-куда-положено/]flibrowser2", или
- средствами DE создать ярлык или кнопку запуска с указанной выше командой

### Под Windows

- Win+R, оттуда запустить команду "[каталог-куда-положено\]pythonw flibrowser2", или
- создать ярлык с соотв. командой

## КАК ИСПОЛЬЗОВАТЬ
### ПОИСК/ВЫБОР КНИГ

1. Выбор по авторам или названиям циклов (сериалов):
   1. Выбрать режим "Авторы" или "Циклы/сериалы" в левой панели
      основного окна.
   2. Выбрать первую букву имени автора или названия цикла в алфавитном
      списке.
   3. Выбрать автора или название цикла в следующем списке.
      Можно сократить список, введя несколько начальных букв имени или
      названия в поле ввода под списком.
      Дополнительно можно двойным кликом мыши или нажатием кнопки "Enter"
      на элементе списка пометить выбранный элемент списка как избранный
      (и далее выбирать соответствующие ему книги, нажимая пункт меню
      "Книги/Избранные авторы" или "Книги/Избранные циклы").
   4. В списке книг выбрать нужные книги. Список можно сократить, введя
      строку для поиска в поле ввода под списком.
      В отличие от списка авторов, строка ищется в полях "название книги"
      и "название серии/цикла" в любой позиции поля (не только в начале).

2. Поиск по нескольким параметрам:
   1. Выбрать режим "Поиск" в левой панели основного окна.
   2. Заполнить нужные поля.
   3. Нажать кнопку "Искать".

   **Внимание!**
   1. При поиске книги попадают в список только при совпадении
      всех введённых (не пустых) полей.
   2. Если в текстовых полях слишком короткие значения, или в полях
      с датами указан слишком большой интервал, в список попадёт
      очень много книг и он может заполняться медленно.

### ИЗВЛЕЧЕНИЕ КНИГ ИЗ АРХИВОВ БИБЛИОТЕКИ

В нижней панели выбирается (при необходимости) нужный каталог, после чего
следует нажать кнопку "Извлечь".

Также можно выбрать режим именования файлов и указать, сжимать ли файлы.

При нажатии кнопки "Извлечь" файлы извлекаются из библиотеки в указанный
каталог, и, если это указано, пакуются в отдельные архивы ZIP
(один архив на одну книгу).

Внимание! Если выбран режим именования файлов "Имя автора/...", программа
создаст подкаталоги с именами авторов.

### ОБНОВЛЕНИЕ БИБЛИОТЕКИ

Если архивы с книгами и индексный файл .inpx были обновлены, следует
обновить БД, выбрав пункт меню "Файл/Импорт библиотеки".

### КЛАВИАТУРНЫЕ СОКРАЩЕНИЯ

- **F10** - меню программы
- **Alt+F1** - просмотреть информацию о программе
- **Ctrl+R** - выбрать случайную книгу
- **Ctrl+E** - извлечь из библиотеки выбранные книги
- **Ctrl+Q** - завершить программу
- **Alt+1** - перейти к панели выбора по авторам
- **Alt+2** - перейти к панели выбора по циклам
- **Ctrl+F** или **Alt+3** - перейти к панели поиска
- **Alt+4** - перейти к списку книг
- **Alt+5** - перейти к полю параметров извлечения книг

## ПАРАМЕТРЫ КОМАНДНОЙ СТРОКИ
- **--app-dir**/**-A** - искать файлы настроек и БД в каталоге, в котором
  расположен Flibrowser
- **--home-dir**/**-H** - искать файлы в домашнем каталоге текущего пользователя

## ФАЙЛЫ НАСТРОЕК И БД:

Если расположение файлов не указано явно параметрами командной строки
(см. раздел "Параметры командной строки"), то очерёдность поиска файлов
такая:

1. Каталог, где расположен сам flibrowser2[.py]
2. Подкаталоги домашнего каталога пользователя:

   - файл настроек:
     - под Linux: ~/.config/flibrowser2/
     - под Windows: %APPDATA%\flibrowser2\
   - файл БД:
     - под Linux: ~/.local/share/flibrowser2/
     - под Windows: %APPDATA%\flibrowser2\

При необходимости отсутствующие каталоги и файл настроек (settings.sqlite3)
программа создаёт автоматически.

БД библиотеки (library.sqlite3) создаётся автоматически при первом импорте
библиотеки.

Расположение индексного файла INPX и каталога архивов с книгами указывается
в окне настроек при первом запуске или повторной настройке программы.
