// var mymap = L.map('mapid').setView([51.505, -0.09], 13);

var uuid = false;
var done = false;

var longitude = 0.0;
var latitude = 0.0;
var zoomLevel = 8;

var mymap = L.map('mapid').setView([longitude, latitude], zoomLevel);
var rectangle = null;

var mapCenter = null;

var popup = L.popup();

function showImage(uuid) {
  var val = document.getElementById('imagename').value
  src = '/api/maps/' + uuid + '/getImage'
  img = document.getElementById("imagename")
  img.src = src;

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
  // document.getElementById("mapGenerator").style.display = "none";
  jQuery('#statusModal').modal({"show": true})
  document.getElementById("results").style.display = "block";
  const XHR = new XMLHttpRequest();
  XHR.responseType = "json";

  // Define what happens on successful data submission
  XHR.addEventListener("load", function (event) {
    status = event.target.response.Status;
    progess = event.target.response.Progress;


    if (progess != null){
      document.getElementById("progressbar").setAttribute('aria-valuenow',progess);
      document.getElementById("progressbar").setAttribute('style','width:'+Number(progess)+'%');
    }

    if (status === "Error") {
      document.getElementById("currentStatus").innerText = event.target.response.Error
    } else if (status !== "Done") {
      statusCounter++;
      document.getElementById("currentStatus").innerText = status

      if (statusCounter % 10 === 0) {
        document.getElementById("currentStatus").innerText = document.getElementById("currentStatus").innerText + " - Don't worry, we're still processing!"
      }

      setTimeout(getStatus, 1000);
    } else {
      document.getElementById("currentStatus").innerText = "Completed!"
      showImage(uuid);
      document.getElementById("download").style.display = 'block'
      statusCounter = 0;
      document.getElementById("downloadButton").setAttribute('class', 'btn btn-success');
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

var zoomSlider = document.getElementById("zoomSlider");
var zoomValue = document.getElementById("zoomValue");
var vtolmapsize = document.getElementById("vtolmapsize");

zoomSlider.oninput = function () {
  vtolmapsize.innerHTML = this.value * 3;
  drawRectangle(mymap.getCenter(), this.value);
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

document.getElementById("enableCityPaint").addEventListener('change', (event) => {
  if (event.currentTarget.checked) {
    document.getElementById("cityAdjustContainer").style.display = "block";
  } else {
    document.getElementById("cityAdjustContainer").style.display = "none";
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


var offsetAmountSlider = document.getElementById("offsetAmountSlider");
var offsetAmountSliderValue = document.getElementById("offsetAmountSliderValue");
offsetAmountSlider.oninput = function () {
  offsetAmountSliderValue.innerHTML = this.value;
}

var latitudeValue = document.getElementById("latitudeValue");
var longitudeValue = document.getElementById("longitudeValue");

function drawRectangle(){
  var mapsize = document.getElementById("vtolmapsize").innerText * 1000;
  if (rectangle != null)
  {
    mymap.removeLayer(rectangle);
  }

  if (mapCenter != null){
    widthInDegrees = mapsize / 111111;

    westLong = mapCenter.lng - (widthInDegrees / 2)
    northLat = mapCenter.lat + (widthInDegrees / 2)

    eastLong = westLong + widthInDegrees
    southLat = northLat - widthInDegrees


    // define rectangle geographical bounds
    var bounds = [[northLat, westLong], [southLat, eastLong]];

    // create an orange rectangle
    rectangle = L.rectangle(bounds, { color: "#00FF00", weight: 1 }).addTo(mymap);
  } else {
    console.log("mapCenter is null!");
  }


}

function onMapClick(e) {
  popup
    .setLatLng(e.latlng)
    .setContent("Map Center")
    .openOn(mymap);

  mapCenter = e.latlng;
  latitudeValue.value = mapCenter.lat;
  longitudeValue.value = mapCenter.lng;
  drawRectangle();
}

function onMapMove(e) {
  console.log(mymap.getCenter());
}

function setPosition(position) {
  latitude = position.coords.latitude;
  longitude = position.coords.longitude;
  latitudeValue.value = position.coords.latitude;
  longitudeValue.value = position.coords.longitude;
  mapCenter.lat = position.coords.latitude;
  mapCenter.lng = position.coords.longitude;
  mymap.setView([latitude, longitude], zoomLevel)
  drawRectangle();
}


const getlocation = document.getElementById("mylocation");

// ...and take over its submit event.
getlocation.addEventListener("click", function (event) {
  event.preventDefault();
  navigator.geolocation.getCurrentPosition(setPosition);
});


L.tileLayer('https://api.mapbox.com/styles/v1/{id}/tiles/{z}/{x}/{y}?access_token=pk.eyJ1IjoibWFwYm94IiwiYSI6ImNpejY4NXVycTA2emYycXBndHRqcmZ3N3gifQ.rJcFIG214AriISLbB6B5aw', {
  maxZoom: 12,
  minZoom: 2,
  attribution: 'Map data &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, ' +
    'Imagery © <a href="https://www.mapbox.com/">Mapbox</a>',
  id: 'mapbox/streets-v11',
  tileSize: 512,
  zoomOffset: -1
}).addTo(mymap);


mymap.setView([39.29084059412512, -76.61540335349957],7)
console.log(mymap.getCenter());
mapCenter = mymap.getCenter();
mymap.on('click', onMapClick);
// mymap.on('moveend', onMapMove);

