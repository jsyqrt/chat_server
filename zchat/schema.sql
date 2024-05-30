DROP TABLE IF EXISTS user;
-- DROP TABLE IF EXISTS appointment;

CREATE TABLE user (
-- TODO avatar ...
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  phonenumber TEXT UNIQUE NOT NULL,
  nickname TEXT NOT NULL,
  gender TEXT NOT NULL,
  edubg TEXT NOT NULL,
  yearofwork TEXT NOT NULL,
  signature_text TEXT,

  as_expert INTEGER NOT NULL,
  email TEXT NOT NULL,
  email_verified INTEGER NOT NULL,
  company TEXT NOT NULL,
  title TEXT NOT NULL,
  profession TEXT NOT NULL,
  business TEXT NOT NULL,
  price REAL NOT NULL,

  as_newbie INTEGER NOT NULL,
  target_company TEXT NOT NULL,
  target_title TEXT NOT NULL,
  target_profession TEXT NOT NULL,
  target_business TEXT NOT NULL,
  target_jd TEXT NOT NULL
);
