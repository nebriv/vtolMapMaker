from . import db

class Stats(db.Model):
    __tablename__ = 'stats'
    id = db.Column(db.Integer, primary_key=True)

    pageViews = db.Column(db.Integer)
    mapsCreated = db.Column(db.Integer)
    sqMiles = db.Column(db.Integer)
    roads = db.Column(db.Integer)
    roadMiles = db.Column(db.Integer)


class Map(db.Model):
    __tablename__ = "maps"
    id = db.Column(db.Integer, primary_key=True)

    requester_ip = db.Column(db.String(40))
    uuid = db.Column(db.String(32))

    geo_region = db.Column(db.String(255))

    forceBelowZero = db.Column(db.Boolean)
    forceRefresh = db.Column(db.Boolean)
    rebuildCity = db.Column(db.Boolean)
    disableCityPaint = db.Column(db.Boolean)
    disablePrefabs = db.Column(db.Boolean)

    cityAdjust = db.Column(db.Integer)
    resolution = db.Column(db.Integer)
    offsetAmount = db.Column(db.Integer)
    mapWidth = db.Column(db.Integer)
    minHighwayLength = db.Column(db.Integer)
    mapName = db.Column(db.String(255))
    generateRoads = db.Column(db.Boolean)
    edgeType = db.Column(db.String(255))
    biome = db.Column(db.String(255))
    heightOffset = db.Column(db.Integer)
    scalingMode = db.Column(db.String(255), nullable=True)

    heightMap = db.Column(db.LargeBinary)
    status = db.Column(db.String(255))
