// var mymap = L.map('mapid').setView([51.505, -0.09], 13);

var uuid = false;
var done = false;

function showImage(uuid) {
  var val = document.getElementById('imagename').value, src = '/api/maps/' + uuid + '/getImage', img = document.createElement('img');
  img.src = src;
  document.body.appendChild(img);
}

function downloadMap(uuid) {
  window.open("/api/maps/" + uuid + "/getZip");
}

const downloadButton = document.getElementById("downloadButton");

// ...and take over its submit event.
downloadButton.addEventListener("click", function (event) {
  event.preventDefault();
  downloadMap(uuid);
});
var statusCounter = 0;
function getStatus() {
  document.getElementById("generator").style.display = "none";
  document.getElementById("results").style.display = "block";
  const XHR = new XMLHttpRequest();
  XHR.responseType = "json";

  // Define what happens on successful data submission
  XHR.addEventListener("load", function (event) {
    status = event.target.response.Status;

    if (event.target.response.Status === "Error") {
      document.getElementById("currentStatus").innerText = event.target.response.Error
    } else if (status !== "Done") {

      statusCounter++;
      document.getElementById("currentStatus").innerText = status

      if (statusCounter % 5 === 0) {
        document.getElementById("currentStatus").innerText = document.getElementById("currentStatus").innerText + " - Don't worry, we're still processing!"
      }

      setTimeout(getStatus, 1000);
    } else {
      document.getElementById("currentStatus").innerText = "Completed!"
      showImage(uuid);
      document.getElementById("download").style.display = 'block'
    }

  });
  // Define what happens in case of error
  XHR.addEventListener("error", function (event) {
    document.getElementById("currentStatus").innerText = "Error connecting to backend service! Please try again later."
  });
  // Set up our request
  XHR.open("GET", "/api/maps/" + uuid + "/status");
  XHR.setRequestHeader("Content-Type", "application/json");

  // The data sent is what the user provided in the form
  XHR.send();
}
var spn = document.getElementById("count");
var btn = document.getElementById("submitButton");

var count = 60;     // Set count
var timer = null;  // For referencing the timer
function countDown() {

  // Display counter and start counting down
  spn.textContent = "Please Wait - " + count + " seconds";

  // Run the function again every second if the count is not zero
  if (count !== 0) {
    timer = setTimeout(countDown, 1000);
    count--; // decrease the timer
  } else {
    // Enable the button
    btn.removeAttribute("disabled");
    spn.textContent = "Submit"
  }
}

window.addEventListener("load", function () {
  function sendData() {

    const XHR = new XMLHttpRequest();
    // XHR.responseType = "json";

    // Bind the FormData object and the form element
    const FD = new FormData(form);
    // FD.forEach((value, key) => object[key] = value);
    var jsonData = JSON.stringify(Object.fromEntries(FD));
    // Define what happens on successful data submission
    XHR.addEventListener("load", function (event) {

      if (event.target.status !== 200) {
        if (event.target.responseText.includes("currently overloaded")) {
          alert("We're currently overloaded, please try resubmitting in a few minutes.")
          countDown();
        } else {

        }

      } else {
        var response = JSON.parse(event.target.responseText);
        if (response.errors === false) {
          uuid = response.uuid;
          setTimeout(getStatus, 100);
        } else {
          errordata = "";
          console.log(response.errors)

          for (var key in response.errors) {
            if (response.errors.hasOwnProperty(key)) {
              errordata += response.errors[key] + " ";
            }
          }
          alert(errordata);
        }
      }

    });

    // Define what happens in case of error
    XHR.addEventListener("error", function (event) {
      alert('Oops! Something went wrong.');
    });
    // Set up our request
    XHR.open("POST", "/api/maps/createMap");
    XHR.setRequestHeader("Content-Type", "application/json");

    // The data sent is what the user provided in the form
    XHR.send(jsonData);

  }

  // Access the form element...
  const form = document.getElementById("mapGenerator");

  // ...and take over its submit event.
  form.addEventListener("submit", function (event) {
    event.preventDefault();
    sendData();
  });
});

var zoomMapping = {
  8: 64,
  9: 32,
  10: 16,
  11: 13,
  12: 8
}
var zoomSlider = document.getElementById("zoomSlider");
var zoomValue = document.getElementById("zoomValue");
var vtolmapsize = document.getElementById("vtolmapsize");
zoomSlider.oninput = function () {
  mymap.setZoom(this.value);
  vtolmapsize.innerHTML = zoomMapping[this.value];
}

var citySlider = document.getElementById("cityAdjust");
var cityValue = document.getElementById("cityAdjustValue");
citySlider.oninput = function () {
  cityValue.innerHTML = this.value;
}
var highwaySlider = document.getElementById("minimumHighwayLength");
var minimumHighwayLengthValue = document.getElementById("minimumHighwayLengthValue");
highwaySlider.oninput = function () {
  minimumHighwayLengthValue.innerHTML = this.value;
}

document.getElementById("forceBelowZero").addEventListener('change', (event) => {
  if (event.currentTarget.checked) {
    document.getElementById("offsetContainer").style.display = "block";
  } else {
    document.getElementById("offsetContainer").style.display = "none";
  }
})

document.getElementById("disableCityPaint").addEventListener('change', (event) => {
  if (event.currentTarget.checked) {
    document.getElementById("cityAdjustContainer").style.display = "none";
  } else {
    document.getElementById("cityAdjustContainer").style.display = "block";
  }
})

document.getElementById("generateRoads").addEventListener('change', (event) => {
  if (event.currentTarget.checked) {
    document.getElementById("minHighwayLengthContainer").style.display = "block";
  } else {
    document.getElementById("minHighwayLengthContainer").style.display = "none";
  }
})

document.getElementById("latitudeValue").addEventListener('change', (event) => {
  if (event.currentTarget.checked) {
    document.getElementById("minHighwayLengthContainer").style.display = "block";
  } else {
    document.getElementById("minHighwayLengthContainer").style.display = "none";
  }
})
document.getElementById("longitudeValue").addEventListener('change', (event) => {
  position = {
    "coords": {
      "longitude": document.getElementById("longitudeValue").value,
      "latitude": document.getElementById("latitudeValue").value
    }
  }
  console.log(position);
  setPosition(position)
})
document.getElementById("latitudeValue").addEventListener('change', (event) => {
  position = {
    "coords": {
      "longitude": document.getElementById("longitudeValue").value,
      "latitude": document.getElementById("latitudeValue").value
    }
  }
  console.log(position);
  setPosition(position)
})
// var mapWidthSlider = document.getElementById("mapWidthSlider");
// var mapWidthSliderValue = document.getElementById("mapWidthSliderValue");
// mapWidthSlider.oninput = function() {
//   mapWidthSliderValue.innerHTML = this.value;
// }

var offsetAmountSlider = document.getElementById("offsetAmountSlider");
var offsetAmountSliderValue = document.getElementById("offsetAmountSliderValue");
offsetAmountSlider.oninput = function () {
  offsetAmountSliderValue.innerHTML = this.value;
}

var latitudeValue = document.getElementById("latitudeValue");
var longitudeValue = document.getElementById("longitudeValue");


longitude = 0.0;
latitude = 0.0;
zoomLevel = 8;
console.log("Starting")
mymap = L.map('mapid').setView([longitude, latitude], zoomLevel);
rectangle = null

var popup = L.popup();


function onMapClick(e) {
  popup
    .setLatLng(e.latlng)
    .setContent("Map Center")
    .openOn(mymap);

  latitudeValue.value = e.latlng.lat;
  longitudeValue.value = e.latlng.lng;

  if (rectangle != null)
  {
    mymap.removeLayer(rectangle);
  }

  widthInDegrees = 192000 / 111111;

  westLong = e.latlng.lng - (widthInDegrees / 2)
  northLat = e.latlng.lat + (widthInDegrees / 2)

  eastLong = westLong + widthInDegrees
  southLat = northLat - widthInDegrees

  
  // define rectangle geographical bounds
  var bounds = [[northLat, westLong], [southLat, eastLong]];

  // create an orange rectangle
  rectangle = L.rectangle(bounds, { color: "#00FF00", weight: 1 }).addTo(mymap);
}

function onZoom(e) {
  zoomValue.innerHTML = mymap.getZoom();
  zoomSlider.value = mymap.getZoom();
  vtolmapsize.innerHTML = zoomMapping[mymap.getZoom()];
}

function onMapMove(e) {
  console.log(mymap.getCenter());
  latitudeValue.value = mymap.getCenter().lat;
  longitudeValue.value = mymap.getCenter().lng;
}

function setPosition(position) {
  latitude = position.coords.latitude;
  longitude = position.coords.longitude;
  mymap.setView([latitude, longitude], zoomLevel)
}


const getlocation = document.getElementById("mylocation");

// ...and take over its submit event.
getlocation.addEventListener("click", function (event) {
  event.preventDefault();
  navigator.geolocation.getCurrentPosition(setPosition);
});


L.tileLayer('https://api.mapbox.com/styles/v1/{id}/tiles/{z}/{x}/{y}?access_token=pk.eyJ1IjoibWFwYm94IiwiYSI6ImNpejY4NXVycTA2emYycXBndHRqcmZ3N3gifQ.rJcFIG214AriISLbB6B5aw', {
  maxZoom: 12,
  minZoom: 8,
  attribution: 'Map data &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, ' +
    'Imagery © <a href="https://www.mapbox.com/">Mapbox</a>',
  id: 'mapbox/streets-v11',
  tileSize: 512,
  zoomOffset: -1
}).addTo(mymap);

mymap.on('click', onMapClick);
mymap.on('zoomend', onZoom);
mymap.on('moveend', onMapMove);

