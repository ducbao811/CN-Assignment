from tkinter import *
import tkinter.messagebox
tkinter.messagebox
from tkinter import messagebox 
tkinter.messagebox
from PIL import Image, ImageTk
import socket, threading, sys, traceback, os
import time
from RtpPacket import RtpPacket


class Client:

	INIT = 0
	READY = 1
	PLAYING = 2
	state = INIT
	
	SETUP = 0
	PLAY = 1
	PAUSE = 2
	TEARDOWN = 3
	DESCRIBE = 4
	
	RTSP_VER = "RTSP/1.0"
	TRANSPORT = "RTP/UDP"
	
 
	# Constructor
	def __init__(self, master, serveraddr, serverport, rtpport, filename):
		self.master = master
		self.master.protocol("WM_DELETE_WINDOW", self.handler)
		self.createWidgets()
		self.serverAddr = serveraddr
		self.serverPort = int(serverport)
		self.rtpPort = int(rtpport)
		self.fileName = filename
		self.rtspSeq = 0
		self.sessionId = 0
		self.requestSent = -1
		self.teardownAcked = 0
		self.connectToServer()
		self.frameNbr = 0
		# Statistic
		self.statDataRate = 0
		self.statTotalBytes = 0
		self.statStartTime = 0
		self.statTotalPlayTime = 0
		self.statFractionLost = 0
		self.statCumLost = 0
		self.statExpectedRptNbr = 0
		self.statHighestSeq = 0

		
	def createWidgets(self):
		"""Build GUI."""
		frame = Frame(self.master)
		frame.pack()
		bottomPFrame = Frame(frame)
		bottomPFrame.pack(side=BOTTOM)
		bottomFrame = Frame(bottomPFrame)
		bottomFrame.pack(side = TOP)
		# Create Setup button
		self.setup = Button(bottomFrame, width=20, padx=10, pady=10)
		self.setup["text"] = "Setup"
		self.setup["command"] = self.setupMovie
		self.setup.pack(side=LEFT)
		
		# Create Play button		
		self.start = Button(bottomFrame, width=20, padx=10, pady=10)
		self.start["text"] = "Play"
		self.start["command"] = self.playMovie
		self.start.pack(side=LEFT)
		
		# Create Pause button			
		self.pause = Button(bottomFrame, width=20, padx=10, pady=10)
		self.pause["text"] = "Pause"
		self.pause["command"] = self.pauseMovie
		self.pause.pack(side=LEFT)
		
		# Create Teardown button
		self.teardown = Button(bottomFrame, width=20, padx=10, pady=10)
		self.teardown["text"] = "Teardown"
		self.teardown["command"] =  self.exitClient
		self.teardown.pack(side=LEFT)

		# Create Describe button
		self.teardown = Button(bottomFrame, width=20, padx=10, pady=10)
		self.teardown["text"] = "Describe"
		self.teardown["command"] =  self.describeMovie
		self.teardown.pack(side=LEFT)

		# Create a label to display the movie

		self.label = Label(frame,height=20)
		self.label.pack(side=LEFT,expand=TRUE)

		# Stat label to display the statistic
		self.dataRate = StringVar()
		self.dataRate.set('Total Bytes Received: 0 Packet Lost Rate: 0 Data Rate: 0')
		self.statLabel1 = Label(bottomPFrame, textvariable=self.dataRate)
		self.statLabel1.pack(side=LEFT)
	
	def setupMovie(self):
		"""Setup button handler."""
		if self.state == self.INIT:
			self.sendRtspRequest(self.SETUP)
	
	def exitClient(self):
		"""Teardown button handler."""
		self.sendRtspRequest(self.TEARDOWN)		
		self.master.destroy() # Close the GUI window
		os.remove("cache-{}.jpg".format(self.sessionId)) # Delete the cache image from video

	def pauseMovie(self):
		"""Pause button handler."""
		if self.state == self.PLAYING:
			self.sendRtspRequest(self.PAUSE)
	
	def playMovie(self):
		"""Play button handler."""
		if self.state == self.READY:
			# Create a new thread to listen for RTP packets
			threading.Thread(target=self.listenRtp).start()
			self.playEvent = threading.Event()
			self.playEvent.clear()
			self.sendRtspRequest(self.PLAY)
	
	def describeMovie(self):
		"""Describe button handler"""
		if self.state != self.INIT:
			self.sendRtspRequest(self.DESCRIBE)

	def listenRtp(self):		
		"""Listen for RTP packets."""
		while True:
			try:
				print("LISTENING...")
				data = self.rtpSocket.recv(20480)
				if data:
					rtpPacket = RtpPacket()
					rtpPacket.decode(data)
					currFrameNbr = rtpPacket.seqNum()
					print ("CURRENT SEQUENCE NUM: " + str(currFrameNbr))
					if currFrameNbr > self.frameNbr:
						self.frameNbr = currFrameNbr
						self.updateMovie(self.writeFrame(rtpPacket.getPayload()))
					currTime = int(round(time.time() * 1000))
					self.statTotalPlayTime += currTime - self.statStartTime
					self.statStartTime = currTime
					self.statExpectedRptNbr += 1
					if currFrameNbr > self.statHighestSeq:
						self.statHighestSeq = currFrameNbr
					if self.statExpectedRptNbr != currFrameNbr:
						self.statCumLost += 1
					if self.statTotalPlayTime == 0:
						self.statDataRate = 0
					else:
						self.statDataRate = self.statTotalBytes / (self.statTotalPlayTime / 1000.0)
					self.statFractionLost = float(self.statCumLost / self.statHighestSeq)
					self.statTotalBytes += rtpPacket.getPayLoadSize()
					self.updateStatLabel()
			except:
				# Stop listening upon requesting PAUSE or TEARDOWN
				if self.playEvent.isSet(): 
					break
				
				# Upon receiving ACK for TEARDOWN request,
				# close the RTP socket
				if self.teardownAcked == 1:
					self.rtpSocket.shutdown(socket.SHUT_RDWR)
					self.rtpSocket.close()
					break
					
	def writeFrame(self, data):
		"""Write the received frame to a cache image file. Return the cache image file."""
		cacheFile = "cache-{}.jpg".format(self.sessionId)
		file = open(cacheFile, "wb")
		file.write(data)
		file.close()
		return cacheFile

	def updateStatLabel(self):
		self.dataRate.set("Total Bytes Received: {} Packet Lost Rate: {} Data Rate: {}".format(self.statTotalBytes, self.statFractionLost, self.statDataRate))
	
	def updateMovie(self, imageFile):
		"""Update the image file as video frame in the GUI."""
		photo = ImageTk.PhotoImage(Image.open(imageFile))
		self.label.configure(image = photo, height=400) 
		self.label.image = photo
		
	def connectToServer(self):
		"""Connect to the Server. Start a new RTSP/TCP session."""
		self.rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		try:
			self.rtspSocket.connect((self.serverAddr, self.serverPort))
		except:
			messagebox.showwarning('Connection Failed', 'Can not connect to {}'.format(self.serverAddr))
	
	def sendRtspRequest(self, requestCode):
		"""Send RTSP request to the server."""	
		
		# Setup request
		if requestCode == self.SETUP and self.state == self.INIT:
	  
			threading.Thread(target=self.recvRtspReply).start()
				
			# Update RTSP sequence number.
			self.rtspSeq+=1
			# Write the RTSP request
			request = "SETUP {} {}\nCSeq: {}\nTransport: {}; client_port= {}".format(self.fileName,self.RTSP_VER, self.rtspSeq, self.TRANSPORT,self.rtpPort)
			# Keep track of the sent request.
			self.requestSent = self.SETUP
			
		# Play request
		elif requestCode == self.PLAY and self.state == self.READY:
		
			# Update RTSP sequence number.
			self.rtspSeq+=1
		
			# Write the RTSP request 
			request = "PLAY {} {}\nCSeq: {}\nSession: {}".format(self.fileName,self.RTSP_VER,self.rtspSeq,self.sessionId)
			
			# Keep track of the sent request.
			self.requestSent = self.PLAY
			
			
		# Pause request
		elif requestCode == self.PAUSE and self.state == self.PLAYING:
		
			# Update RTSP sequence number.
			self.rtspSeq+=1
			
			# Write the RTSP request
			request = "PAUSE {} {}\nCSeq: {}\nSession: {}".format(self.fileName,self.RTSP_VER,self.rtspSeq, self.sessionId)
			
			# Keep track of the sent request.
			self.requestSent = self.PAUSE
			
		# Teardown request
		elif requestCode == self.TEARDOWN and not self.state == self.INIT:
		
			# Update RTSP sequence number.
			self.rtspSeq+=1
			
			# Write the RTSP request 
			request = "TEARDOWN {} {}\nCSeq: {}\nSession: {}".format(self.fileName, self.RTSP_VER, self.rtspSeq, self.sessionId)
			 	
			# Keep track of the sent request.
			self.requestSent = self.TEARDOWN

		elif requestCode == self.DESCRIBE and not self.state == self.INIT:
    
			# Update RTSP sequence number.
			self.rtspSeq+=1

			# Write the RTSP request
			request = "DESCRIBE Application/sdp {} {}\nCSeq: {}\nSession: {}".format(self.fileName, self.RTSP_VER, self.rtspSeq, self.sessionId)

			# Keep track of the sent request
			self.requestSent = self.DESCRIBE

		else:
			return
		
		# Send the RTSP request using rtspSocket.
		self.rtspSocket.send(request.encode("utf-8"))		
		print(request)
	
	def recvRtspReply(self):
		"""Receive RTSP reply from the server."""
		while True:
			reply = self.rtspSocket.recv(1024)
			
			if reply: 
				self.parseRtspReply(reply.decode("utf-8"))
			
			# Close the RTSP socket when sending TEARDOWN request
			if self.requestSent == self.TEARDOWN:
				self.rtspSocket.shutdown(socket.SHUT_RDWR)
				self.rtspSocket.close()
				break
	
	def parseRtspReply(self, data):
		"""Parse the RTSP reply from the server."""
		lines = data.split('\n')
		sequenceNumber = int(lines[1].split(' ')[1])
		# Process only if the server reply's sequence number is the same as the request's
		if sequenceNumber == self.rtspSeq:
			session = int(lines[2].split(' ')[1])
			# New RTSP session ID
			if self.sessionId == 0:
				self.sessionId = session
			
			# Process only if the session ID is the same
			if self.sessionId == session:
				if int(lines[0].split(' ')[1]) == 200: 
					if self.requestSent == self.SETUP:
						
						# Update RTSP state.
						self.state = self.READY
						
						# Open RTP port.
						self.openRtpPort() 
	  
					elif self.requestSent == self.PLAY:
						self.state = self.PLAYING
	  
					elif self.requestSent == self.PAUSE:
						self.state = self.READY
						
						# The play thread exits. A new thread is created on resume.
						self.playEvent.set()
	  
					elif self.requestSent == self.TEARDOWN:
						self.state = self.INIT
						
						# Flag the teardownAcked to close the socket.
						self.teardownAcked = 1
					
					elif self.requestSent == self.DESCRIBE:
						for i in range (4, len(lines)):
							print(lines[i])
	
	def openRtpPort(self):
		"""Open RTP socket and bind its to a specified port."""
		
		# Create a new datagram socket to receive RTP packets from the server
		self.rtpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
			
		# Set the timeout value of the socket to 0.5sec
		self.rtpSocket.settimeout(0.5)
		
		try:
			# Bind the socket to the address using the RTP port given by the client user.
			self.state=self.READY
			self.rtpSocket.bind(('',self.rtpPort))
		except:
			messagebox.showwarning('Unable to Bind', 'Unable to bind PORT={}'.format(self.rtpPort))

	def handler(self):
		"""Handler on intentionally closing the GUI."""
		self.pauseMovie()
		if messagebox.askokcancel("Quit?", "Are you sure you want to quit?"):
			self.exitClient()
		else: # When the user presses cancel, resume playing.
			self.playMovie()
	
	def changeLabel(self):
		self.dataRateLabel.set(self.statDataRate)
