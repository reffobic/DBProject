-- MySQL Workbench Forward Engineering
-- Base schema for DataGov_DB (Milestone I). Run this first; then optionally run
-- alter_organization_contact_to_text.sql and view_user_with_age.sql.

SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0;
SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0;
SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION';

CREATE SCHEMA IF NOT EXISTS `DataGov_DB` DEFAULT CHARACTER SET utf8 ;
USE `DataGov_DB` ;

CREATE TABLE IF NOT EXISTS `DataGov_DB`.`Organization` (
  `description` TEXT NULL,
  `org_type` ENUM('Federal', 'State', 'City', 'Local', 'Other') NOT NULL,
  `contact_information` VARCHAR(45) NULL,
  `org_name` VARCHAR(45) NOT NULL,
  PRIMARY KEY (`org_name`))
ENGINE = InnoDB;

CREATE TABLE IF NOT EXISTS `DataGov_DB`.`Dataset` (
  `identifier` VARCHAR(255) NOT NULL,
  `dataset_name` VARCHAR(255) NOT NULL,
  `description` TEXT NULL,
  `access_level` VARCHAR(50) NOT NULL,
  `license` VARCHAR(100) NULL,
  `metadata_creation_date` DATETIME NULL,
  `metadata_update_date` DATETIME NULL,
  `publisher` VARCHAR(45) NULL,
  `maintainer` VARCHAR(45) NULL,
  `topic` VARCHAR(100) NULL,
  `Organization_org_name` VARCHAR(45) NOT NULL,
  PRIMARY KEY (`identifier`),
  INDEX `fk_Dataset_Organization_idx` (`Organization_org_name` ASC) VISIBLE,
  CONSTRAINT `fk_Dataset_Organization`
    FOREIGN KEY (`Organization_org_name`)
    REFERENCES `DataGov_DB`.`Organization` (`org_name`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION)
ENGINE = InnoDB;

CREATE TABLE IF NOT EXISTS `DataGov_DB`.`User` (
  `email` VARCHAR(255) NOT NULL,
  `username` VARCHAR(45) NOT NULL,
  `gender` VARCHAR(45) NULL,
  `birthdate` DATE NULL,
  `country` VARCHAR(45) NULL,
  PRIMARY KEY (`email`),
  UNIQUE INDEX `username_UNIQUE` (`username` ASC) VISIBLE)
ENGINE = InnoDB;

CREATE TABLE IF NOT EXISTS `DataGov_DB`.`Usage` (
  `usage_id` INT NOT NULL AUTO_INCREMENT,
  `project_name` VARCHAR(45) NULL,
  `project_category` ENUM('analytics', 'machine learning', 'field research') NOT NULL,
  `User_email` VARCHAR(255) NOT NULL,
  `Dataset_identifier` VARCHAR(255) NOT NULL,
  PRIMARY KEY (`usage_id`),
  INDEX `fk_Usage_User1_idx` (`User_email` ASC) VISIBLE,
  INDEX `fk_Usage_Dataset1_idx` (`Dataset_identifier` ASC) VISIBLE,
  CONSTRAINT `fk_Usage_User1`
    FOREIGN KEY (`User_email`)
    REFERENCES `DataGov_DB`.`User` (`email`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION,
  CONSTRAINT `fk_Usage_Dataset1`
    FOREIGN KEY (`Dataset_identifier`)
    REFERENCES `DataGov_DB`.`Dataset` (`identifier`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION)
ENGINE = InnoDB;

CREATE TABLE IF NOT EXISTS `DataGov_DB`.`FileFormat` (
  `format_id` INT NOT NULL AUTO_INCREMENT,
  `format_type` VARCHAR(45) NULL,
  `url` VARCHAR(512) NOT NULL,
  PRIMARY KEY (`format_id`))
ENGINE = InnoDB;

CREATE TABLE IF NOT EXISTS `DataGov_DB`.`tag` (
  `tag_name` VARCHAR(100) NOT NULL,
  PRIMARY KEY (`tag_name`))
ENGINE = InnoDB;

CREATE TABLE IF NOT EXISTS `DataGov_DB`.`Dataset_has_tag` (
  `Dataset_identifier` VARCHAR(255) NOT NULL,
  `tag_tag_name` VARCHAR(100) NOT NULL,
  PRIMARY KEY (`Dataset_identifier`, `tag_tag_name`),
  INDEX `fk_Dataset_has_tag_tag1_idx` (`tag_tag_name` ASC) VISIBLE,
  INDEX `fk_Dataset_has_tag_Dataset1_idx` (`Dataset_identifier` ASC) VISIBLE,
  CONSTRAINT `fk_Dataset_has_tag_Dataset1`
    FOREIGN KEY (`Dataset_identifier`)
    REFERENCES `DataGov_DB`.`Dataset` (`identifier`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION,
  CONSTRAINT `fk_Dataset_has_tag_tag1`
    FOREIGN KEY (`tag_tag_name`)
    REFERENCES `DataGov_DB`.`tag` (`tag_name`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION)
ENGINE = InnoDB;

CREATE TABLE IF NOT EXISTS `DataGov_DB`.`FileFormat_has_Dataset` (
  `FileFormat_format_id` INT NOT NULL,
  `Dataset_identifier` VARCHAR(255) NOT NULL,
  PRIMARY KEY (`FileFormat_format_id`, `Dataset_identifier`),
  INDEX `fk_FileFormat_has_Dataset_Dataset1_idx` (`Dataset_identifier` ASC) VISIBLE,
  INDEX `fk_FileFormat_has_Dataset_FileFormat1_idx` (`FileFormat_format_id` ASC) VISIBLE,
  CONSTRAINT `fk_FileFormat_has_Dataset_FileFormat1`
    FOREIGN KEY (`FileFormat_format_id`)
    REFERENCES `DataGov_DB`.`FileFormat` (`format_id`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION,
  CONSTRAINT `fk_FileFormat_has_Dataset_Dataset1`
    FOREIGN KEY (`Dataset_identifier`)
    REFERENCES `DataGov_DB`.`Dataset` (`identifier`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION)
ENGINE = InnoDB;

SET SQL_MODE=@OLD_SQL_MODE;
SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS;
SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS;
