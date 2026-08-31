SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS `outfit_clothes`;
DROP TABLE IF EXISTS `outfits`;
DROP TABLE IF EXISTS `clothes`;
DROP TABLE IF EXISTS `users`;

CREATE TABLE `users` (
  `id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(50) NOT NULL,
  `password` varchar(50) NOT NULL,
  `create_time` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_users_username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE `clothes` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `name` varchar(100) NOT NULL,
  `image_url` varchar(255) NOT NULL,
  `category` varchar(50) NOT NULL,
  `sub_category` varchar(50) DEFAULT NULL,
  `brand` varchar(50) DEFAULT NULL,
  `style` varchar(50) NOT NULL,
  `color` varchar(50) NOT NULL,
  `sub_color` varchar(50) DEFAULT NULL,
  `season` varchar(20) NOT NULL,
  `material` varchar(50) NOT NULL,
  `occasion` varchar(255) DEFAULT NULL,
  `description` text,
  `thickness` varchar(50) DEFAULT NULL,
  `hash` varchar(64) DEFAULT NULL,
  `create_time` datetime DEFAULT CURRENT_TIMESTAMP,
  `update_time` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_clothes_user_id` (`user_id`),
  KEY `idx_clothes_category` (`category`),
  CONSTRAINT `fk_clothes_user`
    FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE `outfits` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `name` varchar(100) NOT NULL,
  `description` text,
  `image_url` varchar(255) DEFAULT NULL,
  `create_time` datetime DEFAULT CURRENT_TIMESTAMP,
  `update_time` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_outfits_user_id` (`user_id`),
  CONSTRAINT `fk_outfits_user`
    FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE `outfit_clothes` (
  `id` int NOT NULL AUTO_INCREMENT,
  `outfit_id` int NOT NULL,
  `clothes_id` int NOT NULL,
  `position` varchar(50) DEFAULT NULL COMMENT '衣物在穿搭中的位置',
  `create_time` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_outfit_clothes_pair` (`outfit_id`, `clothes_id`),
  KEY `idx_outfit_clothes_clothes_id` (`clothes_id`),
  CONSTRAINT `fk_outfit_clothes_outfit`
    FOREIGN KEY (`outfit_id`) REFERENCES `outfits` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_outfit_clothes_clothes`
    FOREIGN KEY (`clothes_id`) REFERENCES `clothes` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

SET FOREIGN_KEY_CHECKS = 1;
