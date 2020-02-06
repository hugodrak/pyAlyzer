import can
import cantools
import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage.filters import gaussian_filter1d
import os
import json
from win32com.client import Dispatch
import time
from collections import OrderedDict


# Input: vision rec file path
# Takes a rec file and dispatches it to vision.recorderfile for conversion
# Currently only outputs the txt file with same name as rec in the same dir
def convert_vision(rec_path):
    try:
        vision_rec_export_ascii = 0
        rec = Dispatch("vision.RecorderFile")
        print("Exporting rec to txt")
        start_time = time.time()
        rec.Export(rec_path, vision_rec_export_ascii)
        print("Conversion took %s s" % round(time.time() - start_time, 2))
    except ConnectionError:
        raise ConnectionError("Could not connect to Vision.")


# Input: string
# Output: bool that states if it is an integer or not
def is_integer(in_string):
    try:
        int(in_string)
        return True
    except ValueError:
        return False


# Input: a path ex. ./test/mine/firstlog.blf
# Output: the file extension blf
def get_extension(path):
    return path.split(".")[-1].lower()


# Input: dict
# Prints out a more human readable dict structure
def dict_pretty_print(indict):
    print("-----------------------")
    for key, value in indict.items():
        print("%s: %s" % (key, value))
    print("-----------------------")


def log_print(indict):
    out_string = ""
    keys = list(indict.keys())
    keys.remove("time")
    keys.insert(0, "time")
    for key in keys:
        out_string += indict[key] + "\t\t\t"
    return out_string


def csv_print(indict):
    out_string = ""
    keys = list(indict.keys())
    for i, key in enumerate(keys):
        if i+1 < len(keys):
            out_string += indict[key] + ","
        else:
            out_string += indict[key]
    out_string += "\n"
    return out_string


def vision_format(line, keys):
    line_dict = OrderedDict()
    line_list = line.split("\t")
    for i, key in enumerate(keys):
        value = line_list[i]
        if "." in value:
            try:
                value = float(value)
            except ValueError:
                pass
        elif value == "false":
            value = False
        elif value == "true":
            value = True
        else:
            try:
                value = int(value)
            except ValueError:
                pass

        line_dict.update({key: value})
    return line_dict


def change_extension(path, new_ext):
    path_list = path.split(".")
    path_list[-1] = new_ext
    return ".".join(path_list)


class Reader:
    def __init__(self):
        self.databases = []
        self.db_names = []
        self.signals = []
        self.available_signals = []
        self.mode = None
        self.logs = []
        self.log_paths = []
        self.log_formats = []
        self.log_infos = []
        self.interface = None
        self.update_speed = 0.2  # seconds
        self.printout_state = False
        self.output_state = False
        self.output_file = None
        self.plot = False
        self.plot_plt = None
        self.plot_fig = None
        self.plot_ax = None
        self.plot_x_values = []
        self.plot_y_values = []
        self.plot_config = {}

    def mode(self, mode="log"):
        if mode == "log":
            self.mode = mode
        elif mode == "live":
            self.mode = mode
        else:
            raise ValueError("%s is not a valid mode!" % mode)

    def set_sync_speed(self, speed):
        self.update_speed = speed

    def attach_database(self, path_to_database):
        try:
            self.db_names.append(path_to_database.split("/")[-1])
            self.databases.append(cantools.db.load_file(path_to_database))
        except ValueError:
            raise ValueError("%s is not a valid db!" % path_to_database)

    def attach_logs(self, *args):
        self.mode = "log"
        # TODO: add functionality for all log formats
        files = []
        for in_path in args:
            if os.path.isdir(in_path):
                files.extend([in_path + "/" + x for x in os.listdir(in_path)])
            else:
                files.append(in_path)

        for log_path in files:
            if os.path.exists(log_path):
                try:
                    log_ext = get_extension(log_path)
                    if log_ext == "rec" and not os.path.exists(change_extension(log_path, "txt")):
                        print("Converting %s from rec to txt" % log_path)
                        convert_vision(os.path.abspath(log_path))
                        log_path = change_extension(log_path, "txt")
                        log_ext = "txt"
                        while True:
                            if os.path.exists(log_path):
                                break
                            else:
                                time.sleep(1)
                                print("Searching")
                    elif os.path.exists(change_extension(log_path, "txt")):
                        log_path = change_extension(log_path, "txt")
                        log_ext = "txt"

                    if log_ext == "blf":
                        print("Adding log %s" % log_path)
                        self.log_formats.append("unparsed")
                        reader = can.BLFReader(log_path)
                        self.add_log_info(reader)
                        self.logs.append(reader.__iter__())
                        self.log_paths.append(log_path)
                    elif log_ext == "csv":
                        print("Adding log %s" % log_path)
                        self.log_formats.append("unparsed")
                        self.logs.append(can.CSVReader(log_path).__iter__())
                        self.log_paths.append(log_path)
                    elif log_ext == "txt":
                        print("Adding log %s" % log_path)
                        raw_file = open(log_path, "r").readlines()
                        if raw_file[0].split("\t")[0] == '"ATI VISION Recorder Output File"':
                            self.log_formats.append("parsed")
                            self.add_log_info(raw_file)
                            self.logs.append(raw_file[37:].__iter__())
                            self.log_paths.append(log_path)
                            self.available_signals.extend(raw_file[35].replace('"', "").replace("\n", "").split("\t"))
                            self.available_signals.remove("TimeStamp")

                except ValueError:
                    raise ValueError("%s is not a valid log!" % log_path)
            else:
                raise FileExistsError("File does not exist")

    def add_log_info(self, raw_log):
        info_dict = {}
        if type(raw_log) == list:
            info_dict = {"keys": raw_log[35].replace('"', "").split("\t"), "length": len(raw_log),
                         "duration": round(len(raw_log) / 50, 1), "stop_timestamp": float(raw_log[-2].split("\t")[0])}
            print("log contains %s rows and duration is %s min" % (len(raw_log), round(len(raw_log)/3000, 1)))
        else:
            info_dict["stop_timestamp"] = raw_log.stop_timestamp
            print("log contains %s rows and duration is %s min" % (raw_log.object_count, round((raw_log.stop_timestamp-raw_log.start_timestamp)/60, 1)))

        self.log_infos.append(info_dict)

    def attach_interface(self, interface, channel, bitrate):
        self.mode = "live"
        self.interface = can.Bus(interface=interface, channel=channel, bitrate=bitrate)

    def printout(self):
        self.printout_state = True

    def output(self):
        self.output_state = True

    def output_setup(self, filename):
        self.output_file = open(filename, "w+")
        return True

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
        if len(signal.keys()) == 1 and type(signal["name"]) == str:
            self.signals.append(signal)
        else:
            if not type(signal["msg_id"]) == int:
                try:
                    signal["msg_id"] = int(signal["msg_id"], 16)
                except ValueError:
                    raise ValueError("Message id is not correct format")
            if type(signal["db_id"]) == str:
                signal["db_id"] = self.db_names.index(signal["db_id"])
            self.signals.append(signal)

    def add_signals(self, signals):
        if type(signals) == str:
            if os.path.isfile(signals):
                if get_extension(signals) == "json":
                    json_raw = json.load(open(signals))
                    for signal in json_raw["signals"]:
                        if len(signal.keys()) == 1 and signal["name"] == str:
                            self.signals.append(signal)
                        else:
                            if not type(signal["msg_id"]) == int:
                                try:
                                    signal["msg_id"] = int(signal["msg_id"], 16)
                                except ValueError:
                                    raise ValueError("Message id is not correct format")
                            if type(signal["db_id"]) == str:
                                signal["db_id"] = self.db_names.index(signal["db_id"])
                        self.signals.append(signal)

    def all_signals(self, log_id):
        if type(log_id) == str:
            if log_id == "rec" or log_id == "txt":
                for i, log_path in enumerate(self.log_paths):
                    if get_extension(log_path) == "txt":
                        self.signals.extend([{"name": x} for x in self.available_signals])
                        break

        elif type(log_id) == int:
            log_ext = get_extension(self.log_paths[log_id])
            if log_ext == "rec" or log_ext == "txt":
                self.signals.extend([{"name": x} for x in self.available_signals])

    def export_signals(self, filename):
        if get_extension(filename) == "json":
            file = open(filename, "w+")
            out = {"signals": self.signals}
            file.write(json.dumps(out))

    def create_output(self, log_nr):
        output_path = self.log_paths[log_nr].split("/")
        if len(output_path) > 1:
            output_path[-2] = "output"
        else:
            output_path.insert(0, "output")
        if not os.path.isdir("./" + "/".join(output_path[:-1])):
            os.mkdir("./" + "/".join(output_path[:-1]))

        ext = output_path[-1].split(".")
        ext[-1] = "csv"

        output_path[-1] = ".".join(ext)
        self.output_setup("/".join(output_path))
        ###
        out_names = ""
        signals = None
        if self.log_formats[log_nr] == "parsed":
            signals = [x for x in self.signals if len(x.keys()) == 1]
        elif self.log_formats[log_nr] == "unparsed":
            signals = [x for x in self.signals if len(x.keys()) > 1]

        signal_names = [x["name"] for x in signals]
        signal_names.insert(0, "time")
        for i, name in enumerate(signal_names):
            if i + 1 < len(signal_names):
                out_names += name + ","
            else:
                out_names += name
        out_names += "\n"

        self.output_file.write(out_names)

    def create_printout(self, log_nr):
        signals = None
        if self.log_formats[log_nr] == "parsed":
            signals = [x for x in self.signals if len(x.keys()) == 1]
        elif self.log_formats[log_nr] == "unparsed":
            signals = [x for x in self.signals if len(x.keys()) > 1]
        signal_names = [x["name"] for x in signals]
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

    def read(self):
        if self.mode == "log":
            for log_nr, log in enumerate(self.logs):
                print("Start of reading log %s" % self.log_paths[log_nr])
                if self.output_state:
                    print("Outputting log %s" % change_extension(self.log_paths[log_nr], "csv"))
                    self.create_output(log_nr)

                if self.printout_state:
                    self.create_printout(log_nr)

                raw_log_iterator = log
                start_time = None
                sync_time = None

                current_timestamp = 0.0
                if self.log_formats[log_nr] == "parsed":
                    stop_timestamp = self.log_infos[log_nr]["stop_timestamp"]
                    msg_complete = False
                    msg_out = OrderedDict()

                    while current_timestamp <= stop_timestamp:
                        raw_message = vision_format(next(raw_log_iterator), self.log_infos[log_nr]["keys"])

                        current_timestamp = raw_message["TimeStamp"]
                        can_time = round(current_timestamp, 1)

                        if start_time is None:
                            start_time = can_time

                        if sync_time is None:
                            sync_time = can_time

                        if can_time - sync_time < self.update_speed and not msg_complete:
                            time_decimals = len(str(self.update_speed).split('.')[1])
                            msg_out.update({"time": format(can_time, ('.%if' % time_decimals))})
                            for signal in self.signals:
                                if len(signal.keys()) == 1 and type(signal["name"]) == str:
                                    if type(raw_message[signal["name"]]) == float:
                                        msg_out.update({signal["name"]: format(raw_message[signal["name"]], '.4f')})
                                    else:
                                        msg_out.update({signal["name"]: str(raw_message[signal["name"]])})
                            msg_complete = True
                        else:
                            msg_complete = False
                            sync_time = can_time
                            if len(msg_out.keys()) > 0:
                                if self.printout_state:
                                    print(log_print(msg_out))
                                if self.plot:
                                    x_val = float(msg_out[self.plot_config["x_signal"]])
                                    y_val = float(msg_out[self.plot_config["y_signal"]])
                                    self.plot_update(x_val, y_val)
                                if self.output_state:
                                    self.output_file.write(csv_print(msg_out))

                                msg_out = OrderedDict()

                elif self.log_formats[log_nr] == "unparsed":
                    stop_timestamp = self.log_infos[log_nr]["stop_timestamp"]

                    msg_out = OrderedDict()

                    while current_timestamp <= stop_timestamp:
                        raw_message = next(raw_log_iterator)

                        current_timestamp = raw_message.timestamp
                        msg = str(raw_message)
                        msg_id = msg[36:44]
                        can_time = round(float(msg[17:26]), 1)

                        if start_time is None:
                            start_time = can_time

                        if sync_time is None:
                            sync_time = can_time

                        if can_time - sync_time < self.update_speed:
                            msg_out.setdefault("time")
                            time_decimals = len(str(self.update_speed).split('.')[1])
                            msg_out["time"] = format(can_time, ('.%if' % time_decimals))
                            for signal in self.signals:
                                if len(signal.keys()) > 1:
                                    if int(msg_id, 16) == signal["msg_id"]:
                                        message = self.databases[signal["db_id"]].decode_message(
                                            raw_message.arbitration_id, raw_message.data, False)
                                        msg_out.setdefault(signal["name"])
                                        if type(message[signal["name"]]) == float:
                                            msg_out[signal["name"]] = format(message[signal["name"]], '.4f')
                                        else:
                                            msg_out[signal["name"]] = str(message[signal["name"]])
                        else:
                            sync_time = can_time
                            if msg_out != {}:
                                if self.printout_state:
                                    print(log_print(msg_out))
                                if self.plot:
                                    x_val = float(msg_out[self.plot_config["x_signal"]])
                                    y_val = float(msg_out[self.plot_config["y_signal"]])
                                    self.plot_update(x_val, y_val)
                                if self.output_state:
                                    self.output_file.write(csv_print(msg_out))

                                msg_out = OrderedDict()

        elif self.mode == "live":
            for message in self.interface:
                print("{}: {}".format(message.arbitration_id, message.data))
        print("Done! :P")

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
        self.plot_x_values.append(x_val)
        self.plot_y_values.append(y_val)

    def plot_show(self, mode):
        if mode == "linear":
            coefficient = np.polyfit(self.plot_x_values, self.plot_y_values, 1)
            poly1d_fn = np.poly1d(coefficient)
            # poly1d_fn is now a function which takes in x and returns an estimate for y
            plt.plot(self.plot_x_values, self.plot_y_values, 'yo', self.plot_x_values,
                     poly1d_fn(self.plot_x_values), '--k')
        elif mode == "scatter":
            self.plot_plt.scatter(self.plot_x_values, self.plot_y_values, s=5)
        elif mode == "smoothed":
            y_smoothed = gaussian_filter1d(self.plot_y_values, sigma=2)
            plt.plot(self.plot_x_values, y_smoothed)
        self.plot_plt.show(block=True)
