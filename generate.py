import configparser
from lib.helpers import *
from lib.MapGenManager import MapGenManager

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




if __name__ == "__main__":
    forceBelowZero = False
    getData = True
    forceRefresh = False

    rebuildCity = False
    disableCityPaint = False
    generateRoads = True

    map_name = "nevada"
    biome = "Boreal"
    edgeType = "hills"

    centerLong = -115.564715
    centerLat = 37.261492

    # NYC
    # centerLong = -73.972005
    # centerLat = 40.773345

    # Meters
    mapWidth = 96000

    # Height Offset
    offsetAmount = 0

    # HM Resolution
    mapResolution = 256

    cityAdjust = 20
    minHighwayLength = 5
    bingAPIKey = config['BingAPI']['key']
    nextzenAPIKey = config['NextZen']['key']

    ghsFile = "GHS_BUILT_LDS2014_GLOBE_R2018A_54009_1K_V2_0.tif"

    generator = MapGenManager(bingAPIKey, nextzenAPIKey, ghsFile)

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
        if status == "Done":
            break

    print(generator.get_zip(uuid))
    print(generator.get_heightmap_image(uuid))