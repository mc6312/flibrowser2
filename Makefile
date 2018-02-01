packer = 7z
pack = $(packer) a -mx=9
arcx = .7z
docs = COPYING README.md Changelog
basename = flibrowser2
arcname = $(basename)$(arcx)
srcarcname = $(basename)-src$(arcx)
backupdir = ~/shareddocs/pgm/python/
zipname = $(basename).zip
srcs = __main__.py flibrowser2.py fb*.py flibrowser.svg

app:
	zip -9 $(zipname) $(srcs)
	@echo '#!/usr/bin/env python3' >$(basename)
	@cat $(zipname) >> $(basename)
	chmod 755 $(basename)
	rm $(zipname)
archive:
	$(pack) $(srcarcname) *.py *.svg Makefile *.sh *.geany $(docs)
distrib:
	make app
	$(pack) $(arcname) $(basename) $(docs)
backup:
	make archive
	mv $(srcarcname) $(backupdir)
update:
	$(packer) x -y $(backupdir)$(srcarcname)
commit:
	git commit -a -m "$(shell python3 -c 'from fbcommon import VERSION; print(VERSION)')"
	git push
