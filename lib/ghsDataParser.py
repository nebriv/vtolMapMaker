from osgeo import gdal
from pyproj import Transformer
import logging
from osgeo import osr

# TODO: Cleanup Code, road height, city density

logger = logging.getLogger(__name__)

handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

logger.addHandler(handler)
logger.setLevel('DEBUG')


outSpatialRef = osr.SpatialReference()
outSpatialRef.SetFromUserInput('ESRI:54009')

class ghsDataParser:
    ghsFile = False
    transformer = Transformer.from_crs("epsg:4326", "esri:54009")
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
                conv_lat, conv_lon = self.transformer.transform(lat, long3)
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