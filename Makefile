# Cyberpunk-Neon cursor theme
THEME   := Cyberpunk-Neon
VERSION := 1.0.0
PY      := python3
TGZ     := dist/$(THEME)-$(VERSION).tar.gz
ZIP     := dist/$(THEME)-$(VERSION).zip

.PHONY: all theme preview dist install uninstall clean check

all: theme preview dist

theme:
	$(PY) src/generate.py --out $(THEME)

preview:
	$(PY) src/make_previews.py

dist: theme
	@mkdir -p dist
	rm -f $(TGZ) $(ZIP)
	tar -czf $(TGZ) --owner=0 --group=0 $(THEME)
	zip -qry $(ZIP) $(THEME)          # -y keeps the 119 symlinks as symlinks
	cd dist && sha256sum $(notdir $(TGZ)) > $(notdir $(TGZ)).sha256 \
	        && sha256sum $(notdir $(ZIP)) > $(notdir $(ZIP)).sha256
	@ls -lh $(TGZ) $(ZIP)

install:
	./install.sh

uninstall:
	./uninstall.sh

# rebuild and confirm no glyph is clipped
check:
	@$(PY) src/generate.py --out /tmp/$(THEME)-check 2>&1 \
	  | grep -E "edge check|CLIPPED|at \[" || (echo "build failed" && exit 1)
	@rm -rf /tmp/$(THEME)-check

clean:
	rm -rf $(THEME) dist build __pycache__ src/__pycache__
