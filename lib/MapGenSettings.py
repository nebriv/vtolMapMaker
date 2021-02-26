class GenSettings:
    bingKey = None
    nextzenAPIKey = None
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

    def __init__(self, bingAPIKey=None, nextzenAPIKey=None, ghsParser=None, uuid=None, centerLong=0, centerLat=0, forceBelowZero=True, forceRefresh=False, rebuildCity=True,
                 disableCityPaint=False, cityAdjust=10, resolution=512, offsetAmount=15, mapWidth=192000,
                 minHighwayLength=5, mapName=None, generateRoads=True, edgeType="Hills", biome="Boreal"):

        print(uuid)
        self.bingAPIKey = bingAPIKey
        self.nextzenAPIKey = nextzenAPIKey
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
