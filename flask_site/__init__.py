import os
from flask import Flask
from flask import Response
from flask_site.utils import validate_uuid4
from flask import abort, jsonify
from flask import request
from flask import render_template

def create_app(test_config=None):
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY='dev',
        DATABASE=os.path.join(app.instance_path, 'flaskr.sqlite'),
    )

    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # a simple page that says hello
    @app.route('/')
    def hello():
        return "hey!"


    @app.route('/api/createMap', methods=['POST'])
    def createMap():
        return jsonify(request.get_json())

    @app.route('/api/maps/<uuid>/status', methods=['GET'])
    def checkStatus(uuid):
        if validate_uuid4(uuid):
            return "Valid uuid... checking status of %s" % uuid

        return abort(404, description="Resource not found")

    @app.route('/api/maps/<uuid>/getImage', methods=['GET'])
    def getImage(uuid):
        if validate_uuid4(uuid):
            return "Valid uuid... getting image %s" % uuid

        return abort(404, description="Resource not found")

    @app.route('/api/maps/<uuid>/getZip', methods=['GET'])
    def getZip(uuid):
        if validate_uuid4(uuid):
            return "Valid uuid... Getting zip for %s" % uuid

        return abort(404, description="Resource not found")

    return app