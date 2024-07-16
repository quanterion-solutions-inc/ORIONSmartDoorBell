const camera_image = document.getElementById('camera_image');

const messageDiv = document.getElementById('response');
const camera_button = document.getElementById('camera_control');
const gpt_button = document.getElementById('gpt_control');
const listen_button = document.getElementById('listen_control');
const talk_button = document.getElementById('talk_control');
const audio_player = document.getElementById("audioPlayer");

const REMOTE_APP_CAMERA_ONOFF_CONTROL_TOPIC = "ring/remote_app_control/camera"
const REMOTE_DEV_CAMERA_ONOFF_CONTROL_TOPIC = "ring/local_dev_control/camera"
const REMOTE_APP_MICROPHONE_CONTROL_TOPIC = "ring/remote_app_control/microphone"
const REMOTE_APP_AUDIO_DATA_TOPIC = "ring/remote_app_audio_data"

const GPT_RESPONSE_TOPIC = "ring/gptresponse"
const GPT_REQUEST_TOPIC = "ring/gptrequest"
const LISTEN_AUDIO_RESPONSE_TOPIC = "ring/audioresponse"

 let BROKER_PORT = 9001

let is_connected = false
let mediaRecorder;
let audioChunks = [];

async function SetupMediaRecorder() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);

        mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                audioChunks.push(event.data);
            }
        };

        mediaRecorder.onstop = () => {
            const blob = new Blob(audioChunks, { type: 'audio/wav' });
            audioChunks = [];

            const reader = new FileReader();
            reader.onload = function () {
                const arrayBuffer = this.result;
                const uint8Array = new Uint8Array(arrayBuffer);
                SendCommand(REMOTE_APP_AUDIO_DATA_TOPIC, uint8Array)
                console.log("Sent audio chunk: " + uint8Array.length);
            };
            reader.readAsArrayBuffer(blob);
        };
    }
    catch (err) {
        alert(err)
    }
};


mediaRecorder = SetupMediaRecorder()


talk_button.addEventListener('click', async () => {
    if (talk_button.innerHTML.trim() == "Talk") {
        talk_button.innerHTML = "Stop Talking"
        try {
            mediaRecorder.start();
        }
        catch (err) {
            alert(err)
            talk_button.innerHTML = "Talk"
        }

    }
    else if (talk_button.innerHTML.trim() == "Stop Talking") {
        talk_button.innerHTML = "Talk"
        try {
            mediaRecorder.stop();
        }
        catch (err) {
            alert(err)
            talk_button.innerHTML = "Talk"
        }
       
    }
});

gpt_button.addEventListener('click', async () => {

    if (camera_button.innerHTML.trim() == "Stop Camera") {
        request = "describe this image in three sentences"

        SendCommand(GPT_REQUEST_TOPIC, request)
        SendCommand(REMOTE_APP_CAMERA_ONOFF_CONTROL_TOPIC, "off")
        setRemoteCameraMode("off")
    }
    else {
        showAlert("Camera must be in preview", "Turn the camera on first")
    }
});

listen_button.addEventListener('click', async () => {
    microphone_mode_payload = "on"
    if (listen_button.innerHTML.trim() == "Listen") {
        listen_button.innerHTML = "Stop Listening";
        audio_player.style.display = "inline"
    }
    else if (listen_button.innerHTML.trim() == "Stop Listening") {
        microphone_mode_payload = "off"
        listen_button.innerHTML = "Listen";
        audio_player.style.display = "none"
    }

    SendCommand(REMOTE_APP_MICROPHONE_CONTROL_TOPIC, microphone_mode_payload)
});

camera_button.addEventListener('click', async () => {
    camera_mode_payload = "on"

    if (camera_button.innerHTML.trim() == "Start Camera") {

    }
    else if (camera_button.innerHTML.trim() == "Stop Camera") {
        camera_mode_payload = "off"
    }

    setRemoteCameraMode(camera_mode_payload)
    SendCommand(REMOTE_APP_CAMERA_ONOFF_CONTROL_TOPIC, camera_mode_payload)
});

function showAlert(tt, tx) {
    Swal.fire({
        title: tt,
        text: tx,
        icon: 'info',
        confirmButtonText: 'Ok'
    });
}


// Create a client instance
var client = new Paho.MQTT.Client(extractConnectedIP(window.location.href), BROKER_PORT, "doorbell_app" + makeid(7));

// Set callback handlers
client.onConnectionLost = onConnectionLost
client.onMessageArrived = onMessageArrived;


var options = {
    useSSL: false,
    timeout: 5,
    keepAliveInterval: 300,
    onSuccess: onConnect,
    onFailure: onFailure,
}

function SendCommand(topic, payload) {
    var ctlmsg = new Paho.MQTT.Message(payload);
    ctlmsg.destinationName = topic
    client.send(ctlmsg);
}

function setRemoteCameraMode(mode) {

    if (mode == "on") {
        camera_button.innerHTML = "Stop Camera";
        camera_image.style.borderColor = "red"
    }
    else if (mode == "off") {
        camera_button.innerHTML = "Start Camera";
        camera_image.style.borderColor = "white"
    }
}

function extractConnectedIP(address_bar) {
    var ip_expr = /\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b/;   // source: http://www.regular-expressions.info/examples.html
    var matches = address_bar.match(ip_expr);
    return matches[0]
}

function displaySpinner(show) {
    if (show == true) {
        document.getElementById('spinner').style.display = 'block';
        document.getElementById('camera_image').style.display = 'none';
    }
    else {
        document.getElementById('spinner').style.display = 'none';
        document.getElementById('camera_image').style.display = 'inline';
    }
}

function handleListenFromDoorMicrophone(message) {
    const audioBlob = new Blob([message.payloadBytes], { type: 'audio/wav' });
    const audioUrl = URL.createObjectURL(audioBlob);
    audio_player.src = audioUrl;
    // alert(audioUrl)
    audio_player.play();
}

function handleGPTResponseUpdate(message) {
    if (message == "waiting for the AI to Answer...") {
        gpt_button.disabled = true;
        camera_button.disabled = true;
        displaySpinner(true)
    }
    else {
        displaySpinner(false)
        gpt_button.disabled = false
        camera_button.disabled = false;
    }

    messageDiv.innerHTML = message;
}

// source:  https://stackoverflow.com/questions/1349404/generate-random-string-characters-in-javascript
function makeid(length) {
    let result = '';
    const characters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    const charactersLength = characters.length;
    let counter = 0;
    while (counter < length) {
        result += characters.charAt(Math.floor(Math.random() * charactersLength));
        counter += 1;
    }
    return result;
}

// Called when the client connects
function onConnect() {
    console.log("onConnect");
    client.subscribe(GPT_RESPONSE_TOPIC, {
        onSuccess: function () {
            console.log("Subscribed to: " + GPT_RESPONSE_TOPIC);

        },
        onFailure: function (e) {
            console.log("Subscription failed: " + e.errorMessage);
        }
    });


    client.subscribe(REMOTE_DEV_CAMERA_ONOFF_CONTROL_TOPIC, {
        onSuccess: function () {
            console.log("Subscribed to: " + REMOTE_DEV_CAMERA_ONOFF_CONTROL_TOPIC);
        },
        onFailure: function (e) {
            console.log("Subscription failed: " + e.errorMessage);
        }
    });

    client.subscribe(LISTEN_AUDIO_RESPONSE_TOPIC, {
        onSuccess: function () {
            console.log("Subscribed to: " + LISTEN_AUDIO_RESPONSE_TOPIC);
        },
        onFailure: function (e) {
            console.log("Subscription failed: " + e.errorMessage);
        }
    });

    is_connected = true

    // once connnected, enable the user (button) controls
    disableControls(false)
}

// Called when the client loses its connection
function onConnectionLost(responseObject) {
    if (responseObject.errorCode !== 0) {
        console.log("onConnectionLost:" + responseObject.errorMessage);
        is_connected = false
    }
}

// Called when a message arrives
function onMessageArrived(message) {
    if (message.destinationName != LISTEN_AUDIO_RESPONSE_TOPIC)
        console.log("onMessageArrived:" + message.payloadString)

    switch (message.destinationName) {
        case GPT_RESPONSE_TOPIC:
            handleGPTResponseUpdate(message.payloadString)
            break;
        case REMOTE_DEV_CAMERA_ONOFF_CONTROL_TOPIC:
            setRemoteCameraMode(message.payloadString)
            break;
        case LISTEN_AUDIO_RESPONSE_TOPIC:
            console.log("onMessageArrived:" + LISTEN_AUDIO_RESPONSE_TOPIC)
            handleListenFromDoorMicrophone(message)
    }
}

// Called when the client fails to connect
function onFailure(responseObject) {
    console.log("Connect failed:", responseObject.errorMessage);
    is_connected = false;
}

function disableControls(status) {
    camera_button.disabled = status
    gpt_button.disabled = status
    listen_button.disabled = status
    talk_button.disabled = status
}

