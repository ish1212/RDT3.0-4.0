#!/usr/bin/python3
"""Implementation of RDT3.0

functions: rdt_network_init(), rdt_socket(), rdt_bind(), rdt_peer()
           rdt_send(), rdt_recv(), rdt_close()

Student name: Ish Handa
Student No. : 3035238565
Date and version: 14/03/18
Development platform: Ubuntu
Python version: 3.5
"""

import socket
import random
import select
import sys
import struct
import time

#some constants
PAYLOAD = 1000		#size of data payload of the RDT layer
CPORT = 6969			#Client port number - Change to your port number
SPORT = 4242			#Server port number - Change to your port number
TIMEOUT = 0.05		#retransmission timeout duration
TWAIT = 10*TIMEOUT 	#TimeWait duration
snd_state = 0       #initializing states to check for duplicacy
rcv_state = 0

#store peer address info
__peeraddr = ()		#set by rdt_peer()
#define the error rates
__LOSS_RATE = 0.0	#set by rdt_network_init()
__ERR_RATE = 0.0


#internal functions - being called within the module
def __udt_send(sockd, peer_addr, byte_msg):
	global __LOSS_RATE, __ERR_RATE
	if peer_addr == ():
		print("Socket send error: Peer address not set yet")
		return -1
	else:
		#Simulate packet loss
		drop = random.random()
		if drop < __LOSS_RATE:
			#simulate packet loss of unreliable send
			print("WARNING: udt_send: Packet lost in unreliable layer!!")
			return len(byte_msg)

		#Simulate packet corruption
		corrupt = random.random()
		if corrupt < __ERR_RATE:
			err_bytearr = bytearray(byte_msg)
			pos = random.randint(0,len(byte_msg)-1)
			val = err_bytearr[pos]
			if val > 1:
				err_bytearr[pos] -= 2
			else:
				err_bytearr[pos] = 254
			err_msg = bytes(err_bytearr)
			print("WARNING: udt_send: Packet corrupted in unreliable layer!!")
			return sockd.sendto(err_msg, peer_addr)
		else:
			return sockd.sendto(byte_msg, peer_addr)


def __udt_recv(sockd, length):
	(rmsg, peer) = sockd.recvfrom(length)
	return rmsg


def __IntChksum(byte_msg):
	total = 0
	length = len(byte_msg)	#length of the byte message object
	i = 0
	while length > 1:
		total += ((byte_msg[i+1] << 8) & 0xFF00) + ((byte_msg[i]) & 0xFF)
		i += 2
		length -= 2

	if length > 0:
		total += (byte_msg[i] & 0xFF)

	while (total >> 16) > 0:
		total = (total & 0xFFFF) + (total >> 16)

	total = ~total

	return total & 0xFFFF


def rdt_network_init(drop_rate, err_rate):
	random.seed()
	global __LOSS_RATE, __ERR_RATE
	__LOSS_RATE = float(drop_rate)
	__ERR_RATE = float(err_rate)
	print("Drop rate:", __LOSS_RATE, "\tError rate:", __ERR_RATE)


def rdt_socket():
	try:
		sd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	except socket.error as emsg:
		print("Socket creation error: ", emsg)
		return None
	return sd


def rdt_bind(sockd, port):
	try:
		sockd.bind(("",port))
	except socket.error as emsg:
		print("Socket bind error: ", emsg)
		return -1
	return 0


def rdt_peer(peer_ip, port):
	global __peeraddr
	__peeraddr = (peer_ip, port)


def rdt_send(sockd, byte_msg):
    global PAYLOAD, __peeraddr
    global snd_state
    chk_sum = 0
    type_id = 12
    if (len(byte_msg) > PAYLOAD):
    	msg = byte_msg[0:PAYLOAD]
    else:
    	msg = byte_msg
    strct = 'BBHH' + str(len(msg)) + 's'
    message_format = struct.Struct(strct)
    payload_len = len(msg)
    packet = message_format.pack(type_id,snd_state,chk_sum,payload_len,msg)
    chk_sum = __IntChksum(packet)
    packet = message_format.pack(type_id,snd_state,chk_sum,payload_len,msg)   #creating a packet with the required header
    #print("The message (raw):", packet)
    while True:
        try:
            length = __udt_send(sockd, __peeraddr, packet)  ##send the packet
        except socket.error as emsg:
            print("Socket send error: ", emsg)
            return -1
        print("rdt_send: Sent one message of size %d" % length);
        sockd.settimeout(TIMEOUT)  # start timer
        try:
            rmsg = __udt_recv(sockd, len(msg)+6) # try to reieve packet
        except socket.timeout:
            print("rdt_send: Timeout!! Retransmit the packet %d again" % snd_state)  # if there is timeout, wait for packet to retransmit
            continue
        except socket.error as emsg:
            print("Socket recv error: ", emsg)
        #print("rdt_recv: Received a message of size %d" % len(rmsg))
        sockd.settimeout(None) #end timer
        if __IntChksum(rmsg) != 0x0: # calculate the checksum
           print("rdt_send: Recieved a corrupted packet: Type = DATA, Length = %d" % len(rmsg))
           continue
        message_format2 = struct.Struct('BBHH')
        (type_id,sq_num,chk_sum,payload_len) = message_format2.unpack(rmsg) #unpack the ack packet
        if type_id == 11: # if ack then enter
            print("rdt_send: Recieved the expected ACK")
            if sq_num == snd_state:  # update the global variables to alternate states # this is done to check for duplicacy with previous message
                if snd_state == 1:
                    snd_state = 0
                else:
                    snd_state = 1
                return length-6
            else:
                continue # if state is different, retransmit packet
        else:
            print("rdt_send: Retransmit %d packet again" % snd_state) #if it is a data then send another packet


def rdt_recv(sockd, length):
    global PAYLOAD, __peeraddr
    global rcv_state
    while True:
        try:
            rmsg = __udt_recv(sockd,length+6) # recieve the package
        except socket.error as emsg:
            print("Socket recv error: ", emsg)
        print("rdt_recv: Received a message of size %d" % len(rmsg))
        msg_size = (len(rmsg)-6)
        form = 'BBHH'+str(msg_size)+'s'
        message_format = struct.Struct(form)
        (type_id,sq_num,chk_sum,payload_len,msg) = message_format.unpack(rmsg) #unpack the header and the message
        if __IntChksum(rmsg) != 0x0: # check for checksum
            print("rdt_rcv: Recieved a corrupted packet: Type = DATA, Length = %d" % len(rmsg))
            print("rdt_rcv: Drop the packet")
            type_id = 11
            if rcv_state == 0:
                sq_num = 1
            else:
                sq_num = 0
            message_format2 = struct.Struct('BBHH')
            chk_sum = 0
            ACK = message_format2.pack(type_id,sq_num,chk_sum,payload_len)
            chk_sum = __IntChksum(ACK)
            ACK = message_format2.pack(type_id,sq_num,chk_sum,payload_len)
            try:
                length_ack = __udt_send(sockd, __peeraddr, ACK) # send prev ack so that the client would retransmit the package
            except socket.error as emsg:
                print("Socket send error: ", emsg)
                return -1
            #print("rdt_send: Sent one message of size %d" % length_ack)
            continue
        if type_id == 12:
            print("rdt_rcv: Got an expected Packet")
            if sq_num == rcv_state:
                type_id = 11
                chk_sum = 0
                message_format2 = struct.Struct('BBHH')
                ACK = message_format2.pack(type_id,sq_num,chk_sum,payload_len)
                chk_sum = __IntChksum(ACK)
                ACK = message_format2.pack(type_id,sq_num,chk_sum,payload_len)
                try:
                    length_ack = __udt_send(sockd, __peeraddr, ACK) #send ack for recieveing pack succesfully
                except socket.error as emsg:
                    print("Socket send error: ", emsg)
                    return -1
                #print("rdt_send: Sent one message of size %d" % length_ack)
                if rcv_state == 1: #update the recieve states to avoid duplicacy
                    rcv_state = 0
                else:
                    rcv_state = 1
                return msg # return the msg content to file for it to be written in the save file
            else:
                type_id = 11
                chk_sum = 0
                message_format2 = struct.Struct('BBHH')
                ACK = message_format2.pack(type_id,sq_num,chk_sum,payload_len)
                chk_sum = __IntChksum(ACK)
                ACK = message_format2.pack(type_id,sq_num,chk_sum,payload_len)
                try:
                    length_ack = __udt_send(sockd, __peeraddr, ACK) # if incorrect state, send ack to tell client to resend the packet
                except socket.error as emsg:
                    print("Socket send error: ", emsg)
                    return -1
                print("rdt_send: Sent one message of size %d" % length_ack)
        else:
            continue # if ack recieved in the first place then ignore


def rdt_close(sockd):
    global PAYLOAD, __peeraddr
    sockd.settimeout(TWAIT) # start timer
    try:
        rmsg = __udt_recv(sockd, 1000+6)
    except socket.timeout: # if timeout happens close the socket
        try:
            print("rdt_close: Nothing happened for 0.500 second")
            sockd.close()
            print("rdt_close: Release the socket")
            return
        except socket.error as emsg:
            print("Socket close error: ", emsg)
    except socket.error as emsg:
        print("Socket recv error: ", emsg)
    print("rdt_recv: Received a message of size %d" % len(rmsg))
    strct = 'BBHH'+ str(len(rmsg)-6)+'s'
    message_format = struct.Struct(strct)
    (type_id,sq_num, chk_sum,payload_len, msg) = message_format.unpack(rmsg) # if a packet is recevied then un pack it
    if type_id == 12: # check if packet contains data
        sockd.settimeout(None)
        #print("recieving last packet")
        type_id = 11
        chk_sum = 0
        message_format2 = struct.Struct('BBHH')
        ACK = message_format2.pack(type_id,sq_num, chk_sum,payload_len)
        chk_sum = __IntChksum(ACK)
        ACK = message_format2.pack(type_id,sq_num, chk_sum,payload_len)
        try:
            length = __udt_send(sockd, __peeraddr, ACK) # if yes then send last ack for the last data packet
        except socket.error as emsg:
            print("Socket send error: ", emsg)
            return -1
        print("rdt_send: Sent one message of size %d" % length)
    sockd.settimeout(None) # stop the timer
