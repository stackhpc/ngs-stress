# Copyright (c) 2017 StackHPC Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import contextlib
import Queue
import sys
import threading

import networking_generic_switch.generic_switch_mech as generic_switch
from oslo_config import cfg
import oslo_log.log as logging
import uuid


CONF = cfg.CONF
LOG = logging.getLogger(__name__)


OPTS = [
    cfg.StrOpt('mode', choices=['network', 'port'], required=True,
               help='Mode of operation / resource type to exercise'),
    cfg.StrOpt('ports',
                help='Comma-separated list of ports to create in port mode.'),
    cfg.StrOpt('switch', required=True,
               help='Name of switch to connect to'),
    cfg.StrOpt('vlan-range', required=True,
               help='Colon-separated range of vlan IDs to create in network '
                    'mode. In port mode the first will be used'),
]


def _gen_net_id():
    """Dell Force-10 switches can't handle network names beginning with a letter."""
    while True:
        net_id = str(uuid.uuid4())
        try:
            int(net_id[0])
        except ValueError:
            return net_id


def _log_excs_and_reraise(eq):
    """Log all exceptions in a Queue and reraise one."""
    while not eq.empty():
        e = eq.get()
        LOG.error("Exception seen during test", exc_info=e)
        if eq.empty():
            raise e


def _run_threads(ts):
    """Start a list of threads then wait for them to complete."""
    for t in ts:
        t.start()
    for t in ts:
        t.join()


def _create_net(switch, vlan, net_id):
    LOG.info("Creating VLAN %d" % vlan)
    switch.add_network(vlan, net_id)


def _delete_net(switch, vlan):
    LOG.info("Deleting VLAN %d" % vlan)
    switch.del_network(vlan)


def _create_delete_net(switch, vlan, net_id):
    """Create and delete a VLAN."""
    _create_net(switch, vlan, net_id)
    _delete_net(switch, vlan)


class ErrorQueueingThread(threading.Thread):
    """Thread subclass which pushes a raised exception onto a queue."""

    def __init__(self, target=None, eq=None, *args, **kwargs):
        def new_target(*t_args, **t_kwargs):
            with self.exceptions_queued(eq):
                return target(*t_args, **t_kwargs)
        super(ErrorQueueingThread, self).__init__(*args, target=new_target, **kwargs)

    @contextlib.contextmanager
    def exceptions_queued(self, eq):
        try:
            yield
        except Exception as e:
            eq.put(sys.exc_info())
            raise


def _create_delete_nets(switch, vlans):
    """Create and delete VLANs in parallel."""
    ts = []
    eq = Queue.Queue()
    for vlan in vlans:
        args = (switch, vlan, _gen_net_id())
        t = ErrorQueueingThread(target=_create_delete_net, args=args, name='vlan-%d' % vlan, eq=eq)
        ts.append(t)
    _run_threads(ts)
    _log_excs_and_reraise(eq)


def _add_remove_port(switch, port_id, vlan):
    """Add and remove a port to/from a VLAN."""
    LOG.info("Adding port %s to VLAN %d" % (port_id, vlan))
    switch.plug_port_to_network(port_id, vlan)
    LOG.info("Removing port %s from VLAN %d" % (port_id, vlan))
    switch.delete_port(port_id, vlan)


def _add_remove_ports(switch, ports, vlan):
    """Add and remove ports to/from a VLAN in parallel."""
    ts = []
    eq = Queue.Queue()
    _create_net(switch, vlan, _gen_net_id())
    for port_id in ports:
        args = (switch, port_id, vlan)
        t = ErrorQueueingThread(target=_add_remove_port, args=args, name='port-%s' % port_id, eq=eq)
        ts.append(t)
    _run_threads(ts)
    _delete_net(switch, vlan)
    _log_excs_and_reraise(eq)


def _init():
    logging.register_options(CONF)
    CONF.register_cli_opts(OPTS)
    CONF(sys.argv[1:])
    logging.setup(CONF, 'ngs_stress')


def main():
    _init()
    gs = generic_switch.GenericSwitchDriver()
    gs.initialize()
    switch = gs.switches[CONF.switch]
    vlans = range(*map(int, CONF.vlan_range.split(':')))
    if CONF.mode == 'network':
        _create_delete_nets(switch, vlans)
    else:
        vlan = vlans[0]
        ports = CONF.ports.split(',')
        _add_remove_ports(switch, ports, vlan)


if __name__ == "__main__":
    main()