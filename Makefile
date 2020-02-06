packer = 7z
pack = $(packer) a -mx=9
arcx = .7z
docs = COPYING README.md Changelog
basename = flibrowser2
arcname = $(basename)$(arcx)
srcarcname = $(basename)-src$(arcx)
backupdir = ~/shareddocs/pgm/python/
zipname = $(basename).zip
pysrcs = __main__.py $(basename).py fb*.py
srcs = $(pysrcs) *.svg *.ui COPYING
version = $(shell python3 -c 'from fbcommon import VERSION; print(VERSION)')
branch = $(shell git symbolic-ref --short HEAD)

app:
	zip -9 $(zipname) $(srcs)
	@echo '#!/usr/bin/env python3' >$(basename)
	@cat $(zipname) >> $(basename)
	chmod 755 $(basename)
	rm $(zipname)
archive:
	$(pack) $(srcarcname) *.py *.svg Makefile *.sh *.ui *.geany $(docs)
distrib:
	make app
	make icon
	$(pack) $(basename)-$(version)$(arcx) $(basename) $(docs) $(basename).ico
icon:
	convert -background transparent -density 256x256 $(basename).svg $(basename).ico
backup:
	make archive
	mv $(srcarcname) $(backupdir)
update:
	$(packer) x -y $(backupdir)$(srcarcname)
commit:
	git commit -a -uno -m "$(version)"
	# не, push вручную, ибо ваистену
	#git push
docview:
	$(eval docname = README.htm)
	@echo "<html><head><meta charset="utf-8"><title>Flibrowser 2 README</title></head><body>" >$(docname)
	markdown_py README.md >>$(docname)
	@echo "</body></html>" >>$(docname)
	exo-open $(docname)
	#rm $(docname)
todo:
	pytodo.py $(pysrcs) >TODO
show-branch:
	@echo "$(version)-$(branch)"
