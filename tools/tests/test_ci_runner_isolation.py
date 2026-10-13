"""A workstation host's isolation (decision 0081, issue #643), as regression tests.

The Office host sits on a campus network that shuts a port down when it sees a second MAC, and whose
public address space holds the institution's internal services. `verify.py` reads libvirt's own
record of the network and the VM for every way a guest could reach the physical link, and
`test-isolation.sh` runs the host's nftables layer in network namespaces, without root.
"""
import os
import shutil
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.join(os.path.dirname(HERE), "ci-runner")
VERIFY = os.path.join(KIT, "host", "verify.py")

NETWORK = """<network><name>factory-ci</name><forward mode='nat'><nat><port start='1024' end='65535'/></nat></forward>
<bridge name='virbr-fci' stp='on' delay='0'/><dns enable='yes'>{dns}</dns>
<ip address='192.168.150.1' netmask='255.255.255.0'/>{extra}</network>"""
FORWARDERS = "<forwarder addr='1.1.1.1'/><forwarder addr='9.9.9.9'/>"
NIC = """<interface type='network'><mac address='52:54:00:fc:01:01'/><source network='factory-ci'/>
<model type='virtio'/><filterref filter='factory-ci-egress'/></interface>"""
DOMAIN = "<domain><devices>{devices}<memballoon model='virtio' freePageReporting='on'/></devices></domain>"


def verify(kind, text, *args):
    result = subprocess.run([sys.executable, "-I", VERIFY, kind, *args], input=text, capture_output=True, text=True)
    return result.returncode, result.stdout


class TestTheNetworkKeepsTheGuestOffThePhysicalLink(unittest.TestCase):
    def test_the_network_factory_ci_provisions_passes(self):
        code, out = verify("network", NETWORK.format(dns=FORWARDERS, extra=""), "1.1.1.1", "9.9.9.9")
        self.assertEqual(0, code, out)

    def test_a_network_that_bridges_or_routes_onto_a_device_fails(self):
        for forward in ("<forward mode='bridge'/>", "<forward mode='nat' dev='eno1'/>",
                        "<forward mode='nat'><interface dev='eno1'/></forward>", "<forward mode='route'/>"):
            text = NETWORK.format(dns=FORWARDERS, extra="").replace(
                "<forward mode='nat'><nat><port start='1024' end='65535'/></nat></forward>", forward)
            self.assertEqual(1, verify("network", text, "1.1.1.1", "9.9.9.9")[0], forward)

    def test_ipv6_on_the_network_fails(self):
        text = NETWORK.format(dns=FORWARDERS, extra="<ip family='ipv6' address='fd00::1' prefix='64'/>")
        self.assertEqual(1, verify("network", text, "1.1.1.1", "9.9.9.9")[0])

    def test_dns_left_to_the_campus_resolver_fails(self):
        code, out = verify("network", NETWORK.format(dns="", extra=""), "1.1.1.1", "9.9.9.9")
        self.assertEqual(1, code)
        self.assertIn("the host resolver", out)


class TestTheVmHasOneFilteredNicOnThatNetwork(unittest.TestCase):
    def test_the_vm_factory_ci_provisions_passes(self):
        code, out = verify("domain", DOMAIN.format(devices=NIC))
        self.assertEqual(0, code, out)

    def test_every_nic_that_puts_a_guest_mac_on_a_physical_link_fails(self):
        for nic in ("<interface type='bridge'><source bridge='br0'/></interface>",
                    "<interface type='direct'><source dev='eno1' mode='bridge'/></interface>",
                    "<interface type='hostdev'><source><address type='pci'/></source></interface>",
                    "<interface type='user'/>"):
            self.assertEqual(1, verify("domain", DOMAIN.format(devices=nic))[0], nic)
            self.assertEqual(1, verify("domain", DOMAIN.format(devices=NIC + nic))[0], "a second NIC beside the right one")

    def test_a_nic_without_the_egress_filter_fails(self):
        self.assertEqual(1, verify("domain", DOMAIN.format(devices=NIC.replace("<filterref filter='factory-ci-egress'/>", "")))[0])

    def test_a_passed_through_device_fails(self):
        self.assertEqual(1, verify("domain", DOMAIN.format(devices=NIC + "<hostdev mode='subsystem' type='pci'/>"))[0])


class TestTheGateHoldsTheHostFileToTheInstalledRules(unittest.TestCase):
    """Codex 2026-10-13 (P1): a host file's FACTORY_CI_BLOCK that the root ruleset never received."""

    def gate(self, dns, block):
        rules = os.path.join(KIT, "host", "isolation.nft")
        with open(rules, encoding="utf-8") as handle:
            text = handle.read().replace("@BLOCKED@", ", 131.238.0.0/16").replace("@RESOLVERS@", "1.1.1.1, 9.9.9.9")
        result = subprocess.run([sys.executable, "-I", VERIFY, "gate", "/dev/stdin", "--dns", *dns, "--block", *block],
                                input=text, capture_output=True, text=True)
        return result.returncode

    def test_a_host_file_the_rules_hold_passes(self):
        self.assertEqual(0, self.gate(["1.1.1.1", "9.9.9.9"], ["131.238.0.0/16", "131.238.112.0/21"]))

    def test_a_range_or_resolver_the_rules_lack_fails(self):
        self.assertEqual(1, self.gate(["1.1.1.1"], ["4.0.0.0/8"]), "a blocked range the rules do not hold")
        self.assertEqual(1, self.gate(["8.8.8.8"], []), "a resolver dnsmasq may not ask")
        self.assertEqual(1, self.gate([], []), "no resolver: dnsmasq would ask the campus's")


def namespaces_work():
    if not (shutil.which("unshare") and shutil.which("nft") and shutil.which("tcpdump")):
        return False
    probe = subprocess.run(["unshare", "-rn", "nft", "list", "ruleset"], capture_output=True)
    return probe.returncode == 0


class TestTheHostRulesetInNetworkNamespaces(unittest.TestCase):
    """Each probe is first shown to connect without the ruleset, so a refusal is the ruleset's."""

    @unittest.skipUnless(namespaces_work(), "needs unprivileged user and network namespaces, nft and tcpdump")
    def test_isolation_nft_passes_test_isolation(self):
        result = subprocess.run([os.path.join(KIT, "host", "test-isolation.sh"), "131.238.0.0/16"],
                                capture_output=True, text=True, timeout=180)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("isolation: PASS", result.stdout)


class TestPrepareHostRefusesWhatItCannotCheck(unittest.TestCase):
    def test_a_bad_argument_changes_nothing(self):
        script = os.path.join(KIT, "host", "prepare-host.sh")
        for args in (["--block", "131.238.0.0"], ["--block", "x; rm -rf /"], ["--cpu", "0"], ["--memory-max", "10"],
                     ["--io-bandwidth", "fast"], ["--bogus"]):
            result = subprocess.run([script, "--dry-run", *args], capture_output=True, text=True)
            self.assertEqual(2, result.returncode, args)
            self.assertNotIn("+ ", result.stdout, "nothing is even planned")

    def test_the_template_has_one_place_for_the_blocked_ranges(self):
        with open(os.path.join(KIT, "host", "isolation.nft"), encoding="utf-8") as handle:
            text = handle.read()
        self.assertEqual(1, text.count("@BLOCKED@"))
        self.assertNotIn("flush ruleset", text, "it owns its tables and never touches another's")


if __name__ == "__main__":
    unittest.main()
