#!/usr/bin/env python2

# Rekall Memory Forensics
# Copyright 2013 Google Inc. All Rights Reserved.
#
# Author: Michael Cohen scudette@google.com
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or (at
# your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA
#

__author__ = "Mikhail Bushkov <mbushkov@google.com>"

import os
import sys
import webbrowser

from rekall import io_manager
from rekall import plugin
from rekall import testlib

from rekall.plugins.tools.webconsole import pythoncall
from rekall.plugins.tools.webconsole import runplugin

from flask import Blueprint

from gevent import pywsgi
from geventwebsocket.handler import WebSocketHandler

from manuskript import plugins as manuskript_plugins
from manuskript import plugin as manuskript_plugin
from manuskript import server as manuskript_server


try:
    STATIC_PATH = os.path.join(sys._MEIPASS, "webconsole", "static")  # pylint: disable=protected-access
except AttributeError:
    STATIC_PATH = os.path.join(os.path.dirname(__file__), "webconsole",
                               "static")


class RekallWebConsole(manuskript_plugin.Plugin):

    ANGULAR_MODULE = "rekall.webconsole"

    JS_FILES = [
        "/rekall-webconsole/webconsole.js",
        ]


class WebConsole(plugin.Command):
    """Launch the web-based Rekall console."""

    __name = "webconsole"

    @classmethod
    def args(cls, parser):
        super(WebConsole, cls).args(parser)

        parser.add_argument("worksheet",
                            help="The worksheet file name to use.")

        parser.add_argument("--host", default="localhost",
                            help="Host for the web console to use.")

        parser.add_argument("--port", default=0, type=int,
                            help="Port for the web console to use.")

        parser.add_argument("--debug", default=False, action='store_true',
                            help="Start in the debug mode (will monitor "
                            "changes in the resources and reload them as "
                            "needed.")

        parser.add_argument("--no_browser", default=False,
                            action='store_true',
                            help="Don't open webconsole in the default "
                            "browser.")

    def __init__(self, host="localhost", port=0, debug=False,
                 no_browser=False, worksheet=None, **kwargs):
        super(WebConsole, self).__init__(**kwargs)
        self.host = host
        self.port = port
        self.debug = debug
        self.no_browser = no_browser
        if worksheet is None:
            raise plugin.PluginError(
                "A worksheet file name must be provided. This is used "
                "to save the worksheet.")

        self.worksheet_fd = io_manager.Factory(worksheet, mode="a")

    def server_post_activate_callback(self, server):
        # Update the port number, because the server may have launched on a
        # random port.
        self.port = server.server_address[1]
        if not self.no_browser:
            webbrowser.open("http://%s:%d" % (self.host, self.port))
        else:
            sys.stderr.write(
                "\nSupressing web browser (--no_browser flag). "
                "Server running at http://%s:%d\n" % (self.host, self.port))

    def render(self, renderer):
        renderer.format("Starting Manuskript web console.")
        renderer.format("Press Ctrl-c to return to the interactive shell.")

        app = manuskript_server.InitializeApp(
            plugins=[manuskript_plugins.PlainText,
                     manuskript_plugins.Markdown,
                     pythoncall.RekallPythonCall,
                     runplugin.RekallRunPlugin,
                     RekallWebConsole],
            config=dict(
                rekall_session=self.session,
                worksheet=self.worksheet_fd,
                ))

        # Use blueprint as an easy way to serve static files.
        bp = Blueprint('rekall-webconsole', __name__,
                       static_url_path="/rekall-webconsole",
                       static_folder=STATIC_PATH)
        @bp.after_request
        def add_header(response):  # pylint: disable=unused-variable
            response.headers['Cache-Control'] = 'no-cache, no-store'
            return response
        app.register_blueprint(bp)

        server = pywsgi.WSGIServer((self.host, self.port), app,
                                   handler_class=WebSocketHandler)
        server.serve_forever()


class TestWebConsole(testlib.DisabledTest):
    """Disable the test for this command to avoid bringing up the notebook."""
    PARAMETERS = dict(commandline="webconsole")
