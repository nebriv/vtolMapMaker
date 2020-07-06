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


# TODO: Cleanup Code, road height, city density


config = configparser.ConfigParser()
config.read('config.conf')


outSpatialRef = osr.SpatialReference()
outSpatialRef.SetFromUserInput('ESRI:54009')

forceBelowZero = True
getData = False
forceRefresh = False

rebuildCity = True
disableCityPaint = False

centerLong = 12.495228
centerLat = 41.891866

#NYC
# centerLong = -73.972005
# centerLat = 40.773345

# Meters
mapWidth = 192000

# Height Offset
offsetAmount = 15

# HM Resolution
subDivisions = 512

cityAdjust = 20

bingAPIKey = config['BingAPI']['key']

vtmFile = 'test.vtm'


dataHashString = "%s,%s,%s" % (round(centerLong, 2), round(centerLat, 2), mapWidth)
dataHash = hashlib.sha1(dataHashString.encode('utf-8')).hexdigest()


if os.path.isdir("dataSets"):
    if os.path.isfile(os.path.join("dataSets", "%s.p" % dataHash)):
        if not forceRefresh:
            print("Found cached data!")
            heightData = pickle.load(open(os.path.join("dataSets", "%s.p" % dataHash), 'rb'))
        else:
            print("Found the data, but forcing a refresh")
            getData = True
    else:
        print("Data set for given params does not exist")
        getData = True
else:
    print("dataSets folder does not exist")
    getData = True


def createHeightMapFile(heights, width, maxHeight, minHeight, buildup):
    heightDiff = maxHeight - minHeight;
    scaleFactor = 1.0

    print(heightDiff)
    if heightDiff > 255:
        print("Height Diff is more than 255, so we need to scale properly")
        scaleFactor = (255/heightDiff)

    print("Current height scale factor: %s" % scaleFactor)

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
    print("Finding new city scale factor")
    gVal = maxGreen
    cityScale = 1.1
    while gVal != 255 and gVal <= 255:
        gVal = round(maxGreen * cityScale, 0)
        cityScale = round(cityScale + .01, 3)

    print("New city Scale Factor (scaling to 255): %s" % cityScale)

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

def offsetHeights(heights, amount):
    newHeights = []
    for height in heights:
        newHeights.append(height - amount)

    return newHeights


print("Processing Data")


def getBuildupData(subDivisions, southLat, distanceBetween, westLong, eastLong):
    print("Loading GHS-BUILT data")
    dataset = gdal.Open("GHS_BUILT_LDS2014_GLOBE_R2018A_54009_1K_V2_0.tif")

    band = dataset.GetRasterBand(1)

    cols = dataset.RasterXSize
    rows = dataset.RasterYSize

    transform = dataset.GetGeoTransform()

    xOrigin = transform[0]
    yOrigin = transform[3]
    pixelWidth = transform[1]
    pixelHeight = -transform[5]


    data = band.ReadAsArray(0, 0, cols, rows)

    print("Getting GHS build up data!")
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
        #print("Getting Build Up Data")
        for x in range(subDivisions):
            long3 += hopValue

            # This is each point along the latitude
            # print("Converted lat/long: %s, %s" % (lat, long3))
            # print("Orig long: %s" % long2)
            # print(transformer.transform(lat,long3))
            conv_lat, conv_lon = transformer.transform(lat, long3)
            points_list = [(conv_lat, conv_lon)]

            for point in points_list:
                col = int((point[0] - xOrigin) / pixelWidth)
                row = int((yOrigin - point[1]) / pixelHeight)
                buildup_data = data[row][col]
                buildup_data = round(int(buildup_data), 2)
                if buildup_data < minBuildUp:
                    minBuildUp = buildup_data
                if buildup_data > maxBuildUp:
                    maxBuildUp = buildup_data
                buildup_list.append(buildup_data)

    return buildup_list, maxBuildUp, minBuildUp

def getBingTerrainData(subDivisions, southLat, distanceBetween, westLong, eastLong):
    requestUrlTemplate = "http://dev.virtualearth.net/REST/v1/Elevation/Polyline?points={0},{1},{0},{2}&samples={3}&key={4}"
    heights = []
    maxHeight = 0
    minHeight = 29000
    print("Getting Bing Terrain Data")
    for i in range(subDivisions):
        lat = southLat + (distanceBetween * i)
        long1 = westLong
        long2 = eastLong
        url = requestUrlTemplate.format(lat, long1, long2, subDivisions, bingAPIKey)
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

            print("Got a bad response, missing data?")
            print(response.status_code)
            print(response.text)
            print(response.json())
            print("Trying again")
            time.sleep(2)

        if i % 20 == 0:
            print("i: %s, HMax: %s, HMin: %s" % (i, maxHeight, minHeight))
        time.sleep(.1)
    return heights, minHeight, maxHeight


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

def getPoints(subDivisions, southLat,westLong,eastLong, distanceBetween):
    print("Getting Points")
    points = []
    for i in range(subDivisions):
        lat = southLat + (distanceBetween * i)
        long1 = westLong
        long2 = eastLong

        #
        # Get the distance between the left and right points, and found how many subdivisions fit in it
        hopValue = (long2 - long1) / subDivisions
        long3 = long1
        #print("Getting Build Up Data")
        for x in range(subDivisions):
            long3 += hopValue
            points.append({'y': lat, 'x': long3})
    return points


def getTiles(_points, _zoom):
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
    print("tiles:" + str(tiles))
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
    print("\nDownloading %i tiles at zoom level %i" % (len(tiles), _zoom))
    print("Zoom to meters: %s" % tile_to_meters(_zoom))
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
        print("Error: no tiles")
        exit()
    count = 0
    highway_data = {}

    airports = []

    for tile in tiles:
        tilename = "%i-%i-%i.json" % (_zoom, tile['x'], tile['y'])
        r = requests.get(
            "https://tile.nextzen.org/tilezen/vector/v1/all/%i/%i/%i.json?api_key=tsINU1vsQnKLU1jjCimtVw" % (
            _zoom, tile['x'], tile['y']))
        j = json.loads(r.text)

        # extract only buildings layer - nextzen vector tile files are collections of geojson objects -
        # doing this turns each file into a valid standalone geojson files -
        # you can replace "buildings" with whichever layer you want
        # j = json.dumps(j["buildings"])


        # for poi in j['pois']['features']:
        #     if poi['properties']['kind'] == "airfield" or poi['properties']['kind'] == "aerodrome":
        #         airport_location = []
        #         if "name" in poi['properties']:
        #             name = poi['properties']['name']
        #         else:
        #             name = "Unknown Name"
        #
        #         for cords in poi['geometry']['coordinates']:
        #             if isinstance(cords, float):
        #                 airport_location.append("%f,%f" % (poi['geometry']['coordinates'][1], poi['geometry']['coordinates'][0]))
        #                 break
        #             print(cords)
        #             for cord in cords:
        #                 airport_location.append("%f,%f" % (cord[1], cord[0]))
        #
        #         airports.append({"name": name, "cords": airport_location})

        print("Landuse")
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
                        print(cord)
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

                print("%s,%s,%s,%s" % (center_lat, center_lon, "red", "circle"))


                    # if isinstance(cords, float):
                    #     airport_location.append("%f,%f" % (landuse['geometry']['coordinates'][1], landuse['geometry']['coordinates'][0]))
                    #     break
                    # print(cords)
                    # for cord in cords:
                    #     airport_location.append("%f,%f" % (cord[1], cord[0]))

                airports.append({"name": name, "cords": airport_location})
                print("AIRPORT")
                print({"name": name, "cords": airport_location})


        majorroad_data = []

        for road in j['roads']['features']:
            # print(road['properties']['kind'])
            if road['properties']['kind'] == "highway":
                if "shield_text" in road['properties']:
                    roadname = road['properties']['shield_text'].lower()
                else:
                    roadname = "NoName"


                road_data = []
                for cords in road['geometry']['coordinates']:
                    if type(cords[0]) is not float:
                        # print("List")
                        # print(cords)
                        for cord in cords:
                            road_data.append("%f,%f" % (cord[1], cord[0]))
                    else:
                        # print("not list")
                        # print(cords)
                        road_data.append("%f,%f" % (cords[1], cords[0]))
                # if roadname != "a90":
                #     continue
                if roadname in highway_data:
                    highway_data[roadname].append(road_data)
                else:
                    highway_data[roadname] = []
                    highway_data[roadname].append(road_data)
                #highway_data.append(road_data)
            if road['properties']['kind'] == "major_road":

                road_data = []
                for cords in road['geometry']['coordinates']:
                    if type(cords[0]) is not float:
                        # print("List")
                        # print(cords)
                        for cord in cords:
                            road_data.append("%f,%f" % (cord[1], cord[0]))
                    else:
                        # print("not list")
                        # print(cords)
                        road_data.append("%f,%f" % (cords[1], cords[0]))
                majorroad_data.append(road_data)



        majorRoads += majorroad_data

        tileData.append(json.dumps(j))

        # use this jumps() command instead for the original feature collection with all the data
        j = json.dumps(j)

        count += 1
    # print(highway_data)
    # for each in highway_data:
    #     print(each)
    #     for entry in highway_data[each]:
    #         for road in entry:
    #             print(road,",red,circle")
    #
    # exit()

    return highway_data, majorRoads, tileData, airports

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

# lat = 41.8336
# lon = 12.5877
# #
# vector = cordToVector(lat, lon, 100)
# print(vector)
# print(convertToWorldPoint(vector, 0, 0))

#
# lat = 41.8339
# lon = 12.5879
#
# vector = cordToVector(lat, lon)
# print(vector)
# print(convertToWorldPoint(vector, 0,0))
#
# lat = 41.8368
# lon = 12.5899
#
# vector = cordToVector(lat,lon)
# print(vector)
# print(convertToWorldPoint(vector, 0,0))

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

if getData or rebuildCity:
    widthInDegrees = mapWidth / 111111

    westLong = centerLong - (widthInDegrees / 2)
    northLat = centerLat + (widthInDegrees / 2)

    print("Top Left Corner")
    print(northLat, westLong)




    eastLong = westLong + widthInDegrees
    southLat = northLat - widthInDegrees
    print("Bottom Left Corner")
    print(southLat, westLong)

    print(0 - southLat, 0 - westLong)

    latOffset = 0 - southLat
    longOffset = 0 - westLong

    print("Latitude Offset: %s" % latOffset)
    print("Longitude Offset: %s" % longOffset)


    print("Bottom Right Corner")
    print(southLat, eastLong)

    heightMapResolution = mapWidth / subDivisions
    print("Meters per pixel: %s" % heightMapResolution)

    distanceBetween = (northLat - southLat) / (subDivisions - 1)

    transformer = Transformer.from_crs("epsg:4326", "esri:54009")

    if not os.path.isdir("dataSets"):
        os.mkdir("dataSets")

    points = getPoints(subDivisions, southLat, westLong, eastLong, distanceBetween)


    # for each in points:
    #     print("Lat/lon point")
    #     print(each)
    #     print("Calculated 0,0 Offset")
    #     print(each['y'] + latOffset)
    #     print(each['x'] + longOffset)
    #
    #     vector = Vector3D(each['x'] + longOffset, each['y'] + latOffset, 0)
    #     print("World Point")
    #     convertToWorldPoint(vector, 0, 0)

    highways, majorRoads, tileData, airports = getTiles(points, 8)

    i = 0

    highwaySegments = []

    for highway in highways:
        print("Processing %s highway" % highway)
        points = []
        while len(highways[highway]) > 1:
            cord = highways[highway].pop()
            for point in cord:
                values = point.split(",")
                lat = float(values[0])
                lon = float(values[1])
                points.append([lat, lon])

        print("Sorting GPS points")
        points = np.array(points)


        sorted_order, xy_coord_sorted = find_gps_sorted(points)

        first = None
        cordList = xy_coord_sorted.tolist()

        print("Got %s sorted points " % len(cordList))

        while len(cordList) > 1:

            if first == None:
                first = str(gpsTupletoUnityWorldPoint(cordList.pop(), latOffset, longOffset,100))
                ps = False
            else:
                first = highwaySegments[i - 1]['e']
                ps = highwaySegments[i - 1]['id']

            mid = str(gpsTupletoUnityWorldPoint(cordList.pop(), latOffset, longOffset,100))

            last = str(gpsTupletoUnityWorldPoint(cordList.pop(), latOffset, longOffset, 100))
            if len(cordList) != 0:
                ns = i + 1
            else:
                ns = False
            segment = {"id": i, "type": 0, "bridge": False, "length": 100, "s": first, "m": mid, "e": last, 'ns': ns, 'ps': ps}
            highwaySegments.append(segment)
            #print(segment)
            i += 1




    print("Tile Count: %s" % len(tileData))
    print("Highway Count: %s" % len(highways))
    print("Major Road Count: %s" % len(majorRoads))
    print("Total Lat/Lon Points: %s" % len(points))



    prefab_id = 0
    with open(vtmFile, 'a') as prefabFile:
        prefabFile.write("""	StaticPrefabs
	{\n""")
        for airport in airports:
            gamepos = gpsTupletoUnityWorldPoint(airport['cords'],0,0,15.3730)

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


    with open(vtmFile, 'a') as roadFile:
        roadFile.write("""	BezierRoads
	{
		Chunk
		{
			grid = (0,0)\n""")
        for segment in highwaySegments:
            roadFile.write("""			Segment
			{\n""")
            roadFile.write("""				id = %s\n""" % segment['id'])
            roadFile.write("""				type = %s\n""" % segment['type'])
            roadFile.write("""				bridge = %s\n""" % segment['bridge'])
            roadFile.write("""				length = %s\n""" % segment['length'])

            roadFile.write("""				s = (%s)\n""" % segment['s'])
            roadFile.write("""				m = (%s)\n""" % segment['m'])
            roadFile.write("""				e = (%s)\n""" % segment['e'])

            if segment['ns']:
                roadFile.write("""				ns = %s\n""" % segment['ns'])

            if segment['ps']:
                roadFile.write("""				ps = %s\n""" % segment['ps'])

            roadFile.write("""			}\n""")

        roadFile.write("""		}\n""")
        roadFile.write("""	}\n""")

    if rebuildCity:
        buildup_list, maxBuildup, minBuildup = getBuildupData(subDivisions, southLat, distanceBetween, westLong, eastLong)

        print(maxBuildup)
        print(minBuildup)

    if getData:
        heights, minHeight, maxHeight = getBingTerrainData(subDivisions, southLat, distanceBetween, westLong, eastLong)
    else:
        heights = heightData['heights']
        minHeight = heightData['minHeight']
        maxHeight = heightData['maxHeight']

    print(len(buildup_list))
    print(len(heights))

    heightData = {"heights": heights, "minHeight": minHeight, "maxHeight": maxHeight, "builduplist": buildup_list,
                  "minBuildup": minBuildup, "maxBuildup": maxBuildup, 'centerLat': centerLat, 'centerLong': centerLong, 'mapWidth': mapWidth}


    pickle.dump(heightData, open(os.path.join("dataSets", "%s.p" % dataHash), "wb"))



heights = heightData['heights']
minHeight = heightData['minHeight']
maxHeight = heightData['maxHeight']

print("Min Height: %s" % minHeight)
print("Max Height: %s" % maxHeight)

if forceBelowZero:

    vtolvr_heightoffset = abs(offsetAmount - minHeight)
    print("Height Adjustment: %s" % vtolvr_heightoffset)

    print(heights[0:10])

    c = 0
    for height in heights:
        if height < 0:
            c += 1
    print("number of heights below 0")
    print(c)
    heights = offsetHeights(heights, vtolvr_heightoffset)
    print(heights[0:10])

    c = 0
    for height in heights:
        if height < 0:
            c += 1
    print("number of heights below 0")
    print(c)

minHeight = -80
maxHeight = 4000


buildups = heightData['builduplist']

print("Got %s heights" % len(heights))

print("Min Height: %s" % minHeight)
print("Max Height: %s" % maxHeight)



print("Creating Height Map")
createHeightMapFile(heights, subDivisions, maxHeight, minHeight, buildups)

