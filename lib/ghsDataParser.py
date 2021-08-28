from osgeo import gdal
from pyproj import Transformer
import logging
from osgeo import osr
import os
import numpy as np
import json
from os import environ
import gzip, shutil

gdal.SetCacheMax(134217728)

# TODO: Cleanup Code, road height, city density

logger = logging.getLogger(__name__)

handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

logger.addHandler(handler)
logger.setLevel('DEBUG')


outSpatialRef = osr.SpatialReference()
outSpatialRef.SetFromUserInput('ESRI:54009')

buildupDataFile = environ.get('buildupData', default="GHS_Data.npy")
buildupDataJSONFile = environ.get('buildupDataJSON', default="GHS_Data.json")
ghsFile = environ.get('buildupDataRaw', default="GHS_BUILT_LDS2014_GLOBE_R2018A_54009_1K_V2_0.tif")

class ghsDataParser:
    ghsFile = False
    transformer = Transformer.from_crs("epsg:4326", "esri:54009")
    def __init__(self, ghsFile):
        logger.debug("Hello!")
        self.ghsFile = ghsFile

        if os.path.exists(buildupDataFile) and os.path.exists(buildupDataJSONFile):
            self.loadBuildupData()
        else:
            logger.debug("Converted numpy and JSON data does not exist, running conversion now.")
            self.convertTIFtoNumpy()
            self.loadBuildupData()

    def loadBuildupData(self):
        # self.data = zarr.open(buildupDataFile, mode='r', dtype=np.int16, chunks=(10000, 10000))
        logger.debug("Loading  NP GHS-BUILT data: %s" % buildupDataFile)
        self.np_data = np.load(buildupDataFile, mmap_mode='r')

        logger.debug("Loading JSON GHS-BUILT data: %s" % buildupDataJSONFile)
        jsonData = json.load(open(buildupDataJSONFile))
        self.xOrigin = jsonData['xOrigin']
        self.yOrigin = jsonData['yOrigin']
        self.pixelWidth = jsonData['pixelWidth']
        self.pixelHeight = jsonData['pixelHeight']

        logger.debug("Done loading data.")

    def convertTIFtoNumpy(self):
        logger.debug("Loading GHS-BUILT data: %s" % self.ghsFile)

        dataset = gdal.Open(self.ghsFile)

        logger.debug("Done loading DHS data.")

        band = dataset.GetRasterBand(1)

        cols = dataset.RasterXSize
        rows = dataset.RasterYSize

        transform = dataset.GetGeoTransform()

        self.xOrigin = transform[0]
        self.yOrigin = transform[3]
        self.pixelWidth = transform[1]
        self.pixelHeight = -transform[5]

        transformData = {"xOrigin": self.xOrigin,
                         "yOrigin": self.yOrigin,
                         "pixelWidth": self.pixelWidth,
                         "pixelHeight": self.pixelHeight}

        logger.debug("Reading data")
        self.data = band.ReadAsArray(0, 0, cols, rows)
        logger.debug("Converting data to integers")

        self.data = self.data.astype(np.int16)
        logger.debug("Saving data")

        logger.debug("Saving numpy data")
        np.save(buildupDataFile, self.data)

        logger.debug("Compressing numpy data...")
        with open(buildupDataFile, 'rb') as f_in:
            with gzip.open('%s.gz' % buildupDataFile, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)


        logger.debug("Saving JSON data")
        with open("GHS_Data.json", 'w') as outFile:
            json.dump(transformData, outFile)

        logger.debug("Done converting.")


    def getBuildupData(self, subDivisions, southLat, distanceBetween, westLong, eastLong):
        logger.debug("Getting GHS build up data!")
        minBuildUp = 1000
        maxBuildUp = 0

        buildup_list = []

        required_entries = []

        entries = []


        required_rows = []
        for i in range(subDivisions):
            lat = southLat + (distanceBetween * i)
            long2 = westLong
            long1 = eastLong

            # Get the distance between the left and right points, and found how many subdivisions fit in it
            hopValue = (long2 - long1) / subDivisions
            long3 = long1
            # print("Getting Build Up Data")

            for x in range(subDivisions):
                long3 += hopValue

                conv_lat, conv_lon = self.transformer.transform(lat, long3)
                col = int((conv_lat - self.xOrigin) / self.pixelWidth)
                row = int((self.yOrigin - conv_lon) / self.pixelHeight)
                # print([row, col])
                required_entries.append([row, col])
                # entries.append(np.arange(conv_lat, conv_lon))


        filter_indices = np.array(required_entries)
        buildup_list = self.np_data[filter_indices[:,0], filter_indices[:,1]].tolist()

        maxBuildUp = max(buildup_list)
        minBuildUp = min(buildup_list)

        return buildup_list, maxBuildUp, minBuildUp

if __name__ == "__main__":
    os.environ["GDAL_CACHEMAX"] = "64"
    ghsFile = "GHS_BUILT_LDS2014_GLOBE_R2018A_54009_1K_V2_0.tif"
    # gdal.Warp('resize.tif', ghsFile, xRes=.5, yRes=.5)
    # ds = gdal.Warp('warp_test.tif', ghsFile, dstSRS='EPSG:4326',
    #                outputType=gdal.GDT_Int16, xRes=0.00892857142857143, yRes=0.00892857142857143)

    parser = ghsDataParser(ghsFile)
