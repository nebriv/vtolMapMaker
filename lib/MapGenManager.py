import requests
import time
from PIL import Image, ImageOps
import os
import pickle
import json
import numpy as np
import configparser
import logging
from lib.ghsDataParser import ghsDataParser
from lib.helpers import *
from uuid import uuid4
import threading
import zipfile
from lib.MapGenSettings import GenSettings
from lib.MapGen import MapGen
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



class MapGenManager:
    generation_threads = {}

    def __init__(self, bingAPIKey, nextzenAPIKey):
        self.ghsParser = ghsDataParser()

        if not os.path.isdir("dataSets"):
            os.mkdir("dataSets")

        self.bingAPIKey = bingAPIKey
        self.nextzenAPIKey = nextzenAPIKey

    def create_map(self, **kwargs):

        uuid = str(uuid4())
        # def generate(self, uuid, centerLong, centerLat, forceBelowZero=True, forceRefresh=False, rebuildCity=True,
        #              disableCityPaint=False, cityAdjust=10, resolution=512, offsetAmount=15, mapWidth=192000,
        #              minHighwayLength=5, mapName=None, generateRoads=True, edgeType="Hills", biome="Boreal"):
        # thread = threading.Thread(target=self.mapper.generate, args=(uuid, centerLong, centerLat, forceBelowZero, forceRefresh, rebuildCity, disableCityPaint, cityAdjust, resolution, offsetAmount, mapWidth, minHighwayLength, mapName, generateRoads, biome, edgeType))

        print(kwargs)
        mapSettings = GenSettings(bingAPIKey=self.bingAPIKey, nextzenAPIKey=self.nextzenAPIKey, ghsParser=self.ghsParser, uuid=uuid, **kwargs)
        print(mapSettings.__dict__)


        map_thread = MapGen(mapSettings)

        self.generation_threads[uuid] = map_thread
        map_thread.start()

        return uuid

    def get_thread_status(self, uuid):
        return self.generation_threads[uuid].status

    def get_zip(self, uuid):
        map_path = os.path.join("maps", uuid)
        if os.path.exists(map_path):
            for file in os.listdir(map_path):
                if file.endswith(".zip"):
                    return os.path.join(map_path, file)

        return False

    def get_heightmap_image(self, uuid):
        map_path = os.path.join("maps", uuid)
        if os.path.exists(map_path):
            for root, dirs, files in os.walk(map_path):
                for file in files:
                    if file.endswith(".png"):
                        return(os.path.join(root, file))

        return False