#!/usr/bin/env python

import os
import sys
import math
from datetime import datetime, timedelta
from time import sleep
     
class Linkset():
    def __init__(self, lsn, hard, active):
        self.lsn = lsn
        self.hard = hard
        self.active = active
        self.members = {}
        
class ETI():
    def __init__(self):
        self.frame_count = 0
        self.lto = None
        self.time_now = None
        self.time_long = False
        self.eti_frame = 0
        self.last_timestamp = None
        self.timestamp_confidence = False
        self.linksets = {}
        
    def update_time(self, now):
        if self.time_long:
            self.time_now = now
        else:
            if self.time_now == now:
                return
            if self.time_now and not self.timestamp_confidence:
                self.timestamp_confidence = True
            self.time_now = now
            self.last_timestamp = self.frame_count
            
    def increment_frame_count(self):
        self.frame_count += 1
        
    def check_linkset_actuator(self, link_set_number, soft_hard, link_actuator):
        if not soft_hard:
                soft_hard_label = "S"
        else:
            soft_hard_label = "H"
        if link_actuator:
            link_actuator_label = "Active"
        else:
            link_actuator_label = "Inactive"
        linkset_key = "%X%s" % (link_set_number, soft_hard_label)
        if not self.linksets.has_key(linkset_key):
            linkset = Linkset(link_set_number, soft_hard, link_actuator)
            self.linksets[linkset_key] = linkset
            self.send_message("First occurance of linkset %s (%s)" % (linkset_key, link_actuator_label))
        else:
            if self.linksets[linkset_key].active == link_actuator:
                return
            self.linksets[linkset_key].active = link_actuator    
            self.send_message("Setting linkset %s to %s" % (linkset_key, link_actuator_label))
            
    def update_link_set_members(self, link_set_number, soft_hard, qualifier, id_list):
        updated = False
        if not soft_hard:
                soft_hard_label = "S"
        else:
            soft_hard_label = "H"
        linkset_key = "%X%s" % (link_set_number, soft_hard_label)
        linkset = self.linksets[linkset_key]
        if not linkset.members.has_key(qualifier):
            linkset.members[qualifier] = []
        for id in id_list:
            if id not in linkset.members[qualifier]:
                linkset.members[qualifier].append(id)
                updated = True
        if updated:
            message =  "Updated members of link set %s: " % linkset_key
            sub_messages = []
            for qualifier in linkset.members:
                sub_messages.append("%s - %s " % (qualifier, ", ".join(linkset.members[qualifier])))
            message += ", ".join(sub_messages)
            self.send_message(message)
                
    def send_message(self, message):
        eti_time = str(timedelta(seconds = (self.frame_count * (24.0 / 1000))))
        if not self.time_now:
            broadcast_time = "unknown"
        else:
            frame_offset = self.frame_count - self.last_timestamp
            if self.timestamp_confidence:
                broadcast_time = self.time_now + timedelta(seconds = (frame_offset * (24.0 / 1000)))
            else:
                broadcast_time = "Approx %s" % self.time_now
        print "%s\t%s\t%s\t%s" % (self.frame_count, eti_time, broadcast_time, message)
     
class Parser():
    def __init__(self):
        self.eti = ETI()
        self.fic_length = 24 # words (1 word = 4 bytes)

    def process_frame(self, frame):
        # Frame Characterization Field
        (frame_count, fic_flag, num_streams, mode) = self.frame_characterization(frame[4:8])
        if mode == 3:
            self.fic_length = 32
        frame_position = 8
        for n in range(0, num_streams):
            frame_position += 4 # 4 bytes per SSTC
        frame_position += 4 # 4 byte EOH, could check header CRC here        
        # Main Stream Transport
        if fic_flag:
            fic = frame[frame_position:(frame_position+(self.fic_length * 4))]     
            try: 
                self.decode_fic(fic)
            except Exception, e:
                print "Error decoding fic: %s" % e

    def frame_characterization(self, fc):
        frame_count = fc[0]
        fic_flag = (fc[1] & 0x80) >> 7
        num_streams = fc[1] & 0x7f
        mode = (fc[2] & 0x18) >> 3
        if mode == 0: mode = 4
        return (frame_count, fic_flag, num_streams, mode)        
    
    def stream_characterization(self, sstc):
        scid = int(sstc[0:6].to01(), 2)
        sad = int(sstc[6:16].to01(), 2)
        tpl = int(sstc[16:22].to01(), 2)
        stl = int(sstc[22:32].to01(), 2)
        stream = Stream(scid, sad, tpl, stl)
        return stream
    
    def end_of_header(self):
        self.input_file_handler.read(4)
        return

    def decode_fic(self, fibs):
        i = 0
        fib_start = i
        while i < (self.fic_length * 4):
            # Check to see if reached end marker
            if fibs[i] == 0xff:
                i = fib_start + 32
                fib_start = i
                continue
            fig_type = (fibs[i] & 0xe0) >> 5 
            fig_length = (fibs[i] & 0x1f)
            fig_data = fibs[i+1:i+1+fig_length]
            if fig_type == 0:
                current_next = (fig_data[0] & 0x80) >> 7
                other_ensemble = (fig_data[0] & 0x40) >> 6
                programme_data = (fig_data[0] & 0x20) >> 5
                extension =  fig_data[0] & 0x1f
                type0_field = fig_data[1:]
                if extension == 6:
                    self.process_fig_0_6(type0_field, fig_length - 1, programme_data)
                elif extension == 9:
                    self.process_fig_0_9(type0_field)
                elif extension == 10:
                    self.process_fig_0_10(type0_field)
            i = i + 1 + fig_length
            # Skip CRC
            if i == fib_start + 30:
                i = fib_start + 32
                fib_start = i

    def process_fig_0_6(self, data, data_size, pd):
        i = 0
        while i < data_size:
            id_list_flag = (data[i] & 0x80) >> 7
            link_actuator = (data[i] & 0x40) >> 6
            soft_hard = (data[i] & 0x20) >> 5
            international = (data[i] & 0x10) >> 4
            link_set_number = ((data[i] & 0xf) << 8) | data[i+1]    
            i += 2
            self.eti.check_linkset_actuator(link_set_number, soft_hard, link_actuator)            
            if id_list_flag:
                if not pd:
                    identifier_list_qualifier = (data[i] & 0x60) >> 5
                number_of_ids = data[i] & 0x0f
                i += 1
                id_list = []
                for j in range(0, number_of_ids):
                    if not pd and not international:
                        id = "%X" % (data[i] << 8 | data[i+1])
                        id_list.append(id)
                        i += 2
                    elif not pd and international:
                        id = "%X" % (data[i] << 16 | data[i+1] << 8 | data[i+2])
                        id_list.append(id)
                        i += 3
                    elif pd:
                        sid = "%X" % (data[i] << 24 | data[i+1] << 16 | data[i+2] << 8 | data[i])
                        id_list.append(sid)
                        i += 4
                if identifier_list_qualifier == 0: qualifier = "DAB"
                elif identifier_list_qualifier == 1: qualifier = "FM"
                elif identifier_list_qualifier == 2: qualifier = "AM"
                else: qualifier = "DRM / AMSS"
                self.eti.update_link_set_members(link_set_number, soft_hard, qualifier, id_list)
        
    def process_fig_0_9(self, data):
        ensemble_lto_direction = (data[0] & 0x20) >> 5 # 0 postive, 1 negative
        ensemble_lto_value = data[0] & 0x1f
        ensemble_lto_minutes = ensemble_lto_value * 30 * 60 # convert half hours to seconds
        if not ensemble_lto_direction:
            self.eti.lto = ensemble_lto_minutes
        else:
            self.eti.lto = 0 - ensemble_lto_minutes
        
    def process_fig_0_10(self, data):
        modified_julian_date = ((data[0] & 0x7f) << 10) | (data[1] << 2) | ((data[2] & 0xc0) >> 6)
        (year, month, day) = self.mjd_to_ymd(modified_julian_date)
        leap_second_indicator = data[2] & 2 >> 5
        utc_flag = (data[2] & 0x08) >> 3
        hours = ((data[2] & 0x07) << 2) | ((data[3] &0xc0) >> 6)
        minutes = data[3] & 0x3f
        if utc_flag == 0:
            seconds = 0
            miliseconds = 0
        else:
            self.time_long = True
            seconds = (data[4] & 0xfc) >> 2
            miliseconds = ((data[4] & 0x03) << 10) | data[5]
        now = datetime(year, month, day, hours, minutes, seconds, miliseconds*1000)
        if self.eti.lto:
            now = now + timedelta(seconds = self.eti.lto)
            self.eti.update_time(now)

    def mjd_to_ymd(self, mjd):
        # Adapted from http://www.csgnetwork.com/julianmodifdateconv.html
        jd = math.floor(mjd) + 2400000.5
        # Integer Julian day
        jdi = math.floor (jd)
        # Fractional part of day
        jdf = jd - jdi + 0.5
        # Really the next calendar day?
        if jdf >= 1.0:
           jdf = jdf - 1.0;
           jdi  = jdi + 1;
        hour = jdf * 24.0
        l = jdi + 68569
        n = math.floor(4 * l / 146097)
        l = math.floor (l) - math.floor ((146097 * n + 3) / 4)
        year = math.floor (4000 * (l + 1) / 1461001)
        l = l - (math.floor (1461 * year / 4)) + 31
        month = math.floor (80 * l / 2447)
        day = int(l - math.floor (2447 * month / 80))
        l = math.floor (month / 11)
        month = int(math.floor (month + 2 - 12 * l))
        year = int(math.floor (100 * (n - 49) + year + l))
        return (year, month, day)
           
    def process(self):
        print "Frame\tETI time\tBroadcast time\tEvent Details"
        buffer = bytearray()
        framebuffer = bytearray()
        sync_found = False         
        while True:
            try:
                while buffer[1:4] != "\x07\x3A\xB6" and buffer[1:4] != "\xF8\xC5\x49":
                    if len(buffer) == 4:
                        buffer.pop(0)
                    byte = sys.stdin.read(1)
                    buffer.append(byte)
                    framebuffer.append(byte)
            except Exception, e:
                    print "Error: %s" % e
                    raise
                    sys.exit(1)
            if sync_found:
                if len(framebuffer) > 4:
                    self.process_frame(framebuffer[:-4]) # Remove next frame's SYNC bytes
                    self.eti.increment_frame_count()
                framebuffer = bytearray()
                framebuffer.extend(buffer)
                buffer = bytearray()
            sync_found = True
            
eti_parser = Parser()
eti_parser.process()
