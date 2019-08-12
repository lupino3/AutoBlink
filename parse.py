from collections import defaultdict

DEBUG = 0

def debug(s):
    if DEBUG != 0:
        print(s)

def get_stations(filename):
    f = open(filename, 'rb')
    # map DHCP hostname to list of station_info
    stations = defaultdict(list)
    capturing = False
    parens_count = 0
    tmp = {}
    for i, raw_line in enumerate(f.readlines()):
        # We are opening a binary file, some lines won't be text and
        # it's ok to ignore them, as the data we care about is in the
        # text portion of the file.
        try:
            line = raw_line.decode("utf-8")
        except:
            continue

        if capturing:
            data = line.strip()
            debug(data)
            if data.endswith("{"):
                parens_count += 1
                debug("incremented parens_count to %d" % parens_count)
                continue
            if data.endswith("}"):
                parens_count = max(parens_count - 1, 0) # ignore closing station_state_update
                debug("decremented parens_count to %d" % parens_count)

            if parens_count == 0:
                host = tmp["dhcp_hostname"]
                debug("saving data for %s" % host)
                debug(tmp)
                capturing = False
                stations[host].append(tmp)
            elif parens_count == 1 and ":" in data:
                key, value = data.split(":")
                value = value.strip().strip('"')
                if value:
                    debug("Adding %s, %s" % (key, value))
                    tmp[key] = value
                continue

        if "station_info" in line:
            debug("Started capturing at line %d" % (i+1))
            capturing = True
            parens_count = 1
            tmp = {}
            tmp["dhcp_hostname"] = ""

    return stations


stations = get_stations("diag")

connected_stations = [name for name, data in stations.items()
        if all(d["connected"] == "true" for d in data)]

print(connected_stations)
