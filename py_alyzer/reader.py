import can  # Only compatible upto python 3.5!
import cantools
import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage.filters import gaussian_filter1d


def is_integer(instring):
    try:
        int(instring)
        return True
    except ValueError:
        return False


def dict_pretty_print(indict):
    print("-----------------------")
    for key, value in indict.items():
        print("%s: %s" % (key, value))
    print("-----------------------")


def log_print(indict):
    outstring = ""
    keys = list(indict.keys())
    keys.remove("time")
    keys.insert(0, "time")
    for key in keys:
        outstring += indict[key]+"\t\t\t"
    print(outstring)


class Reader:
    def __init__(self):
        self.databases = []
        self.signals = []
        self.mode = None
        self.log = None
        self.interface = None
        self.update_speed = 0.2  # seconds
        self.plot_plt = None
        self.plot = None
        self.plot_fig = None
        self.plot_ax = None
        self.plot_xvals = []
        self.plot_yvals = []
        self.plot_config = {}

    def mode(self, mode="log"):
        if mode == "log":
            self.mode = mode
        elif mode == "live":
            self.mode = mode
        else:
            raise ValueError("%s is not a valid mode!" % mode)

    def set_syncspeed(self, speed):
        self.update_speed = speed

    def attach_database(self, path_to_database):
        try:
            self.databases.append(cantools.database.load_file(path_to_database))
        except ValueError:
            raise ValueError("%s is not a valid db!" % path_to_database)

    def attach_log(self, log_path):
        self.mode = "log"
        # TODO: add functionality for all log formats
        try:
            log_ext = log_path.split(".")[-1]
            if log_ext == "blf":
                self.log = can.BLFReader(log_path)
            else:
                self.log = can.CSVReader(log_path)

            return True

        except ValueError:
            raise ValueError("%s is not a valid log!" % log_path)

    def attach_interface(self, interface, channel, bitrate):
        self.mode = "live"
        self.interface = can.Bus(interface=interface, channel=channel, bitrate=bitrate)

    def select_signals(self):
        signal_list = []
        selected_signals = []
        found = False
        for db_idx, db in enumerate(self.databases):
            for msg in db.messages:
                for signal in msg.signals:
                    signal_list.append({"db_id": db_idx, "msg_id": msg.frame_id, "name": signal.name})

        print("Press q to quit.")
        while True:
            search_string = input("Search string: ")
            if search_string == "q":
                print("All selected signals:", selected_signals)
                self.signals = selected_signals
                break
            elif search_string[0]:
                for index, signal_dict in enumerate(signal_list):
                    if search_string.lower() in signal_dict["name"].lower():
                        print(index, signal_dict["name"])
                        found = True
                if not found:
                    print("No signals found based on your search.")
            if found:
                signals_to_select = input("Which signals?: ").replace(" ", "").split(",")
                if signals_to_select == ['']:
                    pass
                else:
                    for index in [int(x) for x in signals_to_select if is_integer(x)]:
                        selected_signals.append(signal_list[index])
                        dict_pretty_print(signal_list[index])

    def add_signal(self, signal):
        if not type(signal["msg_id"]) == int:
            try:
                signal["msg_id"] = int(signal["msg_id"], 16)
            except ValueError:
                raise ValueError("Message id is not correct format")
        self.signals.append(signal)

    def read(self):
        if self.mode == "log":
            raw_log_iterator = self.log.__iter__()
            start_time = None
            sync_time = None

            current_timestamp = 0.0
            stop_timestamp = self.log.stop_timestamp
            msg_out = {}
            signal_names = [x["name"] for x in self.signals]
            signal_names.sort()
            signal_names.insert(0, "time")
            out_names = ""
            for name in signal_names:
                if len(name) < 6:
                    out_names += (name + '\t\t\t')
                elif len(name) < 12:
                    out_names += (name + '\t\t')
                else:
                    out_names += (name + '\t')

            print(out_names)
            while current_timestamp <= stop_timestamp:
                raw_message = next(raw_log_iterator)
                current_timestamp = raw_message.timestamp
                msg = str(raw_message)
                # example message:
                # 'Timestamp: 1576760256.157329    ID: 13ff3f40    X
                # DLC:  8    ff ff 0f f0 fc ff ff ff     Channel: 1'
                msg_id = msg[36:44]
                can_time = round(float(msg[17:26]), 3)

                if start_time is None:
                    start_time = can_time

                if sync_time is None:
                    sync_time = can_time

                if can_time - sync_time < self.update_speed:
                    msg_out.setdefault("time", None)
                    msg_out["time"] = format(can_time, '.1f')
                    for signal in self.signals:
                        if int(msg_id, 16) == signal["msg_id"]:
                            message = self.databases[signal["db_id"]].decode_message(raw_message.arbitration_id,
                                                                                     raw_message.data, False)
                            msg_out.setdefault(signal["name"], None)
                            msg_out[signal["name"]] = format(message[signal["name"]], '.4f')
                else:
                    sync_time = can_time
                    if msg_out != {}:
                        log_print(msg_out)
                        if self.plot is not None:
                            x_val = float(msg_out[self.plot_config["x_signal"]])
                            y_val = float(msg_out[self.plot_config["y_signal"]])

                            self.plot_update(x_val, y_val)

                        msg_out = {}

        elif self.mode == "live":
            for message in self.interface:
                print("{}: {}".format(message.arbitration_id, message.data))

    def init_plot(self, x_signal, y_signal, title):
        self.plot_config["x_signal"] = x_signal
        self.plot_config["y_signal"] = y_signal
        self.plot_plt = plt
        self.plot_plt.xlabel(x_signal)
        self.plot_plt.ylabel(y_signal)
        self.plot_plt.title(title)
        self.plot_plt.ion()
        self.plot = True

    def plot_update(self, x_val, y_val):
        self.plot_xvals.append(x_val)
        self.plot_yvals.append(y_val)

    def plot_show(self, mode):
        if mode == "linear":
            coef = np.polyfit(self.plot_xvals, self.plot_yvals, 1)
            poly1d_fn = np.poly1d(coef)
            # poly1d_fn is now a function which takes in x and returns an estimate for y
            plt.plot(self.plot_xvals, self.plot_yvals, 'yo', self.plot_xvals, poly1d_fn(self.plot_xvals), '--k')
        elif mode == "scatter":
            self.plot_plt.scatter(self.plot_xvals, self.plot_yvals)
        elif mode == "spline":
            ysmoothed = gaussian_filter1d(self.plot_yvals, sigma=2)
            plt.plot(self.plot_xvals, ysmoothed)
        self.plot_plt.show(block=True)
