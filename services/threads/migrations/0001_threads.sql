-- The thread store: what people (and sessions) write, and nothing else (command-center/D26).
-- Keyed by project (command-center/D18). No table holds a loop's state, so wiping every table loses conversation
-- and never a decision, a claim or a piece of evidence (G4).

-- One row per thread that has been written to or watched. A thread nobody has touched reads as empty without a
-- row. `name` is the loop, `<loop>/<concern>`, or the session id, depending on `scope`.
CREATE TABLE threads (
    id         bigserial   PRIMARY KEY,
    project    text        NOT NULL,
    scope      text        NOT NULL CHECK (scope IN ('loop', 'concern', 'session')),
    name       text        NOT NULL,
    -- For a session thread, the sponsor the runner named in its first post.
    sponsor    text,
    -- The seq of the latest message. Posting locks this row, so seq order is commit order within a thread and a
    -- reader that pages with `after` never skips a message that commits late.
    last_seq   bigint      NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (project, scope, name)
);

CREATE TABLE messages (
    id           bigserial   PRIMARY KEY,
    thread_id    bigint      NOT NULL REFERENCES threads (id),
    seq          bigint      NOT NULL,
    kind         text        NOT NULL CHECK (kind IN ('message', 'milestone', 'narration')),
    author_type  text        NOT NULL CHECK (author_type IN ('person', 'session', 'github')),
    -- A login for a person or a GitHub author, the session id for a session.
    author       text        NOT NULL,
    -- For a session author, its sponsor. For a GitHub author, GitHub's author_association.
    author_label text,
    body         text        NOT NULL,
    -- For a message mirrored from GitHub: what it was, its id there and its URL.
    source_type  text        CHECK (source_type IN ('github_review', 'github_review_comment')),
    source_id    text,
    source_url   text,
    source_pr    integer,
    source_path  text,
    source_state text,
    created_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (thread_id, seq),
    -- A redelivered webhook mirrors nothing twice.
    UNIQUE (thread_id, source_type, source_id)
);

CREATE TABLE watchers (
    thread_id bigint      NOT NULL REFERENCES threads (id),
    login     text        NOT NULL,
    since     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (thread_id, login)
);

-- "Record this?" marks (command-center/D36). A mark is a note between people; nothing reads it to change state.
CREATE TABLE record_marks (
    message_id bigint      NOT NULL REFERENCES messages (id),
    login      text        NOT NULL,
    marked_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (message_id, login)
);
