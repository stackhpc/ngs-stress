#####################################
Networking-generic-switch Stress Test
#####################################

Stress test for the OpenStack Neutron networking-generic-switch (genericswitch)
ML2 mechanism driver.

This script can stress a switch using the genericswitch driver.  There are two
modes of operation:

network
    Create and delete a number of networks in parallel.
port
    Create and delete a number of ports in parallel.

It is possible to use an existing genericswitch configuration file containing
switch configuration.

Installation
############

To install dependencies in a virtualenv::

    virtualenv venv
    source venv/bin/activate
    pip install -U pip
    pip install networking-generic-switch
    pip install git+https://github.com/openstack/neutron

Usage
#####

To run the stress test::

    venv/bin/python ngs_stress.py \
    --config-file /path/to/neutron.conf \
    --config-file /path/to/ml2_conf.ini \
    --mode <network|port> \
    --switch <switch name> \
    --vlan-range <min>:<max> \
    --ports <port1,port2...>
