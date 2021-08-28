import configparser
from lib.helpers import *
from lib.MapGenManager import MapGenManager
import os
import time
# TODO: Cleanup Code, road height, city density

logger = logging.getLogger(__name__)

handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

logger.addHandler(handler)
logger.setLevel('DEBUG')

logger.debug("Checking for config 'config.conf' file...")
if os.path.isfile('config.conf'):
    logger.debug("Loading config file...")

    config = configparser.ConfigParser()
    config.read('config.conf')
else:
    logger.error("Could not find config.conf file!")
    raise FileNotFoundError("Could not find config.conf file!")



# subDivisions = 512
# topLeft = [36.693492432000426,-118.99671543200044]
# bottomRight = [35.82949156799956, -118.13271456799959]
#
# lats = sorted([topLeft[0], bottomRight[0]])
# lons = sorted([topLeft[1], bottomRight[1]])
#
# longCords = pointiterator(lons[0], lons[1], subDivisions)
# latCords = pointiterator(lats[0], lats[1], subDivisions)
#
# longs = np.fromiter(longCords, dtype=np.float64)
# # print(longs)
#
#
# lats = np.fromiter(latCords, dtype=np.float64)
# myarray = np.meshgrid(longs, lats, indexing='xy')
#
#
# xo, yo = np.meshgrid(longs, lats, indexing='xy')
# #
# # # make array of tuples
# tups = np.rec.fromarrays([xo, yo], names='longitude,latitude')
#
# print(tups.shape)
# print(tups.size)
#
#
# # for x in np.nditer(tups):
#
#
# coords = tups.flatten()
# total_cords = len(coords)
#
# chunks = np.array_split(coords, 250)
#
#
# url = "https://api.open-elevation.com/api/v1/lookup"
#
# heights = []
#
# for chunk in chunks:
#
#     request_data = {"locations": []}
#
#     for cord in chunk:
#         request_data['locations'].append({"latitude": cord[1], "longitude": cord[0]})
#
#     print(request_data)
#
#     r = requests.post(url, json=request_data)
#     print(r.status_code)
#     for each in r.json()['results']:
#
#         print(each['elevation'])
#
#
# exit()
if __name__ == "__main__":
    forceBelowZero = False
    getData = True
    forceRefresh = False

    rebuildCity = True
    disableCityPaint = False
    generateRoads = False

    map_name = "nevada"
    biome = "Boreal"
    edgeType = "hills"

    # Cape Code NOT FLIPPED???
    centerLong = -70.27130126953126
    centerLat = 41.93701966042529

    # NYC FLIPPED????
    centerLong = -73.972005
    centerLat = 40.773345

    # Meters
    mapWidth = 192000

    # Height Offset
    offsetAmount = 0

    # HM Resolution
    mapResolution = 512

    cityAdjust = 95
    minHighwayLength = 5
    nextzenAPIKey = config['NextZen']['key']

    ghsFile = "GHS_BUILT_LDS2014_GLOBE_R2018A_54009_1K_V2_0.tif"

    generator = MapGenManager(nextzenAPIKey, "maps", ghsFile)

    uuid = generator.create_map(centerLong=centerLong, centerLat=centerLat, forceBelowZero=forceBelowZero, forceRefresh=forceRefresh,
                                rebuildCity=rebuildCity, disableCityPaint=disableCityPaint, cityAdjust=cityAdjust,
                                resolution=mapResolution, offsetAmount=offsetAmount, mapWidth=mapWidth,
                                minHighwayLength=minHighwayLength, mapName=map_name, generateRoads=generateRoads, biome=biome, edgeType=edgeType)
    last_status = None
    while True:
        status = generator.get_thread_status(uuid)
        if status != last_status:
            print(status)
            last_status = status

        if "Status" in status:
            if status["Status"] == "Done":
                exit()
        if "Error" in status:
            exit()
        if generator.count_running_threads() == 0:
            print("Generator thread exited unexpectedly!")
            exit()
        time.sleep(1)
