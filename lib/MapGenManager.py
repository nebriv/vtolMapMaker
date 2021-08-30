from lib.ghsDataParser import ghsDataParser
from lib.helpers import *
from uuid import uuid4
from lib.MapGenSettings import GenSettings
from lib.MapGen import MapGen
import os

# TODO: Cleanup Code, road height, city density

logger = logging.getLogger(__name__)

handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

logger.addHandler(handler)
logger.setLevel('DEBUG')

# logger.debug("Checking for config 'config.conf' file...")
# if os.path.isfile('config.conf'):
#     logger.debug("Loading config file...")
#
#     config = configparser.ConfigParser()
#     config.read('config.conf')
# else:
#     logger.error("Could not find config.conf file!")
#     raise FileNotFoundError("Could not find config.conf file!")


class MapGenManager:
    generation_threads = {}

    def __init__(self, nextzenAPIKey, outputDir, ghsFile='GHS_BUILT_LDS2014_GLOBE_R2018A_54009_1K_V2_0.tif'):
        self.ghsParser = ghsDataParser(ghsFile)

        if not os.path.isdir("dataSets"):
            os.mkdir("dataSets")

        self.nextzenAPIKey = nextzenAPIKey
        self.outputDir = outputDir

    def create_map(self, **kwargs):

        uuid = str(uuid4())
        # def generate(self, uuid, centerLong, centerLat, forceBelowZero=True, forceRefresh=False, rebuildCity=True,
        #              disableCityPaint=False, cityAdjust=10, resolution=512, offsetAmount=15, mapWidth=192000,
        #              minHighwayLength=5, mapName=None, generateRoads=True, edgeType="Hills", biome="Boreal"):
        # thread = threading.Thread(target=self.mapper.generate, args=(uuid, centerLong, centerLat, forceBelowZero, forceRefresh, rebuildCity, disableCityPaint, cityAdjust, resolution, offsetAmount, mapWidth, minHighwayLength, mapName, generateRoads, biome, edgeType))

        generation_delay = self.count_running_threads() ** 1.8

        mapSettings = GenSettings(nextzenAPIKey=self.nextzenAPIKey, outputDir=self.outputDir, ghsParser=self.ghsParser, uuid=uuid, delay=generation_delay,  **kwargs)

        map_thread = MapGen(mapSettings)

        self.generation_threads[uuid] = map_thread
        map_thread.start()

        return uuid

    def count_running_threads(self):
        count = 0
        for thread in self.generation_threads:
            if self.generation_threads[thread].is_alive():
                if self.generation_threads[thread].status != {"Status": "Done"} and "Error" not in self.generation_threads[thread].status:
                    count += 1
        return count

    def get_thread_status(self, uuid):
        if uuid in self.generation_threads:
            return self.generation_threads[uuid].status
        else:
            return False

    def get_zip(self, uuid):
        if uuid in self.generation_threads:
            if self.generation_threads[uuid].status['Status'] == "Done":
                return self.generation_threads[uuid].zipFile

        return False

    def get_heightmap_image(self, uuid):
        if uuid in self.generation_threads:
            if self.generation_threads[uuid].status['Status'] == "Done":
                return self.generation_threads[uuid].heightMap

        return False