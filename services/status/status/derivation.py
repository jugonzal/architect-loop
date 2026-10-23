"""The derivation: plugin/skills/loop-status/scripts/loop_status.py, from the same commit this service is built from
(command-center/D13, D15).

The image keeps the repository's layout (services/status/status/ and plugin/skills/loop-status/scripts/ under one
root), so the script is found from this file the same way in a checkout and in the image. It is loaded as a module:
the service calls its derive(facts) and pending_queries(facts), the functions `loop_status.py derive --facts`
runs, and its readers of LOOP.md and pull requests, so the service and the terminal read alike.
"""

import importlib.util
import os

SCRIPTS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "plugin",
                                        "skills", "loop-status", "scripts"))
# loop-status's check of a loop-document pull request (LOOP.md §2.1), run as the terminal runs it.
CHECKER = os.path.join(SCRIPTS, "check_loop_pr.sh")


def load(scripts=SCRIPTS):
    path = os.path.join(scripts, "loop_status.py")
    spec = importlib.util.spec_from_file_location("loop_status", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
