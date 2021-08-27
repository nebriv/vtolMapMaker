import math
import hashlib
import numpy as np
from scipy.spatial.distance import pdist, squareform
import logging
import os
import zipfile
import shutil
from threading import Thread
from queue import Queue
import requests
import requests_cache
import time
import pickle
from lib.helpers import *
from lib.helpers import getVersion

requests_cache.install_cache(cache_name='open_elevation', backend='sqlite', expire_after=86400)

r_headers = {"User-Agent": "VTOL Map Maker v%s (https://vtolmapmaker.nebriv.com)" % getVersion()}

# TODO: Cleanup Code, road height, city density

logger = logging.getLogger(__name__)

handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

logger.addHandler(handler)
logger.setLevel('DEBUG')


def get_cached(dataHash, forceRefresh=False):
    cacheData = False
    if os.path.isdir("dataSets"):
        if os.path.isfile(os.path.join("dataSets", "%s.p" % dataHash)):
            if not forceRefresh:
                cacheData = pickle.load(open(os.path.join("dataSets", "%s.p" % dataHash), 'rb'))

    return cacheData

def genDataHash(string):
    dataHashString = string
    return genHash(dataHashString)

def crawl(q, url, result):
    while not q.empty():
        work = q.get()                      #fetch new work from the Queue
        retries = 0
        success = False
        while not success and retries < 3:
            try:
                dataHash = genHash(str(work[1]))
                cached_data = get_cached(dataHash, work[2])
                if cached_data:
                    logger.debug("Got chunk data from cache!")
                    result[work[0]] = cached_data
                else:
                    data = requests.post(url, json=work[1], headers=r_headers)
                    if retries > 0:
                        logger.debug("Requested chunk %s RETRY %s" % (work[0], retries))
                    else:
                        logger.debug("Requested chunk %s" % (work[0]))
                    if "results" in data.json():
                        pickle.dump(data.json(), open(os.path.join("dataSets", "%s.p" % dataHash), "wb"))
                        result[work[0]] = data.json()          #Store data back at correct index
                        success = True
                    else:
                        logger.error("Missing results key in data! %s" % data.json())
                        time.sleep(retries*2)

            except Exception as err:
                logger.error('Error with URL check! %s' % err)
                result[work[0]] = {}
            retries += 1
        #signal to the queue that task has been processed
        q.task_done()
    return True

def divide_chunks(in_array, chunk_length):

    for i in range(0, len(in_array), chunk_length):
        yield in_array[i:i + chunk_length]


def getElevationData(cord_list, forceRefresh):

    chunks = list(divide_chunks(cord_list, 1250))
    logger.debug("Split %s cords into %s" % (len(cord_list), len(chunks)))

    # chunks = np.array_split(cord_list, 800)

    url = "https://api.open-elevation.com/api/v1/lookup"
    heights = []
    maxHeight = 0
    minHeight = 29000

    request_data = []

    for chunk in chunks:
        data = {"locations": []}
        for cord in chunk:
            data['locations'].append({"latitude": cord[0], "longitude": cord[1]})
            # print("%s,%s,red,circle" % (cord[0],cord[1]))
        request_data.append(data)

    q = Queue(maxsize=0)
    num_theads = 50

    # Populating Queue with tasks
    results = [{} for x in request_data];
    # load up the queue with the urls to fetch and the index for each job (as a tuple):
    for i in range(len(request_data)):
        # need the index and the url in each queue item.
        q.put((i, request_data[i], forceRefresh))

    # Starting worker threads on queue processing
    for i in range(num_theads):
        worker = Thread(target=crawl, args=(q, url, results))
        worker.setDaemon(True)  # setting threads as "daemon" allows main program to
        # exit eventually even if these dont finish
        # correctly.
        worker.start()
    # now we wait until the queue has been processed
    q.join()
    logger.info('All tasks completed.')

    for result in results:
        for each in result['results']:
            height = each['elevation']
            if height > maxHeight:
                maxHeight = height
            if height < minHeight:
                minHeight = height
            heights.append(height)

    return heights, minHeight, maxHeight