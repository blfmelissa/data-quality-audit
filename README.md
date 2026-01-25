# 🎮 Steam Games Data Quality Project

A comprehensive data quality audit and improvement project on the Steam Games dataset.

## 📋 Project Overview

This project implements a complete data quality assessment and enhancement approach based on the **Medallion Architecture** (Bronze → Silver → Gold) covering the 6 pillars of data quality:

| Pillar | Description |
|--------|-------------|
| **Completeness** | Missing values detection and handling |
| **Uniqueness** | Duplicate records identification |
| **Accuracy** | Format validation (emails, URLs, dates) |
| **Validity** | Value range and domain constraints |
| **Consistency** | Cross-column logical rules |
| **Timeliness** | Date freshness and future date detection |

## 📊 Dataset

- **Source**: Steam Games Dataset (Kaggle)
- **Size**: ~122,000 games
- **Columns**: 40 attributes (name, price, reviews, genres, tags, etc.)

### Download

The file `games_brut.xlsx` (~150MB) is not included in the repo.

**Download:** [Google Drive](https://drive.google.com/drive/folders/1r-sUaKFj4h9zV5IN3HnjrfFSoZVdMmF1?usp=drive_link)

Place the file in `data/Bronze/`.