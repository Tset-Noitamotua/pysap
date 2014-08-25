#!/usr/bin/env python
# ===========
# pysap - Python library for crafting SAP's network protocols packets
#
# Copyright (C) 2014 Core Security Technologies
#
# The library was designed and developed by Martin Gallo from the Security
# Consulting Services team of Core Security Technologies.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# ==============

# Standard imports
import logging
from socket import error as SocketError
from optparse import OptionParser, OptionGroup
# External imports
from scapy.config import conf
from scapy.packet import bind_layers
# Custom imports
import pysap
from pysap.utils import BaseConsole
from pysap.SAPNI import SAPNI
from pysap.SAPEnqueue import SAPEnqueue, SAPEnqueueParam, enqueue_param_values,\
    SAPEnqueueStreamSocket


# Bind SAP NI with MS packets
bind_layers(SAPNI, SAPEnqueue, )

# Set the verbosity to 0
conf.verb = 0


class SAPEnqueueAdminConsole(BaseConsole):

    intro = "SAP Enqueue Server Admin Console"
    connection = None
    connected = False

    def __init__(self, options):
        super(SAPEnqueueAdminConsole, self).__init__(options)
        self.runtimeoptions["client_name"] = self.options.client
        self.runtimeoptions["client_recv_length"] = 1000
        self.runtimeoptions["client_send_length"] = 1000
        self.runtimeoptions["client_version"] = 3

    # Initialization
    def preloop(self):
        super(SAPEnqueueAdminConsole, self).preloop()
        self.do_connect(None)

    # SAP Enqueue Admin commands

    def do_connect(self, args):
        """ Initiate the connection to the Enqueue Server. """

        # Create the socket connection
        try:
            self.connection = SAPEnqueueStreamSocket.get_nisocket(self.options.remote_host, self.options.remote_port)
        except SocketError as e:
            self._error("Error connecting with the Enqueue Server")
            self._error(str(e))
            return

        self._print("Attached to %s / %d" % (self.options.remote_host, self.options.remote_port))

        params = [SAPEnqueueParam(param=0, value=int(self.runtimeoptions["client_recv_length"])),
                  SAPEnqueueParam(param=1, value=int(self.runtimeoptions["client_send_length"])),
                  SAPEnqueueParam(param=3, set_name=self.runtimeoptions["client_name"]),
                  SAPEnqueueParam(param=2, value=59),
                  SAPEnqueueParam(param=5, value=int(self.runtimeoptions["client_version"])),
                  SAPEnqueueParam(param=6, value=1, len=4)
                  ]
        # Send Parameter Request packet
        p = SAPEnqueue(dest=6, opcode=1, params=params)

        self._debug("Retrieving parameters")
        response = self.connection.sr(p)[SAPEnqueue]

        # Walk over the server's parameters
        for param in response.params:
            self._debug("Server parameter: %s=%s" % (enqueue_param_values[param.param],
                                                     param.value if param.param not in [0x03] else param.set_name))
            # Save server version and name as runtime options
            if param.param == 0x03:
                self.runtimeoptions["server_name"] = param.set_name
            if param.param == 0x05:
                self.runtimeoptions["server_version"] = param.value

        self._print("Server name: %s" % self.runtimeoptions["server_name"])
        self._print("Server version: %d" % self.runtimeoptions["server_version"])
        self.connected = True

    def do_disconnect(self, args):
        """ Disconnects from the Enqueue Server service. """

        if not self.connected:
            self._error("You need to connect to the server first !")
            return

        self.connection.close()
        self._print("Dettached from %s / %d ..." % (self.options.remote_host, self.options.remote_port))
        self.connected = False

    def do_exit(self, args):
        if self.connected:
            self.do_disconnect(None)
        return super(SAPEnqueueAdminConsole, self).do_exit(args)

    def do_dummy_request(self, args):
        """ Send a dummy request to the server to check if it is alive. """

        if not self.connected:
            self._error("You need to connect to the server first !")
            return

        # Send Dummy Request
        p = SAPEnqueue(dest=3, adm_opcode=1)

        self._debug("Sending dummy request")
        response = self.connection.sr(p)[SAPEnqueue]
        response.show()
        self._debug("Performed dummy request")

    def do_get_replication_info(self, args):
        """ Get information about the status and statistics of the replication. """

        if not self.connected:
            self._error("You need to connect to the server first !")
            return

        # Send Get Replication Info
        p = SAPEnqueue(dest=3, adm_opcode=4)

        self._debug("Sending get replication info request")
        response = self.connection.sr(p)[SAPEnqueue]
        response.show()
        self._debug("Obtained replication info")


# Command line options parser
def parse_options():

    description = \
    """This script is an example implementation of SAP's Enqueue Server Monitor
    program (ens_mon). It allows the monitoring of a Enqueue Server service and
    allows sending different admin commands and opcodes. Includes some commands
    not available on the ensmon program.
    """

    epilog = "pysap %(version)s - %(url)s - %(repo)s" % {"version": pysap.__version__,
                                                         "url": pysap.__url__,
                                                         "repo": pysap.__repo__}

    usage = "Usage: %prog [options] -d <remote host>"

    parser = OptionParser(usage=usage, description=description, epilog=epilog)

    target = OptionGroup(parser, "Target")
    target.add_option("-d", "--remote-host", dest="remote_host", help="Remote host")
    target.add_option("-p", "--remote-port", dest="remote_port", type="int", help="Remote port [%default]", default=3200)
    parser.add_option_group(target)

    misc = OptionGroup(parser, "Misc options")
    misc.add_option("-c", "--client", dest="client", default="pysap's-monitor", help="Client name [%default]")
    misc.add_option("-v", "--verbose", dest="verbose", action="store_true", default=False, help="Verbose output [%default]")
    misc.add_option("--log-file", dest="logfile", help="Log file")
    misc.add_option("--console-log", dest="consolelog", help="Console log file")
    misc.add_option("--script", dest="script", help="Script file to run")
    parser.add_option_group(misc)

    (options, _) = parser.parse_args()

    if not options.remote_host:
        parser.error("Remote host is required")

    return options


# Main function
def main():
    options = parse_options()

    if options.verbose:
        logging.basicConfig(level=logging.DEBUG)

    en_console = SAPEnqueueAdminConsole(options)

    try:
        if options.script:
            en_console.do_script(options.script)
        else:
            en_console.cmdloop()
    except KeyboardInterrupt:
        print("Cancelled by the user !")
        en_console.do_exit(None)


if __name__ == "__main__":
    main()
