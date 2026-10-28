-- Synthetic Seed Data Export
-- Seed: 20261022, Scale: 0.05
BEGIN;

INSERT INTO issuers (id, public_id, name, public_key_pem, status, created_at) VALUES (1, 'ISS-00001', 'Indian Institute of Technology (IIT) Delhi', '-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAERn64fEei0zj62oNIvSHdWs7GFg01QXnstEzGjYrQd4=
-----END PUBLIC KEY-----
', 'ACTIVE', '2024-10-22T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO issuers (id, public_id, name, public_key_pem, status, created_at) VALUES (2, 'ISS-00002', 'Indian Institute of Science (IISc) Bengaluru', '-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAC6FCdwfy3OcIvzvOBJj10SgNRJcGrmciapWuodNHsx8=
-----END PUBLIC KEY-----
', 'ACTIVE', '2024-10-22T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO issuers (id, public_id, name, public_key_pem, status, created_at) VALUES (3, 'ISS-00003', 'National Institute of Technology (NIT) Trichy', '-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAr3pUA73qKe0Kaj48kHTf4+EZvOy2WYkPKTMLryGoMiQ=
-----END PUBLIC KEY-----
', 'ACTIVE', '2024-10-22T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO issuers (id, public_id, name, public_key_pem, status, created_at) VALUES (4, 'ISS-00004', 'Birla Institute of Technology and Science (BITS) Pilani', '-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEA/YR48qol2Qr2X5+Blfm4xNk/4MnUkR79nug4QGT5mlg=
-----END PUBLIC KEY-----
', 'ACTIVE', '2024-10-22T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO issuers (id, public_id, name, public_key_pem, status, created_at) VALUES (5, 'ISS-00005', 'International Institute of Information Technology (IIIT) Hyderabad', '-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEACsvKIinh8kS3yBl07/2r6x1w9FuzO1jt+IviOW39cYY=
-----END PUBLIC KEY-----
', 'ACTIVE', '2024-10-22T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO issuers (id, public_id, name, public_key_pem, status, created_at) VALUES (6, 'ISS-00006', 'Delhi Technological University (DTU)', '-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAMcEr9oyqxJguRWSckg4Sfm07sAD5ImjbaXGW4hKePeU=
-----END PUBLIC KEY-----
', 'ACTIVE', '2024-10-22T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO issuers (id, public_id, name, public_key_pem, status, created_at) VALUES (7, 'ISS-00007', 'Anna University College of Engineering', '-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAQOtqOJr1DK7V4b4vP518hlxQa7waeE6gnRyujhXmo2U=
-----END PUBLIC KEY-----
', 'ACTIVE', '2024-10-22T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO courses (id, public_id, title, version, status, created_at) VALUES (1, 'CRS-00001', 'DevSecOps Automation & Infrastructure as Code (301)', '1.0', 'ACTIVE', '2025-03-05T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO courses (id, public_id, title, version, status, created_at) VALUES (2, 'CRS-00002', 'Autonomous Robotics, SLAM & Computer Vision (201)', '1.0', 'ACTIVE', '2025-12-02T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO courses (id, public_id, title, version, status, created_at) VALUES (3, 'CRS-00003', 'Deep Learning & Transformer Architectures (201)', '1.0', 'ACTIVE', '2025-08-28T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO courses (id, public_id, title, version, status, created_at) VALUES (4, 'CRS-00004', 'Advanced Cryptography & Zero-Knowledge Proofs (501)', '1.0', 'ACTIVE', '2025-10-20T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO courses (id, public_id, title, version, status, created_at) VALUES (5, 'CRS-00005', 'Distributed Cloud Architecture & High Availability (201)', '1.0', 'ACTIVE', '2025-09-18T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO courses (id, public_id, title, version, status, created_at) VALUES (6, 'CRS-00006', 'Autonomous Robotics, SLAM & Computer Vision (501)', '1.0', 'ACTIVE', '2025-11-02T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO courses (id, public_id, title, version, status, created_at) VALUES (7, 'CRS-00007', 'Graph Algorithms & Social Network Analysis (201)', '1.0', 'ACTIVE', '2025-10-11T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO courses (id, public_id, title, version, status, created_at) VALUES (8, 'CRS-00008', 'Network Security & Secure Protocols Design (101)', '1.0', 'ACTIVE', '2025-09-07T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO courses (id, public_id, title, version, status, created_at) VALUES (9, 'CRS-00009', 'Applied AI in Healthcare & Bioinformatics (401)', '1.0', 'ACTIVE', '2025-12-24T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO courses (id, public_id, title, version, status, created_at) VALUES (10, 'CRS-00010', 'Applied AI in Healthcare & Bioinformatics (101)', '1.0', 'ACTIVE', '2025-06-21T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO courses (id, public_id, title, version, status, created_at) VALUES (11, 'CRS-00011', 'Offensive Cybersecurity & Penetration Testing (501)', '1.0', 'ACTIVE', '2025-07-01T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO courses (id, public_id, title, version, status, created_at) VALUES (12, 'CRS-00012', 'Natural Language Processing & Large Language Models (101)', '1.0', 'ACTIVE', '2025-11-25T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO courses (id, public_id, title, version, status, created_at) VALUES (13, 'CRS-00013', 'Offensive Cybersecurity & Penetration Testing (201)', '1.0', 'ACTIVE', '2025-05-06T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO courses (id, public_id, title, version, status, created_at) VALUES (14, 'CRS-00014', 'Full-Stack Machine Learning Engineering (101)', '1.0', 'ACTIVE', '2025-03-13T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO courses (id, public_id, title, version, status, created_at) VALUES (15, 'CRS-00015', 'Deep Learning & Transformer Architectures (501)', '1.0', 'ACTIVE', '2025-04-08T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO courses (id, public_id, title, version, status, created_at) VALUES (16, 'CRS-00016', 'Digital Forensics & Incident Response (101)', '1.0', 'ACTIVE', '2025-09-27T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO courses (id, public_id, title, version, status, created_at) VALUES (17, 'CRS-00017', 'Mobile Computing & Cross-Platform Architecture (501)', '1.0', 'ACTIVE', '2025-05-27T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO courses (id, public_id, title, version, status, created_at) VALUES (18, 'CRS-00018', 'Full-Stack Machine Learning Engineering (401)', '1.0', 'ACTIVE', '2025-05-07T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO courses (id, public_id, title, version, status, created_at) VALUES (19, 'CRS-00019', 'Applied Data Science with Python & R (101)', '1.0', 'ACTIVE', '2025-10-23T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO courses (id, public_id, title, version, status, created_at) VALUES (20, 'CRS-00020', 'Software Verification & Formal Methods (501)', '1.0', 'ACTIVE', '2025-09-11T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO courses (id, public_id, title, version, status, created_at) VALUES (21, 'CRS-00021', 'Computer Graphics & Interactive Rendering (101)', '1.0', 'ACTIVE', '2025-11-20T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO courses (id, public_id, title, version, status, created_at) VALUES (22, 'CRS-00022', 'High-Frequency Quantitative Systems (101)', '1.0', 'ACTIVE', '2025-07-27T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO courses (id, public_id, title, version, status, created_at) VALUES (23, 'CRS-00023', 'Network Security & Secure Protocols Design (201)', '1.0', 'ACTIVE', '2025-12-24T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO courses (id, public_id, title, version, status, created_at) VALUES (24, 'CRS-00024', 'Scalable Data Pipelines & Stream Processing (101)', '1.0', 'ACTIVE', '2025-06-10T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO courses (id, public_id, title, version, status, created_at) VALUES (25, 'CRS-00025', 'Deep Learning & Transformer Architectures (501)', '1.0', 'ACTIVE', '2025-04-21T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO courses (id, public_id, title, version, status, created_at) VALUES (26, 'CRS-00026', 'Natural Language Processing & Large Language Models (101)', '1.0', 'ACTIVE', '2025-03-29T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO courses (id, public_id, title, version, status, created_at) VALUES (27, 'CRS-00027', 'Computer Graphics & Interactive Rendering (101)', '1.0', 'ACTIVE', '2025-06-22T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO courses (id, public_id, title, version, status, created_at) VALUES (28, 'CRS-00028', 'Distributed Cloud Architecture & High Availability (501)', '1.0', 'ACTIVE', '2025-06-16T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO courses (id, public_id, title, version, status, created_at) VALUES (29, 'CRS-00029', 'Advanced Cryptography & Zero-Knowledge Proofs (401)', '1.0', 'ACTIVE', '2025-12-08T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO courses (id, public_id, title, version, status, created_at) VALUES (30, 'CRS-00030', 'Deep Learning & Transformer Architectures (101)', '1.0', 'ACTIVE', '2025-10-05T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO courses (id, public_id, title, version, status, created_at) VALUES (31, 'CRS-00031', 'Autonomous Robotics, SLAM & Computer Vision (501)', '1.0', 'ACTIVE', '2025-04-13T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO courses (id, public_id, title, version, status, created_at) VALUES (32, 'CRS-00032', 'Graph Algorithms & Social Network Analysis (501)', '1.0', 'ACTIVE', '2025-06-20T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO courses (id, public_id, title, version, status, created_at) VALUES (33, 'CRS-00033', 'Graph Algorithms & Social Network Analysis (101)', '1.0', 'ACTIVE', '2025-07-22T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO courses (id, public_id, title, version, status, created_at) VALUES (34, 'CRS-00034', 'Embedded Real-Time Operating Systems (RTOS) (101)', '1.0', 'ACTIVE', '2025-10-26T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO courses (id, public_id, title, version, status, created_at) VALUES (35, 'CRS-00035', 'Advanced Cryptography & Zero-Knowledge Proofs (301)', '1.0', 'ACTIVE', '2025-03-04T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO courses (id, public_id, title, version, status, created_at) VALUES (36, 'CRS-00036', 'Applied AI in Healthcare & Bioinformatics (101)', '1.0', 'ACTIVE', '2025-12-04T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO courses (id, public_id, title, version, status, created_at) VALUES (37, 'CRS-00037', 'Graph Algorithms & Social Network Analysis (501)', '1.0', 'ACTIVE', '2025-12-19T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO courses (id, public_id, title, version, status, created_at) VALUES (38, 'CRS-00038', 'Software Verification & Formal Methods (501)', '1.0', 'ACTIVE', '2025-08-05T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO courses (id, public_id, title, version, status, created_at) VALUES (39, 'CRS-00039', 'Mobile Computing & Cross-Platform Architecture (101)', '1.0', 'ACTIVE', '2025-05-05T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO courses (id, public_id, title, version, status, created_at) VALUES (40, 'CRS-00040', 'Graph Algorithms & Social Network Analysis (301)', '1.0', 'ACTIVE', '2025-09-15T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO courses (id, public_id, title, version, status, created_at) VALUES (41, 'CRS-00041', 'Applied Data Science with Python & R (301)', '1.0', 'ACTIVE', '2025-03-16T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO courses (id, public_id, title, version, status, created_at) VALUES (42, 'CRS-00042', 'Applied Data Science with Python & R (501)', '1.0', 'ACTIVE', '2025-03-31T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO courses (id, public_id, title, version, status, created_at) VALUES (43, 'CRS-00043', 'Natural Language Processing & Large Language Models (301)', '1.0', 'ACTIVE', '2025-08-17T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO courses (id, public_id, title, version, status, created_at) VALUES (44, 'CRS-00044', 'Digital Forensics & Incident Response (501)', '1.0', 'ACTIVE', '2025-06-06T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO courses (id, public_id, title, version, status, created_at) VALUES (45, 'CRS-00045', 'Decentralized Systems & Smart Contract Auditing (501)', '1.0', 'ACTIVE', '2025-06-28T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO courses (id, public_id, title, version, status, created_at) VALUES (46, 'CRS-00046', 'Applied Data Science with Python & R (301)', '1.0', 'ACTIVE', '2025-09-26T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO courses (id, public_id, title, version, status, created_at) VALUES (47, 'CRS-00047', 'Offensive Cybersecurity & Penetration Testing (501)', '1.0', 'ACTIVE', '2025-10-10T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO courses (id, public_id, title, version, status, created_at) VALUES (48, 'CRS-00048', 'Embedded Real-Time Operating Systems (RTOS) (501)', '1.0', 'ACTIVE', '2025-07-30T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO courses (id, public_id, title, version, status, created_at) VALUES (49, 'CRS-00049', 'Embedded Real-Time Operating Systems (RTOS) (201)', '1.0', 'ACTIVE', '2025-12-22T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;
INSERT INTO courses (id, public_id, title, version, status, created_at) VALUES (50, 'CRS-00050', 'Distributed Cloud Architecture & High Availability (401)', '1.0', 'ACTIVE', '2025-03-03T12:00:00+00:00') ON CONFLICT (id) DO NOTHING;

COMMIT;
