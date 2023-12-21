#!/usr/bin/env python
# coding: utf-8

# In[1]:


import dpkt
import socket


# In[2]:


traffic_counts = {}
with open("./pcap1_anom.pcap", 'rb') as f:
    pcap = dpkt.pcap.Reader(f)

    for timestamp, buf in pcap:
        try:
            eth = dpkt.ethernet.Ethernet(buf)
            # Make sure the Ethernet frame contains an IP packet
            if not isinstance(eth.data, dpkt.ip.IP):
                continue
            ip = eth.data
    
            src_ip = socket.inet_ntoa(ip.src)
            dst_ip = socket.inet_ntoa(ip.dst)
            ip_pair = (src_ip, dst_ip)
    
            traffic_counts[ip_pair] = traffic_counts.get(ip_pair, 0) + 1
    
        except Exception as e:
            # Ignore malformed packets
            continue
    
print(traffic_counts)


# In[14]:


all_ips = []
def add_ip(ip):
    if not(ip in all_ips):
        all_ips.append(ip)
        
for k in traffic_counts:
    if traffic_counts[k] < 150:
        continue
    (src, dst) = k
    add_ip(src)
    add_ip(dst)

print(all_ips)
print(len(all_ips))


# In[15]:


result = {}
for src in all_ips:
    row = []
    for dst in all_ips:
        row.append(traffic_counts.get((src, dst), 0))
    result[src] = row

print(result)


# In[16]:


import json


# In[17]:


print(json.dumps(result))


# In[ ]:




