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

COPY requirements.txt .
RUN pip3 install -r /opt/vtolmaps/requirements.txt

ADD dataSets dataSets/
ADD flask_site flask_site/

ADD lib lib/
ADD maps maps/
ADD tiles tiles/
COPY .flaskenv .
#COPY GHS_BUILT_LDS2014_GLOBE_R2018A_54009_1K_V2_0.tif .
COPY GHS_Data.json .
COPY GHS_Data.npy.gz .
#ADD GHS_Data.zarr GHS_Data.zarr/

COPY wsgi.py .
COPY start.sh .
RUN chmod +x start.sh && sed -i -e 's/\r$//' start.sh
EXPOSE 5000
CMD [ "./start.sh" ]
