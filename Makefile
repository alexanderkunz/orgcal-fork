main: main.py
	./venv/bin/pyinstaller ./main.py -F

install:
	cp ./dist/main $(ORGCAL_INSTALL_PATH)
