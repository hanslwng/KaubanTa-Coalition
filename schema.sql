-- Run in TiDB Cloud SQL Editor (MySQL-compatible). Select your database first.
CREATE TABLE IF NOT EXISTS members (
  id INT AUTO_INCREMENT PRIMARY KEY,
  full_name VARCHAR(150) NOT NULL,
  email VARCHAR(150) NOT NULL UNIQUE,
  mobile VARCHAR(30) NOT NULL,
  birthday DATE NOT NULL,
  school_or_work VARCHAR(150),
  city_province VARCHAR(150) NOT NULL,
  interests VARCHAR(255),
  availability VARCHAR(50),
  heard_from VARCHAR(50),
  privacy_consent TINYINT(1) NOT NULL DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS subscribers (
  id INT AUTO_INCREMENT PRIMARY KEY,
  email VARCHAR(150) NOT NULL UNIQUE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS activities (
  id INT AUTO_INCREMENT PRIMARY KEY,
  title VARCHAR(200) NOT NULL,
  cause VARCHAR(50) NOT NULL,
  venue VARCHAR(200) NOT NULL,
  starts_at DATETIME NOT NULL,
  slots INT NOT NULL DEFAULT 0,
  description TEXT
);
CREATE TABLE IF NOT EXISTS rsvps (
  id INT AUTO_INCREMENT PRIMARY KEY,
  activity_id INT NOT NULL,
  name VARCHAR(150) NOT NULL,
  email VARCHAR(150) NOT NULL,
  mobile VARCHAR(30),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (activity_id, email)
);
CREATE TABLE IF NOT EXISTS contact_messages (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(150) NOT NULL,
  email VARCHAR(150) NOT NULL,
  subject VARCHAR(50) NOT NULL,
  message TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS newsletters (
  id INT AUTO_INCREMENT PRIMARY KEY,
  type ENUM('weekly','monthly') NOT NULL,
  title VARCHAR(200) NOT NULL,
  summary VARCHAR(300),
  body TEXT NOT NULL,
  pdf_url VARCHAR(255),
  published_at DATE NOT NULL
);
-- Seed: ids 1-4 match the activity cards on the site. Replace with real events.
INSERT INTO activities (id,title,cause,venue,starts_at,slots,description) VALUES
(1,'Lakeshore Clean-up','Environment','Los Baños Lakeshore','2026-12-02 15:00:00',14,'Bring gloves and a refillable bottle.'),
(2,'Reading Buddies','Education','Barangay Library, Calamba','2026-12-03 16:00:00',8,'Read with grade school kids.'),
(3,'Community Pantry Packing','Relief','Santa Rosa Gym','2026-12-05 08:00:00',20,'Sort and pack goods.'),
(4,'Youth Voter Info Booth','Advocacy','Plaza, San Pablo','2026-12-06 10:00:00',6,'Help first-time voters.');
