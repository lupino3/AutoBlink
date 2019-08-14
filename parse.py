from collections import defaultdict
import os
import requests

DEBUG = os.getenv("DEBUG_AUTOBLINK") or 0

def debug(s):
    if DEBUG != 0 and DEBUG != "0":
        print(s)

def get_stations(binary_response_from_onhub):
    # map DHCP hostname to list of station_info
    stations = defaultdict(list)
    capturing = False
    parens_count = 0
    tmp = {}
    for i, raw_line in enumerate(binary_response_from_onhub.split(b"\n")):
        # We are opening a binary file, some lines won't be text and
        # it's ok to ignore them, as the data we care about is in the
        # text portion of the file.
        try:
            line = raw_line.decode("utf-8")
        except:
            continue

        if capturing:
            data = line.strip()
            debug("Line %i: -%s-" % ((i+1), data))
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
                else:
                    debug("Empty key/value pair")
                continue

        if "station_info" in line:
            debug("Started capturing at line %d" % (i+1))
            capturing = True
            parens_count = 1
            tmp = {}
            tmp["dhcp_hostname"] = ""

    return stations

def get_onhub_data():
    # Mimic a browser. Data obtained by converting a request from the browser to
    # cURL format and then converted to requests syntax with https://curl.trillworks.com/
    headers = {
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/76.0.3809.100 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3',
        'Accept-Encoding': 'gzip, deflate',
        'Accept-Language': 'en-US,en;q=0.9,it;q=0.8',
    }

    debug("Connecting to OnHub")
    response = requests.get('http://onhub.here/api/v1/diagnostic-report',
                            headers=headers,
                            verify=False)
    return response.content

def get_connected_stations():
    data = get_onhub_data()
    debug("Parsing request")
    stations = get_stations(data)

    connected_stations = [name for name, data in stations.items()
            if all(d["connected"] == "true" for d in data)]
    return connected_stations

print(get_connected_stations())
