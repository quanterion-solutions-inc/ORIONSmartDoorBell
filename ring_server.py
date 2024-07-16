import io
import json
import picamera
from gpiozero import Button, MotionSensor
import logging
import socketserver
from threading import Condition
from http import server

import paho.mqtt.client as paho
import base64
import requests
import time
import os
import sys

import argparse

import threading

from audioUtils import *
import ssl
import subprocess

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
import pygame

class StreamingOutput(object):
    def __init__(self):
        self.frame = None
        self.buffer = io.BytesIO()
        self.condition = Condition()

    def write(self, buf):
        if buf.startswith(b'\xff\xd8'):
            #new frame, copy the existing buffer's content and notify all
            #clients it's available
            self.buffer.truncate()
            with self.condition:
                self.frame = self.buffer.getvalue()
                self.condition.notify_all()
            self.buffer.seek(0)
        return self.buffer.write(buf)

class StreamingHandler(server.BaseHTTPRequestHandler):   
    def ReadClientApp(self, appfile, binary=False):
        if binary is True:
             with open(appfile, 'rb') as my_file:
                return my_file.read()
        else:
            with open(appfile) as my_file:
                return my_file.read()
      
    def do_GET(self):
        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/index.html')
            self.end_headers()

        elif self.path == '/index.html':
            # if args.secure == "on":
            #    self.path = "./wwwroot/html_pages/https_client_ring_app.html"
            # else:
            self.path = "./wwwroot/html_pages/client_ring_app.html"     
            content = self.ReadClientApp(self.path).encode("utf-8")
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)

        elif self.path == '/favicon.ico':
           self.path = './wwwroot/favicon.ico'
           content = self.ReadClientApp(self.path, True)
           self.send_response(200)
           self.send_header('Content-type', 'image/x-icon')
           self.send_header('Content-Length', len(content))
           self.end_headers()   
           self.wfile.write(content)    

        elif self.path == '/doorbell.png':
            self.path = './wwwroot/images/doorbell.png'
            content = self.ReadClientApp(self.path, True)
            self.send_response(200)
            self.send_header('Content-type', 'image/png')
            self.send_header('Content-Length', len(content))
            self.end_headers()   
            self.wfile.write(content)          

        elif self.path == '/client_app.js':
            self.path = './wwwroot/js/client_app.js'
            content = self.ReadClientApp(self.path).encode("utf-8")
            self.send_response(200)
            self.send_header('Content-type', 'text/javascript')
            self.send_header('Content-Length', len(content))
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()   
            self.wfile.write(content)  
        
        elif self.path == '/client_app_styles.css':
            self.path = './wwwroot/css/client_app_styles.css'
            content = self.ReadClientApp(self.path).encode("utf-8")
            self.send_response(200)
            self.send_header('Content-type', 'text/css')
            self.send_header('Content-Length', len(content))
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()   
            self.wfile.write(content)  
        
        elif self.path == '/stream.mjpg':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while True:
                    with output.condition:
                        output.condition.wait()
                        frame = output.frame

                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', len(frame))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
    
            except Exception as e:
                stopCamera()
                logging.warning(
                    'Removed streaming client %s: %s',
                    self.client_address, str(e))
        else:
            self.send_error(404)
            self.end_headers()


class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def Open_AI_Tell_Me_Who_Is_There(base64_image):
    
    # OpenAI API Key environemnt variable (uncommend to read it)
    # api_key  = os.getenv('DOORBELL_KEY')

    return "I dunno! Connect me to OpenAI, so I can be \"Smart!\" "

    # parse the "content" field from the json "message" response, "choices" array
    # choices = response.json().get("choices", [])
    # return (choices[0]['message']['content'])


def cameraControl(mode): 
    if mode == "on" and not camera.preview:
        camera.start_preview()
        camera.start_recording(output, format='mjpeg')
        print("recording started")
    elif mode == "off" and camera.preview:
        camera.stop_recording()
        camera.stop_preview()
        print("recording ended")


def handleMicrophoneListenControl(mode):
    if mode == "on":
        ap.StartPlaying()
        print("Playback Listening started")
    elif mode == "off":
        ap.StopPlaying()
        print("Playback Listening stopped")


def playDoorBellSound(sound_file, play): 
    if play is True:
         # Load the MP3 file
         pygame.mixer.music.load(sound_file)

         # Play the MP3 file
         pygame.mixer.music.play()
         print("played doorbell chime")


def handleButtonMode():
     playDoorBellSound(doorbell_sound_file_path, True)
     startCamera()


def handleMotionMode():
    playDoorBellSound(doorbell_sound_file_path, (not camera.preview))
    startCamera()


def startCamera():
    if not camera.preview: 
        cameraControl("on")
        client.publish(REMOTE_DEV_CAMERA_ONOFF_CONTROL_TOPIC, payload="on", qos=0, retain=False)


def stopCamera():
    if camera.preview: 
        cameraControl("off")
        client.publish(REMOTE_DEV_CAMERA_ONOFF_CONTROL_TOPIC, payload="off", qos=0, retain=False)  
          


def handleAudioTalk(msg):
    ffmpeg_process = subprocess.Popen(
        ['ffmpeg', '-i', 'pipe:0', '-vn', '-f', 'wav', '-acodec', 'pcm_s16le', '-ar', '44100', '-ac', '1', 'pipe:1'],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
    )
  
    audio_data, _ = ffmpeg_process.communicate(input=msg) 
    pygame.mixer.init(frequency=44100, size=-16, channels=1)

    # Load the audio data into a pygame mixer Sound object from the BytesIO stream
    audio_sound = pygame.mixer.Sound(audio_data)

    # Play the audio
    audio_sound.play()
    
    
def handleGPTRequest():
    # stopCamera()
    client.publish(GPT_RESPONSE_TOPIC, payload="waiting for the AI to Answer...", qos=0, retain=False)
    image_stream = io.BytesIO()
    camera.capture(image_stream, format='jpeg')
    image_stream.seek(0)

    # Convert the image to base64
    image_base64 = base64.b64encode(image_stream.getvalue()).decode('utf-8')
   
    # send the image to OpenAU for a description of whois at the door
    print("Asking OpenAI GPT-4 omni who is at the door....?")
    who_is_at_the_door = Open_AI_Tell_Me_Who_Is_There(image_base64)

    # Publish a message to the topic,  update the client side app 
    client.publish(GPT_RESPONSE_TOPIC, payload=who_is_at_the_door, qos=0, retain=False)
    print("sent message to broker")

    print("I see ..." + who_is_at_the_door)

    # Close the stream
    image_stream.close()


def on_message(client, userdata, msg):
    topic = msg.topic   
    print("Received Topic: " + topic) 
    if topic ==  REMOTE_APP_CAMERA_ONOFF_CONTROL_TOPIC:
        cameraControl(msg.payload.decode())
    elif topic == REMOTE_APP_MICROPHONE_CONTROL_TOPIC:
        handleMicrophoneListenControl(msg.payload.decode())
    elif topic == GPT_REQUEST_TOPIC:
        thread = threading.Thread(target=handleGPTRequest, daemon=True)
        thread.start()
    elif topic == REMOTE_APP_AUDIO_DATA_TOPIC:
        handleAudioTalk(msg.payload)


def on_disconnect(client, userdata, flags, rc, properties):
    logging.info("disconnecting reason  "  +str(rc))
    client.connected_flag=False
    client.disconnect_flag=True
    stopCamera()
        
def on_connect(client, userdata, flags, rc, properties):
    print("connected over web sockets: " + str(rc));    
    client.subscribe(REMOTE_APP_CAMERA_ONOFF_CONTROL_TOPIC)
    client.subscribe(GPT_REQUEST_TOPIC)   
    client.subscribe(REMOTE_APP_MICROPHONE_CONTROL_TOPIC)
    client.subscribe(REMOTE_APP_AUDIO_DATA_TOPIC)
    print("Subscribed to topics");  



REMOTE_APP_CAMERA_ONOFF_CONTROL_TOPIC = "ring/remote_app_control/camera"
REMOTE_DEV_CAMERA_ONOFF_CONTROL_TOPIC = "ring/local_dev_control/camera"

REMOTE_APP_MICROPHONE_CONTROL_TOPIC = "ring/remote_app_control/microphone"
REMOTE_APP_AUDIO_DATA_TOPIC = "ring/remote_app_audio_data"

GPT_RESPONSE_TOPIC = "ring/gptresponse"
GPT_REQUEST_TOPIC = "ring/gptrequest"

LISTEN_AUDIO_RESPONSE_TOPIC = "ring/audioresponse"

parser = argparse.ArgumentParser(description='\"Smart\" Doorbell server version v.0.9')
# parser.add_argument('hostname', type=str, help='specify hostname or IP address')
parser.add_argument('--mode', type=str, default="motion", help='motion | manual (\"manual\" is button activated,  \"motion\" is PIR sensor activated)')
parser.add_argument('--secure', type=str, default="off", help='off | on (off = http on = https')


args = parser.parse_args()

HTTP_SERVER_PORT = 8000
HTTPS_SERVER_PORT = 8001

BROKER_PORT=1883
SSL_BROKER_PORT=8883

host="127.0.0.1"
doorbell_sound_file_path = "./sounds/bell1.mp3"

BUTTON_GPIO_PIN=2
MOTION_SENSOR_GPIO_PIN=4

client = paho.Client(paho.CallbackAPIVersion.VERSION2, transport="tcp")
client.on_message = on_message;  
client.on_connect = on_connect

client.on_disconnect = on_disconnect

# Initialize pygame mixer
pygame.mixer.init()

button = Button(BUTTON_GPIO_PIN)
pir = MotionSensor(MOTION_SENSOR_GPIO_PIN)

if args.mode == "motion":
   pir.when_motion = handleMotionMode

button.when_pressed =  handleButtonMode

with picamera.PiCamera(resolution='1024x768', framerate=24) as camera:
    output = StreamingOutput()
    # camera.rotation = 180
   
    try:
        ap = AudioPlayback()
        ap.SetMQTTClient(client, LISTEN_AUDIO_RESPONSE_TOPIC)

        # streaming video (web server) address and port
        address = ('', HTTP_SERVER_PORT)
        if args.secure == "on":
            address = ('', HTTPS_SERVER_PORT)
      
        server = StreamingServer(address, StreamingHandler)   
        
        print("\"Smart\" Doorbell server started on port: " + str(address[1]))
        if args.secure == "on":   
            # 1. configure the Python HTTP server for HTTPS (TLS support)
            # wrap the TCP socket with an SSL support, then load the certs.
            server.socket  = ssl.wrap_socket (server.socket, 
                keyfile="./certs/ring_server.key", 
                certfile="./certs/ring_server.crt", 
                server_side=True)

            # uncomment to configure the MQTT python client to communicate with Broker over SSL
            # BROKER_PORT = SSL_BROKER_PORT   # 8883 is the TLS configured Port listener in the Broker)
            # client.tls_set("./certs/orion_ca.crt", "./certs/ring_server.crt", "./certs/ring_server.key" )
            # host = [IO-address]
        
        client.connect(host, BROKER_PORT, 60)   # establish connection
        client.loop_start()
        print("Connected to MQTT Broker on port " + str(BROKER_PORT) + " established")
 
        server.serve_forever()

    except KeyboardInterrupt:
        client.disconnect()
        client.loop_stop()
      
        print("MQTT broker connection shutdown")

        server.server_close()
        ap.Close()
        print("Web server shut down")
