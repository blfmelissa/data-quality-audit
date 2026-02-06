-- Base de données Airflow
CREATE DATABASE airflow_db;

-- Schema pour les données brutes Steam (Bronze)

CREATE TABLE IF NOT EXISTS games_brut (
    app_id INTEGER PRIMARY KEY,
    name TEXT,
    release_date TEXT,
    estimated_owners TEXT,
    peak_ccu INTEGER,
    required_age INTEGER,
    price DECIMAL(10, 2),
    discount DECIMAL(5, 2),
    dlc_count INTEGER,
    about_the_game TEXT,
    supported_languages TEXT,
    full_audio_languages TEXT,
    reviews TEXT,
    header_image TEXT,
    website TEXT,
    support_url TEXT,
    support_email TEXT,
    windows BOOLEAN,
    mac BOOLEAN,
    linux BOOLEAN,
    metacritic_score INTEGER,
    metacritic_url TEXT,
    user_score INTEGER,
    positive INTEGER,
    negative INTEGER,
    score_rank TEXT,
    achievements INTEGER,
    recommendations INTEGER,
    notes TEXT,
    average_playtime_forever INTEGER,
    average_playtime_two_weeks INTEGER,
    median_playtime_forever INTEGER,
    median_playtime_two_weeks INTEGER,
    developers TEXT,
    publishers TEXT,
    categories TEXT,
    genres TEXT,
    tags TEXT,
    screenshots TEXT,
    movies TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_games_brut_name ON games_brut(name);
