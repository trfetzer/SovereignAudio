
.PHONY: setup run gui clean

setup:
	python3 -m venv venv
	source venv/bin/activate && pip install -r requirements.txt

run:
	source venv/bin/activate && python main.py

gui:
	source venv/bin/activate && python gui_debug.py

clean:
	rm -rf venv __pycache__ */__pycache__ recordings/imported/* transcriptions/* embeddings/*
