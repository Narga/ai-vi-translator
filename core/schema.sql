CREATE TABLE IF NOT EXISTS projects(slug TEXT PRIMARY KEY, title TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS files(id INTEGER PRIMARY KEY, project_slug TEXT, filename TEXT,
  size_bytes INT, char_count INT, chunk_count INT, status TEXT DEFAULT 'new',
  updated_at TEXT, UNIQUE(project_slug, filename));
CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY, file_id INT, provider TEXT,
  model TEXT, started_at TEXT, finished_at TEXT, status TEXT, error TEXT);
