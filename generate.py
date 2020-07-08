import requests

import time
from PIL import Image, ImageOps

import os
import pickle
import math
from osgeo import gdal
from pyproj import Transformer
import hashlib
from osgeo import osr
import json
import numpy as np
from scipy.spatial.distance import pdist, squareform
import configparser
import logging

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


outSpatialRef = osr.SpatialReference()
outSpatialRef.SetFromUserInput('ESRI:54009')



class Vector3D:
    def __init__(self, x, y, z):
        self.x = x  # lat
        self.y = y  # Lon
        self.z = z  # Alt

    def __str__(self):
        return "%s, %s, %s" % (self.x, self.y, self.z)


def cordToVector(lat, lon, height=0):
    return Vector3D(lat, lon, height)

def convertGlobaltoWorldPoint(vector3):
    vector = vector3

    return vector

def convertToWorldPoint(vector, mapLatitude, mapLongitude):
    # From BD's conversion code in VTMapManager
    num = vector.x - mapLatitude
    num = num * 111319.9

    num2 = abs(math.cos(vector.x * 0.01745329238474369) * 111319.9)

    result = convertGlobaltoWorldPoint(Vector3D((vector.y - mapLongitude) * num2, vector.z, num))
    return result


def gpsTupletoUnityWorldPoint(each, latOffset, longOffset, height=0):
    #print(each)
    lat = float(each[0])
    lon = float(each[1])
    vector = cordToVector(lat + latOffset, lon + longOffset, height)
    converted = convertToWorldPoint(vector, 0, 0)
    return converted

def find_gps_sorted(xy_coord, k0=0):


    """Find iteratively a continuous path from the given points xy_coord,
      starting by the point indexes by k0 """
    # https://stackoverflow.com/a/31458546
    N = len(xy_coord)

    distance_matrix = squareform(pdist(xy_coord, metric='euclidean'))
    mask = np.ones(N, dtype='bool')
    sorted_order = np.zeros(N, dtype=np.int)
    indices = np.arange(N)

    i = 0
    k = k0
    while True:
        sorted_order[i] = k
        mask[k] = False

        dist_k = distance_matrix[k][mask]
        indices_k = indices[mask]

        if not len(indices_k):
            break

        # find next unused closest point
        k = indices_k[np.argmin(dist_k)]
        # you could also add some criterion here on the direction between consecutive points etc.
        i += 1
    return sorted_order, xy_coord[sorted_order]

##
## HELPER FUNCTIONS
##

tile_size = 256
half_circumference_meters = 20037508.342789244;


# Convert lat-lng to mercator meters
def latLngToMeters(coords):
    y = float(coords['y'])
    x = float(coords['x'])
    # Latitude
    y = math.log(math.tan(y * math.pi / 360 + math.pi / 4)) / math.pi
    y *= half_circumference_meters

    # Longitude
    x *= half_circumference_meters / 180;

    return {"x": x, "y": y}


def meterstolatlong(meters):
    y = float(meters['y'])
    x = float(meters['x'])

    # Latitude
    y = math.log(math.tan(y / math.pi * 360 - math.pi * 4)) * math.pi
    y *= half_circumference_meters

    # Longitude
    x *= half_circumference_meters * 180;

    return {"x": x, "y": y}


# convert from tile-space coords to meters, depending on zoom
def tile_to_meters(zoom):
    return 40075016.68557849 / pow(2, zoom)


# Given a point in mercator meters and a zoom level, return the tile X/Y/Z that the point lies in
def tileForMeters(coords, zoom):
    y = float(coords['y'])
    x = float(coords['x'])
    return {
        "x": math.floor((x + half_circumference_meters) / (half_circumference_meters * 2 / pow(2, zoom))),
        "y": math.floor((-y + half_circumference_meters) / (half_circumference_meters * 2 / pow(2, zoom))),
        "z": zoom
    }


# Convert tile location to mercator meters - multiply by pixels per tile, then by meters per pixel, adjust for map origin
def metersForTile(tile):
    return {
        "x": tile['x'] * half_circumference_meters * 2 / pow(2, tile.z) - half_circumference_meters,
        "y": -(tile['y'] * half_circumference_meters * 2 / pow(2, tile.z) - half_circumference_meters)
    }


def getPoints(subDivisions, southLat, westLong, eastLong, distanceBetween):
    logger.debug("Getting points between lat/lons")
    points = []
    for i in range(subDivisions):
        lat = southLat + (distanceBetween * i)
        long1 = westLong
        long2 = eastLong

        #
        # Get the distance between the left and right points, and found how many subdivisions fit in it
        hopValue = (long2 - long1) / subDivisions
        long3 = long1
        # print("Getting Build Up Data")
        for x in range(subDivisions):
            long3 += hopValue
            points.append({'y': lat, 'x': long3})
    return points


def offsetHeights(heights, amount):
    newHeights = []
    for height in heights:
        newHeights.append(height - amount)

    return newHeights

def genHash(plaintext):

    dataHash = hashlib.sha1(plaintext.encode('utf-8')).hexdigest()
    return dataHash

transformer = Transformer.from_crs("epsg:4326", "esri:54009")


class ghsDataParser:
    ghsFile = False

    def __init__(self, ghsFile="GHS_BUILT_LDS2014_GLOBE_R2018A_54009_1K_V2_0.tif"):
        self.ghsFile = ghsFile
        self.loadBuildupData()


    def loadBuildupData(self):
        logger.debug("Loading GHS-BUILT data")
        dataset = gdal.Open(self.ghsFile)

        band = dataset.GetRasterBand(1)

        cols = dataset.RasterXSize
        rows = dataset.RasterYSize

        transform = dataset.GetGeoTransform()

        self.xOrigin = transform[0]
        self.yOrigin = transform[3]
        self.pixelWidth = transform[1]
        self.pixelHeight = -transform[5]

        self.data = band.ReadAsArray(0, 0, cols, rows)


    def getBuildupData(self, subDivisions, southLat, distanceBetween, westLong, eastLong):
        logger.debug("Getting GHS build up data!")
        minBuildUp = 1000
        maxBuildUp = 0

        buildup_list = []
        for i in range(subDivisions):
            lat = southLat + (distanceBetween * i)
            long1 = westLong
            long2 = eastLong

            #
            # Get the distance between the left and right points, and found how many subdivisions fit in it
            hopValue = (long2 - long1) / subDivisions
            long3 = long1
            # print("Getting Build Up Data")
            for x in range(subDivisions):
                long3 += hopValue

                # This is each point along the latitude
                # print("Converted lat/long: %s, %s" % (lat, long3))
                # print("Orig long: %s" % long2)
                # print(transformer.transform(lat,long3))
                conv_lat, conv_lon = transformer.transform(lat, long3)
                points_list = [(conv_lat, conv_lon)]

                for point in points_list:
                    col = int((point[0] - self.xOrigin) / self.pixelWidth)
                    row = int((self.yOrigin - point[1]) / self.pixelHeight)
                    buildup_data = self.data[row][col]
                    buildup_data = round(int(buildup_data), 2)
                    if buildup_data < minBuildUp:
                        minBuildUp = buildup_data
                    if buildup_data > maxBuildUp:
                        maxBuildUp = buildup_data
                    buildup_list.append(buildup_data)

        return buildup_list, maxBuildUp, minBuildUp


class vtolMapper:


    def __init__(self, bingKey, ghsParser = None):
        logger.debug("Initializing vtolMapper")

        if not os.path.isdir("dataSets"):
            os.mkdir("dataSets")

        self.bingAPIKey = bingKey

        if not ghsParser:
            self.ghsParser = ghsDataParser()



    def get_cached(self, dataHash):
        getData = False
        heightData = False
        if os.path.isdir("dataSets"):
            if os.path.isfile(os.path.join("dataSets", "%s.p" % dataHash)):
                if not forceRefresh:
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


    def saveVTM(self):
        raise NotImplemented

    def generateAirportConfig(self):
        pass

    def generate(self, centerLong, centerLat, forceBelowZero = True, forceRefresh = False, rebuildCity=True, disableCityPaint=False, cityAdjust=10, resolution=512, offsetAmount=15, mapWidth=192000, minHighwayLength=5):

        widthInDegrees = mapWidth / 111111

        westLong = centerLong - (widthInDegrees / 2)
        northLat = centerLat + (widthInDegrees / 2)

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


        heightMapResolution = mapWidth / resolution
        logger.debug("Meters per pixel: %s" % heightMapResolution)

        distanceBetween = (northLat - southLat) / (resolution - 1)


        points = getPoints(resolution, southLat, westLong, eastLong, distanceBetween)

        highways, majorRoads, tileData, airports = self.getTiles(points, 8)


        dataHash = self.genDataHash(centerLong, centerLat, mapWidth)


        i = 0

        highwaySegments = []
        heightData = {}

        cachedData = self.get_cached(dataHash)

        if rebuildCity:
            buildup_list, maxBuildup, minBuildup = self.ghsParser.getBuildupData(resolution, southLat, distanceBetween, westLong,
                                                                  eastLong)
            logger.debug(maxBuildup)
            logger.debug(minBuildup)
        elif cachedData:
            buildup_list, maxBuildup, minBuildup = cachedData['builduplist'], cachedData['maxBuildup'], cachedData['minBuildup']
        else:
            buildup_list, maxBuildup, minBuildup = self.ghsParser.getBuildupData(resolution, southLat, distanceBetween, westLong,
                                                                  eastLong)
            logger.debug(maxBuildup)
            logger.debug(minBuildup)


        if cachedData and not forceRefresh:
            heights, minHeight, maxHeight = cachedData['heights'], cachedData['minHeight'], cachedData['maxHeight']
        else:
            heights, minHeight, maxHeight = self.getBingTerrainData(resolution, southLat, distanceBetween, westLong,
                                                           eastLong)


        logger.debug(len(buildup_list))
        logger.debug(len(heights))

        heightData = {"heights": heights, "minHeight": minHeight, "maxHeight": maxHeight,
                      "builduplist": buildup_list,
                      "minBuildup": minBuildup, "maxBuildup": maxBuildup, 'centerLat': centerLat,
                      'centerLong': centerLong, 'mapWidth': mapWidth}

        pickle.dump(heightData, open(os.path.join("dataSets", "%s.p" % dataHash), "wb"))

        heights = heightData['heights']
        minHeight = heightData['minHeight']
        maxHeight = heightData['maxHeight']

        logger.debug("Min Height: %s" % minHeight)
        logger.debug("Max Height: %s" % maxHeight)

        vtolvr_heightoffset = 0

        if forceBelowZero:

            vtolvr_heightoffset = abs(offsetAmount - minHeight)
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
                #logger.debug("Subtracting height offset (%s) from highway height (%s) - %s" % (vtolvr_heightoffset, height, height - vtolvr_heightoffset))
                highwayHeightData["%s,%s" % (lat,lon)] = {"lat": lat, "lon": lon, "height": height - vtolvr_heightoffset}

            #logger.debug("Sorting GPS points")
            points = np.array(points)


            if len(points) > 0 and len(points) > minHighwayLength:
                sorted_order, xy_coord_sorted = find_gps_sorted(points)

                first = None
                cordList = xy_coord_sorted.tolist()


                cordlist_with_height = []
                # Once again re-aligning heights to coordinates
                for point in cordList:
                    cordlist_with_height.append(highwayHeightData["%s,%s" % (point[0], point[1])])

                #logger.debug("Got %s sorted points " % len(cordList))

                cordList = cordlist_with_height

                while len(cordList) > 1:

                    if first == None:
                        each_cord = cordList.pop()
                        first = str(gpsTupletoUnityWorldPoint((each_cord['lat'], each_cord['lon']), latOffset, longOffset, each_cord['height']))
                        ps = False
                    else:
                        first = highwaySegments[i - 1]['e']
                        ps = highwaySegments[i - 1]['id']

                    each_cord = cordList.pop()
                    mid = str(gpsTupletoUnityWorldPoint((each_cord['lat'],each_cord['lon']), latOffset, longOffset, each_cord['height']))

                    last = str(gpsTupletoUnityWorldPoint((each_cord['lat'],each_cord['lon']), latOffset, longOffset, each_cord['height']))
                    if len(cordList) != 0:
                        ns = i + 1
                    else:
                        ns = False
                    segment = {"id": i, "type": 0, "bridge": False, "length": 100, "s": first, "m": mid, "e": last,
                               'ns': ns, 'ps': ps}
                    highwaySegments.append(segment)
                    i += 1
            else:
                logger.warning("Highway %s has no points or highway points (%s) is below the minimum length (%s)." % (highway, len(points), minHighwayLength))

        logger.debug("Tile Count: %s" % len(tileData))
        logger.debug("Highway Count: %s" % len(highways))
        logger.debug("Major Road Count: %s" % len(majorRoads))
        logger.debug("Total Lat/Lon Points: %s" % len(points))

        prefab_id = 0
        with open(vtmFile, 'a') as prefabFile:
            prefabFile.write("""	StaticPrefabs
        {\n""")
            for airport in airports:
                gamepos = gpsTupletoUnityWorldPoint(airport['cords'], 0, 0, airport['height'])

                prefabFile.write("""		StaticPrefab
        	{\n""")
                prefabFile.write("""			prefab = airbase1\n""")
                prefabFile.write("""			id = %s\n""" % prefab_id)
                prefabFile.write("""			globalPos = (%s)\n""" % str(gamepos))
                prefabFile.write("""			rotation = (0, 311.5949, 0)\n""")
                prefabFile.write("""			grid = (0,0)\n""")
                prefabFile.write("""			tSpacePos = (0, 0, 0)\n""")
                prefabFile.write("""			terrainToLocalMatrix = 0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;1;\n""")
                prefabFile.write("""			baseName = %s\n""" % airport['name'])
                prefabFile.write("""		}\n""")
                prefab_id += 1
            prefabFile.write("""	}\n""")
        #
        # with open(vtmFile, 'a') as roadFile:
        #     roadFile.write("""	BezierRoads
        # {
        # 	Chunk
        # 	{
        # 		grid = (0,0)\n""")
        #     for segment in highwaySegments:
        #         roadFile.write("""			Segment
        # 		{\n""")
        #         roadFile.write("""				id = %s\n""" % segment['id'])
        #         roadFile.write("""				type = %s\n""" % segment['type'])
        #         roadFile.write("""				bridge = %s\n""" % segment['bridge'])
        #         roadFile.write("""				length = %s\n""" % segment['length'])
        #
        #         roadFile.write("""				s = (%s)\n""" % segment['s'])
        #         roadFile.write("""				m = (%s)\n""" % segment['m'])
        #         roadFile.write("""				e = (%s)\n""" % segment['e'])
        #
        #         if segment['ns']:
        #             roadFile.write("""				ns = %s\n""" % segment['ns'])
        #
        #         if segment['ps']:
        #             roadFile.write("""				ps = %s\n""" % segment['ps'])
        #
        #         roadFile.write("""			}\n""")
        #
        #     roadFile.write("""		}\n""")
        #     roadFile.write("""	}\n""")


        minHeight = -80
        maxHeight = 4000

        buildups = heightData['builduplist']

        logger.debug("Got %s heights" % len(heights))

        logger.debug("Min Height: %s" % minHeight)
        logger.debug("Max Height: %s" % maxHeight)

        logger.debug("Creating Height Map")
        self.createHeightMapFile(heights, resolution, maxHeight, minHeight, buildups, cityAdjust)


    def createHeightMapFile(self, heights, width, maxHeight, minHeight, buildup, cityAdjust):
        heightDiff = maxHeight - minHeight;
        scaleFactor = 1.0

        logger.debug(heightDiff)
        if heightDiff > 255:
            logger.debug("Height Diff is more than 255, so we need to scale properly")
            scaleFactor = (255/heightDiff)

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

                    if disableCityPaint:
                        greenValue = 0

                    if redValue < 0 and greenValue < 0:
                        image.putpixel((i, j), (0,0,0,255))
                    else:
                        image.putpixel((i, j), (redValue, greenValue, 0, 255))

        image = ImageOps.mirror(image)
        image = ImageOps.flip(image)
        image = image.transpose(Image.ROTATE_270)

        image.save("height.png", "PNG")
        image.show()


    def getBingTerrainDataPolyLine(self, points, resolution=30):
        # List of tuples containing GPS points in (lat,lon) format
        logger.debug("Getting %s elevation points from Bing" % len(points))
        requestUrlTemplate = "http://dev.virtualearth.net/REST/v1/Elevation/List?key=%s" % bingAPIKey
        # requestUrlTemplate = "http://dev.virtualearth.net/REST/v1/Elevation/Polyline?points={0}&samples={1}&key={2}"
        heights = []

        point_string = ""
        for point in points:
            point_string += "%s,%s," % (point[0], point[1])


        point_string = point_string.rstrip(",")

        postData = {"points": point_string, 'samples': resolution}
        #postData = "points=%s" % point_string

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
            raise ValueError("No elevations returned by Bing Terrain Poly Line")


        return heights

    def getBingTerrainData(self, subDivisions, southLat, distanceBetween, westLong, eastLong):
        requestUrlTemplate = "http://dev.virtualearth.net/REST/v1/Elevation/Polyline?points={0},{1},{0},{2}&samples={3}&key={4}"
        heights = []
        maxHeight = 0
        minHeight = 29000
        logger.debug("Getting Bing Terrain Data")
        for i in range(subDivisions):
            lat = southLat + (distanceBetween * i)
            long1 = westLong
            long2 = eastLong
            url = requestUrlTemplate.format(lat, long1, long2, subDivisions, self.bingAPIKey)
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

        # for the_file in os.listdir(folder):
        #     file_path = os.path.join(folder, the_file)
        #     try:
        #         if os.path.isfile(file_path):
        #             os.unlink(file_path)
        #     except Exception, e:
        #         print e

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
                    "https://tile.nextzen.org/tilezen/vector/v1/all/%i/%i/%i.json?api_key=tsINU1vsQnKLU1jjCimtVw" % (
                    _zoom, tile['x'], tile['y']))
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
                                    # print("%s,%s,%s,%s" % (sublist[1], sublist[0], "red", "circle"))
                            else:
                                cord_list.append([cord[1], cord[0]])
                                # print("%s,%s,%s,%s" % (cord[1], cord[0], "red", "circle"))


                    lat_list = []
                    lon_list = []

                    for each in cord_list:
                        lat_list.append(each[0])
                        lon_list.append(each[1])

                    center_lat = sum(lat_list) / len(lat_list)
                    center_lon = sum(lon_list) / len(lon_list)

                    airport_location = [center_lat, center_lon]

                    #logger.debug("%s,%s,%s,%s" % (center_lat, center_lon, "red", "circle"))


                        # if isinstance(cords, float):
                        #     airport_location.append("%f,%f" % (landuse['geometry']['coordinates'][1], landuse['geometry']['coordinates'][0]))
                        #     break
                        # print(cords)
                        # for cord in cords:
                        #     airport_location.append("%f,%f" % (cord[1], cord[0]))

                    airports.append({"name": name, "cords": airport_location})
                    logger.debug("AIRPORT - %s" % {"name": name, "cords": airport_location})

            majorroad_data = []

            roadCount = 0
            for road in j['roads']['features']:
                roadCount += 1
                # print(road['properties']['kind'])
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
                            # print("List")
                            # print(cords)
                            for cord in cords:

                                road_data.append({"lat": cord[1], "lon": cord[0], "height": 0})
                        else:
                            # print("not list")
                            # print(cords)
                            road_data.append({"lat": cords[1], "lon": cords[0], "height": 0})
                    # if roadname != "a90":
                    #     continue
                    if roadname in highway_data:
                        highway_data[roadname] += road_data
                    else:
                        highway_data[roadname] = []
                        highway_data[roadname] = road_data
                    #highway_data.append(road_data)
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
                exit()
            for point in highway_data[highway]:

                highway_elevation.append((point['lat'], point['lon']))


        if len(highway_elevation) == 0:
            logger.warning("No highways found in tile")
            exit()


        highway_elevation_new = self.getBingTerrainDataPolyLine(highway_elevation)

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

            airport_elevation = self.getBingTerrainDataPolyLine(airport_elevation)
            for i, airport in enumerate(airports):
                airports[i]['height'] = airport_elevation[i]

        return highway_data, majorRoads, tileData, airports


if __name__ == "__main__":

    forceBelowZero = True
    getData = False
    forceRefresh = False

    rebuildCity = True
    disableCityPaint = False

    # centerLong = 12.495228
    # centerLat = 41.891866

    # NYC
    centerLong = -73.972005
    centerLat = 40.773345

    # Meters
    mapWidth = 192000

    # Height Offset
    offsetAmount = 15

    # HM Resolution
    #subDivisions = 512

    cityAdjust = 20

    bingAPIKey = config['BingAPI']['key']

    ghsFile = "GHS_BUILT_LDS2014_GLOBE_R2018A_54009_1K_V2_0.tif"

    mapper = vtolMapper(bingAPIKey)

    vtmFile = 'test.vtm'

    mapper.generate(centerLong, centerLat, forceBelowZero=True, forceRefresh=False, rebuildCity=True, disableCityPaint=False, cityAdjust=50, resolution=512, offsetAmount=15, mapWidth=192000)


