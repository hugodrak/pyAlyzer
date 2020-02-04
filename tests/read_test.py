# import py_alyzer
#
# can_reader = py_alyzer.Reader()
# can_reader.attach_log("test.blf")
# can_reader.attach_database("bb1.dbc")
# can_reader.attach_database("debug.dbc")
# can_reader.select_signals()
# can_reader.set_syncspeed(1.0)
#
# can_reader.read()

import py_alyzer

can_reader = py_alyzer.Reader()
can_reader.attach_log("test.blf")
can_reader.attach_database("bb1.dbc")
can_reader.attach_database("debug.dbc")
can_reader.set_syncspeed(1.0)
can_reader.add_signal({'db_id': 1, 'name': 'debug_engTorque', 'msg_id': 486533656})
can_reader.add_signal({'db_id': 0, 'name': 'EngineSpeed', 'msg_id': 217056256})
can_reader.init_plot("time", 'EngineSpeed', "rpm_time")
can_reader.read()
can_reader.plot_show("spline")
