import argparse
from datetime import datetime
import json
import math
from pathlib import Path
import subprocess
import sys
from typing import Any, Dict, List, Tuple
from jinja2 import Environment, FileSystemLoader, select_autoescape
import matplotlib.pyplot as plt


def make_linkable_as(asn: int) -> Dict[str, Any]:
    return {
        "asn": asn,
        "url": f"<a href='https://bgp.tools/as/{asn}' target='_blank'>AS{asn}</a>"
    }


def build_leaderboard(data: List[Dict[str, Any]]) -> Dict[str, str]:
    out = {
        "lowest_asn": {
            "asn": 4294967295,
            "link": ""
        },
        "highest_asn": {
            "asn": 0,
            "link": ""
        },
        "most_ipv4": {
            "winners": [],
            "count": 0
        },
        "most_ipv6": {
            "winners": [],
            "count": 0
        },
        "most_prefixes": {
            "winners": [],
            "count": 0
        },
        "most_announcements": {
            "winners": [],
            "count": 0
        },
        "largest_prefix_v4": {
            "winners": [],
            "size": 32,
        },
        "largest_prefix_v6": {
            "winners": [],
            "size": 128,
        },
        "most_announcers": {
            "prefix": "",
            "winners": [],
        }
    }

    for asn in data:

        # Find the lowest ASN
        if asn["asn"] < out["lowest_asn"]["asn"] and asn["prefixes"]:
            out["lowest_asn"] = make_linkable_as(asn["asn"])

        # Find the highest ASN
        if asn["asn"] > out["highest_asn"]["asn"] and asn["prefixes"]:
            out["highest_asn"] = make_linkable_as(asn["asn"])

        # Find the prefix counts
        ipv4_24s = 0
        ipv6_48s = 0
        for prefix in (asn["prefixes"] or []):
            if ":" in prefix:
                cidr = int(prefix.split("/")[1])
                ipv6_48s += int(math.pow(2, (128 - cidr)) /
                                math.pow(2, (128 - 48)))
            else:
                cidr = int(prefix.split("/")[1])
                ipv4_24s += int(math.pow(2, (32 - cidr)) /
                                math.pow(2, (32 - 24)))

        # Find the most IPv4 prefixes
        if ipv4_24s > out["most_ipv4"]["count"]:
            out["most_ipv4"]["winners"] = [make_linkable_as(asn["asn"])["url"]]
            out["most_ipv4"]["count"] = ipv4_24s
        elif ipv4_24s == out["most_ipv4"]["count"]:
            out["most_ipv4"]["winners"].append(
                make_linkable_as(asn["asn"])["url"])

        # Find the most IPv6 prefixes
        if ipv6_48s > out["most_ipv6"]["count"]:
            out["most_ipv6"]["winners"] = [make_linkable_as(asn["asn"])["url"]]
            out["most_ipv6"]["count"] = ipv6_48s
        elif ipv6_48s == out["most_ipv6"]["count"]:
            out["most_ipv6"]["winners"].append(
                make_linkable_as(asn["asn"])["url"])

        # Find the most prefixes
        if ipv4_24s + ipv6_48s > out["most_prefixes"]["count"]:
            out["most_prefixes"]["winners"] = [
                make_linkable_as(asn["asn"])["url"]]
            out["most_prefixes"]["count"] = ipv4_24s + ipv6_48s
        elif ipv4_24s + ipv6_48s == out["most_prefixes"]["count"]:
            out["most_prefixes"]["winners"].append(
                make_linkable_as(asn["asn"])["url"])

        # Find the highest number of announcements
        if len(asn["prefixes"] or []) > out["most_announcements"]["count"]:
            out["most_announcements"]["count"] = len(asn["prefixes"] or [])
            out["most_announcements"]["winners"] = [
                make_linkable_as(asn["asn"])["url"]]
        elif len(asn["prefixes"] or []) == out["most_announcements"]["count"]:
            out["most_announcements"]["winners"].append(
                make_linkable_as(asn["asn"])["url"])
            
        # Find the largest prefixes
        for prefix in (asn["prefixes"] or []):
            cidr = int(prefix.split("/")[1])
            if cidr < out["largest_prefix_v4"]["size"] and "." in prefix:
                out["largest_prefix_v4"]["winners"] = [
                    make_linkable_as(asn["asn"])["url"]]
                out["largest_prefix_v4"]["size"] = cidr
            elif cidr == out["largest_prefix_v4"]["size"] and "." in prefix:
                out["largest_prefix_v4"]["winners"].append(
                    make_linkable_as(asn["asn"])["url"])
            if cidr < out["largest_prefix_v6"]["size"] and ":" in prefix:
                out["largest_prefix_v6"]["winners"] = [
                    make_linkable_as(asn["asn"])["url"]]
                out["largest_prefix_v6"]["size"] = cidr
            elif cidr == out["largest_prefix_v6"]["size"] and ":" in prefix:
                out["largest_prefix_v6"]["winners"].append(
                    make_linkable_as(asn["asn"])["url"])
                
    prefix_to_origin_map = {}
    for asn in data:
        for prefix in (asn["prefixes"] or []):
            prefix_to_origin_map.setdefault(prefix, []).append(asn["asn"])
            
    # Set the most announcers
    for prefix in prefix_to_origin_map:
        if len(prefix_to_origin_map[prefix]) > len(out["most_announcers"]["winners"]):
            out["most_announcers"]["winners"] = [make_linkable_as(x)["url"] for x in prefix_to_origin_map[prefix]]
            out["most_announcers"]["prefix"] = prefix
    
    
    return out


def build_demographics(data: List[Dict[str, Any]]) -> Dict[str, Any]:
    out = {
        "rirs": {},
        "countries": {},
    }

    for asn in data:
        out["rirs"].setdefault(asn["governing_body"], 0)
        out["rirs"][asn["governing_body"]] += 1
        out["countries"].setdefault(asn["country"], 0)
        out["countries"][asn["country"]] += 1

    out["rirs"] = sorted(out["rirs"].items(), key=lambda x: x[1], reverse=True)
    out["countries"] = sorted(out["countries"].items(),
                              key=lambda x: x[1], reverse=True)

    # Take the top 19 countries, and add all the rest to "Other"
    other = 0
    for i in range(19, len(out["countries"])):
        other += out["countries"][i][1]
    out["countries"] = out["countries"][:19]
    out["countries"].append(("Other", other))

    return out


def graph_demographics(demographics: Dict[str, Any], output_dir: Path) -> None:

    # Make a matplotlib pie chart of the RIRs
    plt.figure(figsize=(10, 10))
    plt.pie([x[1] for x in demographics["rirs"]], labels=[x[0] for x in demographics["rirs"]],
            autopct='%1.1f%%', startangle=45)
    plt.axis('equal')
    plt.title("ASN registration by RIR")
    plt.savefig(output_dir / "rirs.png")

    # Make a matplotlib pie chart of the countries
    plt.figure(figsize=(10, 10))
    plt.pie([x[1] for x in demographics["countries"]], labels=[x[0] for x in demographics["countries"]],
            autopct='%1.1f%%', startangle=45)
    plt.axis('equal')
    plt.title("ASN registration by country")
    plt.savefig(output_dir / "countries.png")


def build_ip_stack_stats(data: List[Dict[str, Any]]) -> Dict[str, Any]:
    out = {
        "asn_stack": {
            "IPv4 Only": 0,
            "IPv6 Only": 0,
            "Dual-Stacked": 0,
            "No Prefixes": 0,
        }
    }

    for asn in data:
        if not asn["prefixes"] or len(asn["prefixes"]) == 0:
            out["asn_stack"]["No Prefixes"] += 1
        elif len(asn["prefixes"]) == 1:
            if ":" in asn["prefixes"][0]:
                out["asn_stack"]["IPv6 Only"] += 1
            else:
                out["asn_stack"]["IPv4 Only"] += 1
        else:
            out["asn_stack"]["Dual-Stacked"] += 1

    return out


def graph_ip_stack_stats(stats: Dict[str, Any], output_dir: Path) -> None:

    # Make a matplotlib pie chart of the IP stack stats
    plt.figure(figsize=(10, 10))
    plt.pie([x[1] for x in stats["asn_stack"].items()], labels=[x[0] for x in stats["asn_stack"].items()],
            autopct='%1.1f%%', startangle=45)
    plt.axis('equal')
    plt.title("IP Stack Statistics")
    plt.savefig(output_dir / "ip_stack.png")


def build_ripe_lir_stats(data: List[Dict[str, Any]]) -> List[Tuple[str, int]]:
    out = {
    }

    # Write the query to a file
    with open("/tmp/ripe_lir_stats_query.txt", "w") as f:
        f.write("!!\n")
        for line in data:
            f.write(f"AS{line['asn']}\n")
        f.write("quit\n")

    # Run the query
    process = subprocess.run(
        ["bash", "-c", "cat /tmp/ripe_lir_stats_query.txt | nc whois.radb.net 43"], capture_output=True)

    # Parse the output
    for line in process.stdout.decode("utf-8").split("\n"):
        if line.startswith("sponsoring-org:"):
            out.setdefault(line.split(":")[1].strip(), 0)
            out[line.split(":")[1].strip()] += 1

    # Sort the output and take top 10
    out = sorted(out.items(), key=lambda x: x[1], reverse=True)[:10]

    # Rewrite the names to actual LIR names
    for i in range(len(out)):
        data = subprocess.Popen(
            ["bash", "-c", f"whois -h whois.ripe.net {out[i][0]} | grep org-name"], stdout=subprocess.PIPE).communicate()[0].decode("utf-8")
        out[i] = (data.split(":")[1].strip(), out[i][1])

    return out


def main() -> int:
    # Handle program arguments
    ap = argparse.ArgumentParser()
    ap.add_argument("data", help="JSON data file to read")
    args = ap.parse_args()
    out_dir = Path("site")
    out_dir.mkdir(exist_ok=True)

    # Load the data
    data = [json.loads(line) for line in open(args.data, "r")]

    # Compile stats
    leaderboard = build_leaderboard(data)
    demographics = build_demographics(data)
    graph_demographics(demographics, out_dir)
    ip_stack_stats = build_ip_stack_stats(data)
    graph_ip_stack_stats(ip_stack_stats, out_dir)
    ripe_lir_stats = build_ripe_lir_stats(data)
    v4_only_ases = [make_linkable_as(x["asn"])[
        "url"] for x in data if x["prefixes"] and ":" not in " ".join(x["prefixes"])]
    inactive_ases = [make_linkable_as(x["asn"])["url"] for x in data if not x["prefixes"]]

    # Set up Jinja2
    templ_env = Environment(
        loader=FileSystemLoader("templates"),
        autoescape=select_autoescape()
    )
    conf_template = templ_env.get_template("index.html")

    # Render the file
    with open(out_dir / "index.html", "w") as f:
        f.write(conf_template.render(leaderboard=leaderboard,
                                     demographics=demographics,
                                     ip_stack_stats=ip_stack_stats,
                                     ripe_lir_stats=ripe_lir_stats,
                                     v4_only_ases=v4_only_ases,
                                     inactive_ases=inactive_ases,
                last_updated=datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

    return 0


if __name__ == "__main__":
    sys.exit(main())
