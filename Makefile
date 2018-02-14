packer = 7z
pack = $(packer) a -mx=9
arcx = .7z
docs = COPYING README.md Changelog
basename = flibrowser2
arcname = $(basename)$(arcx)
srcarcname = $(basename)-src$(arcx)
backupdir = ~/shareddocs/pgm/python/
zipname = $(basename).zip
srcs = __main__.py $(basename).py fb*.py *.svg COPYING

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
	make icon
	$(pack) $(basename)-$(shell python3 -c 'from fbcommon import VERSION; print(VERSION)')$(arcx) $(basename) $(docs) $(basename).ico
icon:
	convert $(basename).svg $(basename).ico
backup:
	make archive
	mv $(srcarcname) $(backupdir)
update:
	$(packer) x -y $(backupdir)$(srcarcname)
commit:
	git commit -a -m "$(shell python3 -c 'from fbcommon import VERSION; print(VERSION)')"
	# не, push вручную, ибо ваистену
	#git push
docview:
	$(eval docname = README.htm)
	@echo "<html><head><meta charset="utf-8"><title>Flibrowser 2 README</title></head><body>" >$(docname)
	markdown README.md >>$(docname)
	@echo "</body></html>" >>$(docname)
	exo-open $(docname)
	#rm $(docname)
