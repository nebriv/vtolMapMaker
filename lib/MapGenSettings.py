class ValidSettings:
    biomes = ['Boreal', "Desert", "Artic"]
    edgeType = ['Hills', "Water"]
    mapWidth = ['192000']


class GenSettings:
    bingKey = None
    nextzenAPIKey = None
    outputDir = ''
    ghsParser = None
    uuid = None
    centerLong = None
    centerLat = None
    forceBelowZero = True
    forceRefresh = False
    rebuildCity = True
    disableCityPaint = False
    cityAdjust = 10
    resolution = 512
    offsetAmount = 15
    mapWidth = 192000
    minHighwayLength = 5
    mapName = None
    generateRoads = True
    edgeType = "Hills"
    biome = "Boreal"

    def __init__(self, bingAPIKey=None, nextzenAPIKey=None, outputDir=None, ghsParser=None, uuid=None, centerLong=0, centerLat=0, forceBelowZero=True, forceRefresh=False, rebuildCity=True,
                 disableCityPaint=False, cityAdjust=10, resolution=512, offsetAmount=15, mapWidth=192000,
                 minHighwayLength=5, mapName=None, generateRoads=True, edgeType="Hills", biome="Boreal"):

        self.bingAPIKey = bingAPIKey
        self.nextzenAPIKey = nextzenAPIKey
        self.outputDir = outputDir
        self.ghsParser = ghsParser
        self.uuid = uuid
        self.centerLong = centerLong
        self.centerLat = centerLat
        self.forceBelowZero = forceBelowZero
        self.forceRefresh = forceRefresh
        self.rebuildCity = rebuildCity
        self.disableCityPaint = disableCityPaint
        self.cityAdjust = cityAdjust
        self.resolution = resolution
        self.offsetAmount = offsetAmount
        self.mapWidth = mapWidth
        self.minHighwayLength = minHighwayLength
        self.mapName = mapName
        self.generateRoads = generateRoads
        self.edgeType = edgeType
        self.biome = biome
