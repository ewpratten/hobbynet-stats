from typing import Any, Dict, List
import requests
import re
import time
import socket

IXP_RE = re.compile(r"^1\[([A-Z]+)\] \(([\d\sa-z]+)\)\s+([A-Za-z\d\-\s()]+) - ")
PEERING_RE = re.compile(r"^1\[([A-Z]+)\]\s+AS(\d+)")

def get_asn_data(asn: int) -> Dict[str, List[Any]]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(('bgp.tools', 70))
    
    # Send query
    sock.send(f'/as/{asn}\r\n'.encode('utf-8'))
    
    # Read response
    buf = []
    while True:
        data = sock.recv(1024)
        if not data:
            break
        buf.extend(data.decode('utf-8').splitlines())
    
    # Read lines until we find the upstreams section
    out = {
        "upstreams": [],
        "downstreams": [],
        "ixps": [],
    }
    upstream_section = False
    downstream_section = False
    ixp_section = False
    for line in buf:
        if line.startswith('iUpstreams'):
            upstream_section = True
            downstream_section = False
            ixp_section = False
        if line.startswith('iPeers'):
            upstream_section = False
            downstream_section = False
            ixp_section = False
        if line.startswith('iDownstreams'):
            upstream_section = False
            downstream_section = True
            ixp_section = False
        if line.startswith('i-------- IX'):
            upstream_section = False
            downstream_section = False
            ixp_section = True
            
        if not (upstream_section or downstream_section or ixp_section):
            continue
        
        if ixp_section:
            matches = IXP_RE.match(line)
            if not matches:
                continue 
            country = matches.group(1)
            speed = matches.group(2)
            ix_name = matches.group(3)
            out['ixps'].append({
                'country': country,
                'speed': speed,
                'name': ix_name,
            })
            continue
        else:
            matches = PEERING_RE.match(line)
            if not matches:
                continue
            country = matches.group(1)
            peer_asn = int(matches.group(2))
            
            if upstream_section:
                out['upstreams'].append({
                    'country': country,
                    'asn': peer_asn,
                })
            elif downstream_section:
                out['downstreams'].append({
                    'country': country,
                    'asn': peer_asn,
                })
    
    return out
        
    

with open('ases_of_interest') as f:
    asns = [int(x) for x in f.read().splitlines()]

data = {}
for asn in asns:
    print(f"Processing ASN: {asn}")
    data.setdefault(asn, {}).update(get_asn_data(asn))
    
    # Rate limit
    time.sleep(0.5)


# Write the data to files
with open('as_upstreams', 'w') as f:
    for asn, info in data.items():
        for upstream in info['upstreams']:
            f.write("{asn}, {peer}, {country}\n".format(asn=asn, peer=upstream['asn'], country=upstream['country']))
            
with open('as_downstreams', 'w') as f:
    for asn, info in data.items():
        for downstream in info['downstreams']:
            f.write("{asn}, {peer}, {country}\n".format(asn=asn, peer=downstream['asn'], country=downstream['country']))
            
with open('as_ixps', 'w') as f:
    for asn, info in data.items():
        for ixp in info['ixps']:
            f.write("{asn}, {country}, {speed}, \"{name}\"\n".format(asn=asn, name=ixp['name'], country=ixp['country'], speed=ixp['speed']))
        