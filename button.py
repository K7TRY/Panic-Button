#!/usr/bin/env python

import os
import sys
import threading
import RPi.GPIO as GPIO
from datetime import datetime
from time import sleep
import smtplib
import base64
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
import urllib2
import pjsua as pj # To build the pjsua module see https://trac.pjsip.org/repos/wiki/Python_SIP/Build_Install

###################################################
## Edit the variables below to suite your needs. ##
###################################################

#GPIO
buttonPin = 23

## Email
fromAddress = ''
toAddress = ''
mailSubject = 'TEST PANIC ALERT!! ' + datetime.now().strftime('%I:%M %p %m/%d/%Y')
mailCamPicName = 'frontDeskCam.png'
mailSMTP = ''

## Webcam
webcamUrl = ''
webcamUserName = ''
webcamPass = ''

## SIP Phone Call
# Edit the callDestExt Array to change which extensions to dial. They're strings!
callDestExt = ""
playWavFile = '/home/pi/panic.wav'
sipId = ''
sipPassword = ''
sipRegistrar = ''
callDestURI = 'sip:' + callDestExt + '@' + sipRegistrar

## End of user configurable global variables ##
running = True
callInstance = {} # Leave empty
buttonPressed = False

def getCamImage():
	imgRequest = urllib2.Request(webcamUrl)
	
	base64string = base64.b64encode('%s:%s' % ('mafcam', 'mafcam'))
	imgRequest.add_header("Authorization", "Basic %s" % base64string)
	
	return urllib2.urlopen(imgRequest).read()

class t_sendEmail(threading.Thread):
	def run ( self ):
		camImage = getCamImage()
		msg = MIMEMultipart()

		msg['Subject'] = mailSubject
		msg['From'] = fromAddress
		msg['To'] = toAddress
		msg.Importance = 2
		
		msg.add_header("X-Priority", "1 (Highest)")
		msg.add_header("X-MSMail-Priority", "High")
		msg.add_header("Importance", "High")
		msg.add_header("Urgency", "High")
		
		# Put the text into the email message.
		fp = open('alert.txt', 'r')
		msgTxt = fp.read()
		msg.preamble = msgTxt
		text = MIMEText(msgTxt)
		msg.attach(text)
		fp.close()
		
		image = MIMEImage(camImage, name=os.path.basename(mailCamPicName))
		msg.attach(image)
		
		s = smtplib.SMTP(mailSMTP)
		s.sendmail(fromAddress, toAddress, msg.as_string())
		s.quit()

###############################################
## CALL BACK FUNCTIONS AND CLASSES FOR PJSUA ##
###############################################
# define a function to print out call back logs to the terminal
def log_cb(level,str,len):
    print str

# Callback to receive events from Call
class MyCallCallback(pj.CallCallback):
    def __init__(self, call=None):
        pj.CallCallback.__init__(self, call)

    # Notification when call state has changed
    def on_state(self):
        print "Call is ", self.call.info().state_text,
        print "last code =", self.call.info().last_code,
        print "(" + self.call.info().last_reason + ")"

    # Notification when calls media state has changed.
    def on_media_state(self):
        # Connect egress and regress channels to each other
        global lib
        global wav_player

        if self.call.info().media_state == pj.MediaState.ACTIVE:
            # Set the media player to play at the beginning of the file
            lib.player_set_pos(wav_player,0)

            # Connect the call to sound device
            call_slot = self.call.info().conf_slot
            lib.conf_connect(wav_slot,call_slot)

# Define AccountCallback Class for Registrations
class MyAccountCallback(pj.AccountCallback):
	sem = None

	def __init__(self, account=None):
		pj.AccountCallback.__init__(self, account)

	# On incoming calls to defined acct, display message to terminal
	def on_incoming_call(self, call):
		call.hangup(501, "Sorry, not ready to accept calls yet")

    # Output the registration status on register status change
	def on_reg_state(self):
		print 'Registration status = ', self.account.info().reg_status, '(' + self.account.info().reg_reason + ')'
	
	def wait(self):
		self.sem = threading.Semaphore(0)
		self.sem.acquire()
		
def callPhones():
	print('Attempting to call ' + callDestURI)
	try:
		callInstance = acc.make_call(callDestURI, cb=MyCallCallback())
	except pj.Error:
		print("Error making outgoing call:",pj.Error)
#	except:
#		print("Major error in making the SIP call")
	print("Call made")

	sleep(240)
	lib.hangup_all()

def setupGpio():
	########################
	## GPIO INITIAL SETUP ##
	########################

	GPIO.setmode(GPIO.BCM)
	GPIO.setup(buttonPin, GPIO.IN, pull_up_down = GPIO.PUD_UP)
	#GPIO.add_event_detect(buttonPin, GPIO.RISING, callback=buttonPushed, bouncetime=4800)

setupGpio()
#########################
## PJSUA LIBRARY SETUP ##
#########################
lib = pj.Lib()
# Init library with verbose level 3 and callback log function
# Verbosity goes from level 1 (lowest) to 7 (highest)
lib.init(log_cfg = pj.LogConfig(level=3, callback=log_cb))

# Set the library to not send audio through any physical devices
lib.set_null_snd_dev()

transport = lib.create_transport(pj.TransportType.UDP)

lib.start()

wav_player = lib.create_player(playWavFile,loop=True)
wav_slot = lib.player_get_slot(wav_player)

acc_cfg = pj.AccountConfig()
acc_cfg.reg_uri = 'sip:' + sipRegistrar
acc_cfg.id = 'sip:' + sipId + '@' + sipRegistrar
acc_cfg.auth_cred = [pj.AuthCred('*', sipId ,sipPassword)]

acc_cb = MyAccountCallback()
acc = lib.create_account(acc_cfg, cb=acc_cb)

while ((str(acc.info().reg_status) != "200") or (str(acc.info().reg_status) == "403")):
	print('Waiting to register.')
	sleep(5)
		
try:
	while running:
		print('Panic button program is running.')
		GPIO.wait_for_edge(buttonPin, GPIO.FALLING)
		
		if buttonPressed == False:
			buttonPressed = True
			print('The Panic Button was pressed!!')
			
			# Start the email task on a new thread.
			t = t_sendEmail()
			t.start()
			
			callPhones() # This has to be on the main thread.
			
			buttonPressed = False
		

except KeyboardInterrupt:
	running = False
	print('Program terminated.')

GPIO.cleanup()

lib.hangup_all()
lib.destroy()
lib = None
transport = None
acc_cb = None
