"""`python -m runner job` runs the session named by RUNNER_SESSION_ID; `python -m runner serve` serves the API."""

import os
import sys

from .main import run_job, serve


def main(argv):
    if argv[1:2] == ["job"]:
        return run_job()
    if argv[1:2] == ["serve"]:
        serve(int(os.environ.get("PORT", "8080")))
        return 0
    print(__doc__, file=sys.stderr)
    return 2


sys.exit(main(sys.argv))
