"""The last document of one project, reused while it is fresh (C1).

A document is fresh while it is at most `max_age` seconds old and no delivery from GitHub has marked it stale since
its facts began to be gathered. A stale mark during a gather leaves that gather's document stale, since its facts
may predate the event. Readers at the same time share one gather. A gather that fails leaves nothing to reuse: the
next reader gathers again, and no earlier document is ever served in its place (C2).
"""

import threading


class Board:
    def __init__(self, gather, max_age, clock):
        self.gather = gather
        self.max_age = max_age
        self.clock = clock
        self._state = threading.Lock()
        self._gathering = threading.Lock()
        self._generation = 0
        self._doc = None
        self._doc_generation = -1
        self._doc_started = None

    def stale(self):
        """GitHub delivered an event about the project: the next reader gathers again."""
        with self._state:
            self._generation += 1

    def _fresh(self):
        if self._doc is None or self._doc_generation != self._generation:
            return None
        if self.clock() - self._doc_started > self.max_age:
            return None
        return self._doc

    def current(self):
        """A fresh document, gathering one if there is none. Raises whatever the gather raises."""
        with self._state:
            doc = self._fresh()
        if doc is not None:
            return doc
        with self._gathering:
            with self._state:
                doc = self._fresh()  # another reader gathered while this one waited
                if doc is not None:
                    return doc
                generation, started = self._generation, self.clock()
                self._doc = None
            doc = self.gather()
            with self._state:
                self._doc, self._doc_generation, self._doc_started = doc, generation, started
            return doc
