#!/usr/bin/env python3
"""verify -- the checks `factory-ci verify` cannot say in shell (decision 0081). Standard library only.

  verify.py network DNS...        the libvirt network's XML on stdin: NAT bound to no interface,
                                  bridge virbr-fci, no IPv6, DNS forwarded to exactly DNS...
  verify.py domain                the VM's XML on stdin: one NIC, on factory-ci, under the egress
                                  filter; nothing passed through; freed memory returned
  verify.py guest LAN CAMPUS_DNS  run in the guest: what it may reach and what it may not
  verify.py gate RULES --dns IP... --block CIDR...
                                  the host file against the installed isolation: at least one
                                  resolver, each public and unblocked, and every resolver and
                                  blocked range present in RULES

Each prints one line per check, `ok` or `X`, and exits 1 when any is X.
"""
import ipaddress
import re
import socket
import sys
import xml.etree.ElementTree as ET

failed = False


def say(good, what):
    global failed
    failed |= not good
    print(("  ok  " if good else "  X   ") + what)


def network(text, dns):
    net = ET.fromstring(text)
    forward = net.find("forward")
    say(forward is not None and forward.get("mode") == "nat" and not forward.findall("interface") and not forward.get("dev"),
        "network factory-ci forwards by NAT, bound to no interface")
    bridge = net.find("bridge")
    say(bridge is not None and bridge.get("name") == "virbr-fci", "its bridge is virbr-fci")
    say(not [ip for ip in net.findall("ip") if ip.get("family") == "ipv6"], "it has no IPv6 address")
    got = [f.get("addr") for f in net.iter("forwarder")]
    say(got == dns, f"its DNS forwards to {', '.join(got) or 'the host resolver'}" + ("" if got == dns else f", want {', '.join(dns) or 'the host resolver'}"))


def domain(text):
    devices = ET.fromstring(text).find("devices")
    nics = devices.findall("interface")
    say(len(nics) == 1 and nics[0].get("type") == "network" and nics[0].find("source").get("network") == "factory-ci",
        "the VM has one NIC, on network factory-ci (no bridge, direct/macvtap, hostdev or user NIC)")
    say(all((n.find("filterref") is not None and n.find("filterref").get("filter") == "factory-ci-egress") for n in nics),
        "every NIC is under the factory-ci-egress filter")
    say(not devices.findall("hostdev"), "no device is passed through")
    balloon = devices.find("memballoon")
    say(balloon is not None and balloon.get("freePageReporting") == "on", "the balloon returns freed guest memory to the host")


def tcp(host, port, family=socket.AF_INET):
    try:
        with socket.socket(family, socket.SOCK_STREAM) as s:
            s.settimeout(3)
            s.connect((host, port))
        return "open"
    except OSError:
        return "closed"


def udp53(server):
    query = b"\x12\x34\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00\x06github\x03com\x00\x00\x01\x00\x01"
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.settimeout(3)
        try:
            s.sendto(query, (server, 53))
            s.recv(512)
            return "open"
        except OSError:
            return "closed"


def guest(lan, campus_dns):
    checks = [
        ("github.com:443", lambda: tcp("github.com", 443), "open"),
        ("api.nuget.org:443", lambda: tcp("api.nuget.org", 443), "open"),
        ("DNS at the gateway", lambda: udp53("192.168.150.1"), "open"),
        ("DNS at 1.1.1.1 over UDP", lambda: udp53("1.1.1.1"), "closed"),
        ("DNS at 1.1.1.1 over TCP", lambda: tcp("1.1.1.1", 53), "closed"),
        (f"the campus resolver {campus_dns}", lambda: udp53(campus_dns), "closed"),
        ("github.com:22", lambda: tcp("github.com", 22), "closed"),
        (f"the host's LAN address {lan}:22", lambda: tcp(lan, 22), "closed"),
        (f"the host's LAN address {lan}:443", lambda: tcp(lan, 443), "closed"),
        ("the host at the gateway, 192.168.150.1:22", lambda: tcp("192.168.150.1", 22), "closed"),
        ("the campus, udayton.edu:443", lambda: tcp("udayton.edu", 443), "closed"),
        ("IPv6, [2606:4700:4700::1111]:443", lambda: tcp("2606:4700:4700::1111", 443, socket.AF_INET6), "closed"),
    ]
    for what, probe, want in checks:
        got = probe()
        say(got == want, f"{what}: {got}" + ("" if got == want else f", want {want}"))


def gate(rules_path, dns, block):
    with open(rules_path, encoding="utf-8") as handle:
        rules = handle.read()
    sets = {name: {ipaddress.ip_network(e.strip(), strict=False) for e in body.split(",") if e.strip()}
            for name, body in re.findall(r"set (\w+) \{[^}]*?elements = \{([^}]*)\}", rules, re.S)}
    blocked, resolvers = sets.get("blocked", set()), sets.get("resolvers", set())
    say(bool(dns), f"the host file names resolvers ({' '.join(dns) or 'none'})")
    for r in dns:
        a = ipaddress.ip_address(r)
        say(a.version == 4 and a.is_global and not any(a in n for n in blocked), f"resolver {r} is public and not blocked")
        say(ipaddress.ip_network(r) in resolvers, f"resolver {r} is one the installed rules let dnsmasq ask")
    for b in block:
        net = ipaddress.ip_network(b, strict=False)
        say(any(net.subnet_of(n) for n in blocked if n.version == 4), f"{b} is blocked by the installed rules")


if __name__ == "__main__":
    kind, args = sys.argv[1], sys.argv[2:]
    text = sys.stdin.read() if kind in ("network", "domain") else ""
    if kind in ("network", "domain") and not text.strip():
        say(False, f"libvirt has no {'network factory-ci' if kind == 'network' else 'such VM'}")
    elif kind == "network":
        network(text, args)
    elif kind == "domain":
        domain(text)
    elif kind == "guest":
        guest(args[0], args[1])
    elif kind == "gate":
        cut = args.index("--block") if "--block" in args else len(args)
        gate(args[0], [a for a in args[1:cut] if a != "--dns"], args[cut + 1:])
    else:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    sys.exit(1 if failed else 0)
