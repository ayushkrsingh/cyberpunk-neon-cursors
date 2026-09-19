# Cyberpunk-Neon cursor theme
THEME   := Cyberpunk-Neon
VERSION := 1.0.0
PY      := python3
ARCHIVE := dist/$(THEME)-$(VERSION).tar.gz

.PHONY: all theme preview dist install uninstall clean check

all: theme preview dist

theme:
	$(PY) src/generate.py --out $(THEME)

preview:
	$(PY) src/make_previews.py

dist: theme
	@mkdir -p dist
	tar -czf $(ARCHIVE) --owner=0 --group=0 $(THEME)
	cd dist && sha256sum $(notdir $(ARCHIVE)) > $(notdir $(ARCHIVE)).sha256
	@ls -lh $(ARCHIVE)

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
