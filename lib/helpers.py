import math
import hashlib
import numpy as np
from scipy.spatial.distance import pdist, squareform

import logging

# TODO: Cleanup Code, road height, city density

logger = logging.getLogger(__name__)

handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

logger.addHandler(handler)
logger.setLevel('DEBUG')



class Vector3D:
    def __init__(self, x, y, z):
        self.x = x  # lat
        self.y = y  # Lon
        self.z = z  # Alt

    def __str__(self):
        return "%s, %s, %s" % (self.x, self.y, self.z)




def format_filename(s):
    import string
    """Take a string and return a valid filename constructed from the string.
Uses a whitelist approach: any characters not present in valid_chars are
removed. Also spaces are replaced with underscores.

Note: this method may produce invalid filenames such as ``, `.` or `..`
When I use this method I prepend a date string like '2009_01_15_19_46_32_'
and append a file extension like '.txt', so I avoid the potential of using
an invalid filename.

https://gist.github.com/seanh/93666

"""
    valid_chars = "-_.() %s%s" % (string.ascii_letters, string.digits)
    filename = ''.join(c for c in s if c in valid_chars)
    filename = filename.replace(' ', '_')  # I don't like spaces in filenames.
    return filename


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


def getGridFromWorldPoint(vector, mapResolution):
    # public IntVector2 WorldToGridPos(Vector3 worldPos)
    # {
    #     Vector3D vector3D = FloatingOrigin.accumOffset + worldPos;
    #     int x = (int)Math.Round(vector3D.x / (double)this.chunkSize);
    #     int y = (int)Math.Round(vector3D.z / (double)this.chunkSize);
    #     return new IntVector2(x, y);
    # }

    logger.debug(
        "Converting WorldPoint (x:%s,y:%s,z:%s,res:%s) to grid" % (vector.x, vector.y, vector.z, mapResolution))

    x = int(round(vector.x / mapResolution, 0))
    y = int(round(vector.z / mapResolution, 0))

    return (x, y)


def gpsTupletoUnityWorldPoint(each, latOffset, longOffset, height=0):
    # print(each)
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
