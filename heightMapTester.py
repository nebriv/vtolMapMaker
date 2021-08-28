from PIL import Image, ImageOps
import math
import numpy as np



im = Image.open("F:\SteamLibrary\steamapps\common\VTOL VR\CustomMaps\Testing\height.png")
pixels = list(im.getdata())

red = []
green = []
blue = []
a = []

for pixel in pixels:
    print(pixel)
    red.append(pixel[0])
    green.append(pixel[1])
    blue.append(pixel[2])
    a.append(pixel[3])

print(np.mean(red))