-- Cookieless counters (D1, free plan). No IP, no user agent, no identifiers: only "how many times", per day / per answer.
CREATE TABLE IF NOT EXISTS events (day TEXT NOT NULL, name TEXT NOT NULL, n INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (day, name));
CREATE TABLE IF NOT EXISTS poll (q TEXT NOT NULL, a TEXT NOT NULL, n INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (q, a));
