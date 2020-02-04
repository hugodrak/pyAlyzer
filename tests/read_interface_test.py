import py_alyzer

can_reader = py_alyzer.Reader()
can_reader.attach_interface("vector", 0, 500000)
# can_reader.attach_database("bb1.dbc")
can_reader.attach_database("debug.dbc")
can_reader.add_signal({'db_id': 1, 'name': 'debug_massCalc', 'msg_id': 486534680})

can_reader.read()
