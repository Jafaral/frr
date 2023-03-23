#!/usr/bin/env python
# SPDX-License-Identifier: ISC

#
# test_ospf_metric_propagation.py
#
# Copyright (c) 2023 ATCorp
# Jafar Al-Gharaibeh
#

import os
import sys
from functools import partial
import pytest

# pylint: disable=C0413
# Import topogen and topotest helpers
from lib import topotest
from lib.topogen import Topogen, TopoRouter, get_topogen
from lib.topolog import logger


"""
test_ospf_multi_vrf_bgp_route_leak.py: Test OSPF with multi vrf setup and route leaking.
"""

TOPOLOGY = """


                                 eth1 +-----+           eth0            +-----+
                                      |     |                           |     |
                        +-------------+ rA  +---------------------------+ rB  +---------------+
                        |          .5 |     | .5                     .6 |     | .6            |
                        |             +--+--+     10.0.50.0/24          +--+--+ .6            |
                        |                |.5                               |.6                |
                        |            eth2|                                 |                  |
                 10.0.10.0/24            |                                 |                  |
                        |            10.0.20.0/24                   10.0.30.0/24          10.0.40.0/24
                        |blue            |blue                             |blue              |blue
                        |                |                                 |                  |
                    eth1|.1          eth1|.2                           eth1|.3            eth1|.4
    +-----+eth0  eth2+--+--+   eth0   +--+--+eth2   eth1+-----+eth2  eth3+-+---+   eth0     +-+---+eth2 eth0+------+
    |     |          |     |          |     |           |     |          |     |            |     |         |      |
    | h1  +----------+ R1  +----------+ R2  +-----------+ rC  +----------+ R3  +------------+ R4  +---------+ h2   |
    |     |          |     |          |     |           |     |          |     |            |     |         |      |
    +-----+.2     .1 +-----+.1      .2+-----+.2      .7 +-----+.7      .3+-----+.3        .4+-----+.4     .2+------+
                  green                   green                      green                         green
    
       10.0.91.0/24        10.0.1.0/24      10.0.70.0/24      10.0.80.0/24     10.0.3.0/24        10.0.94.0/24


"""

# Save the Current Working Directory to find configuration files.
CWD = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(CWD, "../"))

# Required to instantiate the topology builder class.

pytestmark = [pytest.mark.ospfd, pytest.mark.bgpd]


def build_topo(tgen):
    "Build function"

    # Create 4 routers
    for routern in range(1, 5):
        tgen.add_router("r{}".format(routern))

    tgen.add_router("ra")
    tgen.add_router("rb")
    tgen.add_router("rc")
    tgen.add_router("h1")
    tgen.add_router("h2")


    # Interconect router 1, 2
    switch = tgen.add_switch("s1-2")
    switch.add_link(tgen.gears["r1"])
    switch.add_link(tgen.gears["r2"])

    # Interconect router 3, 4
    switch = tgen.add_switch("s3-4")
    switch.add_link(tgen.gears["r3"])
    switch.add_link(tgen.gears["r4"])

    # Interconect router a, b
    switch = tgen.add_switch("sa-b")
    switch.add_link(tgen.gears["ra"])
    switch.add_link(tgen.gears["rb"])

    # Interconect router 1, a
    switch = tgen.add_switch("s1-a")
    switch.add_link(tgen.gears["r1"])
    switch.add_link(tgen.gears["ra"])

    # Interconect router 2, a
    switch = tgen.add_switch("s2-a")
    switch.add_link(tgen.gears["r2"])
    switch.add_link(tgen.gears["ra"])

    # Interconect router 3, b
    switch = tgen.add_switch("s3-b")
    switch.add_link(tgen.gears["r3"])
    switch.add_link(tgen.gears["rb"])

    # Interconect router 4, b
    switch = tgen.add_switch("s4-b")
    switch.add_link(tgen.gears["r4"])
    switch.add_link(tgen.gears["rb"])

    # Interconect router 1, h1
    switch = tgen.add_switch("s1-h1")
    switch.add_link(tgen.gears["r1"])
    switch.add_link(tgen.gears["h1"])

    # Interconect router 4, h2
    switch = tgen.add_switch("s4-h2")
    switch.add_link(tgen.gears["r4"])
    switch.add_link(tgen.gears["h2"])

    # Interconect router 2, c
    switch = tgen.add_switch("s2-c")
    switch.add_link(tgen.gears["r2"])
    switch.add_link(tgen.gears["rc"])

    # Interconect router 3, c
    switch = tgen.add_switch("s3-c")
    switch.add_link(tgen.gears["r3"])
    switch.add_link(tgen.gears["rc"])

def setup_module(mod):
    logger.info("OSPF Metric Propagation:\n {}".format(TOPOLOGY))

    tgen = Topogen(build_topo, mod.__name__)
    tgen.start_topology()

    vrf_setup_cmds = [
        "ip link add name blue type vrf table 11",
        "ip link set dev blue up",
        "ip link add name green type vrf table 12",
        "ip link set dev green up",
    ]

    # Starting Routers
    router_list = tgen.routers()

    # Create VRFs and bind to interfaces
    for routern in range(1, 5):
        for cmd in vrf_setup_cmds:
            tgen.net["r{}".format(routern)].cmd(cmd)
    for routern in range(1, 5):
        tgen.net["r{}".format(routern)].cmd("ip link set dev r{}-eth1 vrf blue up".format(routern))
        tgen.net["r{}".format(routern)].cmd("ip link set dev r{}-eth2 vrf green up".format(routern))

    logger.info("Testing OSPF VRF support")

    for rname, router in router_list.items():
        logger.info("Loading router %s" % rname)
        router.load_frr_config(os.path.join(CWD, "{}/frr.conf".format(rname)))

    # Initialize all routers.
    tgen.start_router()
    for router in router_list.values():
        if router.has_version("<", "4.0"):
            tgen.set_error("unsupported version")


def teardown_module(mod):
    "Teardown the pytest environment"
    tgen = get_topogen()
    tgen.stop_topology()


# Shared test function to validate expected output.
def compare_show_ip_route_vrf(rname, expected, vrf_name):
    """
    Calls 'show ip route vrf [vrf_name] route' and compare the obtained
    result with the expected output.
    """
    tgen = get_topogen()
    current = topotest.ip4_route_zebra(tgen.gears[rname], vrf_name)
    ret = topotest.difflines(
        current, expected, title1="Current output", title2="Expected output"
    )
    return ret


def test_ospf_convergence():
    "Test OSPF daemon convergence"
    tgen = get_topogen()

    if tgen.routers_have_failure():
        pytest.skip("skipped because of router(s) failure")

    for rname, router in tgen.routers().items():
        logger.info('Waiting for router "%s" convergence', rname)

        for vrf in ["default", "neno", "ray"]:
            # Load expected results from the command
            reffile = os.path.join(CWD, "{}/ospf-vrf-{}.txt".format(rname, vrf))
            if vrf == "default" or os.path.exists(reffile):
                expected = open(reffile).read()

                # Run test function until we get an result. Wait at most 80 seconds.
                test_func = partial(
                    topotest.router_output_cmp,
                    router,
                    "show ip ospf vrf {} route".format(vrf),
                    expected,
                )
                result, diff = topotest.run_and_expect(
                    test_func, "", count=80, wait=1
                )
                assertmsg = "OSPF did not converge on {}:\n{}".format(rname, diff)
                assert result, assertmsg


def test_ospf_kernel_route():
    "Test OSPF kernel route installation"
    tgen = get_topogen()

    if tgen.routers_have_failure():
        pytest.skip("skipped because of router(s) failure")

    rlist = tgen.routers().values()
    for router in rlist:
        logger.info('Checking OSPF IPv4 kernel routes in "%s"', router.name)
        for vrf in ["default", "neno", "ray"]:
            reffile = os.path.join(CWD, "{}/zebra-vrf-{}.txt".format(router.name, vrf))
            if vrf == "default" or os.path.exists(reffile):
                expected = open(reffile).read()
                # Run test function until we get an result. Wait at most 80 seconds.
                test_func = partial(
                    compare_show_ip_route_vrf, router.name, expected, vrf
                )
                result, diff = topotest.run_and_expect(
                    test_func, "", count=80, wait=1
                )
                assertmsg = 'OSPF IPv4 route mismatch in router "{}": {}'.format(
                    router.name, diff
                )
                assert result, assertmsg


def test_memory_leak():
    "Run the memory leak test and report results."
    tgen = get_topogen()
    if not tgen.is_memleak_enabled():
        pytest.skip("Memory leak test/report is disabled")

    tgen.report_memory_leaks()


if __name__ == "__main__":
    args = ["-s"] + sys.argv[1:]
    sys.exit(pytest.main(args))
