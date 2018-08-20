#!/usr/bin/python3
"""Implementation of RDT4.0

functions: rdt_network_init, rdt_socket(), rdt_bind(), rdt_peer()
           rdt_send(), rdt_recv(), rdt_close()

Student name: Ish Handa
Student No. : 3035238565
Date and version: 09/04/18
Development platform: Ubuntu
Python version: Python 3.6
"""

import socket
import random
import math
import select
import sys
import struct
import time

#some constants
PAYLOAD = 1000		#size of data payload of each packet
CPORT = 6969			#Client port number - Change to your port number
SPORT = 7272			#Server port number - Change to your port number
TIMEOUT = 0.05		#retransmission timeout duration
TWAIT = 10*TIMEOUT 	#TimeWait duration

S = 0
next_seq_num = 0
expected_seq_num = 0

#store peer address info
__peeraddr = ()		#set by rdt_peer()
#define the error rates and window size
__LOSS_RATE = 0.0	#set by rdt_network_init()
__ERR_RATE = 0.0
__W = 1

#internal functions - being called within the module
def __udt_send(sockd, peer_addr, byte_msg):
	"""This function is for simulating packet loss or corruption in an unreliable channel.

	Input arguments: Unix socket object, peer address 2-tuple and the message
	Return  -> size of data sent, -1 on error
	Note: it does not catch any exception
	"""
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
	"""Retrieve message from underlying layer

	Input arguments: Unix socket object and the max amount of data to be received
	Return  -> the received bytes message object
	Note: it does not catch any exception
	"""
	(rmsg, peer) = sockd.recvfrom(length)
	return rmsg

def __IntChksum(byte_msg):
	"""Implement the Internet Checksum algorithm

	Input argument: the bytes message object
	Return  -> 16-bit checksum value
	Note: it does not check whether the input object is a bytes object
	"""
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


#These are the functions used by appliation

def rdt_network_init(drop_rate, err_rate, W):
	"""Application calls this function to set properties of underlying network.

    Input arguments: packet drop probability, packet corruption probability and Window size
	"""
	random.seed()
	global __LOSS_RATE, __ERR_RATE, __W
	__LOSS_RATE = float(drop_rate)
	__ERR_RATE = float(err_rate)
	__W = int(W)
	print("Drop rate:", __LOSS_RATE, "\tError rate:", __ERR_RATE, "\tWindow size:", __W)

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
    global next_seq_num, S, expected_seq_num
    N = 0
    S = next_seq_num
    k = 0
    chk_sum = 0
    type_id = 12
    if (len(byte_msg) == PAYLOAD):
        N = 1
    else:
    	N = math.ceil(float(len(byte_msg)/PAYLOAD))  #finding N to get no. of packets

    if (N==0): # if N is error, there is an error
        PRINT("N=0 ERROR")
        return -1

    for i in range(1,N+1):  #sending and allocating N packets and its msgs
        if i == N:
            msg = byte_msg[PAYLOAD*(i-1):]
        else:
            msg = byte_msg[PAYLOAD*(i-1):PAYLOAD*i]

        strct = 'BBHH' + str(len(msg)) + 's'
        message_format = struct.Struct(strct)
        payload_len = socket.htons(len(msg)) #maintaining byte order
        chk_sum = 0
        packet = message_format.pack(type_id,next_seq_num%256,chk_sum,payload_len,msg)
        chk_sum = __IntChksum(packet)
        packet = message_format.pack(type_id,next_seq_num%256,chk_sum,payload_len,msg)   #creating a packet with the required header

        try:
            length = __udt_send(sockd, __peeraddr, packet)  ##send the packet
        except socket.error as emsg:
            print("Socket send error: ", emsg)
            return -1
        print("rdt_send: Sent one message of size %d" % length)
        next_seq_num = next_seq_num + 1  #modulous
        if next_seq_num == 256:
            next_seq_num = 0

    sockd.settimeout(TIMEOUT)  # start timer
    while True:
        try:
            rmsg = __udt_recv(sockd, len(msg)+6) # try to reieve packet
        except socket.timeout:
            print("rdt_send: Timeout!! Retransmit the packets again, k=", k)
            for i in range(k,N+1):  #if timeout occurs, we will need to send N-k packets since k is no. of acked packets
                if i == N:
                    msg = byte_msg[PAYLOAD*(i-1):]
                else:
                    msg = byte_msg[PAYLOAD*(i-1):PAYLOAD*i]

                strct = 'BBHH' + str(len(msg)) + 's'
                message_format = struct.Struct(strct)
                payload_len = socket.htons(len(msg))
                chk_sum = 0
                type_id = 12
                old_seq = next_seq_num-(N-i+1) #getting the correct seq no. of the unacked packets
                packet = message_format.pack(type_id,old_seq%256,chk_sum,payload_len,msg)
                chk_sum = __IntChksum(packet)
                packet2 = message_format.pack(type_id,old_seq%256, chk_sum,payload_len,msg)   #creating a packet with the required header

                try:
                    length = __udt_send(sockd, __peeraddr, packet2)  ##send the packet
                except socket.error as emsg:
                    print("Socket send error: ", emsg)
                    return -1
                print("rdt_send: Sent one message of size %d" % length)
            sockd.settimeout(TIMEOUT)  # restart timer
            continue
        except socket.error as emsg:
            print("Socket recv error: ", emsg)
        #print("rdt_recv: Received a message of size %d" % len(rmsg))
        if __IntChksum(rmsg) != 0x0: # calculate the checksum
           print("rdt_send: Recieved a corrupted packet: Type = ACK, Length = %d" % len(rmsg))
           continue

        message_format2 = struct.Struct('BBHH%ds' % (int)(len(rmsg)-6))
        (type_id,sq_num,chk_sum,payload_len,ms) = message_format2.unpack(rmsg) #unpack the ack packet
        payload_len=socket.ntohs(payload_len)
        if type_id == 11: # if ack then enter
            if (sq_num == (S+N-1)%256):
                sockd.settimeout(None) # stop the timer
                return len(byte_msg)
            elif(sq_num >= S or sq_num <= S+N-2):  #mainitng the value of acked packets incase of packet loss or corruption
                if (sq_num > k):
                    k = (sq_num-S+1)%256
                    print("rdt_send: Recieved correct Ack with seq no.=",sq_num)
                else:
                    k = (sq_num-S+1)%256
                    print("rdt_send: Recieved wrong ACK with seq no.=",sq_num)
                    continue
            else:
                print("rdt_send: Recieved Out of range ACK...discarding")
                continue
        elif type_id == 12:  #if recieved an unexpected packet, send ack with expected_seq_num-1
            type_id = 11
            chk_sum = 0
            message_format2 = struct.Struct('BBHH')
            seq = expected_seq_num-1
            ACK = message_format2.pack(type_id,seq%256,chk_sum,payload_len)
            chk_sum = __IntChksum(ACK)
            ACK = message_format2.pack(type_id,seq%256,chk_sum,payload_len)
            try:
                length_ack = __udt_send(sockd, __peeraddr, ACK)
            except socket.error as emsg:
                print("Socket send error: ", emsg)
                return -1


def rdt_recv(sockd, length):
    global PAYLOAD, __peeraddr
    global expected_seq_num, next_seq_num
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
        payload_len = socket.ntohs(payload_len)

        if __IntChksum(rmsg) != 0x0: # check for checksum
            print("rdt_rcv: Recieved corrupt Packet Type = Data, Length = %d" % len(rmsg))
            continue

        if type_id == 12:
            if sq_num == expected_seq_num:
                print("rdt_rcv: Got an expected Packet with seq no.=",sq_num)
                type_id = 11
                chk_sum = 0
                message_format2 = struct.Struct('BBHH')
                ACK = message_format2.pack(type_id,sq_num%256,chk_sum,payload_len)
                chk_sum = __IntChksum(ACK)
                ACK = message_format2.pack(type_id,sq_num%256,chk_sum,payload_len)
                try:
                    length_ack = __udt_send(sockd, __peeraddr, ACK) #send ack for recieveing pack succesfully
                except socket.error as emsg:
                    print("Socket send error: ", emsg)
                    return -1
                #print("rdt_send: Sent one message of size %d" % length_ack)
                expected_seq_num = expected_seq_num + 1
                if expected_seq_num == 256:
                    expected_seq_num = 0

                return msg # return the msg content to file for it to be written in the save file
            else:
                type_id = 11
                chk_sum = 0
                message_format2 = struct.Struct('BBHH')
                ack_seq = expected_seq_num-1
                ACK = message_format2.pack(type_id,ack_seq%256,chk_sum,payload_len)
                chk_sum = __IntChksum(ACK)
                ACK = message_format2.pack(type_id,ack_seq%256,chk_sum,payload_len)
                try:
                    length_ack = __udt_send(sockd, __peeraddr, ACK) # if incorrect state, send ack to tell client to resend the packet
                except socket.error as emsg:
                    print("Socket send error: ", emsg)
                    return -1
                print("rdt_recv: Sent one message of size %d" % length_ack)
        else:
            continue # if ack recieved in the first place then ignore


def rdt_close(sockd):
    global PAYLOAD, __peeraddr, expected_seq_num

    while True:
        sockd.settimeout(TWAIT) # start timer
        try:
            rmsg = __udt_recv(sockd, 1000+6)
        except socket.timeout: # if timeout happens close the socket
            try:
                print("rdt_close: Nothing happened for 0.500 second")
                sockd.close()
                print("rdt_close: Release the socket")
                return 0
            except socket.error as emsg:
                print("Socket close error: ", emsg)
        except socket.error as emsg:
            print("Socket recv error: ", emsg)
        print("rdt_close: Received a message of size %d" % len(rmsg))
        strct = 'BBHH'+ str(len(rmsg)-6)+'s'
        message_format = struct.Struct(strct)
        (type_id,sq_num, chk_sum,payload_len, msg) = message_format.unpack(rmsg) # if a packet is recevied then un pack it
        payload_len=socket.ntohs(payload_len)

        if __IntChksum(rmsg) != 0x0: # check for checksum
            print("rdt_rcv: Recieved corrupt Packet Type = Data, Length = %d" % len(rmsg))
            continue
        if type_id == 12: # check if packet contains data
            sockd.settimeout(None)
            #print("recieving last packet")
            print("rdt_close: Got an expected Packet with seq no.=",sq_num)
            type_id = 11
            chk_sum = 0
            last_seq = expected_seq_num-1
            message_format2 = struct.Struct('BBHH')
            ACK = message_format2.pack(type_id,last_seq%256,chk_sum,payload_len)
            chk_sum = __IntChksum(ACK)
            ACK = message_format2.pack(type_id,last_seq%256,chk_sum,payload_len)
            try:
                length_ack = __udt_send(sockd, __peeraddr, ACK) #send ack for recieveing pack succesfully
            except socket.error as emsg:
                print("Socket send error: ", emsg)
                return -1
