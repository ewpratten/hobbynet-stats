import argparse
from datetime import datetime
from pathlib import Path
import sys
from typing import Dict, List, Optional
from dataclasses import dataclass
from dataclasses_json import dataclass_json
import csv
import requests
import socket


@dataclass_json
@dataclass
class AsnStatistics:
    asn: int
    country: str
    custom_name: str
    governing_body: str
    creation_date: str
    name: Optional[str] = None
    prefixes: Optional[List[str]] = None
    # peering_db_name: Optional[str] = None


def get_personal_ases() -> List[int]:

    # Check if a cache file exists and is older than 30 minutes
    cache_file = Path("/tmp/personal_asns.csv")
    if cache_file.exists() and (datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)).total_seconds() < 1800:
        print("Using cached ASN data")
        csv_data = cache_file.read_text()

    else:
        # Get all personal ASNs known to bgp.tools
        print("Refreshing ASN data cache")
        csv_data = requests.get("https://bgp.tools/tags/perso.csv", headers={
                                "User-Agent": "hobbynet-stats (Contact: noc@ewpratten.com)"}).text

        # Cache the data
        cache_file.write_text(csv_data)

    # Parse the CSV data
    asns: List[int] = []
    for row in csv.reader(csv_data.splitlines()):
        asns.append(int(row[0].replace("AS", "")))

    return asns


def read_bgp_tools_bulk(query: str) -> str:

    # Handle cache file
    cache_file = Path(f"/tmp/bgp_tools_query.txt")
    if cache_file.exists() and (datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)).total_seconds() < 1700:
        print("Using cached WHOIS data")
        return cache_file.read_text()

    else:

        # Open a connection to bgp.tools WHOIS service
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("bgp.tools", 43))

        # Send the query
        s.sendall(query.encode("utf-8"))

        # Read the response
        output = []
        print("Refreshing WHOIS cache. this will take a bit...")
        while True:
            data = s.recv(1024)
            if not data:
                break
            data = data.decode("utf-8")
            if data.startswith("You are querying too fast"):
                print("Encountered rate limit")
                raise Exception("Rate limit")
            output.append(data)

        file = "".join(output)

        # Cache the data
        cache_file.write_text(file)

        return file


def build_registration_data(asns: List[int]) -> List[AsnStatistics]:

    # Build a bulk-mode query
    query = "begin\n" + "\n".join([f"as{asn}" for asn in asns]) + "\nend\n"
    data = read_bgp_tools_bulk(query)

    # Read the response
    output: List[AsnStatistics] = []
    for line in data.splitlines():

        fields = [x.strip() for x in line.split("|")]

        if not fields[0]:
            break

        if len(fields) < 7:
            continue

        print(f"Processing registration for: AS{fields[0]}")

        output.append(AsnStatistics(
            asn=int(fields[0]),
            country=fields[3],
            governing_body=fields[4],
            creation_date=fields[5],
            custom_name=fields[6],
        ))

    return output


def add_visibility_data(data: List[AsnStatistics]) -> List[AsnStatistics]:
    # Get the current visibility data
    print("Downloading full BGP table")
    visibility_data = requests.get("https://bgp.tools/table.txt", headers={
        "User-Agent": "hobbynet-stats (Contact: noc@ewpratten.com)"}).text

    # Load the full table as a searchable dict
    full_table: Dict[str, List[str]] = {}
    for line in visibility_data.splitlines():
        if not line:
            continue
        prefix, asn = line.split(" ", 1)

        full_table.setdefault(asn, []).append(prefix)

    # Add the visibility data to the data
    output: List[AsnStatistics] = []
    for entry in data:
        if str(entry.asn) in full_table:
            entry.prefixes = full_table[str(entry.asn)]
        output.append(entry)
            
    return output


def main() -> int:
    # Handle program arguments
    ap = argparse.ArgumentParser()
    ap.add_argument("output", help="Output JSON file to store data in")
    args = ap.parse_args()

    # Get all personal ASes
    asns = get_personal_ases()
    print(f"Found {len(asns)} personal ASes")

    # Build registration data
    data = build_registration_data(asns)
    
    # Add visibility data
    data = add_visibility_data(data)

    # Write the data to a file
    print("Writing data file")
    with open(args.output, "w") as f:
        for entry in data:
            f.write(entry.to_json() + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
