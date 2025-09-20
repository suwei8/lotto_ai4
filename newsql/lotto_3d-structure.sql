/*
 Navicat Premium Data Transfer

 Source Server         : 悉尼彩票开发机
 Source Server Type    : MySQL
 Source Server Version : 80036 (8.0.36)
 Source Host           : 140.238.195.36:3306
 Source Schema         : lotto_3d

 Target Server Type    : MySQL
 Target Server Version : 80036 (8.0.36)
 File Encoding         : 65001

 Date: 20/09/2025 14:36:03
*/

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for expert_hit_stat
-- ----------------------------
DROP TABLE IF EXISTS `expert_hit_stat`;
CREATE TABLE `expert_hit_stat`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `issue_name` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `user_id` int NOT NULL,
  `playtype_id` int NOT NULL,
  `total_count` int NULL DEFAULT 0,
  `hit_count` int NULL DEFAULT 0,
  `hit_number_count` int NULL DEFAULT 0,
  `avg_hit_gap` float NULL DEFAULT NULL,
  PRIMARY KEY (`id`, `issue_name`) USING BTREE,
  INDEX `idx_issue_name`(`issue_name` ASC) USING BTREE,
  INDEX `idx_expert_hit_stat_playtype_id`(`playtype_id` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 10854460 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Table structure for expert_info
-- ----------------------------
DROP TABLE IF EXISTS `expert_info`;
CREATE TABLE `expert_info`  (
  `user_id` bigint NOT NULL COMMENT '专家ID',
  `nick_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '专家昵称',
  PRIMARY KEY (`user_id`) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci COMMENT = '福彩3D-专家信息' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Table structure for expert_predictions
-- ----------------------------
DROP TABLE IF EXISTS `expert_predictions`;
CREATE TABLE `expert_predictions`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` bigint NOT NULL,
  `issue_name` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `lottery_id` int NULL DEFAULT NULL,
  `playtype_id` int NULL DEFAULT NULL,
  `numbers` text CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL,
  PRIMARY KEY (`id`, `issue_name`) USING BTREE,
  INDEX `idx_user_id`(`user_id` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 5215990 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Table structure for lottery_results
-- ----------------------------
DROP TABLE IF EXISTS `lottery_results`;
CREATE TABLE `lottery_results`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `lottery_name` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '彩票类型（例如“福彩3D”）',
  `issue_name` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '期号（例如“2025010”）',
  `open_code` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '开奖号码（例如“1,2,3,4,5,6”），用逗号分隔的数字',
  `sum` int NULL DEFAULT NULL COMMENT '和值，即所有号码的和',
  `span` int NULL DEFAULT NULL COMMENT '跨度，即号码的最大值减去最小值',
  `odd_even_ratio` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '奇偶比，表示奇数和偶数的比例',
  `big_small_ratio` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '大小比，表示大号和小号的比例',
  `open_time` datetime NULL DEFAULT NULL COMMENT '开奖时间',
  PRIMARY KEY (`id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 7409 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci COMMENT = '福彩3D-历史开奖数据表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Table structure for playtype_dict
-- ----------------------------
DROP TABLE IF EXISTS `playtype_dict`;
CREATE TABLE `playtype_dict`  (
  `lottery_id` int NOT NULL,
  `playtype_id` int NOT NULL,
  `playtype_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Table structure for red_val_list
-- ----------------------------
DROP TABLE IF EXISTS `red_val_list`;
CREATE TABLE `red_val_list`  (
  `id` int NOT NULL DEFAULT 0 COMMENT '自增ID',
  `user_id` bigint NULL DEFAULT NULL COMMENT '专家ID (0代表公共分布)',
  `lottery_id` int NULL DEFAULT NULL COMMENT '彩种ID',
  `playtype_id` int NULL DEFAULT NULL COMMENT '玩法ID',
  `issue_name` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '期号',
  `num` text CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL COMMENT '号码集合',
  `val` text CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL COMMENT '权重集合'
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Table structure for red_val_list_v2
-- ----------------------------
DROP TABLE IF EXISTS `red_val_list_v2`;
CREATE TABLE `red_val_list_v2`  (
  `id` int NOT NULL DEFAULT 0 COMMENT '自增ID',
  `user_id` bigint NULL DEFAULT NULL COMMENT '专家ID (0代表公共分布)',
  `lottery_id` int NULL DEFAULT NULL COMMENT '彩种ID',
  `playtype_id` int NULL DEFAULT NULL COMMENT '玩法ID',
  `issue_name` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '期号',
  `num` text CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL COMMENT '号码集合',
  `val` text CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL COMMENT '权重集合',
  `type` tinyint NULL DEFAULT NULL COMMENT '排序类型（如1=命中率,2=当前红连，3=历史最高红连，4=综合排名，5=当前连黑,6=历史最高连黑）',
  `rank_count` int NULL DEFAULT NULL COMMENT 'rankList中参与排名的专家总数',
  `hit_count_map` text CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL COMMENT 'hitCount分布统计（JSON格式）',
  `serial_hit_count_map` text CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL COMMENT 'serialHitCount分布统计（JSON格式）',
  `series_not_hit_count_map` text CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL COMMENT 'seriesNotHitCount分布统计（JSON格式）',
  `max_serial_hit_count_map` text CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL COMMENT 'maxSerialHitCount分布统计（JSON格式）',
  `max_series_not_hit_count_map` text CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL COMMENT 'maxSeriesNotHitCount分布统计（JSON格式）',
  `his_max_serial_hit_count_map` text CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL COMMENT 'hisMaxSerialHitCount分布统计（JSON格式）',
  `his_max_series_not_hit_count_map` text CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL COMMENT 'hisMaxSeriesNotHitCount分布统计（JSON格式）'
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = DYNAMIC;

SET FOREIGN_KEY_CHECKS = 1;
