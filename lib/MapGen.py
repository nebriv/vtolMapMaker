import requests
import time
from PIL import Image, ImageOps
import pickle
import json
from lib.helpers import *
import threading
import datetime
import traceback
import requests_cache
from lib import elevationData
import os
import math
r_headers = {"User-Agent": "VTOL Map Maker v%s (https://vtolmapmaker.nebriv.com)" % getVersion()}

requests_cache.install_cache(cache_name='github_cache', backend='sqlite', expire_after=86400)

logger = logging.getLogger(__name__)

handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

logger.addHandler(handler)
logger.setLevel('DEBUG')
#
# logger.debug("Checking for config 'config.conf' file...")
# if os.path.isfile('config.conf'):
#     logger.debug("Loading config file...")
#
#     config = configparser.ConfigParser()
#     config.read('config.conf')
# else:
#     logger.error("Could not find config.conf file!")
#     raise FileNotFoundError("Could not find config.conf file!")
#




class MapGen(threading.Thread):

    status = "Not Started"
    vtmData = None
    heightMap = None
    zipFile = None

    def __init__(self, genSettings):
        super().__init__()

        logger.debug("Initializing vtol mapping thread")

        self.status = {"Status": "Initialized"}

        self.settings = genSettings

    def run(self):
        if self.settings.delay > 0:
            logger.warning("Delaying generation thread %s seconds" % self.settings.delay)


            sleep_counter = math.ceil(self.settings.delay)
            while sleep_counter > 0:
                self.status = {"Status": "Waiting in fake queue - %s" % sleep_counter, "Progress": 1}
                time.sleep(1)
                sleep_counter -= 1
        try:
            if self.settings.mapName == None:
                raise ValueError("Invalid or missing Map Name")

            self.run_date = datetime.datetime.now()

            mapNameFile = format_filename(self.settings.mapName)
            curDir = os.path.dirname(os.path.abspath(__file__))

            uuid_folder = os.path.join(self.settings.outputDir, self.settings.uuid)
            mapFolder = os.path.join(uuid_folder, mapNameFile)


            if not os.path.isdir(self.settings.outputDir):
                os.mkdir(self.settings.outputDir)
            if not os.path.isdir(mapFolder):
                os.makedirs(mapFolder)

            self.status = {"Status": "Calculating map width and resolution information", "Progress": 10}

            widthInDegrees = self.settings.mapWidth / 111111

            westLong = self.settings.centerLong - (widthInDegrees / 2)
            northLat = self.settings.centerLat + (widthInDegrees / 2)

            logger.debug("Top Left Corner")
            logger.debug("%s,%s" % (northLat, westLong))


            eastLong = westLong + widthInDegrees
            southLat = northLat - widthInDegrees
            logger.debug("Bottom Left Corner")
            logger.debug("%s,%s" % (southLat, westLong))

            logger.debug("Top Right Corner")
            logger.debug("%s,%s" % (northLat, eastLong))

            logger.debug("Bottom Right Corner")
            logger.debug("%s,%s" % (southLat, eastLong))


            top_left = (northLat, westLong)
            bottom_left = (southLat, westLong)
            top_right = (northLat, eastLong)
            bottom_right = (southLat, eastLong)

            latOffset = 0 - southLat
            longOffset = 0 - westLong

            logger.debug("Latitude Offset: %s" % latOffset)
            logger.debug("Longitude Offset: %s" % longOffset)


            heightMapResolution = self.settings.mapWidth / self.settings.resolution
            logger.debug("Meters per pixel: %s" % heightMapResolution)

            distanceBetween = (northLat - southLat) / (self.settings.resolution - 1)

            # Get points between locations for use with height map and tile fetch
            coordinate_list = getPoints(self.settings.resolution, southLat, westLong, eastLong, distanceBetween)

            self.status = {"Status": "Collecting area roads and airports", "Progress": 20}


            if len(coordinate_list) > 0:

                try:
                    highways, majorRoads, tileData, airports = self.getTiles(coordinate_list, 8)
                    if self.settings.disablePrefabs:
                        airports = []

                except Exception as error:
                    logger.debug("Received error generating Tile Data")
                    traceback.print_exc()
                    self.status = {"Error": "Error collecting area roads and airports.", "Status": "Error"}
                    highways = []
                    majorRoads = []
                    tileData = []
                    airports = []
            else:
                self.status = {"Status": "No roads or airports in the area."}
                highways = []
                majorRoads = []
                tileData = []
                airports = []

            dataHash = self.genDataHash(self.settings.centerLong, self.settings.centerLat, self.settings.mapWidth, self.settings.resolution)

            cachedData = self.get_cached(dataHash)


            # Getting city build up data
            if not self.settings.disableCityPaint:
                if self.settings.rebuildCity or not cachedData:
                    self.status = {"Status": "Collecting city build up information", "Progress": 30}
                    buildup_list, maxBuildup, minBuildup = self.settings.ghsParser.getBuildupData(self.settings.resolution, southLat, distanceBetween, westLong, eastLong)
                    logger.debug("Max Build Up: %s" % maxBuildup)
                    logger.debug("Min Build Up: %s" % minBuildup)
                elif cachedData:
                    logger.debug("Got cached city data")
                    buildup_list, maxBuildup, minBuildup = cachedData['builduplist'], cachedData['maxBuildup'], cachedData['minBuildup']
                else:
                    logger.error("Final Else hit on cache/rebuild check for city paint generation")
                    buildup_list, maxBuildup, minBuildup = [],0,0
            else:
                buildup_list, maxBuildup, minBuildup = [], 0,0


            # Getting elevation data
            if cachedData and not self.settings.forceRefresh:
                heights, minHeight, maxHeight = cachedData['heights'], cachedData['minHeight'], cachedData['maxHeight']
            else:
                self.status = {"Status": "Collecting height map data.", "Progress": 40}
                heights, minHeight, maxHeight = self.getOpenElevationBoundingBox(coordinate_list)


            vtolvr_heightoffset = 0
            if self.settings.forceBelowZero:
                self.status = {"Status": "Running height map offset calculations", "Progress": 50}
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

            # logger.debug("Smoothing height map")
            # heights = smoothPoints(heights, smoothness=10)


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

 
            if self.settings.generateRoads:
                highwaySegments = self.generateHighways(highways, vtolvr_heightoffset, latOffset, longOffset)
            else:
                highwaySegments = []

            logger.debug("Tile Count: %s" % len(tileData))
            logger.debug("Highway Count: %s" % len(highways))
            logger.debug("Major Road Count: %s" % len(majorRoads))
            logger.debug("Total Lat/Lon Points: %s" % len(coordinate_list))
            self.status = {"Status": "Creating VTM data", "Progress": 60}
            self.vtmData = self.createVTM(self.settings.mapName, self.settings.mapName, "test", self.settings.mapWidth, self.settings.resolution, "HeightMap", self.settings.edgeType, self.settings.biome, "seed", airports, highwaySegments)

            vtmFile = os.path.join(mapFolder, mapNameFile)
            vtmFile = vtmFile + ".vtm"

            # vtmFile = tempfile.TemporaryFile()
            # vtmFile.writeLines(self.vtmData)

            logger.debug("Creating VTM File: %s" % vtmFile)

            with open(vtmFile, 'w') as outFile:
                outFile.writelines(s + '\n' for s in self.vtmData)

            minHeight = -80
            maxHeight = 4000

            buildups = heightData['builduplist']
            logger.debug("Number of build ups in list: %s" % len(buildups))

            logger.debug("Got %s heights" % len(heights))

            logger.debug("Min Height: %s" % minHeight)
            logger.debug("Max Height: %s" % maxHeight)

            heightMapFile = os.path.join(mapFolder, "height.png")
            logger.debug("Creating Height Map: %s" % heightMapFile)

            self.status = {"Status": "Wrangling pixels", "Progress": 70}

            #heights = smoothPoints(heights, 5)

            generatedPixels = self.generatePixels(heights, self.settings.resolution, maxHeight, minHeight, buildups, self.settings.cityAdjust)
            self.status = {"Status": "Creating height map", "Progress": 80}
            self.heightMap = self.generateSingleMap(generatedPixels, self.settings.resolution, heightMapFile)

            self.status = {"Status": "Creating split height map", "Progress": 85}
            self.generateSplitMap(generatedPixels, self.settings.resolution, heightMapFile, 4)

            self.status = {"Status": "Creating zip", "Progress": 90}
            self.zipFile = os.path.join(uuid_folder, "%s.zip" % self.settings.mapName)
            zipdir(mapFolder, self.zipFile)

            self.status = {"Status": "Done", "Progress": 100}
        except Exception as error:
            if "Error" not in self.status:
                self.status = {"Error": "An unknown error occurred while processing.", "Status": "Error"}
            logger.error("Error processing %s: %s" % (self.settings.uuid, error))
            traceback.print_exc()

    def generateHighways(self, highways, vtolvr_heightoffset, latOffset, longOffset):
        self.status = {"Status": "Calculating highway elevations"}
        highwaySegments = []
        i = 0
        for highway in highways:
            points = []
            highwayHeightData = {}
            while len(highways[highway]) > 1:
                cord = highways[highway].pop()
                lat = float(cord['lat'])
                lon = float(cord['lon'])
                height = cord['height']
                points.append([lat, lon])
                # logger.debug("Subtracting height offset (%s) from highway height (%s) - %s" % (vtolvr_heightoffset, height, height - vtolvr_heightoffset))
                highwayHeightData["%s,%s" % (lat, lon)] = {"lat": lat, "lon": lon, "height": height - vtolvr_heightoffset}

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
        return highwaySegments

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

    def genDataHash(self, centerLong, centerLat, mapWidth, resolution):
        dataHashString = "%s,%s,%s,%s" % (round(centerLong, 2), round(centerLat, 2), mapWidth, resolution)
        return genHash(dataHashString)

    def createVTM(self, mapID, mapName, mapDescription, mapSize, mapResolution, mapType, edgeMode, biome, seed, airports,
                roads):
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
        file_lines.append("\tBezierRoads")
        file_lines.append("\t{")

        # Roads
        if len(roads) > 0:
            file_lines.append("\t\tChunk")
            file_lines.append("\t\t{")
            file_lines.append("\t\t\tgrid = (0,0)")
            for segment in roads:
                file_lines.append("\t\t\tSegment")
                file_lines.append("\t\t\t{")
                file_lines.append("\t\t\t\tid = %s" % segment['id'])
                file_lines.append("\t\t\t\ttype = %s" % segment['type'])
                file_lines.append("\t\t\t\tbridge = %s" % segment['bridge'])
                file_lines.append("\t\t\t\tlength = %s" % segment['length'])
                file_lines.append("\t\t\t\ts = (%s)" % segment['s'])
                file_lines.append("\t\t\t\tm = (%s)" % segment['m'])
                file_lines.append("\t\t\t\te = (%s)" % segment['e'])
                if segment['ns']:
                    file_lines.append("\t\t\t\tns = %s" % segment['ns'])
                if segment['ps']:
                    file_lines.append("\t\t\t\tps = %s" % segment['ps'])
                file_lines.append("\t\t\t}")

            file_lines.append("\t\t}")

        file_lines.append("\t}")
        file_lines.append("}")

        return file_lines
        # with open(vtmFileName, 'w') as outFile:
        #     outFile.writelines(s + '\n' for s in file_lines)

    def generateAirportConfig(self):
        pass

    def generateSplitMap(self, pixels, width, fileName, count):

        greens = []
        reds = []

        for i in range(width):
            for j in range(width):
                if i < width and j < width:
                    index = j + (width * i)

                    greenValue = int(pixels[index][1])
                    redValue = int(pixels[index][0])
                    greens.append(greenValue)
                    reds.append(redValue)

        greens_split = splitHeight(greens, count)
        reds_split = splitHeight(reds, count)


        for c in range(count):

            image = Image.new('RGBA', (width, width))
            for i in range(width):
                for j in range(width):
                    if i < width and j < width:
                        index = j + (width * i)
                        redValue = reds_split[c][index]
                        image.putpixel((i, j), (redValue, 0, 0, 255))

            image = smoothImage(image, 2)

            for i in range(width):
                for j in range(width):
                    if i < width and j < width:
                        index = j + (width * i)

                        greenValue = greens_split[c][index]

                        redValue = image.getpixel((i, j))[0]

                        if redValue < 2:
                            greenValue = 0

                        if greenValue < 0:
                            image.putpixel((i, j), (0, 0, 0, 255))
                        else:
                            image.putpixel((i, j), (redValue, greenValue, 0, 255))


            image = ImageOps.mirror(image)
            image = image.rotate(270)

            splitFileName = fileName.replace(".png", "%s.png" % c)

            image.save(splitFileName)


    def generateSingleMap(self, pixels, width, mapFileName):
        image = Image.new('RGBA', (width, width))

        for i in range(width):
            for j in range(width):
                if i < width and j < width:
                    index = j + (width * i)

                    redValue = int(pixels[index][0])
                    if redValue < 0:
                        image.putpixel((i, j), (0, 0, 0, 255))
                    else:
                        image.putpixel((i, j), (redValue, 0, 0, 255))

        image = smoothImage(image, 2)

        for i in range(width):
            for j in range(width):
                if i < width and j < width:
                    index = j + (width * i)

                    greenValue = int(pixels[index][1])

                    redValue = image.getpixel((i,j))[0]

                    if redValue < 2:
                        greenValue = 0

                    if greenValue < 0:
                        image.putpixel((i, j), (0, 0, 0, 255))
                    else:
                        image.putpixel((i, j), (redValue, greenValue, 0, 255))

        image = ImageOps.mirror(image)
        image = image.rotate(270)
        image.save(mapFileName)

        return image

    def generatePixels(self, heights, width, maxHeight, minHeight, buildup, cityAdjust):
        heightDiff = maxHeight - minHeight;
        scaleFactor = 1.0

        scaling_mode = None

        pixel_scale = 5.8823529411764

        logger.debug(heightDiff)
        if heightDiff > 255:
            logger.debug("Height Diff is more than 255, so we need to scale properly")
            scaleFactor = (heightDiff / 255)

        logger.debug("Current height scale factor: %s" % scaleFactor)
        mean_height = np.mean(heights)
        logger.debug("Mean height: %s" % mean_height)

        logger.debug("Average height: %s" % np.average(heights))

        # exit()
        image = Image.new('RGBA', (width, width))

        maxGreen = 0
        minGreen = 300

        if len(buildup) > 0:
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
            while gVal != 255 and gVal <= 255 and gVal > 0:
                gVal = round(maxGreen * cityScale, 0)
                cityScale = round(cityScale + .01, 3)

            logger.debug("New city Scale Factor (scaling to 255): %s" % cityScale)

            # Reseting min/max for sanity checking
            maxGreen = 0
            minGreen = 300
        else:
            logger.debug("Not enough build up data.")


        red_pixels = []
        green_pixels = []

        for i in range(width):
            for j in range(width):
                if i < width and j < width:
                    index = j + (width * i)

                    belowWater = False
                    height = heights[index]

                    if height > 6000:
                        height = 6000


                    height = heights[index] + 3

                    if scaling_mode == "exaggerated":
                        height += .5
                        height_scale = height / mean_height
                        if height_scale > .1:
                            if height_scale > 3:
                                height = height * (height_scale * .3)
                            elif height_scale > 2.5:
                                height = height * (height_scale * .4)
                            elif height_scale > 2:
                                height = height * (height_scale * .5)
                            elif height_scale > 1.5:
                                height = height * (height_scale * 1.1)
                            elif height_scale < .4:
                                height = height / (height_scale * 1.2)
                            elif height_scale < .2:
                                height = height / (height_scale * 1.3)
                            elif height_scale < .1:
                                height = height / (height_scale * 1.4)


                    if not self.settings.disableCityPaint and len(buildup) > 0:
                        afterCityAdjust = buildup[index] - cityAdjust

                        if afterCityAdjust < 0:
                            buildupValue = ((buildup[index] - cityAdjust) / cityScale)
                        else:
                            buildupValue = ((buildup[index] - cityAdjust) * cityScale)

                        greenValue = buildupValue
                        if greenValue < 0:
                            greenValue = 0

                        if greenValue > maxGreen:
                            maxGreen = greenValue

                        if greenValue < minGreen:
                            minGreen = greenValue

                    else:
                        greenValue = 0


                    if height > 6000:
                        height = 6000

                    if height < 10:
                        height = height * 5
                    elif height < 20:
                        height = height * 4
                    elif height < 30:
                        height = height * 3
                    elif height < 40:
                        height = height * 2
                    elif height < 50:
                        height = height * 1.8
                    elif height < 60:
                        height = height * 1.7
                    elif height < 70:
                        height = height * 1.6
                    elif height < 80:
                        height = height * 1.5
                    elif height < 90:
                        height = height * 1.25

                    if greenValue > 20:
                        if height < 20:
                            greenValue = 0
                        elif height < 30:
                            height = 30

                    redValue = height/pixel_scale



                    red_pixels.append(redValue)

                    green_pixels.append(greenValue)

        pixels = []
        for i in range(width):
            for j in range(width):
                if i < width and j < width:
                    index = j + (width * i)
                    pixels.append((red_pixels[index], green_pixels[index], 0, 0))

        return pixels

    def getOpenElevationBoundingBox(self, points):
        logger.debug("Getting Terrain Data")

        return elevationData.getElevationData(points, self.settings.forceRefresh)


    def getTiles(self, _points, _zoom):
        tiles = []

        ## find the tile which contains each point
        for point in _points:
            tiles.append(tileForMeters(latLngToMeters({'x': point[1], 'y': point[0]}), _zoom))

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
        ## download tiles
        logger.debug("Getting %i tiles at zoom level %i" % (len(tiles), _zoom))
        logger.debug("Zoom to meters: %s" % tile_to_meters(_zoom))
        for tile in tiles:
            tilename = "%i-%i-%i.json" % (_zoom, tile['x'], tile['y'])

            tilename = os.path.join("tiles", tilename)

            if os.path.isfile(tilename):
                logger.debug("Tile already cached")
                with open(tilename, 'r') as infile:
                    j = json.load(infile)
            else:
                logger.debug("Tile not cached, downloading from nextzen")
                r = requests.get(
                    "https://tile.nextzen.org/tilezen/vector/v1/all/%i/%i/%i.json?api_key=%s" % (
                        _zoom, tile['x'], tile['y'], self.settings.nextzenAPIKey), headers=r_headers)
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

        if len(highway_elevation) > 0:
            try:
                highway_elevation_new, minHeight, maxHeight = elevationData.getElevationData(highway_elevation, self.settings.forceRefresh)
            except Exception as err:
                raise ValueError("Error getting terrain data for highways: %s" % err)
        else:
            highway_elevation_new = 0

        if len(highway_elevation_new) > 0:
            # Re-adding the new heights to the highway data, by aligning the lists.
            highwayPoints = 0
            for h_i, highway in enumerate(highway_data):
                for p_i, point in enumerate(highway_data[highway]):
                    highway_data[highway][p_i]['height'] = highway_elevation_new[highwayPoints]
                    highwayPoints += 1
        else:
            highway_data = []

        if len(airports) > 0:
            logger.debug("Getting airport elevation data")
            airport_elevation = []
            for airport in airports:
                airport_elevation.append(airport['cords'])
            try:
                airport_elevation, minHeight, maxHeight = elevationData.getElevationData(airport_elevation, self.settings.forceRefresh)
            except Exception as err:
                raise ValueError("Error getting terrain data for airports: %s" % err)

            if len(airport_elevation) > 0:
                for i, airport in enumerate(airports):
                    airports[i]['height'] = airport_elevation[i]
            else:
                airports = []

        return highway_data, majorRoads, tileData, airports

