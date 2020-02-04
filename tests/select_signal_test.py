import py_alyzer

can_reader = py_alyzer.Reader()
can_reader.attach_database("bb1.dbc")
can_reader.attach_database("debug.dbc")
can_reader.select_signals()