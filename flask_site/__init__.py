import os
from flask import Flask
from flask_site.utils import validate_uuid4, serve_pil_image
from flask import abort, jsonify
from flask import request
from flask import render_template
from os import environ
from lib.MapGenManager import MapGenManager
from lib.MapGenSettings import ValidSettings
from flask import send_file, send_from_directory
from dotenv import load_dotenv
import logging
from lib.helpers import getVersion
import pathlib


logger = logging.getLogger(__name__)

handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

logger.addHandler(handler)
logger.setLevel('DEBUG')

load_dotenv()
version = getVersion()
NextZen = environ.get('NextZen')
OutputDir = environ.get('OutputDir')
StaticDir = environ.get('StaticDir')

if not StaticDir:
    StaticDir = os.path.join(pathlib.Path(__file__).parent.resolve(), "static")

# create and configure the app
app = Flask(__name__, instance_relative_config=True, static_folder=StaticDir)

# ensure the instance folder exists
try:
    os.makedirs(app.instance_path)
except OSError:
    pass

generator = MapGenManager(NextZen, OutputDir)

@app.context_processor
def inject_dict_for_all_templates():
    return dict(version= version)

# a simple page that says hello
@app.route('/')
def hello():
    if generator.count_running_threads() > 5:
        return abort(503, description="Sorry - we're currently overloaded and cannont accept more map requests. Please try again shortly!")

    return render_template('home.html', content={"uuid": "123", "version": version})


@app.route('/api/maps/createMap', methods=['POST'])
def createMap():

    if generator.count_running_threads() > 10:
        return abort(503, description="Sorry - we're currently overloaded and cannont accept more map requests. Please try again shortly!")

    validationErrors = []

    settings = request.get_json()

    try:
        centerLong = float(settings['longitudeValue'])
        centerLat = float(settings['latitudeValue'])
        cityAdjust = int(settings['cityAdjust'])
        mapResolution = int(settings['mapResolution'])
        offsetAmount = int(settings['offsetAmount'])
        minHighwayLength = int(settings['minHighwayLength'])
        mapName = settings['mapName']
        biome = settings['biome']
        edgeType = settings['edgeType']
        zoomValue = int(settings['zoomValue'])
    except KeyError as err:
        return jsonify({"errors": ["Missing input value"]})
    except ValueError as err:
        return jsonify({"errors": ["Incorrect input value"]})
    except Exception as err:
        logger.error("Error in map create api: %s" % err)
        return jsonify({"errors": ["Exception in map creation API."]})



    if "forceBelowZero" in settings:
        forceBelowZero = True
    else:
        forceBelowZero = False

    forceRefresh = False
    rebuildCity = True

    if "disableCityPaint" in settings:
        disableCityPaint = True
    else:
        disableCityPaint = False


    if "generateRoads" in settings:
        generateRoads = True
    else:
        generateRoads = False


    if zoomValue < 8 or zoomValue > 12:
        validationErrors.append({"zoomValue": "Invalid zoom value."})
    zoomMapping = {8:64,
                   9:32,
                   10:16,
                   11:13,
                   12:8}
    mapWidth = zoomMapping[zoomValue]
    mapWidth = mapWidth * 1000 * 3

    if biome not in ValidSettings.biomes:
        validationErrors.append({"biome": "Invalid biome value"})

    if edgeType not in ValidSettings.edgeType:
        validationErrors.append({'edgeType': "Invalid edgetype value"})

    if not mapName:
        validationErrors.append({"mapName": "Map name cannot be empty"})
    else:
        if not utils.checkMapName(mapName):
            validationErrors.append({"mapName": "Map name contains invalid characters"})

    if len(validationErrors) > 0:
        return jsonify({"errors": "Invalid Input", "validationErrors": validationErrors})

    uuid = generator.create_map(centerLong=centerLong, centerLat=centerLat, forceBelowZero=forceBelowZero,
                                forceRefresh=forceRefresh,
                                rebuildCity=rebuildCity, disableCityPaint=disableCityPaint, cityAdjust=cityAdjust,
                                resolution=mapResolution, offsetAmount=offsetAmount, mapWidth=mapWidth,
                                minHighwayLength=minHighwayLength, mapName=mapName, generateRoads=generateRoads,
                                biome=biome, edgeType=edgeType)


    return jsonify({"errors": False, "uuid": uuid})

@app.route('/api/maps/<uuid>/status', methods=['GET'])
def status(uuid):
    if validate_uuid4(uuid):
        status = generator.get_thread_status(uuid)
        print(status)
        if status:
            # if "Error" in status:
            #
            #     return abort(500, description=status['Error'])
            return jsonify(status)
        else:
            return abort(404, description="Invalid resource ID")

    return abort(400, description="Invalid resource ID")

@app.route('/api/maps/<uuid>/getImage', methods=['GET'])
def getImage(uuid):
    if validate_uuid4(uuid):
        status = generator.get_thread_status(uuid)
        if status['Status'] == "Done":
            heightMap = generator.get_heightmap_image(uuid)
            if heightMap:
                return serve_pil_image(heightMap)
        return abort(404, description="Still processing")
    return abort(404, description="Resource not found")

@app.route('/api/maps/<uuid>/getZip', methods=['GET'])
def getZip(uuid):
    if validate_uuid4(uuid):
        status = generator.get_thread_status(uuid)
        if status['Status'] == "Done":
            zipFile = generator.get_zip(uuid)
            return send_file(zipFile, mimetype='application/zip', as_attachment=True)
        return abort(404, description="Still processing")
    return abort(404, description="Resource not found")


@app.route('/processingStatus', methods=['GET'])
def processingStatus():
    status = {}
    for thread in generator.generation_threads:
        status[thread] = generator.generation_threads[thread].status
    return jsonify(status)

