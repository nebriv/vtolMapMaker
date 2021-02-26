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


class MapGen(threading.Thread):

    status = "Not Started"

    def __init__(self, genSettings):
        super().__init__()

        logger.debug("Initializing vtol mapping thread")

        # self.bingAPIKey = bingKey
        # self.nextzenAPIKey = nextzenAPIKey
        #
        # if not ghsParser:
        #     self.ghsParser = ghsDataParser()

        self.status = "Initialized"

        self.settings = genSettings

    def run(self):

        if self.settings.mapName == None:
            raise ValueError("Invalid or missing Map Name")

        mapNameFile = format_filename(self.settings.mapName)

        uuid_folder = os.path.join("maps", self.settings.uuid)

        mapFolder = os.path.join(uuid_folder, mapNameFile)

        vtmFile = os.path.join(mapFolder, mapNameFile)
        vtmFile = vtmFile + ".vtm"

        if not os.path.isdir("maps"):
            os.mkdir("maps")
        if not os.path.isdir(mapFolder):
            os.makedirs(mapFolder)

        self.status = "Calculating map width and resolution information"

        widthInDegrees = self.settings.mapWidth / 111111

        westLong = self.settings.centerLong - (widthInDegrees / 2)
        northLat = self.settings.centerLat + (widthInDegrees / 2)

        logger.debug("Top Left Corner")
        logger.debug("%s, %s" % (northLat, westLong))

        eastLong = westLong + widthInDegrees
        southLat = northLat - widthInDegrees
        logger.debug("Bottom Left Corner")
        logger.debug("%s, %s" % (southLat, westLong))

        logger.debug("%s, %s" % (0 - southLat, 0 - westLong))

        latOffset = 0 - southLat
        longOffset = 0 - westLong

        logger.debug("Latitude Offset: %s" % latOffset)
        logger.debug("Longitude Offset: %s" % longOffset)

        logger.debug("Bottom Right Corner")
        logger.debug("%s, %s" % (southLat, eastLong))

        heightMapResolution = self.settings.mapWidth / self.settings.resolution
        logger.debug("Meters per pixel: %s" % heightMapResolution)

        distanceBetween = (northLat - southLat) / (self.settings.resolution - 1)

        # Get points between locations
        points = getPoints(self.settings.resolution, southLat, westLong, eastLong, distanceBetween)

        self.status = "Collecting area roads and airports"
        highways, majorRoads, tileData, airports = self.getTiles(points, 8)

        dataHash = self.genDataHash(self.settings.centerLong, self.settings.centerLat, self.settings.mapWidth)

        i = 0

        highwaySegments = []
        heightData = {}

        cachedData = self.get_cached(dataHash)

        if self.settings.rebuildCity:
            self.status = "Collecting city build information"

            buildup_list, maxBuildup, minBuildup = self.settings.ghsParser.getBuildupData(self.settings.resolution, southLat, distanceBetween,
                                                                                 westLong,
                                                                                 eastLong)
            logger.debug(maxBuildup)
            logger.debug(minBuildup)
        elif cachedData:
            buildup_list, maxBuildup, minBuildup = cachedData['builduplist'], cachedData['maxBuildup'], cachedData[
                'minBuildup']
        else:
            self.status = "Collecting city build information"
            buildup_list, maxBuildup, minBuildup = self.settings.ghsParser.getBuildupData(self.settings.resolution, southLat, distanceBetween,
                                                                                 westLong,
                                                                                 eastLong)
            logger.debug(maxBuildup)
            logger.debug(minBuildup)

        if cachedData and not self.settings.forceRefresh:
            heights, minHeight, maxHeight = cachedData['heights'], cachedData['minHeight'], cachedData['maxHeight']
        else:
            self.status = "Collecting height map data."
            heights, minHeight, maxHeight = self.getBingTerrainData(self.settings.resolution, southLat, distanceBetween, westLong,
                                                                    eastLong)

        logger.debug(len(buildup_list))
        logger.debug(len(heights))

        heightData = {"heights": heights, "minHeight": minHeight, "maxHeight": maxHeight,
                      "builduplist": buildup_list,
                      "minBuildup": minBuildup, "maxBuildup": maxBuildup, 'centerLat': self.settings.centerLat,
                      'centerLong': self.settings.centerLong, 'mapWidth': self.settings.mapWidth}

        pickle.dump(heightData, open(os.path.join("dataSets", "%s.p" % dataHash), "wb"))

        heights = heightData['heights']
        minHeight = heightData['minHeight']
        maxHeight = heightData['maxHeight']

        logger.debug("Min Height: %s" % minHeight)
        logger.debug("Max Height: %s" % maxHeight)

        vtolvr_heightoffset = 0

        if self.settings.forceBelowZero:
            self.status = "Running height map offset calculations"
            vtolvr_heightoffset = abs(self.settings.offsetAmount - minHeight)
            logger.debug("Height Adjustment: %s" % vtolvr_heightoffset)

            logger.debug(heights[0:10])

            c = 0
            for height in heights:
                if height < 0:
                    c += 1
            logger.debug("number of heights below 0: %s" % c)
            heights = offsetHeights(heights, vtolvr_heightoffset)

            c = 0
            for height in heights:
                if height < 0:
                    c += 1
            logger.debug("number of heights below 0: %s" % c)

        if self.settings.generateRoads:
            self.status = "Calculating highway elevations"
            for highway in highways:
                logger.debug("Processing %s highway" % highway)
                points = []
                highwayHeightData = {}
                while len(highways[highway]) > 1:
                    cord = highways[highway].pop()
                    lat = float(cord['lat'])
                    lon = float(cord['lon'])
                    height = cord['height']
                    points.append([lat, lon])
                    # logger.debug("Subtracting height offset (%s) from highway height (%s) - %s" % (vtolvr_heightoffset, height, height - vtolvr_heightoffset))
                    highwayHeightData["%s,%s" % (lat, lon)] = {"lat": lat, "lon": lon,
                                                               "height": height - vtolvr_heightoffset}

                # logger.debug("Sorting GPS points")
                points = np.array(points)

                if len(points) > 0 and len(points) > self.settings.minHighwayLength:
                    sorted_order, xy_coord_sorted = find_gps_sorted(points)

                    first = None
                    cordList = xy_coord_sorted.tolist()

                    cordlist_with_height = []
                    # Once again re-aligning heights to coordinates
                    for point in cordList:
                        cordlist_with_height.append(highwayHeightData["%s,%s" % (point[0], point[1])])

                    # logger.debug("Got %s sorted points " % len(cordList))

                    cordList = cordlist_with_height

                    while len(cordList) > 1:

                        if first == None:
                            each_cord = cordList.pop()
                            first = str(
                                gpsTupletoUnityWorldPoint((each_cord['lat'], each_cord['lon']), latOffset, longOffset,
                                                          each_cord['height']))
                            ps = False
                        else:
                            first = highwaySegments[i - 1]['e']
                            ps = highwaySegments[i - 1]['id']

                        each_cord = cordList.pop()
                        mid = str(gpsTupletoUnityWorldPoint((each_cord['lat'], each_cord['lon']), latOffset, longOffset,
                                                            each_cord['height']))

                        last = str(
                            gpsTupletoUnityWorldPoint((each_cord['lat'], each_cord['lon']), latOffset, longOffset,
                                                      each_cord['height']))
                        if len(cordList) != 0:
                            ns = i + 1
                        else:
                            ns = False

                        grid = getGridFromWorldPoint(
                            gpsTupletoUnityWorldPoint((each_cord['lat'], each_cord['lon']), latOffset, longOffset,
                                                      each_cord['height']), self.settings.resolution)

                        segment = {"id": i, "type": 0, "bridge": False, "length": 100, "s": first, "m": mid, "e": last,
                                   'ns': ns, 'ps': ps, "grid": grid}
                        highwaySegments.append(segment)
                        i += 1
                else:
                    logger.warning(
                        "Highway %s has no points or highway points (%s) is below the minimum length (%s)." % (
                            highway, len(points), self.settings.minHighwayLength))


        logger.debug("Tile Count: %s" % len(tileData))
        logger.debug("Highway Count: %s" % len(highways))
        logger.debug("Major Road Count: %s" % len(majorRoads))
        logger.debug("Total Lat/Lon Points: %s" % len(points))
        self.status = "Saving VTM file"
        self.saveVTM(self.settings.mapName, self.settings.mapName, "test", self.settings.mapWidth, self.settings.resolution, "HeightMap", self.settings.edgeType, self.settings.biome, self.settings.mapName, airports,
                     highwaySegments, vtmFile)

        minHeight = -80
        maxHeight = 4000

        buildups = heightData['builduplist']

        logger.debug("Got %s heights" % len(heights))

        logger.debug("Min Height: %s" % minHeight)
        logger.debug("Max Height: %s" % maxHeight)

        logger.debug("Creating Height Map")

        heightMapFile = os.path.join(mapFolder, "height.png")
        self.status = "Saving height map file"
        self.createHeightMapFile(heights, self.settings.resolution, maxHeight, minHeight, buildups, self.settings.cityAdjust, heightMapFile)

        self.status = "Creating zip"

        zip_file = os.path.join(uuid_folder, "%s.zip" % self.settings.mapName)
        zipdir(mapFolder, zip_file)

        self.status = "Done"

    def get_cached(self, dataHash):
        getData = False
        heightData = False
        if os.path.isdir("dataSets"):
            if os.path.isfile(os.path.join("dataSets", "%s.p" % dataHash)):
                if not self.settings.forceRefresh:
                    logger.debug("Found cached data!")
                    heightData = pickle.load(open(os.path.join("dataSets", "%s.p" % dataHash), 'rb'))
                else:
                    logger.debug("Found the data, but forcing a refresh")
                    getData = True
            else:
                logger.debug("Data set for given params does not exist")
                getData = True
        else:
            logger.debug("dataSets folder does not exist")
            getData = True

        return heightData

    def genDataHash(self, centerLong, centerLat, mapWidth):
        dataHashString = "%s,%s,%s" % (round(centerLong, 2), round(centerLat, 2), mapWidth)
        return genHash(dataHashString)

    def saveVTM(self, mapID, mapName, mapDescription, mapSize, mapResolution, mapType, edgeMode, biome, seed, airports,
                roads, vtmFileName):
        file_lines = []

        file_lines.append("VTMapCustom")
        file_lines.append("{")
        file_lines.append("\tmapId = %s" % mapID)
        file_lines.append("\tmapName = %s" % mapName)
        file_lines.append("\tmapDescription = %s" % mapDescription)
        file_lines.append("\tmapType = %s" % mapType)
        file_lines.append("\tedgeMode = %s" % edgeMode)
        file_lines.append("\tbiome = %s" % biome)
        file_lines.append("\tseed = %s" % seed)
        file_lines.append("\tmapSize = %s" % int(((mapSize / 1000) / 3)))

        file_lines.append("\tTerrainSettings")
        file_lines.append("\t{")
        file_lines.append("\t}")

        # Prefabs
        prefab_id = 0

        file_lines.append("\tStaticPrefabs")
        file_lines.append("\t{")

        for airport in airports:
            gamepos = gpsTupletoUnityWorldPoint(airport['cords'], 0, 0, airport['height'])

            grid = getGridFromWorldPoint(gamepos, mapResolution)

            file_lines.append("\t\tStaticPrefab")
            file_lines.append("\t\t{")
            file_lines.append("\t\t\tprefab = airbase1")
            file_lines.append("\t\t\tid = %s" % prefab_id)
            file_lines.append("\t\t\tglobalPos = (%s)" % str(gamepos))
            file_lines.append("\t\t\trotation = (0, 311.5949, 0)")
            file_lines.append("\t\t\tgrid = (%s, %s)" % (grid[0], grid[1]))
            file_lines.append("\t\t\ttSpacePos = (0, 0, 0)")
            file_lines.append("\t\t\tterrainToLocalMatrix = 0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;1;")
            file_lines.append("\t\t\tbaseName = %s" % airport['name'])
            file_lines.append("\t\t}")
            prefab_id += 1

        file_lines.append("\t}")
        file_lines.append("""	BezierRoads
\t{""")
        # Roads
        if len(roads) > 0:
            file_lines.append("""
            Chunk
            {
                grid = (0,0)""")
            for segment in roads:
                file_lines.append("""			Segment
                {""")
                file_lines.append("""				id = %s""" % segment['id'])
                file_lines.append("""				type = %s""" % segment['type'])
                file_lines.append("""				bridge = %s""" % segment['bridge'])
                file_lines.append("""				length = %s""" % segment['length'])
                file_lines.append("""				s = (%s)""" % segment['s'])
                file_lines.append("""				m = (%s)""" % segment['m'])
                file_lines.append("""				e = (%s)""" % segment['e'])
                if segment['ns']:
                    file_lines.append("""				ns = %s""" % segment['ns'])
                if segment['ps']:
                    file_lines.append("""				ps = %s""" % segment['ps'])
                file_lines.append("""			}""")

            file_lines.append("""		}""")

        file_lines.append("""	}""")
        file_lines.append("}")

        with open(vtmFileName, 'w') as outFile:
            outFile.writelines(s + '\n' for s in file_lines)

    def generateAirportConfig(self):
        pass

    def createHeightMapFile(self, heights, width, maxHeight, minHeight, buildup, cityAdjust, heightMapFile):
        heightDiff = maxHeight - minHeight;
        scaleFactor = 1.0

        logger.debug(heightDiff)
        if heightDiff > 255:
            logger.debug("Height Diff is more than 255, so we need to scale properly")
            scaleFactor = (255 / heightDiff)

        logger.debug("Current height scale factor: %s" % scaleFactor)

        image = Image.new('RGBA', (width, width))

        maxGreen = 0
        minGreen = 300

        # Finds the new min/max after adjust for the city adjust parameter (To reduce the number of cities)
        for i in range(width):
            for j in range(width):
                if i < width and j < width:
                    index = j + (width * i)
                    buildupValue = (buildup[index] - cityAdjust)
                    greenValue = int(buildupValue)

                    if greenValue > maxGreen:
                        maxGreen = greenValue

                    if greenValue < minGreen:
                        minGreen = greenValue

        # This brute forces a new scale to stretch the new min/max green values to fill the 0-255 bits in the image
        logger.debug("Finding new city scale factor")
        gVal = maxGreen
        cityScale = 1.1
        while gVal != 255 and gVal <= 255:
            gVal = round(maxGreen * cityScale, 0)
            cityScale = round(cityScale + .01, 3)

        logger.debug("New city Scale Factor (scaling to 255): %s" % cityScale)

        # Reseting min/max for sanity checking
        maxGreen = 0
        minGreen = 300

        for i in range(width):
            for j in range(width):
                if i < width and j < width:
                    index = j + (width * i)

                    belowWater = False

                    if heights[index] < -3:
                        belowWater = True

                    redValue = int(scaleFactor * (heights[index] - minHeight))

                    afterCityAdjust = buildup[index] - cityAdjust

                    if afterCityAdjust < 0:
                        buildupValue = ((buildup[index] - cityAdjust) / cityScale)
                    else:
                        buildupValue = ((buildup[index] - cityAdjust) * cityScale)

                    greenValue = int(buildupValue)
                    if greenValue < 0:
                        greenValue = 0

                    if greenValue > maxGreen:
                        maxGreen = greenValue

                    if greenValue < minGreen:
                        minGreen = greenValue

                    if belowWater:
                        greenValue = 0

                    if self.settings.disableCityPaint:
                        greenValue = 0

                    if redValue < 0 and greenValue < 0:
                        image.putpixel((i, j), (0, 0, 0, 255))
                    else:
                        image.putpixel((i, j), (redValue, greenValue, 0, 255))

        image = ImageOps.mirror(image)
        image = ImageOps.flip(image)
        image = image.transpose(Image.ROTATE_270)

        image.save(heightMapFile, "PNG")
        # image.show()

    def getBingTerrainDataPointList(self, points, resolution=30):
        # List of tuples containing GPS points in (lat,lon) format
        logger.debug("Getting %s elevation points from Bing" % len(points))
        requestUrlTemplate = "http://dev.virtualearth.net/REST/v1/Elevation/List?key=%s" % self.settings.bingAPIKey
        # requestUrlTemplate = "http://dev.virtualearth.net/REST/v1/Elevation/Polyline?points={0}&samples={1}&key={2}"
        heights = []

        point_string = ""
        for point in points:
            point_string += "%s,%s," % (point[0], point[1])

        point_string = point_string.rstrip(",")

        postData = {"points": point_string, 'samples': resolution}
        # postData = "points=%s" % point_string

        # Content - Length: insertLengthOfHTTPBody
        # Content - Type: text / plain;
        # charset = utf - 8

        headers = {"Content-Type": "text/plain", "charset": "utf-8"}

        url = requestUrlTemplate
        # url = requestUrlTemplate.format(point_string, resolution, self.bingAPIKey)

        response = requests.post(url, data=postData, headers=headers)
        try:
            if "resourceSets" in response.json():
                if 'resources' in response.json()['resourceSets'][0]:
                    if 'elevations' in response.json()['resourceSets'][0]['resources'][0]:
                        for height in response.json()['resourceSets'][0]['resources'][0]['elevations']:
                            heights.append(height)

        except IndexError as err:
            logger.error("Error getting elevations for poly line.")
            logger.error(err)
            logger.error(response.text)

        if len(heights) == 0:
            self.status = "Error: No elevations returned by Bing Terrain List"
            raise ValueError("No elevations returned by Bing Terrain List")

        return heights

    def getBingTerrainData(self, subDivisions, southLat, distanceBetween, westLong, eastLong):
        # TODO: Rewrite this to use bounding box.
        requestUrlTemplate = "http://dev.virtualearth.net/REST/v1/Elevation/Polyline?points={0},{1},{0},{2}&samples={3}&key={4}"
        heights = []
        maxHeight = 0
        minHeight = 29000
        logger.debug("Getting Bing Terrain Data")
        for i in range(subDivisions):
            lat = southLat + (distanceBetween * i)
            long1 = westLong
            long2 = eastLong
            url = requestUrlTemplate.format(lat, long1, long2, subDivisions, self.settings.bingAPIKey)
            goodResponse = False
            maxRetry = 3
            attempts = 1
            while not goodResponse and attempts <= maxRetry:
                response = requests.get(url)
                if response.status_code == 200:
                    if "resourceSets" in response.json():
                        if 'resources' in response.json()['resourceSets'][0]:
                            if 'elevations' in response.json()['resourceSets'][0]['resources'][0]:
                                for height in response.json()['resourceSets'][0]['resources'][0]['elevations']:
                                    if height > maxHeight:
                                        maxHeight = height
                                    if height < minHeight:
                                        minHeight = height
                                    heights.append(height)
                                goodResponse = True
                                break
                attempts += 1

                # TODO: Handle this better.
                logger.debug("Got a bad response, missing data?")
                logger.debug(response.status_code)
                logger.debug(response.text)
                logger.debug(response.json())
                logger.debug("Trying again")
                time.sleep(2)

            if i % 20 == 0:
                logger.debug("i: %s, HMax: %s, HMin: %s" % (i, maxHeight, minHeight))
            time.sleep(.1)
        return heights, minHeight, maxHeight

    def getTiles(self, _points, _zoom):
        tiles = []

        ## find the tile which contains each point
        for point in _points:
            tiles.append(tileForMeters(latLngToMeters({'x': point['x'], 'y': point['y']}), _zoom))

        ## de-dupe
        tiles = [dict(tupleized) for tupleized in set(tuple(item.items()) for item in tiles)]

        ## patch holes in tileset

        ## get min and max tiles for lat and long
        # set min vals to maximum tile #s + 1 at zoom 21
        minx = 2097152
        maxx = -1
        miny = 2097152
        maxy = -1
        logger.debug("tiles:" + str(tiles))
        for tile in tiles:
            minx = min(minx, tile['x'])
            maxx = max(maxx, tile['x'])
            miny = min(miny, tile['y'])
            maxy = max(maxy, tile['y'])
        # print miny, minx, maxy, maxx

        newtiles = []

        highways = []
        majorRoads = []
        tileData = []

        for tile in tiles:
            # find furthest tiles from this tile on x and y axes
            # todo: check across the dateline, maybe with some kind of mod(360) -
            # if a closer value is found, use that instead and warp across the antimeridian
            x = tile['x']
            lessx = 2097152
            morex = -1
            y = tile['y']
            lessy = 2097152
            morey = -1
            for t in tiles:
                if int(t['x']) == int(tile['x']):
                    # check on y axis
                    lessy = min(lessy, t['y'])
                    morey = max(morey, t['y'])
                if int(t['y']) == int(tile['y']):
                    # check on x axis
                    lessx = min(lessx, t['x'])
                    morex = max(morex, t['x'])

            # if a tile is found which is not directly adjacent, add all the tiles between the two
            if (lessy + 2) < tile['y']:
                for i in range(int(lessy + 1), int(tile['y'])):
                    newtiles.append({'x': tile['x'], 'y': i, 'z': _zoom})
            if (morey - 2) > tile['y']:
                for i in range(int(morey - 1), int(tile['y'])):
                    newtiles.append({'x': tile['x'], 'y': i, 'z': _zoom})
            if (lessx + 2) < tile['x']:
                for i in range(int(lessx + 1), int(tile['x'])):
                    newtiles.append({'x': i, 'y': tile['y'], 'z': _zoom})
            if (morex - 2) > tile['x']:
                for i in range(int(morex - 1), int(tile['x'])):
                    newtiles.append({'x': i, 'y': tile['y'], 'z': _zoom})

        ## de-dupe
        newtiles = [dict(tupleized) for tupleized in set(tuple(item.items()) for item in newtiles)]
        ## add fill tiles to boundary tiles
        tiles = tiles + newtiles
        ## de-dupe
        tiles = [dict(tupleized) for tupleized in set(tuple(item.items()) for item in tiles)]

        ## download tiles
        logger.debug("Downloading %i tiles at zoom level %i" % (len(tiles), _zoom))
        logger.debug("Zoom to meters: %s" % tile_to_meters(_zoom))
        ## make/empty the tiles folder
        folder = "tiles"
        if not os.path.exists(folder):
            os.makedirs(folder)

        total = len(tiles)
        if total == 0:
            logger.error("Error: no tiles")
            exit()
        count = 0
        highway_data = {}

        airports = []

        for tile in tiles:
            tilename = "%i-%i-%i.json" % (_zoom, tile['x'], tile['y'])

            tilename = os.path.join("tiles", tilename)

            if os.path.isfile(tilename):
                with open(tilename, 'r') as infile:
                    j = json.load(infile)
            else:

                r = requests.get(
                    "https://tile.nextzen.org/tilezen/vector/v1/all/%i/%i/%i.json?api_key=%s" % (
                        _zoom, tile['x'], tile['y'], self.settings.nextzenAPIKey))
                j = json.loads(r.text)

                with open(tilename, 'w') as outfile:
                    outfile.write(r.text)

            logger.debug("Processing Tile %i-%i-%i " % (_zoom, tile['x'], tile['y']))

            # extract only buildings layer - nextzen vector tile files are collections of geojson objects -
            # doing this turns each file into a valid standalone geojson files -
            # you can replace "buildings" with whichever layer you want
            # j = json.dumps(j["buildings"])

            for landuse in j['landuse']['features']:
                if landuse['properties']['kind'] == "airfield" or landuse['properties']['kind'] == "aerodrome":
                    airport_location = []
                    if "operator" in landuse['properties']:
                        name = landuse['properties']['operator']
                    else:
                        name = "Unknown Name"

                    cord_list = []

                    for cords in landuse['geometry']['coordinates']:
                        for cord in cords:
                            if isinstance(cord[0], list):
                                for sublist in cord:
                                    cord_list.append([sublist[1], sublist[0]])
                            else:
                                cord_list.append([cord[1], cord[0]])

                    lat_list = []
                    lon_list = []

                    for each in cord_list:
                        lat_list.append(each[0])
                        lon_list.append(each[1])

                    center_lat = sum(lat_list) / len(lat_list)
                    center_lon = sum(lon_list) / len(lon_list)

                    airport_location = [center_lat, center_lon]

                    airports.append({"name": name, "cords": airport_location})
                    logger.debug("AIRPORT - %s" % {"name": name, "cords": airport_location})

            majorroad_data = []

            roadCount = 0
            for road in j['roads']['features']:
                roadCount += 1
                if road['properties']['kind'] == "highway":
                    if "shield_text" in road['properties']:
                        if road['properties']['shield_text']:
                            roadname = road['properties']['shield_text'].lower()
                        else:
                            roadname = "NoName-%s" % roadCount
                    else:
                        roadname = "NoName-%s" % roadCount

                    road_data = []
                    for cords in road['geometry']['coordinates']:
                        if type(cords[0]) is not float:
                            for cord in cords:
                                road_data.append({"lat": cord[1], "lon": cord[0], "height": 0})
                        else:
                            road_data.append({"lat": cords[1], "lon": cords[0], "height": 0})

                    if roadname in highway_data:
                        highway_data[roadname] += road_data
                    else:
                        highway_data[roadname] = []
                        highway_data[roadname] = road_data
                    # highway_data.append(road_data)
                if road['properties']['kind'] == "major_road":

                    road_data = []
                    for cords in road['geometry']['coordinates']:
                        if type(cords[0]) is not float:
                            # print("List")
                            # print(cords)
                            for cord in cords:
                                road_data.append({"lat": cord[1], "lon": cord[0], "height": 0})
                        else:
                            # print("not list")
                            # print(cords)
                            road_data.append({"lat": cords[1], "lon": cords[0], "height": 0})
                    majorroad_data.append(road_data)

            majorRoads += majorroad_data

            tileData.append(json.dumps(j))

            # use this jumps() command instead for the original feature collection with all the data
            j = json.dumps(j)

            count += 1

        highway_elevation = []

        for highway in highway_data:
            if len(highway_data[highway]) == 0:
                print("%s is empty" % highway)
            for point in highway_data[highway]:
                highway_elevation.append((point['lat'], point['lon']))

        if len(highway_elevation) == 0:
            logger.warning("No highway elevations found in tile")
            highway_data = None

        highway_elevation_new = self.getBingTerrainDataPointList(highway_elevation)

        # Re-adding the new heights to the highway data, by aligning the lists.
        highwayPoints = 0
        for h_i, highway in enumerate(highway_data):
            for p_i, point in enumerate(highway_data[highway]):
                highway_data[highway][p_i]['height'] = highway_elevation_new[highwayPoints]
                highwayPoints += 1

        if len(airports) > 0:
            logger.debug("Getting airport elevation data")
            airport_elevation = []
            for airport in airports:
                airport_elevation.append(airport['cords'])

            airport_elevation = self.getBingTerrainDataPointList(airport_elevation)
            for i, airport in enumerate(airports):
                airports[i]['height'] = airport_elevation[i]

        return highway_data, majorRoads, tileData, airports

