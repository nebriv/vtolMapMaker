FROM osgeo/gdal:ubuntu-small-latest
# Install python/pip
ENV PYTHONUNBUFFERED=1

RUN apt-get update
RUN apt-get install --no-install-recommends --yes python3-pip
RUN pip install --no-cache --upgrade pip setuptools

ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
RUN mkdir /opt/vtolmaps/
WORKDIR /opt/vtolmaps/
ADD dataSets dataSets/
ADD flask_site flask_site/
ADD lib lib/
ADD maps maps/
ADD tiles tiles/
COPY .flaskenv .
COPY GHS_BUILT_LDS2014_GLOBE_R2018A_54009_1K_V2_0.tif .
COPY requirements.txt .
COPY wsgi.py .
RUN pip3 install -r /opt/vtolmaps/requirements.txt
EXPOSE 5000
CMD [ "python", "wsgi.py" ]
