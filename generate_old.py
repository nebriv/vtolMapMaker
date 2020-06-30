from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver import ActionChains
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.firefox.options import Options
import time


def getDownLoadedFileName(waitTime):
    driver.execute_script("window.open()")
    WebDriverWait(driver,10).until(EC.new_window_is_opened)
    driver.switch_to.window(driver.window_handles[-1])
    driver.get("about:downloads")

    endTime = time.time()+waitTime
    while True:
        try:
            fileName = driver.execute_script("return document.querySelector('#contentAreaDownloadsView .downloadMainArea .downloadContainer description:nth-of-type(1)').value")
            if fileName:
                return fileName
        except:
            pass
        time.sleep(1)
        if time.time() > endTime:
            break

options = Options()
options.set_preference("browser.download.folderList",2)
options.set_preference("browser.download.manager.showWhenStarting", True)
options.set_preference("browser.download.dir","C:\\Users\\ben\\Downloads\\Test")
options.set_preference("browser.helperApps.neverAsk.saveToDisk", "image/png")
driver = webdriver.Firefox(options=options)






latitude = 41.9100498
longitude = 12.4659589
zoom = 8

mapSize = 196000

resolution = round(mapSize / 70)

print(resolution)

driver.set_window_size(resolution, resolution)

driver.implicitly_wait(10)
print("Loading Tangram height map for %s,%s at zoom level %s" % (latitude,longitude,zoom))

driver.get("https://tangrams.github.io/heightmapper/#%s/%s/%s" % (zoom, latitude, longitude))
assert "Heightmapper" in driver.title
time.sleep(2)

print("Changing to manual exposure")

elem = driver.find_elements_by_xpath("//*[contains(text(), 'auto-exposure')]")


parentElem = elem[0].find_element_by_xpath("./..")


c_elem = parentElem.find_element_by_class_name("c")
button = c_elem.find_element_by_tag_name("input")
button.click()
time.sleep(.5)

print("Setting max elevation to 6000")
elem = driver.find_elements_by_xpath("//*[contains(text(), 'max elevation')]")

parentElem = elem[0].find_element_by_xpath("./..")

c_elem = parentElem.find_element_by_class_name("c")
maxHeight = c_elem.find_element_by_tag_name("input")
maxHeight.clear()
maxHeight.send_keys("6000")
maxHeight.send_keys(Keys.ENTER)

time.sleep(.5)
print("Setting min elevation to -80")
elem = driver.find_elements_by_xpath("//*[contains(text(), 'min elevation')]")

parentElem = elem[0].find_element_by_xpath("./..")

c_elem = parentElem.find_element_by_class_name("c")
maxHeight = c_elem.find_element_by_tag_name("input")
maxHeight.clear()
maxHeight.send_keys("-80")
maxHeight.send_keys(Keys.ENTER)

time.sleep(1)

print("Exporting PNG!")
elem = driver.find_elements_by_xpath("//*[contains(text(), 'export')]")

parentElem = elem[1].find_element_by_xpath("./..")

c_elem = parentElem.find_element_by_class_name("c")
button = c_elem.find_element_by_class_name("button")
driver.execute_script("arguments[0].click();", button)
latestDownloadedFileName = getDownLoadedFileName(180)
print(latestDownloadedFileName)
print("Donezo!")

driver.close()
