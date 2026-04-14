-- MySQL schema for subdomain service
-- Usage: mysql -u root -p < schema.sql

CREATE DATABASE IF NOT EXISTS subdomain_service
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE subdomain_service;

CREATE TABLE IF NOT EXISTS subdomains (
    id INT AUTO_INCREMENT PRIMARY KEY,
    label VARCHAR(63) NOT NULL UNIQUE,
    fqdn VARCHAR(255) NOT NULL,
    ns_records JSON NOT NULL,
    owner_note VARCHAR(100),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NOT NULL,
    INDEX idx_expires (expires_at)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
